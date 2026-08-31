from data.domain.analysis import ResponseOption
from data.domain.decisions import (
    ApprovalSatisfaction,
    ApprovalTarget,
    StandingAuthorization,
)


_ROLE_PERSONAS = {"quality_approver": "RL-PERSONA-JORDAN"}


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
        if authorization.role == role
        and (
            role not in _ROLE_PERSONAS
            or authorization.persona_id == _ROLE_PERSONAS[role]
        )
        and authorization.permits(option, target)
    )
