from datetime import datetime

from data.domain.analysis import ResponseOption
from data.domain.decisions import ApprovalSatisfaction, StandingAuthorization


def evaluate_approval_satisfaction(
    *,
    option: ResponseOption,
    analysis_id: str,
    standing_authorizations: tuple[StandingAuthorization, ...],
    scenario_effective_time: datetime,
) -> tuple[ApprovalSatisfaction, ...]:
    required = set(option.prerequisite_roles) - {"response_approver"}
    return tuple(
        ApprovalSatisfaction.from_authorization(analysis_id, option, authorization)
        for role in sorted(required)
        for authorization in standing_authorizations
        if authorization.role == role
        and authorization.permits(option, scenario_effective_time)
    )
