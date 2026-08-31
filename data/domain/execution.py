from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from pydantic import model_validator

from .common import FrozenModel

if TYPE_CHECKING:
    from .decisions import Decision


class OutboxClaimStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    PROCESSED = "processed"


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


class ExecutionActionKind(StrEnum):
    PREPARE_ALPHA_RECOVERY_DRAFT = "prepare_alpha_recovery_draft"
    COORDINATE_ALPHA_EXPEDITED_PARTIAL = "coordinate_alpha_expedited_partial"
    TRANSFER_DALLAS_TO_CHICAGO = "transfer_dallas_to_chicago"
    RESEQUENCE_PRIORITY_PRODUCTION = "resequence_priority_production"
    UPDATE_DISRUPTION_STATUS = "update_disruption_status"


class ExecutionOwnerKind(StrEnum):
    PERSONA = "persona"
    SYSTEM = "system"


class ExecutionStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ALLOWED_TRANSITIONS: dict[ExecutionStatus, frozenset[ExecutionStatus]] = {
    ExecutionStatus.PLANNED: frozenset(
        {ExecutionStatus.IN_PROGRESS, ExecutionStatus.CANCELLED}
    ),
    ExecutionStatus.IN_PROGRESS: frozenset(
        {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        }
    ),
    ExecutionStatus.FAILED: frozenset({ExecutionStatus.IN_PROGRESS}),
    ExecutionStatus.COMPLETED: frozenset(),
    ExecutionStatus.CANCELLED: frozenset(),
}


class ExecutionAction(FrozenModel):
    action_id: str
    case_id: str
    decision_id: str
    kind: ExecutionActionKind
    owner_kind: ExecutionOwnerKind
    owner_persona_id: str | None
    status: ExecutionStatus = ExecutionStatus.PLANNED
    created_at: datetime
    draft_artifact_id: str | None = None

    @model_validator(mode="after")
    def validate_owner_and_draft(self) -> "ExecutionAction":
        if self.kind is ExecutionActionKind.UPDATE_DISRUPTION_STATUS:
            if (
                self.owner_kind is not ExecutionOwnerKind.SYSTEM
                or self.owner_persona_id is not None
            ):
                raise ValueError("status-update action must be system-owned")
        elif (
            self.owner_kind is not ExecutionOwnerKind.PERSONA
            or self.owner_persona_id != "RL-PERSONA-ALEX"
        ):
            raise ValueError("coordinated actions must be owned by Alex")

        owns_draft = self.kind is ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT
        if owns_draft != (self.draft_artifact_id is not None):
            raise ValueError("only the recovery-request action owns a Draft Artifact")
        return self


class DraftArtifact(FrozenModel):
    artifact_id: str
    action_id: str
    decision_id: str
    artifact_kind: Literal["alpha_recovery_request"] = "alpha_recovery_request"
    created_at: datetime
    sent: Literal[False] = False


class ExecutionAttempt(FrozenModel):
    attempt_id: str
    action_id: str
    decision_id: str
    attempt_number: int
    status: ExecutionStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None


class ExecutionStatusEvent(FrozenModel):
    execution_event_id: str
    action_id: str
    decision_id: str
    sequence_number: int
    from_status: ExecutionStatus | None
    to_status: ExecutionStatus
    attempt_id: str | None = None
    error_code: str | None = None
    occurred_at: datetime


class OutboxProcessingState(FrozenModel):
    event_id: str
    claim_status: OutboxClaimStatus
    processed_at: datetime | None
    attempt_count: int
    last_error: str | None
