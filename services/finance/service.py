import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from data.domain.analysis import AnalysisResponseOptionMaterial
from data.domain.cases import WorkflowVersion
from data.domain.decisions import IdentitySnapshot
from data.domain.finance import FinanceProposal, FinanceReviewStatus
from data.domain.proposals import ProposalSelection, ProposalState, SelectionReceipt
from services.finance.contracts import (
    FinanceReviewDetail,
    ResolutionResult,
    ResolveFinanceCommand,
    SubmissionResult,
    SubmitProposalCommand,
)
from services.finance.identity import (
    BoundFinanceActors,
    FinancePermissionDenied,
    authority_material,
)
from services.persistence.finance_reviews import (
    FinanceReviewIdempotencyConflict,
    FinanceReviewRevisionConflict,
)
from services.persistence.ports import UnitOfWork
from services.persistence.proposals import SelectionIdempotencyConflict, StaleProposal
from services.persistence.store import PersistenceIntegrityError
from services.policy.finance_review import resolve_finance_review, submit_finance_review
from services.policy.thresholds import requires_finance_approval


class FinanceCommandConflict(RuntimeError):
    pass


class FinanceRequestInvalid(ValueError):
    pass


def _fingerprint(operation, command, actor):
    material = {
        "operation": operation,
        "command": command.model_dump(mode="json"),
        "actor": authority_material(actor),
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


_CONTENTION = (
    IntegrityError,
    StaleProposal,
    SelectionIdempotencyConflict,
    FinanceReviewIdempotencyConflict,
    FinanceReviewRevisionConflict,
)


class FinanceService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        actors: BoundFinanceActors,
        clock: Callable[[], datetime] | None = None,
    ):
        self._uow_factory = uow_factory
        self._actors = actors
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self):
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise FinanceRequestInvalid("Server clock must be timezone-aware")
        return now

    def status(self, case_id: str, actor: IdentitySnapshot) -> ProposalState:
        self._actors.require_alex(actor)
        with self._uow_factory() as uow:
            state = uow.proposals.get_state(case_id)
            case = uow.cases.get_projection(case_id).case
            if (
                case.effective_workflow_version
                is not WorkflowVersion.INDEPENDENT_FINANCE
            ):
                raise FinanceRequestInvalid("Independent Finance workflow is required")
            if state.selection is not None:
                self._actors.require_alex(state.selection.submitted_by)
            return state

    def _detail(self, uow, review_id: str) -> FinanceReviewDetail:
        selection = uow.proposals.get_selection_for_review(review_id)
        self._actors.require_alex(selection.submitted_by)
        state = uow.proposals.get_state(selection.proposal.case_id)
        review, revision = uow.finance_reviews.get_latest(review_id)
        self._actors.require_alex(review.submitted_by)
        if review.reviewed_by is not None:
            self._actors.require_taylor(review.reviewed_by)
        if (
            review.proposal != selection.proposal
            or selection.finance_review_id != review_id
        ):
            raise PersistenceIntegrityError(
                "Historical review and selection binding differ"
            )
        analysis = uow.cases.get_analysis(selection.proposal.analysis_id)
        option = next(
            (
                item
                for item in analysis.response_options
                if item.option_id == selection.proposal.option_id
            ),
            None,
        )
        if (
            option is None
            or analysis.material_hash != selection.proposal.analysis_material_hash
            or option.predicted is None
            or option.predicted.response_cost != selection.proposal.response_cost
        ):
            raise PersistenceIntegrityError(
                "Historical review material differs from analysis"
            )
        if uow.proposals.get_state(selection.proposal.case_id).token != state.token:
            raise StaleProposal("Review state changed while reading")
        return FinanceReviewDetail(
            selection=selection,
            review=review,
            review_revision=revision,
            analysis=analysis,
            option=option,
            is_current=state.token.selection_id == selection.selection_id,
            current_token=state.token,
        )

    def detail(self, review_id: str, actor: IdentitySnapshot) -> FinanceReviewDetail:
        self._actors.require_taylor(actor)
        with self._uow_factory() as uow:
            return self._detail(uow, review_id)

    def list_pending(self, actor: IdentitySnapshot) -> tuple[FinanceReviewDetail, ...]:
        self._actors.require_taylor(actor)
        with self._uow_factory() as uow:
            results = []
            for case_id in uow.proposals.list_pending_case_ids():
                state = uow.proposals.get_state(case_id)
                if (
                    state.selection is None
                    or state.review is None
                    or state.review.status is not FinanceReviewStatus.PENDING
                ):
                    continue
                try:
                    self._actors.require_alex(state.selection.submitted_by)
                except FinancePermissionDenied:
                    continue
                detail = self._detail(uow, state.review.review_id)
                if (
                    detail.is_current
                    and detail.review.status is FinanceReviewStatus.PENDING
                ):
                    results.append(detail)
            return tuple(results)

    def _submission_replay(self, uow, key, fingerprint):
        stored = uow.proposals.get_by_idempotency_key(key)
        if stored is None:
            return None
        if stored.request_fingerprint != fingerprint:
            raise FinanceCommandConflict("Key was already used for another submission")
        self._actors.require_alex(stored.selection.submitted_by)
        return self._submission_result(uow, stored.selection)

    @staticmethod
    def _submission_result(uow, selection):
        pending = (
            uow.finance_reviews.get_revision(selection.finance_review_id, 1)
            if selection.finance_review_id is not None
            else None
        )
        return SubmissionResult(
            selection=selection,
            review=pending,
            review_revision=1 if pending is not None else None,
        )

    def _resolution_replay(self, uow, key, fingerprint):
        stored = uow.finance_reviews.get_by_idempotency_key(key)
        if stored is None:
            return None
        review, revision, original_fingerprint = stored
        if original_fingerprint != fingerprint:
            raise FinanceCommandConflict(
                "Key was already used for another review command"
            )
        self._actors.require_alex(review.submitted_by)
        if review.reviewed_by is None:
            raise PersistenceIntegrityError("Resolution receipt lacks reviewer")
        self._actors.require_taylor(review.reviewed_by)
        return ResolutionResult(review=review, review_revision=revision)

    def submit(
        self, command: SubmitProposalCommand, actor: IdentitySnapshot
    ) -> SubmissionResult:
        self._actors.require_alex(actor)
        key = f"finance-submit:{command.idempotency_key}"
        fingerprint = _fingerprint("submit", command, actor)
        try:
            with self._uow_factory() as uow:
                replay = self._submission_replay(uow, key, fingerprint)
                if replay is not None:
                    return replay
                state = uow.proposals.get_state(command.case_id)
                if state.token != command.expected:
                    raise StaleProposal("Case analysis or proposal changed")
                case = uow.cases.get_projection(command.case_id).case
                if (
                    case.effective_workflow_version
                    is not WorkflowVersion.INDEPENDENT_FINANCE
                ):
                    raise FinanceRequestInvalid(
                        "Independent Finance workflow is required"
                    )
                analysis_id = command.expected.analysis_id
                if analysis_id is None:
                    raise FinanceRequestInvalid("Submission requires an analyzed case")
                analysis = uow.cases.get_analysis(analysis_id)
                if (
                    analysis.case_id != case.case_id
                    or analysis.material_hash != command.expected.analysis_material_hash
                ):
                    raise StaleProposal("Analysis binding changed")
                option = next(
                    (
                        o
                        for o in analysis.response_options
                        if o.option_id == command.option_id
                    ),
                    None,
                )
                material_option = next(
                    (
                        o
                        for o in analysis.material.response_options
                        if o.option_id == command.option_id
                    ),
                    None,
                )
                if (
                    option is None
                    or material_option is None
                    or AnalysisResponseOptionMaterial.from_option(option)
                    != material_option
                    or not option.executable
                    or not option.active_mitigation
                    or option.predicted is None
                    or option.blocking_codes
                ):
                    raise FinanceRequestInvalid(
                        "Selected response is not executable mitigation"
                    )
                if state.selection is not None:
                    self._actors.require_alex(state.selection.submitted_by)
                now = self._now()
                proposal = FinanceProposal(
                    case_id=case.case_id,
                    analysis_id=analysis.analysis_id,
                    analysis_material_hash=analysis.material_hash,
                    option_id=option.option_id,
                    response_cost=option.predicted.response_cost,
                )
                selection_id = f"RL-SELECTION-{uuid4()}"
                review_id = (
                    f"RL-FINANCE-{uuid4()}"
                    if requires_finance_approval(proposal.response_cost)
                    else None
                )
                selection = ProposalSelection(
                    selection_id=selection_id,
                    proposal=proposal,
                    workflow_version=case.effective_workflow_version,
                    submitted_by=actor,
                    submitted_at=now,
                    finance_review_id=review_id,
                )
                if review_id is not None:
                    pending = submit_finance_review(
                        review_id=review_id, proposal=proposal, actor=actor, now=now
                    )
                    uow.finance_reviews.append(
                        pending,
                        expected_revision=None,
                        idempotency_key=f"finance-pending:{selection_id}",
                        request_fingerprint=fingerprint,
                    )
                selection = uow.proposals.publish(
                    SelectionReceipt(
                        selection=selection,
                        expected=command.expected,
                        idempotency_key=key,
                        request_fingerprint=fingerprint,
                    )
                )
                result = self._submission_result(uow, selection)
                uow.commit()
                return result
        except _CONTENTION as error:
            self._actors.require_alex(actor)
            with self._uow_factory() as uow:
                replay = self._submission_replay(uow, key, fingerprint)
                if replay is not None:
                    return replay
                state = uow.proposals.get_state(command.case_id)
                if state.token != command.expected:
                    raise FinanceCommandConflict(
                        "Submission lost a current-proposal race"
                    ) from error
            raise

    def resolve(
        self, command: ResolveFinanceCommand, actor: IdentitySnapshot
    ) -> ResolutionResult:
        self._actors.require_taylor(actor)
        key = f"finance-resolve:{command.idempotency_key}"
        fingerprint = _fingerprint("resolve", command, actor)
        try:
            with self._uow_factory() as uow:
                replay = self._resolution_replay(uow, key, fingerprint)
                if replay is not None:
                    return replay
                review, revision = uow.finance_reviews.get_latest(command.review_id)
                self._actors.require_alex(review.submitted_by)
                state = uow.proposals.get_state(review.proposal.case_id)
                if (
                    state.token != command.expected
                    or state.review is None
                    or state.selection is None
                    or state.review.review_id != command.review_id
                    or state.review != review
                    or state.review_revision != revision
                    or revision != command.expected_review_revision
                ):
                    raise StaleProposal(
                        "Review is no longer the expected current request"
                    )
                resolved = resolve_finance_review(
                    review=review,
                    current_proposal=state.selection.proposal,
                    actor=actor,
                    approved=command.approved,
                    reason=command.reason,
                    now=self._now(),
                )
                uow.proposals.guard_current(
                    review.proposal.case_id, expected=command.expected
                )
                resolved, revision = uow.finance_reviews.append(
                    resolved,
                    expected_revision=command.expected_review_revision,
                    idempotency_key=key,
                    request_fingerprint=fingerprint,
                )
                result = ResolutionResult(review=resolved, review_revision=revision)
                uow.commit()
                return result
        except _CONTENTION as error:
            self._actors.require_taylor(actor)
            with self._uow_factory() as uow:
                replay = self._resolution_replay(uow, key, fingerprint)
                if replay is not None:
                    return replay
                review, revision = uow.finance_reviews.get_latest(command.review_id)
                state = uow.proposals.get_state(review.proposal.case_id)
                if (
                    state.token != command.expected
                    or revision != command.expected_review_revision
                ):
                    raise FinanceCommandConflict(
                        "Review lost a current-proposal race"
                    ) from error
            raise
