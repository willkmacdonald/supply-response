from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from data.domain.analysis import AnalysisVersion
from data.domain.common import ResponseOptionKind
from data.domain.decisions import Decision, DecisionKind
from data.domain.execution import (
    ExecutionAction,
    ExecutionActionKind,
    ExecutionOwnerKind,
)
from data.synthetic.rl001 import OperationalSnapshot

ACTION_KINDS_BY_OPTION: dict[ResponseOptionKind, tuple[ExecutionActionKind, ...]] = {
    ResponseOptionKind.EXPEDITE: (
        ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT,
        ExecutionActionKind.COORDINATE_ALPHA_EXPEDITED_PARTIAL,
        ExecutionActionKind.UPDATE_DISRUPTION_STATUS,
    ),
    ResponseOptionKind.TRANSFER: (
        ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT,
        ExecutionActionKind.TRANSFER_DALLAS_TO_CHICAGO,
        ExecutionActionKind.UPDATE_DISRUPTION_STATUS,
    ),
    ResponseOptionKind.RESEQUENCE: (
        ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT,
        ExecutionActionKind.RESEQUENCE_PRIORITY_PRODUCTION,
        ExecutionActionKind.UPDATE_DISRUPTION_STATUS,
    ),
    ResponseOptionKind.COMBINED: tuple(ExecutionActionKind),
}
ExecutionMode = Literal["simulation", "communication_preparation"]


def deterministic_action_id(decision_id: str, action_kind: str) -> str:
    value = uuid5(NAMESPACE_URL, f"{decision_id}:{action_kind}")
    return f"RL-ACTION-{value}"


def deterministic_draft_artifact_id(decision_id: str) -> str:
    value = uuid5(NAMESPACE_URL, f"{decision_id}:alpha_recovery_request")
    return f"RL-DRAFT-{value}"


def _date_label(value: date) -> str:
    return f"{value:%B} {value.day}, {value.year}"


def _entity_label(identifier: str, prefix: str) -> str:
    value = identifier.removeprefix(prefix)
    return {"CHI": "Chicago", "DAL": "Dallas"}.get(
        value, value.replace("-", " ").title()
    )


def action_kinds_for(
    option_kind: ResponseOptionKind,
) -> tuple[ExecutionActionKind, ...]:
    try:
        return ACTION_KINDS_BY_OPTION[option_kind]
    except KeyError:
        raise ValueError(
            "Decision does not identify a current executable option"
        ) from None


def _action_display(
    decision: Decision,
    snapshot: OperationalSnapshot,
    kind: ExecutionActionKind,
) -> tuple[str, str, ExecutionMode]:
    supplier = _entity_label(snapshot.disruption.supplier_id, "RL-SUP-")
    disruption_plant = _entity_label(snapshot.disruption.plant_id, "RL-PLANT-")
    if kind is ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT:
        return (
            (
                f"Prepare supplier communication to {supplier} about disruption "
                f"{snapshot.disruption.disruption_id} for "
                f"{snapshot.disruption.part_id}."
            ),
            "An unsent supplier recovery-request draft is ready for Alex's review.",
            "communication_preparation",
        )
    if kind is ExecutionActionKind.COORDINATE_ALPHA_EXPEDITED_PARTIAL:
        expedite = snapshot.alpha_expedite
        if expedite is None:
            raise ValueError("approved Analysis snapshot lacks Alpha expedite details")
        return (
            (
                f"Coordinate {expedite.quantity:,} expedited units from {supplier} "
                f"to {disruption_plant} by {_date_label(expedite.due_date)} at "
                f"${expedite.incremental_cost_per_unit:.2f} per unit."
            ),
            (
                f"{expedite.quantity:,} units are simulated as arriving at "
                f"{disruption_plant} on {_date_label(expedite.due_date)}."
            ),
            "simulation",
        )
    if kind is ExecutionActionKind.TRANSFER_DALLAS_TO_CHICAGO:
        transfer = snapshot.transfer
        source = _entity_label(transfer.source_plant_id, "RL-PLANT-")
        destination = _entity_label(transfer.destination_plant_id, "RL-PLANT-")
        return (
            (
                f"Coordinate a {transfer.quantity:,}-unit transfer from {source} to "
                f"{destination}, arriving {_date_label(transfer.arrival_date)}."
            ),
            (
                f"{transfer.quantity:,} units are simulated as available in "
                f"{destination} on {_date_label(transfer.arrival_date)}."
            ),
            "simulation",
        )
    if kind is ExecutionActionKind.RESEQUENCE_PRIORITY_PRODUCTION:
        option = decision.selected_option
        protected_ids = (
            ()
            if option is None or option.predicted is None
            else option.predicted.protected_customer_order_ids
        )
        if not protected_ids:
            priorities = tuple(
                order.customer_priority
                for order in snapshot.production_orders
                if order.customer_priority is not None
                and order.customer_order_id is not None
            )
            highest_priority = min(priorities, default=None)
            protected_ids = tuple(
                order.customer_order_id
                for order in snapshot.production_orders
                if highest_priority is not None
                and order.customer_priority == highest_priority
                and order.customer_order_id is not None
            )
        protected_orders = tuple(
            order
            for order in snapshot.customer_orders
            if order.customer_order_line_id in protected_ids
        )
        if len(protected_orders) != len(protected_ids):
            raise ValueError(
                "approved option names an unknown protected customer order"
            )
        order_names = ", ".join(
            order.customer_order_line_id for order in protected_orders
        )
        order_results = "; ".join(
            f"{order.customer_order_line_id} at "
            f"{_entity_label(order.plant_id, 'RL-PLANT-')} due "
            f"{_date_label(order.due_date)}"
            for order in protected_orders
        )
        return (
            f"Resequence priority production to protect customer order(s) {order_names}.",
            f"Production is simulated as prioritized for {order_results}.",
            "simulation",
        )
    return (
        (
            f"Update disruption {snapshot.disruption.disruption_id} status for "
            f"{snapshot.disruption.part_id} at {disruption_plant}."
        ),
        "The system status reflects the approved mitigation coordination.",
        "simulation",
    )


def build_action(
    decision: Decision,
    snapshot: OperationalSnapshot,
    kind: ExecutionActionKind,
) -> ExecutionAction:
    purpose, expected_result, execution_mode = _action_display(decision, snapshot, kind)
    system_owned = kind is ExecutionActionKind.UPDATE_DISRUPTION_STATUS
    owns_draft = kind is ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT
    return ExecutionAction(
        action_id=deterministic_action_id(decision.decision_id, kind.value),
        case_id=decision.case_id,
        decision_id=decision.decision_id,
        kind=kind,
        owner_kind=(
            ExecutionOwnerKind.SYSTEM if system_owned else ExecutionOwnerKind.PERSONA
        ),
        owner_persona_id=None if system_owned else "RL-PERSONA-ALEX",
        created_at=decision.decided_at,
        draft_artifact_id=(
            deterministic_draft_artifact_id(decision.decision_id)
            if owns_draft
            else None
        ),
        purpose=purpose,
        expected_result=expected_result,
        execution_mode=execution_mode,
    )


def plan_actions(
    decision: Decision,
    analysis: AnalysisVersion,
) -> tuple[ExecutionAction, ...]:
    if decision.kind is not DecisionKind.APPROVED:
        raise ValueError("actions require an approved Decision")
    if (
        decision.analysis_id != analysis.analysis_id
        or decision.analysis_material_hash != analysis.material_hash
        or decision.selected_option is None
        or decision.selected_option_id != decision.selected_option.option_id
        or not decision.selected_option.executable
    ):
        raise ValueError("Decision does not identify a current executable option")
    snapshot = OperationalSnapshot.model_validate_json(
        analysis.material.operational_snapshot_json
    )
    kinds = action_kinds_for(decision.selected_option.option_kind)
    return tuple(build_action(decision, snapshot, kind) for kind in kinds)
