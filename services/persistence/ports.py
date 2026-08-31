from types import TracebackType
from typing import Protocol, runtime_checkable

from data.domain import CaseInstance, CasePurpose
from data.domain.analysis import AnalysisVersion
from data.domain.decisions import ApprovalSatisfaction, CaseProjection, Decision
from data.domain.execution import (
    ActionPlanningRequested,
    DraftArtifact,
    ExecutionAction,
    ExecutionAttempt,
    ExecutionStatusEvent,
    OutboxClaim,
    OutboxProcessingState,
    OutcomeObservation,
    Playback,
)
from data.synthetic.rl001 import OperationalSnapshot


@runtime_checkable
class CaseStore(Protocol):
    def create_case(
        self,
        case: CaseInstance,
        snapshot: OperationalSnapshot,
    ) -> None: ...

    def get_case(self, case_id: str) -> CaseInstance: ...

    def save_analysis(self, analysis: AnalysisVersion) -> None: ...

    def get_analysis(self, analysis_id: str) -> AnalysisVersion: ...

    def get_projection(self, case_id: str) -> CaseProjection: ...

    def set_current_decision(self, case_id: str, decision_id: str) -> None: ...

    def mark_rejected(self, case_id: str, decision_id: str) -> None: ...

    def mark_action_planning_complete(self, case_id: str) -> None: ...

    def mark_action_planning_failed(self, case_id: str) -> None: ...

    def save_case_projection(self, case: CaseInstance) -> None: ...

    def list_cases(
        self,
        *,
        purpose: CasePurpose | None = None,
    ) -> tuple[CaseInstance, ...]: ...


class DecisionStore(Protocol):
    def get(self, decision_id: str) -> Decision: ...

    def get_by_idempotency_key(self, idempotency_key: str) -> Decision | None: ...

    def list_for_case(self, case_id: str) -> tuple[Decision, ...]: ...

    def insert(self, decision: Decision) -> None: ...

    def insert_satisfactions(
        self,
        decision_id: str,
        satisfactions: tuple[ApprovalSatisfaction, ...],
    ) -> None: ...

    def list_approval_satisfactions(
        self,
        decision_id: str,
    ) -> tuple[ApprovalSatisfaction, ...]: ...


class ExecutionStore(Protocol):
    def insert_outbox(self, event: ActionPlanningRequested) -> None: ...

    def list_outbox(
        self,
        *,
        decision_id: str,
    ) -> tuple[ActionPlanningRequested, ...]: ...

    def claim_next_outbox(
        self,
        event_type: str,
    ) -> OutboxClaim | None: ...

    def claim_next_unattempted_outbox(
        self,
        event_type: str,
    ) -> OutboxClaim | None: ...

    def claim_outbox_for_decision(
        self,
        event_type: str,
        decision_id: str,
    ) -> OutboxClaim | None: ...

    def validate_claimed_outbox(
        self,
        claim: OutboxClaim,
    ) -> ActionPlanningRequested: ...

    def mark_outbox_processed(self, event_id: str) -> None: ...

    def record_outbox_failure(self, event_id: str, error_code: str) -> None: ...

    def get_outbox_state(self, event_id: str) -> OutboxProcessingState: ...

    def insert_action_if_absent(self, action: ExecutionAction) -> bool: ...

    def get_action(self, action_id: str) -> ExecutionAction: ...

    def list_actions(self, *, decision_id: str) -> tuple[ExecutionAction, ...]: ...

    def get_draft_artifact(self, action_id: str) -> DraftArtifact: ...

    def fill_draft_artifact(self, artifact: DraftArtifact) -> None: ...

    def insert_attempt(self, attempt: ExecutionAttempt) -> None: ...

    def update_attempt(self, attempt: ExecutionAttempt) -> None: ...

    def get_attempt(self, attempt_id: str) -> ExecutionAttempt: ...

    def list_attempts(self, action_id: str) -> tuple[ExecutionAttempt, ...]: ...

    def update_action_projection(self, action: ExecutionAction) -> None: ...

    def append_status_event(self, event: ExecutionStatusEvent) -> None: ...

    def list_status_events(
        self,
        action_id: str,
    ) -> tuple[ExecutionStatusEvent, ...]: ...

    def insert_playback_if_absent(self, playback: Playback) -> bool: ...

    def get_playback(self, playback_id: str) -> Playback: ...

    def get_playback_for_decision(self, decision_id: str) -> Playback | None: ...

    def update_playback(self, playback: Playback) -> None: ...

    def insert_observation(self, observation: OutcomeObservation) -> None: ...

    def list_observations(
        self,
        decision_id: str,
    ) -> tuple[OutcomeObservation, ...]: ...


class UnitOfWork(Protocol):
    cases: CaseStore
    decisions: DecisionStore
    execution: ExecutionStore

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
