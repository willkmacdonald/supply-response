from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from data.domain.decisions import Decision, DecisionKind
from data.domain.execution import (
    ExecutionAction,
    ExecutionActionKind,
    ExecutionOwnerKind,
)


def deterministic_action_id(decision_id: str, action_kind: str) -> str:
    value = uuid5(NAMESPACE_URL, f"{decision_id}:{action_kind}")
    return f"RL-ACTION-{value}"


def deterministic_draft_artifact_id(decision_id: str) -> str:
    value = uuid5(NAMESPACE_URL, f"{decision_id}:alpha_recovery_request")
    return f"RL-DRAFT-{value}"


def plan_actions(decision: Decision) -> tuple[ExecutionAction, ...]:
    if decision.kind is not DecisionKind.APPROVED:
        raise ValueError("actions can be planned only for an approved Decision")
    if decision.selected_option_id != "RL-OPTION-COMBINED":
        raise ValueError("bounded planning requires the approved combined option")

    kinds = tuple(ExecutionActionKind)
    actions: list[ExecutionAction] = []
    for kind in kinds:
        system_owned = kind is ExecutionActionKind.UPDATE_DISRUPTION_STATUS
        owns_draft = kind is ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT
        actions.append(
            ExecutionAction(
                action_id=deterministic_action_id(decision.decision_id, kind.value),
                case_id=decision.case_id,
                decision_id=decision.decision_id,
                kind=kind,
                owner_kind=(
                    ExecutionOwnerKind.SYSTEM
                    if system_owned
                    else ExecutionOwnerKind.PERSONA
                ),
                owner_persona_id=None if system_owned else "RL-PERSONA-ALEX",
                created_at=decision.decided_at,
                draft_artifact_id=(
                    deterministic_draft_artifact_id(decision.decision_id)
                    if owns_draft
                    else None
                ),
            )
        )
    return tuple(actions)
