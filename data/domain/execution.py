from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from .common import FrozenModel

if TYPE_CHECKING:
    from .decisions import Decision


class OutboxClaimStatus(StrEnum):
    PENDING = "pending"


class ActionPlanningRequested(FrozenModel):
    event_id: str
    decision_id: str
    case_id: str
    analysis_id: str
    event_type: Literal["ActionPlanningRequested"] = "ActionPlanningRequested"
    created_at: datetime
    available_at: datetime
    claim_status: OutboxClaimStatus = OutboxClaimStatus.PENDING

    @classmethod
    def for_decision(cls, decision: Decision) -> ActionPlanningRequested:
        return cls(
            event_id=f"RL-OUTBOX-{uuid4()}",
            decision_id=decision.decision_id,
            case_id=decision.case_id,
            analysis_id=decision.analysis_id,
            created_at=decision.decided_at,
            available_at=decision.decided_at,
        )
