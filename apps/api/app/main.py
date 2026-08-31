from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from apps.api.app.contracts import (
    AnalyzeCaseResponse,
    CaseResponse,
    CreateCaseRequest,
    DashboardSummary,
    DecisionRequest,
    DecisionResponse,
    ResponseOptionsResponse,
)
from data.domain import (
    CaseInstance,
    CasePurpose,
    CaseStatus,
    Disruption,
    RuntimeMode,
    serialize_money,
)
from data.domain.analysis import AnalysisVersion
from data.domain.decisions import CorpusScope, StandingAuthorization
from data.domain.evidence import (
    ActorProvenance,
    IdentitySource,
)
from data.synthetic.rl001 import (
    OperationalSnapshot,
    build_rl001_evidence,
    instantiate_rl001,
)
from services.analysis.service import AnalyzeCaseCommand, analyze_case as run_analysis


@dataclass
class CaseRecord:
    case: CaseInstance
    disruption: Disruption
    snapshot: OperationalSnapshot
    analysis: AnalysisVersion | None = None
    selected_option_id: str | None = None


app = FastAPI(title="Supply Response API", version="0.2.0")
CASES: dict[str, CaseRecord] = {}
DECISIONS: list[DecisionResponse] = []


def _response(record: CaseRecord) -> CaseResponse:
    return CaseResponse(
        case=record.case,
        disruption=record.disruption,
        analysis=record.analysis,
        selected_option_id=record.selected_option_id,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/cases", response_model=CaseResponse, status_code=201)
def create_case(request: CreateCaseRequest) -> CaseResponse:
    case_id = f"RL-CASE-{uuid4().hex[:8].upper()}"
    case, snapshot = instantiate_rl001(
        case_id=case_id,
        purpose=CasePurpose.SHOWCASE,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    snapshot = snapshot.model_copy(update={"disruption": request.disruption})
    record = CaseRecord(case=case, disruption=request.disruption, snapshot=snapshot)
    CASES[case_id] = record
    return _response(record)


def _case(case_id: str) -> CaseRecord:
    try:
        return CASES[case_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="Case not found") from None


@app.get("/api/cases/{case_id}", response_model=CaseResponse)
def get_case(case_id: str) -> CaseResponse:
    return _response(_case(case_id))


@app.post("/api/cases/{case_id}/analyze", response_model=AnalyzeCaseResponse)
def analyze(case_id: str) -> AnalyzeCaseResponse:
    record = _case(case_id)
    analysis_id = f"RL-ANALYSIS-{uuid4().hex[:8].upper()}"
    analysis_started_at = datetime.now(timezone.utc)
    snapshot = record.snapshot

    evidence_items = build_rl001_evidence(
        snapshot,
        analysis_id=analysis_id,
        retrieved_at=analysis_started_at,
    )
    analysis = run_analysis(
        AnalyzeCaseCommand(
            analysis_id=analysis_id,
            case=record.case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=evidence_items,
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
            analysis_started_at=analysis_started_at,
            created_at=datetime.now(timezone.utc),
            calculation_version="rl001-options-v1",
        )
    )
    record.analysis = analysis
    record.case = record.case.model_copy(
        update={"status": CaseStatus.AWAITING_DECISION}
    )
    return analysis


@app.get("/api/cases/{case_id}/options", response_model=ResponseOptionsResponse)
def get_options(case_id: str) -> ResponseOptionsResponse:
    analysis = _case(case_id).analysis
    if analysis is None:
        raise HTTPException(
            status_code=409, detail="Case has no authoritative analysis"
        )
    return analysis.response_options


def _decide(case_id: str, request: DecisionRequest, decision: str) -> CaseResponse:
    record = _case(case_id)
    if record.analysis is None:
        raise HTTPException(
            status_code=409, detail="Case has no authoritative analysis"
        )
    option = next(
        (
            item
            for item in record.analysis.response_options
            if item.option_id == request.option_id
        ),
        None,
    )
    if option is None:
        raise HTTPException(
            status_code=400,
            detail="Response option has not been analyzed for this case",
        )
    if decision == "approved" and (
        not option.executable or option.predicted is None or option.blocking_codes
    ):
        raise HTTPException(status_code=409, detail="Response option is not executable")

    satisfied_roles: set[str] = set()
    if decision == "approved":
        if not _is_alex_material_planner(request.actor):
            raise HTTPException(
                status_code=403,
                detail="Approval requires authenticated Alex Material Planner interaction",
            )
        satisfied_roles.add("material_planner")
        satisfied_roles.update(
            satisfaction.role
            for satisfaction in record.analysis.approval_satisfactions
            if satisfaction.option_id == option.option_id and satisfaction.satisfied
        )
        required_roles = set(option.prerequisite_roles) - {"response_approver"}
        missing_roles = tuple(sorted(required_roles - satisfied_roles))
        if missing_roles:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Response option prerequisite approvals are not satisfied: "
                    + ", ".join(missing_roles)
                ),
            )

    record.selected_option_id = option.option_id
    record.case = record.case.model_copy(
        update={
            "status": (
                CaseStatus.ACTION_PLANNING
                if decision == "approved"
                else CaseStatus.DECISION_REJECTED
            )
        }
    )
    DECISIONS.append(
        DecisionResponse(
            case_id=case_id,
            analysis_id=record.analysis.analysis_id,
            option_id=option.option_id,
            decision=decision,
            decided_at=datetime.now(timezone.utc),
            satisfied_prerequisite_roles=tuple(sorted(satisfied_roles)),
        )
    )
    return _response(record)


@app.post("/api/cases/{case_id}/approve", response_model=CaseResponse)
def approve_case(case_id: str, request: DecisionRequest) -> CaseResponse:
    return _decide(case_id, request, "approved")


@app.post("/api/cases/{case_id}/reject", response_model=CaseResponse)
def reject_case(case_id: str, request: DecisionRequest) -> CaseResponse:
    return _decide(case_id, request, "rejected")


def _is_alex_material_planner(actor: ActorProvenance) -> bool:
    return (
        actor.persona_id == "RL-PERSONA-ALEX"
        and actor.identity_source == IdentitySource.ENTRA
        and actor.source_id == "RL-ENTRA-ALEX"
        and "material_planner" in actor.roles
    )


@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> DashboardSummary:
    analyses = tuple(
        record.analysis for record in CASES.values() if record.analysis is not None
    )
    no_mitigation = tuple(
        option
        for analysis in analyses
        for option in analysis.response_options
        if not option.active_mitigation and option.predicted is not None
    )
    return DashboardSummary(
        active_disruptions=sum(
            record.case.status != CaseStatus.CLOSED for record in CASES.values()
        ),
        analyzed_cases=len(analyses),
        approved_cases=sum(
            record.case.status == CaseStatus.ACTION_PLANNING
            for record in CASES.values()
        ),
        rejected_cases=sum(
            record.case.status == CaseStatus.DECISION_REJECTED
            for record in CASES.values()
        ),
        revenue_at_risk=serialize_money(
            sum(
                (option.predicted.revenue_at_risk for option in no_mitigation),
                Decimal("0"),
            )
        ),
        otif_lines_at_risk=sum(
            int(option.predicted.otif_loss_percentage > 0) for option in no_mitigation
        ),
    )
