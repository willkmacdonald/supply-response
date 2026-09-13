from data.domain.cases import CaseInstance, WorkflowVersion
from data.domain.decisions import StandingAuthorization


def approval_policy_for(case: CaseInstance) -> str:
    return case.effective_workflow_version.value


def standing_authorizations_for(
    case: CaseInstance,
    authorizations: tuple[StandingAuthorization, ...],
) -> tuple[StandingAuthorization, ...]:
    if case.effective_workflow_version is WorkflowVersion.LEGACY:
        return authorizations
    return tuple(item for item in authorizations if item.role != "finance_approver")
