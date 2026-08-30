from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from apps.api.app.contracts import (
    AnalyzeCaseResponse,
    CreateCaseRequest,
    DashboardSummary,
    DecisionRequest,
)
from data.schemas.models import (
    ActionLedgerRecord,
    CaseStatus,
    ResponseScenario,
    SupplyResponseCase,
    TimedQuantity,
)
from data.synthetic.generator import generate_dataset
from services.exposure.calculator import calculate_exposure
from services.scenarios.evaluator import build_initial_scenarios

app = FastAPI(title="Supply Response API", version="0.1.0")
DATASET = generate_dataset(seed=42)
CASES: dict[str, SupplyResponseCase] = {}
ACTION_LEDGER: list[ActionLedgerRecord] = []


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/cases", response_model=SupplyResponseCase, status_code=201)
def create_case(request: CreateCaseRequest) -> SupplyResponseCase:
    case_id = f"RL-CASE-{uuid4().hex[:8].upper()}"
    case = SupplyResponseCase(case_id=case_id, disruption=request.disruption)
    CASES[case_id] = case
    return case


def _case(case_id: str) -> SupplyResponseCase:
    try:
        return CASES[case_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="Case not found")


@app.get("/api/cases/{case_id}", response_model=SupplyResponseCase)
def get_case(case_id: str) -> SupplyResponseCase:
    return _case(case_id)


@app.post("/api/cases/{case_id}/analyze", response_model=AnalyzeCaseResponse)
def analyze_case(case_id: str) -> AnalyzeCaseResponse:
    case = _case(case_id)
    d = case.disruption
    receipts = []
    if d.partial_quantity and d.partial_due_date:
        receipts.append(
            TimedQuantity(
                date=d.partial_due_date,
                quantity=d.partial_quantity,
                source_id=d.source_ref,
            )
        )
    exposure = calculate_exposure(
        scenario_id="RL-SCENARIO-BASELINE",
        part_id=d.part_id,
        plant_id=d.plant_id,
        inventory_positions=DATASET.inventory_positions,
        receipts=receipts,
        transfers=[],
        bom_components=DATASET.bom_components,
        production_orders=DATASET.production_orders,
        customer_orders=DATASET.customer_orders,
        assumptions=("Only confirmed receipts are included",),
        remaining_uncertainty=("Remaining supplier recovery date is unconfirmed",)
        if d.recovery_date is None
        else (),
    )
    scenarios = build_initial_scenarios(d, DATASET.quality_qualifications)
    case.exposure = exposure
    case.scenarios = scenarios
    case.status = CaseStatus.ANALYZED
    return AnalyzeCaseResponse(case_id=case_id, exposure=exposure, scenarios=scenarios)


@app.get("/api/cases/{case_id}/scenarios", response_model=list[ResponseScenario])
def get_scenarios(case_id: str):
    return _case(case_id).scenarios


def _decide(
    case_id: str, request: DecisionRequest, decision: str
) -> SupplyResponseCase:
    case = _case(case_id)
    scenario = next(
        (s for s in case.scenarios if s.scenario_id == request.scenario_id), None
    )
    if scenario is None:
        raise HTTPException(
            status_code=400, detail="Scenario has not been analyzed for this case"
        )
    if decision == "approved" and not scenario.executable:
        raise HTTPException(status_code=409, detail="Scenario is not executable")
    if case.exposure is None:
        raise HTTPException(
            status_code=409, detail="Case has no authoritative analysis"
        )
    case.selected_scenario_id = scenario.scenario_id
    case.status = CaseStatus.APPROVED if decision == "approved" else CaseStatus.REJECTED
    ACTION_LEDGER.append(
        ActionLedgerRecord(
            action_id=f"RL-ACTION-{uuid4().hex[:8].upper()}",
            case_id=case_id,
            scenario_id=scenario.scenario_id,
            decision=decision,
            decided_at=datetime.now(timezone.utc),
            scenario_evidence_refs=scenario.evidence_refs,
            approval_evidence_refs=tuple(request.evidence_refs),
            calculation_version=case.exposure.metadata.calculation_version,
            source_data_lineage=case.exposure.metadata.source_data_lineage,
        )
    )
    return case


@app.post("/api/cases/{case_id}/approve", response_model=SupplyResponseCase)
def approve_case(case_id: str, request: DecisionRequest) -> SupplyResponseCase:
    return _decide(case_id, request, "approved")


@app.post("/api/cases/{case_id}/reject", response_model=SupplyResponseCase)
def reject_case(case_id: str, request: DecisionRequest) -> SupplyResponseCase:
    return _decide(case_id, request, "rejected")


@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> DashboardSummary:
    exposures = [c.exposure for c in CASES.values() if c.exposure]
    return DashboardSummary(
        active_disruptions=sum(
            c.status in {CaseStatus.OPEN, CaseStatus.ANALYZED} for c in CASES.values()
        ),
        analyzed_cases=sum(c.status == CaseStatus.ANALYZED for c in CASES.values()),
        approved_cases=sum(c.status == CaseStatus.APPROVED for c in CASES.values()),
        rejected_cases=sum(c.status == CaseStatus.REJECTED for c in CASES.values()),
        revenue_at_risk=str(sum((e.revenue_at_risk for e in exposures), Decimal("0"))),
        otif_lines_at_risk=sum(e.otif_lines_at_risk for e in exposures),
    )
