"""Disruption case endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api import services
from apps.api.database import ActionRecord, CaseRecord, get_session
from apps.api.dataset import get_dataset
from apps.api.schemas import (
    AnalyzeResponse,
    CaseCreateRequest,
    CaseDetail,
    CaseSummary,
    DecisionRequest,
    DecisionResponse,
    NarrativeResponse,
    ScenarioListResponse,
)
from services.exposure.calculator import CALCULATION_VERSION, ExposureResult

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _get_case(session: Session, case_id: str) -> CaseRecord:
    case = session.get(CaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Unknown case {case_id}")
    return case


@router.post("", response_model=CaseDetail, status_code=status.HTTP_201_CREATED)
def create_case(
    request: CaseCreateRequest, session: Session = Depends(get_session)
) -> CaseDetail:
    dataset = get_dataset()
    try:
        disruption = services.find_disruption(dataset, request.disruption_id)
    except services.CaseError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error

    context = services.build_context(
        dataset, disruption, request.horizon_start, request.horizon_end
    )
    now = datetime.now(timezone.utc)
    case = CaseRecord(
        case_id=services.next_case_id(session),
        disruption_id=disruption.disruption_id,
        supplier_id=disruption.supplier_id,
        part_id=disruption.part_id,
        plant_id=disruption.plant_id,
        title=request.title
        or f"{disruption.disruption_id} {disruption.supplier_id} delivery delay",
        summary=request.notes or disruption.summary,
        status="new",
        severity=disruption.severity.value,
        signal_reference=disruption.signal_reference,
        signal_received_at=disruption.signal_received_at.replace(tzinfo=None),
        horizon_start=context.horizon_start,
        horizon_end=context.horizon_end,
        created_by=request.created_by,
        created_at=now.replace(tzinfo=None),
        updated_at=now.replace(tzinfo=None),
        disruption=disruption.model_dump(mode="json"),
        evidence=[item.model_dump() for item in services.case_evidence(disruption)],
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return services.to_case_detail(case, dataset)


@router.get("", response_model=list[CaseSummary])
def list_cases(session: Session = Depends(get_session)) -> list[CaseSummary]:
    cases = session.execute(select(CaseRecord).order_by(CaseRecord.case_id)).scalars().all()
    return [services.to_case_summary(case) for case in cases]


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, session: Session = Depends(get_session)) -> CaseDetail:
    case = _get_case(session, case_id)
    return services.to_case_detail(case, get_dataset())


@router.post("/{case_id}/analyze", response_model=AnalyzeResponse)
def analyze_case(case_id: str, session: Session = Depends(get_session)) -> AnalyzeResponse:
    case = _get_case(session, case_id)
    dataset = get_dataset()
    try:
        disruption = services.find_disruption(dataset, case.disruption_id)
    except services.CaseError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error

    analyzed_at = datetime.now(timezone.utc)
    exposure, evaluations = services.analyze(
        dataset,
        disruption,
        case.horizon_start,
        case.horizon_end,
        analyzed_at,
    )
    services.persist_analysis(
        session, case, exposure, evaluations, analyzed_at.replace(tzinfo=None)
    )
    session.commit()
    session.refresh(case)

    return AnalyzeResponse(
        case_id=case.case_id,
        status=case.status,
        analyzed_at=case.analyzed_at,
        calculation_version=CALCULATION_VERSION,
        exposure=exposure,
        scenarios=evaluations,
        recommended_scenario_id=services.recommended_scenario_id(evaluations),
        facts=services.case_facts(disruption),
        uncertainties=services.case_uncertainties(disruption, dataset),
        evidence=services.case_evidence(disruption),
    )


@router.get("/{case_id}/scenarios", response_model=ScenarioListResponse)
def get_scenarios(case_id: str, session: Session = Depends(get_session)) -> ScenarioListResponse:
    case = _get_case(session, case_id)
    evaluations = services.load_scenarios(case)
    if not evaluations:
        raise HTTPException(
            status_code=409,
            detail=f"Case {case_id} has not been analyzed yet. POST /api/cases/{case_id}/analyze first.",
        )
    return ScenarioListResponse(
        case_id=case.case_id,
        calculation_version=CALCULATION_VERSION,
        scenarios=evaluations,
        recommended_scenario_id=services.recommended_scenario_id(evaluations),
    )


def _decide(
    session: Session, case_id: str, request: DecisionRequest, approve: bool
) -> DecisionResponse:
    case = _get_case(session, case_id)
    evaluations = services.load_scenarios(case)
    if not evaluations:
        raise HTTPException(
            status_code=409, detail=f"Case {case_id} has not been analyzed yet."
        )
    selected = next(
        (e for e in evaluations if e.scenario_id == request.scenario_id), None
    )
    if selected is None:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario {request.scenario_id} is not part of case {case_id}",
        )
    if approve and not selected.executable:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Scenario {selected.scenario_id} is not executable: "
                f"{selected.blocking_constraint}"
            ),
        )

    disruption = services.find_disruption(get_dataset(), case.disruption_id)
    decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    tasks = services.bounded_actions(selected, disruption) if approve else []
    record = ActionRecord(
        action_id=services.next_action_id(session),
        case_id=case.case_id,
        disruption_id=case.disruption_id,
        scenario_id=selected.scenario_id,
        action_type="approve_response" if approve else "reject_response",
        status="approved" if approve else "rejected",
        decided_by=request.decided_by,
        decided_at=decided_at,
        rationale=request.rationale,
        calculation_version=CALCULATION_VERSION,
        evidence=list(selected.evidence),
        follow_up_tasks=tasks,
        predicted_cost=selected.response_cost,
        predicted_revenue_protected=selected.revenue_protected,
    )
    session.add(record)
    case.status = "approved" if approve else "rejected"
    case.updated_at = decided_at
    session.commit()
    session.refresh(case)
    session.refresh(record)

    return DecisionResponse(
        case_id=case.case_id,
        status=case.status,
        action=services.to_action_response(record),
        scenario=selected,
        bounded_actions=tasks,
    )


@router.post("/{case_id}/approve", response_model=DecisionResponse)
def approve_case(
    case_id: str, request: DecisionRequest, session: Session = Depends(get_session)
) -> DecisionResponse:
    return _decide(session, case_id, request, approve=True)


@router.post("/{case_id}/reject", response_model=DecisionResponse)
def reject_case(
    case_id: str, request: DecisionRequest, session: Session = Depends(get_session)
) -> DecisionResponse:
    return _decide(session, case_id, request, approve=False)


@router.get("/{case_id}/narrative", response_model=NarrativeResponse)
def get_narrative(case_id: str, session: Session = Depends(get_session)) -> NarrativeResponse:
    """Return a narrative explanation produced by the Decision agent.

    The case must be analyzed before calling this endpoint (exposure and
    scenarios must already be stored).  Uses Azure OpenAI when configured;
    falls back to a deterministic template in all other cases.
    """
    from agents.decision import agent as decision_agent

    case = _get_case(session, case_id)
    evaluations = services.load_scenarios(case)
    if not evaluations or case.exposure is None:
        raise HTTPException(
            status_code=409,
            detail=f"Case {case_id} has not been analyzed yet. POST /api/cases/{case_id}/analyze first.",
        )

    dataset = get_dataset()
    disruption = services.find_disruption(dataset, case.disruption_id)
    exposure = ExposureResult.model_validate(case.exposure)
    facts = services.case_facts(disruption)
    uncertainties = services.case_uncertainties(disruption, dataset)
    recommended_id = services.recommended_scenario_id(evaluations)

    narrative, source = decision_agent.narrate(
        facts=facts,
        uncertainties=uncertainties,
        exposure=exposure,
        evaluations=evaluations,
        recommended_scenario_id=recommended_id,
    )

    return NarrativeResponse(
        case_id=case.case_id,
        narrative=narrative,
        source=source,
        agent_version=decision_agent.AGENT_VERSION,
    )
