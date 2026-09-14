import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from data.domain.cases import WorkflowVersion
from data.domain.decisions import (
    Decision,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
)
from data.domain.execution import ActionPlanningRequested
from data.domain.finance import FinanceReviewStatus
from data.domain.finance_decisions import ProposalApprovalEvidence
from data.domain.proposals import ProposalState
from services.decisions.service import DecisionPolicy
from services.finance.contracts import FinalizeProposalCommand
from services.finance.identity import BoundFinanceActors, authority_material
from services.persistence.finance_reviews import (
    FinanceReviewIdempotencyConflict,
    FinanceReviewRevisionConflict,
)
from services.persistence.ports import UnitOfWork
from services.persistence.proposals import StaleProposal
from services.policy.thresholds import requires_finance_approval


class FinanceFinalizationConflict(RuntimeError):
    pass


class FinanceFinalizationInvalid(ValueError):
    pass


def finalization_fingerprint(
    command: FinalizeProposalCommand, actor: IdentitySnapshot
) -> str:
    material = {
        "operation": "finance-finalize",
        "command": command.model_dump(mode="json"),
        "actor": authority_material(actor),
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


FINALIZATION_CONTENTION = (
    IntegrityError,
    StaleProposal,
    FinanceReviewIdempotencyConflict,
    FinanceReviewRevisionConflict,
)


class FinanceDecisionService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        actors: BoundFinanceActors,
        policy: DecisionPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._actors = actors
        self._policy = policy or DecisionPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise FinanceFinalizationInvalid("Server clock must be timezone-aware")
        return now

    @staticmethod
    def _already_approved(uow: UnitOfWork, case_id: str, selection_id: str) -> bool:
        return any(
            item.kind is DecisionKind.APPROVED
            and item.proposal_approval is not None
            and item.proposal_approval.selection.selection_id == selection_id
            for item in uow.decisions.list_for_case(case_id)
        )

    def _return_existing(self, decision: Decision, fingerprint: str) -> Decision:
        if decision.request_fingerprint != fingerprint:
            raise FinanceFinalizationConflict("Key was used for another finalization")
        self._actors.require_alex(decision.actor)
        if decision.proposal_approval is not None:
            self._actors.require_alex(decision.proposal_approval.selection.submitted_by)
        return decision

    def _evidence(self, state: ProposalState) -> ProposalApprovalEvidence:
        selection = state.selection
        if selection is None:
            raise FinanceFinalizationInvalid("Approval requires current selection")
        self._actors.require_alex(selection.submitted_by)
        if requires_finance_approval(selection.proposal.response_cost):
            review = state.review
            if (
                review is None
                or state.review_revision is None
                or review.status is not FinanceReviewStatus.APPROVED
                or review.reviewed_by is None
            ):
                raise FinanceFinalizationInvalid(
                    "Current proposal lacks Finance approval"
                )
            self._actors.require_taylor(review.reviewed_by)
            return ProposalApprovalEvidence(
                selection=selection,
                review=review,
                review_revision=state.review_revision,
            )
        return ProposalApprovalEvidence(
            selection=selection, review=None, review_revision=None
        )

    def _once(
        self,
        command: FinalizeProposalCommand,
        actor: IdentitySnapshot,
        *,
        key: str,
        fingerprint: str,
    ) -> Decision:
        with self._uow_factory() as uow:
            existing = uow.decisions.get_by_idempotency_key(key)
            if existing is not None:
                return self._return_existing(existing, fingerprint)
            state = uow.proposals.get_state(command.case_id)
            if state.token != command.expected:
                raise StaleProposal("Case analysis or proposal changed")
            if state.selection is not None:
                self._actors.require_alex(state.selection.submitted_by)
            projection = uow.cases.get_projection(command.case_id)
            case = projection.case
            if (
                case.effective_workflow_version
                is not WorkflowVersion.INDEPENDENT_FINANCE
            ):
                raise FinanceFinalizationInvalid(
                    "Independent Finance workflow is required"
                )
            analysis_id = command.expected.analysis_id
            if analysis_id is None:
                raise FinanceFinalizationInvalid("Current analysis is required")
            analysis = uow.cases.get_analysis(analysis_id)
            if (
                analysis.case_id != command.case_id
                or analysis.material_hash != command.expected.analysis_material_hash
            ):
                raise StaleProposal("Analysis binding changed")
            evidence = None
            option_id = None
            if command.kind is DecisionKind.APPROVED:
                evidence = self._evidence(state)
                option_id = evidence.selection.proposal.option_id
                if self._already_approved(
                    uow, command.case_id, evidence.selection.selection_id
                ):
                    raise FinanceFinalizationConflict(
                        "Current proposal selection was already finalized"
                    )
            elif state.selection is not None and self._already_approved(
                uow, command.case_id, state.selection.selection_id
            ):
                raise FinanceFinalizationConflict(
                    "Finalized selection belongs to active execution"
                )
            record = RecordDecisionCommand(
                case_id=command.case_id,
                analysis_id=analysis.analysis_id,
                selected_option_id=option_id,
                kind=command.kind,
                idempotency_key=key,
                rejection_reason=command.rejection_reason,
            )
            satisfactions = self._policy.authorize_independent_and_materialize(
                record, actor, case, projection, analysis, evidence
            )
            decided_at = self._now()
            decision = Decision.from_command(
                record,
                actor,
                analysis,
                satisfactions,
                request_fingerprint=fingerprint,
                decided_at=decided_at,
                proposal_approval=evidence,
            )
            if command.kind is DecisionKind.APPROVED:
                uow.proposals.guard_current(command.case_id, expected=command.expected)
            else:
                uow.proposals.withdraw_current(
                    command.case_id,
                    expected=command.expected,
                    now=decided_at,
                    operation_id=decision.decision_id,
                )
            uow.decisions.insert(decision)
            uow.decisions.insert_satisfactions(decision.decision_id, satisfactions)
            if command.kind is DecisionKind.APPROVED:
                uow.execution.insert_outbox(
                    ActionPlanningRequested.for_decision(decision)
                )
                uow.cases.set_current_decision(decision.case_id, decision.decision_id)
            else:
                uow.cases.mark_rejected(decision.case_id, decision.decision_id)
            uow.commit()
            return decision

    def finalize(
        self, command: FinalizeProposalCommand, actor: IdentitySnapshot
    ) -> Decision:
        self._actors.require_alex(actor)
        key = f"finance-finalize:{command.idempotency_key}"
        fingerprint = finalization_fingerprint(command, actor)
        try:
            return self._once(command, actor, key=key, fingerprint=fingerprint)
        except FINALIZATION_CONTENTION as error:
            self._actors.require_alex(actor)
            with self._uow_factory() as uow:
                existing = uow.decisions.get_by_idempotency_key(key)
                if existing is not None:
                    return self._return_existing(existing, fingerprint)
                if uow.proposals.get_state(command.case_id).token != command.expected:
                    raise FinanceFinalizationConflict(
                        "Finalization lost a current-state race"
                    ) from error
            raise
