from __future__ import annotations

from decimal import Decimal

from data.domain import (
    PredictedOutcome,
    QualificationStatus,
    ResponseOption,
    TimedQuantity,
)
from data.domain.common import ResponseOptionKind
from data.synthetic.rl001 import OperationalSnapshot
from services.analysis.exposure import allocate_component_supply
from services.policy.thresholds import requires_finance_approval


MATERIAL_PLANNER = "material_planner"
FINANCE_APPROVER = "finance_approver"
QUALITY_APPROVER = "quality_approver"
RESPONSE_APPROVER = "response_approver"


def calculate_approval_burden(prerequisite_roles: tuple[str, ...]) -> int:
    """Count distinct prerequisite roles, excluding only the final approver."""
    return len({role for role in prerequisite_roles if role != RESPONSE_APPROVER})


def calculate_execution_risk(
    *,
    unconfirmed_external_commitments: int = 0,
    cross_plant_movements: int = 0,
    schedule_changes: int = 0,
    coordinated_action_count: int = 0,
) -> int:
    """Apply the frozen, deterministic execution-risk factor weights."""
    return (
        2 * unconfirmed_external_commitments
        + cross_plant_movements
        + schedule_changes
        + max(0, coordinated_action_count - 1)
    )


def _plain_decimal(value: Decimal) -> Decimal:
    """Remove insignificant trailing zeroes without Decimal's exponent notation."""
    return Decimal(format(value.normalize(), "f"))


def _calculate_intervention_outcome(
    snapshot: OperationalSnapshot,
    *,
    receipts: tuple[TimedQuantity, ...] = (),
    transfers: tuple[TimedQuantity, ...] = (),
    resequence_by_priority: bool = False,
    response_cost: Decimal = Decimal("0"),
) -> PredictedOutcome:
    orders = tuple(
        sorted(
            snapshot.production_orders,
            key=(
                (lambda item: (item.customer_priority, item.production_order_id))
                if resequence_by_priority
                else (lambda item: (item.due_date, item.production_order_id))
            ),
        )
    )
    allocation = allocate_component_supply(
        starting_inventory=snapshot.usable_inventory(
            snapshot.disruption.part_id, snapshot.disruption.plant_id
        ),
        receipts=receipts,
        transfers=transfers,
        production_orders=orders,
    )
    protected = tuple(
        item for item in orders if allocation[item.production_order_id].full_and_on_time
    )
    return PredictedOutcome(
        uncovered_part_demand=allocation.uncovered_component_units,
        otif_loss_percentage=100 * (len(orders) - len(protected)) // len(orders),
        revenue_at_risk=sum(
            (item.customer_revenue for item in orders if item not in protected),
            Decimal("0"),
        ),
        margin_at_risk=sum(
            (item.customer_margin for item in orders if item not in protected),
            Decimal("0"),
        ),
        response_cost=_plain_decimal(response_cost),
        protected_customer_order_ids=tuple(
            item.customer_order_id
            for item in protected
            if item.customer_order_id is not None
        ),
    )


def _alpha_receipt(snapshot: OperationalSnapshot) -> TimedQuantity | None:
    if snapshot.alpha_expedite is None:
        return None
    return TimedQuantity(
        date=snapshot.alpha_expedite.due_date,
        quantity=snapshot.alpha_expedite.quantity,
        source_id=snapshot.alpha_expedite.receipt_id,
    )


def _dallas_transfer(snapshot: OperationalSnapshot) -> TimedQuantity:
    return TimedQuantity(
        date=snapshot.transfer.arrival_date,
        quantity=snapshot.transfer.quantity,
        source_id=snapshot.transfer.transfer_id,
    )


def _option_roles(
    *, finance_required: bool = False, quality_required: bool = False
) -> tuple[str, ...]:
    roles = [MATERIAL_PLANNER]
    if finance_required:
        roles.append(FINANCE_APPROVER)
    if quality_required:
        roles.append(QUALITY_APPROVER)
    return tuple(roles)


def _unconfirmed_recovery_commitments(snapshot: OperationalSnapshot) -> int:
    return int(snapshot.disruption.recovery_date is None)


def _recovery_uncertainties(snapshot: OperationalSnapshot) -> tuple[str, ...]:
    if snapshot.disruption.recovery_date is None:
        return ("Remaining supplier recovery date is unconfirmed.",)
    return ()


def _transfer_available(snapshot: OperationalSnapshot) -> bool:
    return (
        snapshot.usable_inventory(
            snapshot.transfer.part_id, snapshot.transfer.source_plant_id
        )
        >= snapshot.transfer.quantity
    )


def _resequence_available(snapshot: OperationalSnapshot) -> bool:
    due_order = tuple(
        item.production_order_id
        for item in sorted(
            snapshot.production_orders,
            key=lambda item: (item.due_date, item.production_order_id),
        )
    )
    priority_order = tuple(
        item.production_order_id
        for item in sorted(
            snapshot.production_orders,
            key=lambda item: (item.customer_priority, item.production_order_id),
        )
    )
    return priority_order != due_order


def _cross_plant_movements(snapshot: OperationalSnapshot) -> int:
    return int(
        snapshot.transfer.source_plant_id != snapshot.transfer.destination_plant_id
    )


def _schedule_changes(*, resequenced: bool) -> int:
    return int(resequenced)


def _coordinated_action_count(
    *, expedite: bool = False, transfer: bool = False, resequence: bool = False
) -> int:
    return sum((expedite, transfer, resequence))


def _lineage(
    snapshot: OperationalSnapshot,
    *,
    include_alpha: bool = False,
    include_transfer: bool = False,
    include_beta: bool = False,
) -> tuple[str, ...]:
    lineage = [snapshot.disruption.source_ref]
    lineage.extend(
        position.inventory_id
        for position in snapshot.inventory_positions
        if position.part_id == snapshot.disruption.part_id
        and position.plant_id == snapshot.disruption.plant_id
    )
    lineage.extend(order.production_order_id for order in snapshot.production_orders)
    if include_alpha and snapshot.alpha_expedite is not None:
        lineage.append(snapshot.alpha_expedite.receipt_id)
    if include_transfer:
        lineage.extend(
            position.inventory_id
            for position in snapshot.inventory_positions
            if position.part_id == snapshot.transfer.part_id
            and position.plant_id == snapshot.transfer.source_plant_id
        )
        lineage.append(snapshot.transfer.transfer_id)
    if include_beta:
        lineage.append(snapshot.beta_qualification.evidence_ref)
    return tuple(lineage)


def _response_option(
    *,
    option_id: str,
    option_kind: ResponseOptionKind,
    name: str,
    executable: bool,
    active_mitigation: bool,
    predicted: PredictedOutcome | None,
    prerequisite_roles: tuple[str, ...] = (),
    blocking_codes: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
    evidence_ids: tuple[str, ...] = (),
    source_data_lineage: tuple[str, ...] = (),
    unconfirmed_external_commitments: int = 0,
    cross_plant_movements: int = 0,
    schedule_changes: int = 0,
    coordinated_action_count: int = 0,
) -> ResponseOption:
    return ResponseOption(
        option_id=option_id,
        option_kind=option_kind,
        name=name,
        executable=executable,
        active_mitigation=active_mitigation,
        predicted=predicted,
        prerequisite_roles=prerequisite_roles,
        approval_burden=calculate_approval_burden(prerequisite_roles),
        execution_risk=calculate_execution_risk(
            unconfirmed_external_commitments=unconfirmed_external_commitments,
            cross_plant_movements=cross_plant_movements,
            schedule_changes=schedule_changes,
            coordinated_action_count=coordinated_action_count,
        ),
        blocking_codes=blocking_codes,
        assumptions=assumptions,
        evidence_ids=evidence_ids,
        source_data_lineage=source_data_lineage,
    )


def _option_outcomes(snapshot: OperationalSnapshot) -> dict[str, PredictedOutcome]:
    alpha_receipt = _alpha_receipt(snapshot)
    dallas_transfer = _dallas_transfer(snapshot)
    expedite_cost = (
        Decimal(alpha_receipt.quantity)
        * snapshot.alpha_expedite.incremental_cost_per_unit
        if alpha_receipt is not None and snapshot.alpha_expedite is not None
        else Decimal("0")
    )
    transfer_cost = (
        Decimal(snapshot.transfer.quantity)
        * snapshot.transfer.incremental_cost_per_unit
    )
    combined_cost = expedite_cost + transfer_cost
    expedite_receipts = (alpha_receipt,) if alpha_receipt is not None else ()
    return {
        "RL-OPTION-NO-MITIGATION": _calculate_intervention_outcome(snapshot),
        "RL-OPTION-EXPEDITE": _calculate_intervention_outcome(
            snapshot, receipts=expedite_receipts, response_cost=expedite_cost
        ),
        "RL-OPTION-TRANSFER": _calculate_intervention_outcome(
            snapshot, transfers=(dallas_transfer,), response_cost=transfer_cost
        ),
        "RL-OPTION-RESEQUENCE": _calculate_intervention_outcome(
            snapshot, resequence_by_priority=True
        ),
        "RL-OPTION-COMBINED": _calculate_intervention_outcome(
            snapshot,
            receipts=expedite_receipts,
            transfers=(dallas_transfer,),
            resequence_by_priority=True,
            response_cost=combined_cost,
        ),
    }


def evaluate_response_options(
    snapshot: OperationalSnapshot,
) -> tuple[ResponseOption, ...]:
    outcomes = _option_outcomes(snapshot)
    expedite_cost = outcomes["RL-OPTION-EXPEDITE"].response_cost
    combined_cost = outcomes["RL-OPTION-COMBINED"].response_cost
    beta_blocked = snapshot.beta_qualification.status != QualificationStatus.APPROVED
    alpha_available = snapshot.alpha_expedite is not None
    transfer_available = _transfer_available(snapshot)
    resequence_available = _resequence_available(snapshot)
    return (
        _response_option(
            option_id="RL-OPTION-NO-MITIGATION",
            option_kind=ResponseOptionKind.NO_MITIGATION,
            name="No-Mitigation Baseline",
            executable=False,
            active_mitigation=False,
            predicted=outcomes["RL-OPTION-NO-MITIGATION"],
            assumptions=("Optional Alpha expedite receipt is excluded.",),
            source_data_lineage=_lineage(snapshot),
        ),
        _response_option(
            option_id="RL-OPTION-EXPEDITE",
            option_kind=ResponseOptionKind.EXPEDITE,
            name="Expedite Alpha partial receipt",
            executable=alpha_available,
            active_mitigation=True,
            predicted=outcomes["RL-OPTION-EXPEDITE"],
            prerequisite_roles=_option_roles(
                finance_required=requires_finance_approval(expedite_cost)
            ),
            blocking_codes=("ALPHA_PARTIAL_SHIPMENT_UNAVAILABLE",)
            if not alpha_available
            else (),
            assumptions=(
                *(
                    ("Alpha receipt is confirmed for its offered due date.",)
                    if alpha_available
                    else ("No positive Alpha partial-shipment offer is available.",)
                ),
                *_recovery_uncertainties(snapshot),
            ),
            evidence_ids=(
                (snapshot.alpha_expedite.receipt_id,)
                if snapshot.alpha_expedite is not None
                else ()
            ),
            source_data_lineage=_lineage(snapshot, include_alpha=True),
            unconfirmed_external_commitments=_unconfirmed_recovery_commitments(
                snapshot
            ),
            coordinated_action_count=_coordinated_action_count(expedite=True),
        ),
        _response_option(
            option_id="RL-OPTION-TRANSFER",
            option_kind=ResponseOptionKind.TRANSFER,
            name="Transfer inventory from Dallas",
            executable=transfer_available,
            active_mitigation=True,
            predicted=outcomes["RL-OPTION-TRANSFER"],
            prerequisite_roles=_option_roles(),
            blocking_codes=("TRANSFER_INVENTORY_UNAVAILABLE",)
            if not transfer_available
            else (),
            evidence_ids=(snapshot.transfer.transfer_id,),
            source_data_lineage=_lineage(snapshot, include_transfer=True),
            cross_plant_movements=_cross_plant_movements(snapshot),
            coordinated_action_count=_coordinated_action_count(transfer=True),
        ),
        _response_option(
            option_id="RL-OPTION-RESEQUENCE",
            option_kind=ResponseOptionKind.RESEQUENCE,
            name="Resequence production toward priority customers",
            executable=resequence_available,
            active_mitigation=True,
            predicted=outcomes["RL-OPTION-RESEQUENCE"],
            prerequisite_roles=_option_roles(),
            blocking_codes=("RESEQUENCE_NOT_APPLICABLE",)
            if not resequence_available
            else (),
            source_data_lineage=_lineage(snapshot),
            schedule_changes=_schedule_changes(resequenced=True),
            coordinated_action_count=_coordinated_action_count(resequence=True),
        ),
        _response_option(
            option_id="RL-OPTION-BETA",
            option_kind=ResponseOptionKind.ALTERNATE_SOURCE,
            name="Source from Supplier Beta",
            executable=not beta_blocked,
            active_mitigation=True,
            predicted=(
                outcomes["RL-OPTION-NO-MITIGATION"] if not beta_blocked else None
            ),
            prerequisite_roles=_option_roles(quality_required=True),
            blocking_codes=("QUALITY_QUALIFICATION_PENDING",) if beta_blocked else (),
            assumptions=(
                (
                    "No confirmed Beta receipt quantity or date; conservative "
                    "baseline exposure is retained."
                ),
            )
            if not beta_blocked
            else (),
            evidence_ids=(snapshot.beta_qualification.evidence_ref,),
            source_data_lineage=_lineage(snapshot, include_beta=True),
            unconfirmed_external_commitments=_unconfirmed_recovery_commitments(
                snapshot
            ),
            coordinated_action_count=_coordinated_action_count(expedite=True),
        ),
        _response_option(
            option_id="RL-OPTION-COMBINED",
            option_kind=ResponseOptionKind.COMBINED,
            name="Combine expedite, transfer, and resequencing",
            executable=alpha_available and transfer_available and resequence_available,
            active_mitigation=True,
            predicted=outcomes["RL-OPTION-COMBINED"],
            prerequisite_roles=_option_roles(
                finance_required=requires_finance_approval(combined_cost)
            ),
            assumptions=_recovery_uncertainties(snapshot),
            blocking_codes=tuple(
                code
                for unavailable, code in (
                    (
                        not alpha_available,
                        "ALPHA_PARTIAL_SHIPMENT_UNAVAILABLE",
                    ),
                    (
                        not transfer_available,
                        "TRANSFER_INVENTORY_UNAVAILABLE",
                    ),
                    (not resequence_available, "RESEQUENCE_NOT_APPLICABLE"),
                )
                if unavailable
            ),
            evidence_ids=(
                *(
                    (snapshot.alpha_expedite.receipt_id,)
                    if snapshot.alpha_expedite is not None
                    else ()
                ),
                snapshot.transfer.transfer_id,
            ),
            source_data_lineage=_lineage(
                snapshot, include_alpha=True, include_transfer=True
            ),
            unconfirmed_external_commitments=_unconfirmed_recovery_commitments(
                snapshot
            ),
            cross_plant_movements=_cross_plant_movements(snapshot),
            schedule_changes=_schedule_changes(resequenced=True),
            coordinated_action_count=_coordinated_action_count(
                expedite=True, transfer=True, resequence=True
            ),
        ),
    )


def calculate_option_outcome(
    snapshot: OperationalSnapshot, option_id: str
) -> PredictedOutcome:
    """Return the deterministic predicted outcome for one executable option."""
    option = next(
        (
            item
            for item in evaluate_response_options(snapshot)
            if item.option_id == option_id
        ),
        None,
    )
    if option is None:
        raise ValueError(f"Unknown response option: {option_id}")
    if option.predicted is None:
        raise ValueError(f"Response option {option_id} has no predicted outcome")
    return option.predicted
