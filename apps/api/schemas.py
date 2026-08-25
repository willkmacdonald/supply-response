"""Request and response contracts for the Supply Response API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from data.schemas.models import Disruption
from services.exposure.calculator import ExposureResult
from services.scenarios.evaluator import ScenarioEvaluation


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseCreateRequest(ApiModel):
    disruption_id: str = Field(
        default="RL-001",
        description="Disruption in the reference dataset that this case tracks.",
    )
    created_by: str = "Alex Morgan"
    horizon_start: Optional[date] = None
    horizon_end: Optional[date] = None
    title: Optional[str] = None
    notes: str = ""


class EvidenceItem(ApiModel):
    evidence_id: str
    source: str
    reference: str
    title: str
    content: str
    captured_at: str


class CaseSummary(ApiModel):
    case_id: str
    disruption_id: str
    supplier_id: str
    part_id: str
    plant_id: str
    title: str
    status: str
    severity: str
    signal_reference: str
    signal_received_at: datetime
    created_at: datetime
    updated_at: datetime
    analyzed_at: Optional[datetime] = None
    revenue_at_risk: float = 0.0
    margin_at_risk: float = 0.0
    otif_lines_at_risk: int = 0
    scenario_count: int = 0


class ActionResponse(ApiModel):
    action_id: str
    case_id: str
    disruption_id: str
    scenario_id: Optional[str] = None
    action_type: str
    status: str
    decided_by: str
    decided_at: datetime
    rationale: str = ""
    calculation_version: str = ""
    evidence: list[str] = Field(default_factory=list)
    follow_up_tasks: list[str] = Field(default_factory=list)
    predicted_cost: float = 0.0
    predicted_revenue_protected: float = 0.0


class CaseDetail(CaseSummary):
    summary: str = ""
    created_by: str = ""
    horizon_start: date
    horizon_end: date
    disruption: Disruption
    facts: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    exposure: Optional[ExposureResult] = None
    scenarios: list[ScenarioEvaluation] = Field(default_factory=list)
    actions: list[ActionResponse] = Field(default_factory=list)


class AnalyzeResponse(ApiModel):
    case_id: str
    status: str
    analyzed_at: datetime
    calculation_version: str
    exposure: ExposureResult
    scenarios: list[ScenarioEvaluation]
    recommended_scenario_id: Optional[str] = None
    facts: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ScenarioListResponse(ApiModel):
    case_id: str
    calculation_version: str
    scenarios: list[ScenarioEvaluation]
    recommended_scenario_id: Optional[str] = None


class DecisionRequest(ApiModel):
    scenario_id: str
    decided_by: str = "Alex Morgan"
    rationale: str = ""


class DecisionResponse(ApiModel):
    case_id: str
    status: str
    action: ActionResponse
    scenario: ScenarioEvaluation
    bounded_actions: list[str] = Field(default_factory=list)


class NarrativeResponse(ApiModel):
    case_id: str
    narrative: str
    source: str
    agent_version: str


class DashboardSummary(ApiModel):
    generated_at: datetime
    calculation_version: str
    active_cases: int
    cases_by_status: dict[str, int]
    cases_by_severity: dict[str, int]
    total_revenue_at_risk: float
    total_margin_at_risk: float
    total_otif_lines_at_risk: int
    approved_actions: int
    rejected_actions: int
    average_minutes_to_decision: Optional[float] = None
    dataset_row_counts: dict[str, int] = Field(default_factory=dict)
    cases: list[CaseSummary] = Field(default_factory=list)
    top_scenarios: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "ActionResponse",
    "AnalyzeResponse",
    "CaseCreateRequest",
    "CaseDetail",
    "CaseSummary",
    "DashboardSummary",
    "DecisionRequest",
    "DecisionResponse",
    "EvidenceItem",
    "NarrativeResponse",
    "ScenarioListResponse",
]
