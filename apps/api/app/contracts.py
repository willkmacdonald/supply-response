from pydantic import BaseModel, Field
from data.schemas.models import Disruption, ExposureResult, ResponseScenario, SupplyResponseCase


class CreateCaseRequest(BaseModel):
    disruption: Disruption


class AnalyzeCaseResponse(BaseModel):
    case_id: str
    exposure: ExposureResult
    scenarios: list[ResponseScenario]


class DecisionRequest(BaseModel):
    scenario_id: str
    evidence_refs: list[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    active_disruptions: int
    analyzed_cases: int
    approved_cases: int
    rejected_cases: int
    revenue_at_risk: str
    otif_lines_at_risk: int
