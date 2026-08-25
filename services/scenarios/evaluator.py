"""Scenario evaluation and ranking.

Each candidate response scenario is re-costed against the deterministic exposure
engine: the scenario's incremental supply (expedite / transfer) and demand
changes (resequencing) are applied, the exposure is recalculated, and the result
is compared to the do-nothing baseline.

Ranking is deterministic. No LLM is used.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Collection, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from data.schemas.models import (
    BomComponent,
    Customer,
    CustomerOrder,
    Disruption,
    InventoryPosition,
    ProductionOrder,
    PurchaseOrder,
    QualityQualification,
    ResponseScenario,
    ScenarioType,
    TransportOption,
)
from services.exposure.calculator import (
    CALCULATION_VERSION,
    component_demand,
    ExposureResult,
    SupplyEvent,
    Transfer,
    calculate_exposure,
    response_cost,
    revenue_protected,
)
from services.policy.checker import PolicyDecision, check_spend_approval, check_supplier_qualification, merge_decisions

EVALUATOR_VERSION = "1.0.0"

#: Flat internal cost booked for every production order that is resequenced.
RESEQUENCE_COST_PER_ORDER = 1_500.0

#: Backlog penalty booked per unit of unmet demand when a delay is accepted.
BACKLOG_PENALTY_PER_UNIT = 2.5


class EvaluationContext(BaseModel):
    """Everything the evaluator needs to score scenarios for one disruption."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    disruption: Disruption
    horizon_start: date
    horizon_end: date
    inventory_positions: list[InventoryPosition] = Field(default_factory=list)
    purchase_orders: list[PurchaseOrder] = Field(default_factory=list)
    production_orders: list[ProductionOrder] = Field(default_factory=list)
    bom_components: list[BomComponent] = Field(default_factory=list)
    customer_orders: list[CustomerOrder] = Field(default_factory=list)
    customers: list[Customer] = Field(default_factory=list)
    transport_options: list[TransportOption] = Field(default_factory=list)
    quality_qualifications: list[QualityQualification] = Field(default_factory=list)

    @property
    def customer_priority(self) -> dict[str, int]:
        return {c.customer_id: c.priority_tier for c in self.customers}


class ScenarioEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    disruption_id: str
    scenario_type: ScenarioType
    title: str
    description: str
    calculation_version: str = CALCULATION_VERSION
    evaluator_version: str = EVALUATOR_VERSION
    evaluated_at: datetime
    executable: bool
    conditional: bool = False
    blocking_constraint: Optional[str] = None
    requires_approval: bool = False
    approver_roles: list[str] = Field(default_factory=list)
    response_cost: float = 0.0
    revenue_protected: float = 0.0
    net_benefit: float = 0.0
    revenue_at_risk: float = 0.0
    margin_at_risk: float = 0.0
    otif_lines_at_risk: int = 0
    first_stockout_date: Optional[date] = None
    max_shortage_qty: int = 0
    inventory_impact: int = 0
    score: float = 0.0
    rank: int = 0
    recommended: bool = False
    assumptions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    exposure: Optional[ExposureResult] = None


def _transport(context: EvaluationContext, transport_option_id: Optional[str]) -> Optional[TransportOption]:
    if not transport_option_id:
        return None
    for option in context.transport_options:
        if option.transport_option_id == transport_option_id:
            return option
    return None


def _consuming_order_ids(
    context: "EvaluationContext", part_id: str, plant_id: str
) -> set[str]:
    """Ids of open production orders that consume ``part_id`` at ``plant_id``."""
    events = component_demand(
        context.production_orders,
        context.bom_components,
        part_id,
        plant_id,
        context.horizon_start,
        context.horizon_end,
    )
    return {event.production_order_id for event in events}


def _apply_resequencing(
    production_orders: Sequence[ProductionOrder],
    resequenced_qty: int,
    eligible_ids: Collection[str],
) -> tuple[list[ProductionOrder], int]:
    """Defer the lowest-priority production orders out of the horizon.

    Only orders in ``eligible_ids`` (those that consume the disrupted component
    at the affected plant inside the horizon) may be deferred: resequencing an
    unrelated order would cost money without relieving the shortage.

    Returns the modified order list and the number of deferred orders. Orders are
    deferred lowest priority first (priority 5 is lowest, 1 is highest), then by
    latest due date, until ``resequenced_qty`` units have been deferred.
    """
    if resequenced_qty <= 0:
        return list(production_orders), 0

    candidates = sorted(
        (o for o in production_orders if o.production_order_id in eligible_ids),
        key=lambda o: (-o.priority, o.due_date, o.production_order_id),
    )
    deferred: set[str] = set()
    remaining = resequenced_qty
    for order in candidates:
        if remaining <= 0:
            break
        deferred.add(order.production_order_id)
        remaining -= order.quantity

    updated: list[ProductionOrder] = []
    for order in production_orders:
        if order.production_order_id in deferred:
            updated.append(
                order.model_copy(
                    update={
                        "start_date": date(9999, 12, 31),
                        "due_date": date(9999, 12, 31),
                    }
                )
            )
        else:
            updated.append(order)
    return updated, len(deferred)


def evaluate_scenario(
    scenario: ResponseScenario,
    context: EvaluationContext,
    baseline: Optional[ExposureResult] = None,
    evaluated_at: Optional[datetime] = None,
) -> ScenarioEvaluation:
    """Score a single scenario against the deterministic exposure engine."""
    evaluated_at = evaluated_at or datetime.now(timezone.utc)
    disruption = context.disruption
    part_id = disruption.part_id
    plant_id = disruption.plant_id
    baseline = baseline or calculate_baseline(context, evaluated_at)

    extra_receipts: list[SupplyEvent] = []
    transfers: list[Transfer] = []
    expedite_transport = _transport(context, scenario.transport_option_id)
    available_date = scenario.available_date or disruption.partial_date or disruption.original_date

    premium_freight_cost = 0.0
    if scenario.expedite_qty > 0:
        extra_receipts.append(
            SupplyEvent(
                date=available_date,
                quantity=scenario.expedite_qty,
                source_type="expedite",
                source_id=scenario.scenario_id,
            )
        )
        premium_freight_cost = response_cost(
            expedite_qty=scenario.expedite_qty,
            expedite_cost_per_unit=expedite_transport.cost_per_unit if expedite_transport else 0.0,
            expedite_fixed_cost=expedite_transport.fixed_cost if expedite_transport else 0.0,
        )

    transfer_cost = 0.0
    if scenario.transfer_qty > 0:
        transfers.append(
            Transfer(
                part_id=part_id,
                to_plant_id=plant_id,
                from_plant_id=_source_plant(context, part_id, plant_id),
                quantity=scenario.transfer_qty,
                available_date=available_date,
            )
        )
        transfer_option = _find_transfer_option(context, plant_id)
        transfer_cost = response_cost(
            transfer_qty=scenario.transfer_qty,
            transfer_cost_per_unit=transfer_option.cost_per_unit if transfer_option else 0.0,
            transfer_fixed_cost=transfer_option.fixed_cost if transfer_option else 0.0,
        )

    production_orders, deferred_count = _apply_resequencing(
        context.production_orders,
        scenario.resequenced_qty,
        _consuming_order_ids(context, part_id, plant_id),
    )
    resequencing_cost = deferred_count * RESEQUENCE_COST_PER_ORDER

    exposure = calculate_exposure(
        scenario_id=scenario.scenario_id,
        part_id=part_id,
        plant_id=plant_id,
        horizon_start=context.horizon_start,
        horizon_end=context.horizon_end,
        inventory_positions=context.inventory_positions,
        purchase_orders=context.purchase_orders,
        production_orders=production_orders,
        bom_components=context.bom_components,
        customer_orders=context.customer_orders,
        transfers=transfers,
        extra_receipts=extra_receipts,
        customer_priority=context.customer_priority,
        assumptions=scenario.assumptions,
        calculated_at=evaluated_at,
    )

    penalty_cost = 0.0
    if scenario.scenario_type == ScenarioType.ACCEPT_DELAY:
        penalty_cost = round(exposure.total_shortage_qty * BACKLOG_PENALTY_PER_UNIT, 2)

    cost = round(premium_freight_cost + transfer_cost + resequencing_cost + penalty_cost, 2)
    protected = revenue_protected(baseline.revenue_at_risk, exposure.revenue_at_risk)

    policy = merge_decisions(check_spend_approval(cost, premium_freight_cost))
    if scenario.alternate_supplier_id:
        policy = merge_decisions(
            policy,
            check_supplier_qualification(
                context.quality_qualifications, scenario.alternate_supplier_id, part_id
            ),
        )

    executable = scenario.executable and policy.executable
    blocking = policy.blocking_constraint or (
        scenario.blocking_constraint if not scenario.executable else None
    )

    evaluation = ScenarioEvaluation(
        scenario_id=scenario.scenario_id,
        disruption_id=scenario.disruption_id,
        scenario_type=scenario.scenario_type,
        title=scenario.title,
        description=scenario.description,
        evaluated_at=evaluated_at,
        executable=executable,
        conditional=policy.conditional or not executable,
        blocking_constraint=blocking,
        requires_approval=scenario.requires_approval or policy.requires_approval,
        approver_roles=policy.approver_roles,
        response_cost=cost,
        revenue_protected=protected,
        net_benefit=round(protected - cost, 2),
        revenue_at_risk=exposure.revenue_at_risk,
        margin_at_risk=exposure.margin_at_risk,
        otif_lines_at_risk=exposure.otif_lines_at_risk,
        first_stockout_date=exposure.first_stockout_date,
        max_shortage_qty=exposure.max_shortage_qty,
        inventory_impact=scenario.transfer_qty + scenario.expedite_qty,
        assumptions=list(scenario.assumptions),
        evidence=_evidence(scenario, disruption, policy),
        open_questions=_open_questions(disruption, executable, blocking),
        exposure=exposure,
    )
    evaluation.score = score_scenario(evaluation)
    return evaluation


def score_scenario(evaluation: ScenarioEvaluation) -> float:
    """Deterministic score: net benefit, penalised for OTIF risk and shortages."""
    if not evaluation.executable:
        return float("-inf")
    score = (
        evaluation.net_benefit
        - evaluation.otif_lines_at_risk * 1_000.0
        - evaluation.max_shortage_qty * 1.0
    )
    return round(score, 2)


def calculate_baseline(
    context: EvaluationContext, calculated_at: Optional[datetime] = None
) -> ExposureResult:
    """Do-nothing exposure used as the comparison point for every scenario."""
    disruption = context.disruption
    open_questions = []
    if not disruption.recovery_date_confirmed:
        open_questions.append(
            "Supplier has not confirmed a recovery date for the remaining quantity."
        )
    return calculate_exposure(
        scenario_id=f"{disruption.disruption_id}-BASELINE",
        part_id=disruption.part_id,
        plant_id=disruption.plant_id,
        horizon_start=context.horizon_start,
        horizon_end=context.horizon_end,
        inventory_positions=context.inventory_positions,
        purchase_orders=context.purchase_orders,
        production_orders=context.production_orders,
        bom_components=context.bom_components,
        customer_orders=context.customer_orders,
        customer_priority=context.customer_priority,
        assumptions=[
            "Delayed purchase-order quantity is excluded until a supplier commitment exists.",
            "Open production orders consume components on their start date.",
        ],
        open_questions=open_questions,
        calculated_at=calculated_at,
    )


def evaluate_scenarios(
    scenarios: Sequence[ResponseScenario],
    context: EvaluationContext,
    evaluated_at: Optional[datetime] = None,
) -> list[ScenarioEvaluation]:
    """Evaluate and rank every scenario. Executable scenarios rank first."""
    evaluated_at = evaluated_at or datetime.now(timezone.utc)
    baseline = calculate_baseline(context, evaluated_at)
    evaluations = [
        evaluate_scenario(scenario, context, baseline, evaluated_at) for scenario in scenarios
    ]
    return rank_scenarios(evaluations)


def rank_scenarios(evaluations: Sequence[ScenarioEvaluation]) -> list[ScenarioEvaluation]:
    """Sort by executability, then score, then cost, then scenario id."""
    ordered = sorted(
        evaluations,
        key=lambda e: (
            0 if e.executable else 1,
            -e.score if e.executable else 0.0,
            e.response_cost,
            e.scenario_id,
        ),
    )
    for index, evaluation in enumerate(ordered, start=1):
        evaluation.rank = index
        evaluation.recommended = index == 1 and evaluation.executable
    return ordered


def _source_plant(context: EvaluationContext, part_id: str, exclude_plant_id: str) -> str:
    candidates = sorted(
        {
            position.plant_id
            for position in context.inventory_positions
            if position.part_id == part_id and position.plant_id != exclude_plant_id
        }
    )
    return candidates[0] if candidates else ""


def _find_transfer_option(context: EvaluationContext, destination: str) -> Optional[TransportOption]:
    for option in context.transport_options:
        if option.destination == destination and option.mode.value in {"road", "rail"}:
            return option
    return None


def _evidence(
    scenario: ResponseScenario, disruption: Disruption, policy: PolicyDecision
) -> list[str]:
    evidence = [
        f"{disruption.disruption_id}: {disruption.signal_reference or disruption.signal_source}",
    ]
    if disruption.po_id:
        evidence.append(f"purchase_order:{disruption.po_id}")
    for violation in policy.violations:
        evidence.append(f"policy:{violation.code}")
        if violation.source_reference:
            evidence.append(violation.source_reference)
    if scenario.transport_option_id:
        evidence.append(f"transport_option:{scenario.transport_option_id}")
    return evidence


def _open_questions(
    disruption: Disruption, executable: bool, blocking: Optional[str]
) -> list[str]:
    questions: list[str] = []
    if not disruption.recovery_date_confirmed:
        questions.append("When will the supplier confirm the remaining quantity?")
    if not executable and blocking:
        questions.append(f"How and when is this constraint cleared: {blocking}")
    return questions


__all__ = [
    "BACKLOG_PENALTY_PER_UNIT",
    "EVALUATOR_VERSION",
    "RESEQUENCE_COST_PER_ORDER",
    "EvaluationContext",
    "ScenarioEvaluation",
    "calculate_baseline",
    "evaluate_scenario",
    "evaluate_scenarios",
    "rank_scenarios",
    "score_scenario",
]
