"""Case orchestration: the deterministic equivalent of the Foundry orchestrator.

The agents in ``agents/`` describe how the hosted Foundry agents call into these
functions. Locally every step is deterministic so the demo is reproducible.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.database import ActionRecord, CaseRecord, ScenarioRecord
from apps.api.schemas import ActionResponse, CaseDetail, CaseSummary, EvidenceItem
from data.fixtures import demo as demo_fixtures
from data.schemas.models import Dataset, Disruption
from services.exposure.calculator import CALCULATION_VERSION, ExposureResult
from services.scenarios.builder import scenarios_for
from services.scenarios.evaluator import (
    EvaluationContext,
    ScenarioEvaluation,
    calculate_baseline,
    evaluate_scenarios,
)

DEFAULT_HORIZON_DAYS = 29


class CaseError(Exception):
    """Raised for invalid case operations; mapped to HTTP errors by routers."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def next_case_id(session: Session) -> str:
    count = session.execute(select(func.count()).select_from(CaseRecord)).scalar_one()
    return f"RL-CASE-{count + 1:06d}"


def next_action_id(session: Session) -> str:
    count = session.execute(select(func.count()).select_from(ActionRecord)).scalar_one()
    return f"RL-ACT-{count + 1:06d}"


def find_disruption(dataset: Dataset, disruption_id: str) -> Disruption:
    for disruption in dataset.disruptions:
        if disruption.disruption_id == disruption_id:
            return disruption
    raise CaseError(f"Unknown disruption {disruption_id}", status_code=404)


def build_context(
    dataset: Dataset,
    disruption: Disruption,
    horizon_start: Optional[date] = None,
    horizon_end: Optional[date] = None,
) -> EvaluationContext:
    start = horizon_start or min(
        disruption.original_date, disruption.signal_received_at.date()
    )
    end = horizon_end or (start + timedelta(days=DEFAULT_HORIZON_DAYS))
    return EvaluationContext(
        disruption=disruption,
        horizon_start=start,
        horizon_end=end,
        inventory_positions=list(dataset.inventory_positions),
        purchase_orders=list(dataset.purchase_orders),
        production_orders=list(dataset.production_orders),
        bom_components=list(dataset.bom_components),
        customer_orders=list(dataset.customer_orders),
        customers=list(dataset.customers),
        transport_options=list(dataset.transport_options),
        quality_qualifications=list(dataset.quality_qualifications),
    )


def case_facts(disruption: Disruption) -> list[str]:
    """Confirmed facts, extracted without inference."""
    facts = [
        f"Supplier {disruption.supplier_id} cannot deliver {disruption.delayed_qty} "
        f"units of {disruption.part_id} on {disruption.original_date.isoformat()}.",
    ]
    if disruption.po_id:
        facts.append(
            f"Affected purchase order line: {disruption.po_id} line {disruption.po_line}."
        )
    if disruption.partial_qty and disruption.partial_date:
        facts.append(
            f"Supplier offers {disruption.partial_qty} units on "
            f"{disruption.partial_date.isoformat()}."
        )
    if disruption.revised_date:
        facts.append(f"Revised delivery date: {disruption.revised_date.isoformat()}.")
    facts.append(f"Signal received {disruption.signal_received_at.isoformat()} via {disruption.signal_source}.")
    return facts


def case_uncertainties(disruption: Disruption, dataset: Dataset) -> list[str]:
    """Unresolved questions. Nothing here is inferred or invented."""
    unknowns: list[str] = []
    if not disruption.recovery_date_confirmed:
        remaining = max(disruption.delayed_qty - disruption.partial_qty, 0)
        unknowns.append(
            f"Recovery date for the remaining {remaining} units is unconfirmed."
        )
    blocked = [
        qualification
        for qualification in dataset.quality_qualifications
        if qualification.part_id == disruption.part_id and not qualification.executable
    ]
    for qualification in blocked:
        unknowns.append(
            f"{qualification.qualification_id}: {qualification.supplier_id} is not "
            f"approved for {qualification.part_id}"
            + (
                f"; earliest decision {qualification.expected_decision_date.isoformat()}."
                if qualification.expected_decision_date
                else "."
            )
        )
    return unknowns


def case_evidence(disruption: Disruption) -> list[EvidenceItem]:
    """Work IQ style evidence. Only the demo case has curated evidence."""
    if disruption.disruption_id == demo_fixtures.DEMO_DISRUPTION_ID:
        return [EvidenceItem(**item) for item in demo_fixtures.demo_evidence()]
    return [
        EvidenceItem(
            evidence_id=f"RL-EVD-{disruption.disruption_id}",
            source=disruption.signal_source,
            reference=disruption.signal_reference or disruption.disruption_id,
            title=f"Supplier signal {disruption.disruption_id}",
            content=disruption.summary,
            captured_at=disruption.signal_received_at.isoformat(),
        )
    ]


def analyze(
    dataset: Dataset,
    disruption: Disruption,
    horizon_start: Optional[date] = None,
    horizon_end: Optional[date] = None,
    analyzed_at: Optional[datetime] = None,
) -> tuple[ExposureResult, list[ScenarioEvaluation]]:
    """Run the deterministic exposure and scenario analysis for a disruption."""
    analyzed_at = analyzed_at or datetime.now(timezone.utc)
    context = build_context(dataset, disruption, horizon_start, horizon_end)
    baseline = calculate_baseline(context, analyzed_at)
    scenarios = scenarios_for(context, baseline, dataset.response_scenarios)
    evaluations = evaluate_scenarios(scenarios, context, analyzed_at)
    return baseline, evaluations


def persist_analysis(
    session: Session,
    case: CaseRecord,
    exposure: ExposureResult,
    evaluations: Sequence[ScenarioEvaluation],
    analyzed_at: datetime,
) -> None:
    for record in list(case.scenarios):
        session.delete(record)
    session.flush()

    case.exposure = exposure.model_dump(mode="json")
    case.revenue_at_risk = exposure.revenue_at_risk
    case.margin_at_risk = exposure.margin_at_risk
    case.otif_lines_at_risk = exposure.otif_lines_at_risk
    case.analyzed_at = analyzed_at
    case.status = "awaiting_approval"

    for evaluation in evaluations:
        session.add(
            ScenarioRecord(
                case_id=case.case_id,
                scenario_id=evaluation.scenario_id,
                rank=evaluation.rank,
                executable=evaluation.executable,
                recommended=evaluation.recommended,
                response_cost=evaluation.response_cost,
                revenue_protected=evaluation.revenue_protected,
                score=evaluation.score if evaluation.executable else 0.0,
                payload=evaluation.model_dump(mode="json"),
            )
        )
    session.flush()


def load_scenarios(case: CaseRecord) -> list[ScenarioEvaluation]:
    return [
        ScenarioEvaluation.model_validate(record.payload)
        for record in sorted(case.scenarios, key=lambda r: r.rank)
    ]


def recommended_scenario_id(evaluations: Sequence[ScenarioEvaluation]) -> Optional[str]:
    for evaluation in evaluations:
        if evaluation.recommended:
            return evaluation.scenario_id
    return None


def bounded_actions(evaluation: ScenarioEvaluation, disruption: Disruption) -> list[str]:
    """The follow-up tasks the prototype is allowed to create.

    The prototype never creates a real purchase order or financial commitment.
    """
    tasks = [
        f"Draft supplier recovery request to {disruption.supplier_id} for the "
        f"outstanding {max(disruption.delayed_qty - disruption.partial_qty, 0)} units.",
        f"Create Procurement follow-up task for {disruption.po_id or disruption.disruption_id}.",
        "Create Quality follow-up task to confirm alternate-source qualification status.",
        f"Update disruption case status for {disruption.disruption_id}.",
    ]
    if evaluation.blocking_constraint:
        tasks.append(
            "Mark the blocked alternate supplier as a conditional future option: "
            f"{evaluation.blocking_constraint}"
        )
    return tasks


def to_action_response(record: ActionRecord) -> ActionResponse:
    return ActionResponse(
        action_id=record.action_id,
        case_id=record.case_id,
        disruption_id=record.disruption_id,
        scenario_id=record.scenario_id,
        action_type=record.action_type,
        status=record.status,
        decided_by=record.decided_by,
        decided_at=record.decided_at,
        rationale=record.rationale,
        calculation_version=record.calculation_version,
        evidence=list(record.evidence or []),
        follow_up_tasks=list(record.follow_up_tasks or []),
        predicted_cost=record.predicted_cost,
        predicted_revenue_protected=record.predicted_revenue_protected,
    )


def to_case_summary(case: CaseRecord) -> CaseSummary:
    return CaseSummary(
        case_id=case.case_id,
        disruption_id=case.disruption_id,
        supplier_id=case.supplier_id,
        part_id=case.part_id,
        plant_id=case.plant_id,
        title=case.title,
        status=case.status,
        severity=case.severity,
        signal_reference=case.signal_reference,
        signal_received_at=case.signal_received_at,
        created_at=case.created_at,
        updated_at=case.updated_at,
        analyzed_at=case.analyzed_at,
        revenue_at_risk=case.revenue_at_risk,
        margin_at_risk=case.margin_at_risk,
        otif_lines_at_risk=case.otif_lines_at_risk,
        scenario_count=len(case.scenarios),
    )


def to_case_detail(case: CaseRecord, dataset: Dataset) -> CaseDetail:
    disruption = Disruption.model_validate(case.disruption)
    exposure = ExposureResult.model_validate(case.exposure) if case.exposure else None
    summary = to_case_summary(case)
    return CaseDetail(
        **summary.model_dump(),
        summary=case.summary,
        created_by=case.created_by,
        horizon_start=case.horizon_start,
        horizon_end=case.horizon_end,
        disruption=disruption,
        facts=case_facts(disruption),
        uncertainties=case_uncertainties(disruption, dataset),
        evidence=[EvidenceItem.model_validate(item) for item in (case.evidence or [])],
        exposure=exposure,
        scenarios=load_scenarios(case),
        actions=[to_action_response(record) for record in case.actions],
    )


__all__ = [
    "CALCULATION_VERSION",
    "CaseError",
    "analyze",
    "bounded_actions",
    "build_context",
    "case_evidence",
    "case_facts",
    "case_uncertainties",
    "find_disruption",
    "load_scenarios",
    "next_action_id",
    "next_case_id",
    "persist_analysis",
    "recommended_scenario_id",
    "to_action_response",
    "to_case_detail",
    "to_case_summary",
]
