from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from data.domain import CasePurpose, CaseStatus, RuntimeMode
from data.domain.analysis import (
    AnalysisMaterial,
    EvidenceValidation,
    RankingResult,
    ResponseOption,
)
from data.domain.decisions import ApprovalSatisfaction
from data.domain.evidence import EvidenceItem


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateCaseRequest(StrictRequest):
    template_id: Literal["RL-001"]
    purpose: CasePurpose


class DecisionRequest(StrictRequest):
    analysis_id: str
    kind: Literal["approved", "rejected"]
    selected_option_id: str | None = None
    rejection_reason: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "DecisionRequest":
        if self.kind == "approved":
            if self.selected_option_id is None:
                raise ValueError("approval requires selected_option_id")
            if self.rejection_reason is not None:
                raise ValueError("approval cannot include rejection_reason")
        elif self.selected_option_id is not None:
            raise ValueError("rejection cannot include selected_option_id")
        elif self.rejection_reason is None or not self.rejection_reason.strip():
            raise ValueError("rejection requires a nonblank rejection_reason")
        return self


class RuntimeResponse(BaseModel):
    runtime_mode: RuntimeMode
    work_iq: Literal["synthetic"]
    operational_store: Literal["sqlite"]
    agent_runtime: Literal["local"]
    power_bi_available: Literal[False]


class CaseControls(BaseModel):
    new_analysis: bool
    decide: bool
    retry_action_planning: bool
    start_playback: bool


class CaseResponse(BaseModel):
    case_id: str
    template_id: str
    purpose: CasePurpose
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime
    scenario_timezone: Literal["America/Chicago"]
    status: CaseStatus
    current_analysis_id: str | None
    current_decision_id: str | None
    display_status: str | None
    recorded_at: datetime
    projection_updated_at: datetime
    controls: CaseControls


class AnalysisResponse(BaseModel):
    analysis_id: str
    case_id: str
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime
    analysis_started_at: datetime
    retrieval_window_ends_at: datetime
    created_at: datetime
    material_hash: str
    material: AnalysisMaterial
    evidence_items: tuple[EvidenceItem, ...]
    evidence_validation: EvidenceValidation
    response_options: tuple[ResponseOption, ...]
    approval_satisfactions: tuple[ApprovalSatisfaction, ...]
    ranking: RankingResult
    recommendation: ResponseOption | None


class DecisionResponse(BaseModel):
    decision_id: str
    case_id: str
    analysis_id: str
    analysis_material_hash: str
    kind: Literal["approved", "rejected"]
    selected_option_id: str | None
    rejection_reason: str | None
    evidence_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]
    prerequisite_roles: tuple[str, ...]
    approval_satisfactions: tuple[ApprovalSatisfaction, ...]
    calculation_version: str
    evidence_policy_version: str
    approval_policy_version: str
    ranking_policy_version: str
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime
    decided_at: datetime
    projection_updated_at: datetime
    action_planning_status: Literal["not_applicable", "pending", "failed", "complete"]
    new_analysis_available: bool


class ActionResponse(BaseModel):
    action_id: str
    case_id: str
    decision_id: str
    kind: str
    owner_kind: str
    owner_persona_id: str | None
    status: str
    created_at: datetime
    draft_artifact_id: str | None
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime
    projection_updated_at: datetime


class DraftResponse(BaseModel):
    artifact_id: str
    action_id: str
    decision_id: str
    artifact_kind: str
    created_at: datetime
    subject: str | None
    body: str | None
    sent: Literal[False]
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime


class PlaybackResponse(BaseModel):
    playback_id: str
    case_id: str
    decision_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime


class ObservationResponse(BaseModel):
    observation_id: str
    case_id: str
    decision_id: str
    playback_id: str | None
    action_id: str | None
    metric: str
    observed_value: str
    unit: str
    predicted_value: str
    scenario_effective_time: datetime
    scenario_timezone: Literal["America/Chicago"]
    recorded_at: datetime
    source_reference: str
    kind: str
    synthetic: bool
    display_label: str
    runtime_mode: RuntimeMode


class DashboardCaseResponse(CaseResponse):
    analysis_created_at: datetime | None
    decision_decided_at: datetime | None
    recommended_option_id: str | None
    selected_option_id: str | None
    action_count: int
    observation_count: int
