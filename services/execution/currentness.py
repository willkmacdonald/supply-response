from data.domain.cases import WorkflowVersion
from data.domain.decisions import Decision, DecisionKind
from data.domain.finance import FinanceReviewStatus
from data.domain.proposals import ProposalToken
from services.persistence.ports import UnitOfWork
from services.persistence.proposals import StaleProposal
from services.persistence.store import PersistenceIntegrityError


class ExecutionProposalStale(RuntimeError):
    """An execution mutation no longer has its exact current approval."""


def check_execution_current(
    uow: UnitOfWork, decision_id: str
) -> tuple[Decision, ProposalToken | None]:
    decision = uow.decisions.get(decision_id)
    if decision.kind is not DecisionKind.APPROVED:
        raise ExecutionProposalStale("Execution requires an approved Decision")
    if decision.approval_policy_version != WorkflowVersion.INDEPENDENT_FINANCE.value:
        return decision, None
    evidence = decision.proposal_approval
    if evidence is None:
        raise PersistenceIntegrityError("Independent Decision lacks proposal evidence")
    try:
        state = uow.proposals.get_state(decision.case_id)
        projection = uow.cases.get_projection(decision.case_id)
        if (
            projection.current_decision_id != decision.decision_id
            or projection.current_analysis_id != decision.analysis_id
            or projection.current_analysis_hash != decision.analysis_material_hash
            or state.token.analysis_id != decision.analysis_id
            or state.token.analysis_material_hash != decision.analysis_material_hash
            or state.token.selection_id != evidence.selection.selection_id
            or state.selection != evidence.selection
            or state.review != evidence.review
            or state.review_revision != evidence.review_revision
            or (
                state.review is not None
                and state.review.status is not FinanceReviewStatus.APPROVED
            )
        ):
            raise ExecutionProposalStale(
                "Decision proposal approval is no longer current"
            )
        if uow.proposals.get_state(decision.case_id).token != state.token:
            raise ExecutionProposalStale("Execution approval changed while reading")
        return decision, state.token
    except StaleProposal as error:
        raise ExecutionProposalStale(
            "Execution approval changed while reading"
        ) from error


def guard_execution_current(uow: UnitOfWork, decision_id: str) -> Decision:
    decision, token = check_execution_current(uow, decision_id)
    if token is not None:
        try:
            uow.proposals.guard_current(decision.case_id, expected=token)
        except StaleProposal as error:
            raise ExecutionProposalStale(
                "Execution lost a current-proposal race"
            ) from error
    return decision
