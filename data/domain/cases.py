from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Mapping, Self

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

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        """Return a validated copy without reusing an ID across runtime modes."""
        values = self.model_dump(mode="python")
        values.update(update or {})
        changed = type(self).model_validate(values)
        if (
            changed.runtime_mode != self.runtime_mode
            and changed.case_id == self.case_id
        ):
            raise ValueError("runtime_mode changes require a different case_id")
        return changed
