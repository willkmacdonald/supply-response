from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from data.domain import CaseInstance, Disruption
from data.domain.analysis import AnalysisVersion, ResponseOption


AnalyzeCaseResponse = AnalysisVersion
ResponseOptionsResponse = tuple[ResponseOption, ...]


class CreateCaseRequest(BaseModel):
    disruption: Disruption


class CaseResponse(BaseModel):
    case: CaseInstance
    disruption: Disruption
    analysis: AnalysisVersion | None = None
    selected_option_id: str | None = None


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str


class DecisionResponse(BaseModel):
    case_id: str
    analysis_id: str
    option_id: str
    decision: Literal["approved", "rejected"]
    decided_at: datetime
    satisfied_prerequisite_roles: tuple[str, ...]


class DashboardSummary(BaseModel):
    active_disruptions: int
    analyzed_cases: int
    approved_cases: int
    rejected_cases: int
    revenue_at_risk: str
    otif_lines_at_risk: int
