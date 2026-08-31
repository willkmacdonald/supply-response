from datetime import datetime
from enum import StrEnum
from typing import Literal

from .common import CasePurpose, FrozenModel, RuntimeMode


class CaseStatus(StrEnum):
    OPEN = "open"
    ANALYZING = "analyzing"
    AWAITING_DECISION = "awaiting_decision"
    DECISION_REJECTED = "decision_rejected"
    ACTION_PLANNING = "action_planning"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    REANALYSIS_REQUIRED = "reanalysis_required"
    CLOSED = "closed"


class DemoTemplate(FrozenModel):
    template_id: str
    scenario_effective_time: datetime
    scenario_timezone: Literal["America/Chicago"] = "America/Chicago"


class CaseInstance(FrozenModel):
    case_id: str
    template_id: str
    purpose: CasePurpose
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime
    scenario_timezone: Literal["America/Chicago"] = "America/Chicago"
    status: CaseStatus = CaseStatus.OPEN
