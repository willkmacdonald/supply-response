from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from data.domain import CaseInstance, CasePurpose
from data.domain.analysis import AnalysisVersion
from data.domain.cases import WorkflowVersion
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
from data.domain.finance import FinanceReview
from data.domain.outbound_mail import SupplierEmailDelivery, SupplierEmailRevision
from data.domain.proposals import (
    ProposalSelection,
    ProposalState,
    ProposalToken,
    SelectionReceipt,
)
from data.synthetic.rl001 import OperationalSnapshot

if TYPE_CHECKING:
    from services.persistence.presenter_runs import (
        PresenterRetentionPlan,
        PresenterRetentionResult,
    )

EXECUTION_PROPOSAL_STALE_ERROR = "EXECUTION_PROPOSAL_STALE"


@runtime_checkable
class CaseStore(Protocol):
    def create_presenter_case(
        self,
        case: CaseInstance,
        snapshot: OperationalSnapshot,
        *,
        historical_limit: int = 3,
    ) -> PresenterRetentionResult: ...

    def preview_presenter_retention(
        self,
        *,
        historical_limit: int = 3,
    ) -> PresenterRetentionPlan: ...

    def apply_presenter_retention(
        self,
        plan: PresenterRetentionPlan,
    ) -> PresenterRetentionResult: ...

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


class FinanceReviewStore(Protocol):
    def get_revision(self, review_id: str, revision: int) -> FinanceReview: ...
    def get_latest(self, review_id: str) -> tuple[FinanceReview, int]: ...

    def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> tuple[FinanceReview, int, str] | None: ...

    def append(
        self,
        review: FinanceReview,
        *,
        expected_revision: int | None,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[FinanceReview, int]: ...


class ProposalStore(Protocol):
    def get_state(self, case_id: str) -> ProposalState: ...
    def get_selection(self, selection_id: str) -> ProposalSelection: ...
    def get_selection_for_review(self, review_id: str) -> ProposalSelection: ...
    def list_pending_case_ids(self) -> tuple[str, ...]: ...
    def get_by_idempotency_key(self, key: str) -> SelectionReceipt | None: ...
    def publish(self, receipt: SelectionReceipt) -> ProposalSelection: ...
    def guard_current(
        self, case_id: str, *, expected: ProposalToken
    ) -> ProposalToken: ...

    def withdraw_current(
        self,
        case_id: str,
        *,
        expected: ProposalToken,
        now: datetime,
        operation_id: str,
    ) -> ProposalToken: ...


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
        *,
        workflow_versions: tuple[WorkflowVersion, ...] | None = None,
    ) -> OutboxClaim | None: ...

    def claim_next_unattempted_outbox(
        self,
        event_type: str,
        *,
        workflow_versions: tuple[WorkflowVersion, ...] | None = None,
    ) -> OutboxClaim | None: ...

    def claim_outbox_for_decision(
        self,
        event_type: str,
        decision_id: str,
        *,
        workflow_versions: tuple[WorkflowVersion, ...] | None = None,
    ) -> OutboxClaim | None: ...

    def validate_claimed_outbox(
        self,
        claim: OutboxClaim,
    ) -> ActionPlanningRequested: ...

    def mark_outbox_processed(self, event_id: str) -> None: ...

    def record_outbox_failure(self, event_id: str, error_code: str) -> None: ...

    def record_outbox_failure_if_current(
        self,
        event_id: str,
        *,
        expected: OutboxProcessingState,
        error_code: str,
    ) -> bool: ...

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


class SupplierEmailStore(Protocol):
    def get_current(
        self, decision_id: str
    ) -> tuple[SupplierEmailRevision, SupplierEmailDelivery] | None: ...

    def get_revision(self, email_id: str, revision: int) -> SupplierEmailRevision: ...

    def insert_initial(
        self,
        revision: SupplierEmailRevision,
        delivery: SupplierEmailDelivery,
    ) -> None: ...

    def append_revision(
        self,
        revision: SupplierEmailRevision,
        *,
        expected_revision: int,
    ) -> bool: ...

    def mark_reviewed(
        self,
        revision: SupplierEmailRevision,
        delivery: SupplierEmailDelivery,
        *,
        expected_revision: int,
    ) -> bool: ...


class UnitOfWork(Protocol):
    cases: CaseStore
    decisions: DecisionStore
    execution: ExecutionStore
    finance_reviews: FinanceReviewStore
    mail: SupplierEmailStore
    proposals: ProposalStore

    def __enter__(self) -> UnitOfWork: ...  # noqa: PYI034

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
