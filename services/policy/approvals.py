from data.domain.analysis import ResponseOption
from data.domain.decisions import (
    ApprovalSatisfaction,
    ApprovalTarget,
    StandingAuthorization,
)


def evaluate_approval_satisfaction(
    *,
    option: ResponseOption,
    analysis_id: str,
    standing_authorizations: tuple[StandingAuthorization, ...],
    target: ApprovalTarget,
) -> tuple[ApprovalSatisfaction, ...]:
    required = set(option.prerequisite_roles) - {"response_approver"}
    return tuple(
        ApprovalSatisfaction.from_authorization(
            analysis_id, option, authorization, target
        )
        for role in sorted(required)
        for authorization in standing_authorizations
        if authorization.role == role and authorization.permits(option, target)
    )
