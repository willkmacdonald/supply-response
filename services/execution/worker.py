from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from data.domain.decisions import Decision
from data.domain.execution import (
    ALLOWED_TRANSITIONS,
    ExecutionAction,
    ExecutionAttempt,
    ExecutionStatus,
    ExecutionStatusEvent,
)
from services.execution.planner import plan_actions
from services.persistence.ports import UnitOfWork


UnitOfWorkFactory = Callable[[], UnitOfWork]
Planner = Callable[[Decision], tuple[ExecutionAction, ...]]
Clock = Callable[[], datetime]


class IllegalExecutionTransition(RuntimeError):
    """Raised when an action is moved outside the bounded transition graph."""


def error_code(error: Exception) -> str:
    name = type(error).__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


class ActionPlanningWorker:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        planner: Planner = plan_actions,
    ) -> None:
        self._uow_factory = uow_factory
        self._planner = planner

    def process_next_outbox(self) -> bool:
        return self._process_outbox(decision_id=None)

    def process_decision_outbox(self, decision_id: str) -> bool:
        return self._process_outbox(decision_id=decision_id)

    def _process_outbox(self, *, decision_id: str | None) -> bool:
        with self._uow_factory() as uow:
            claim = (
                uow.execution.claim_next_outbox("ActionPlanningRequested")
                if decision_id is None
                else uow.execution.claim_outbox_for_decision(
                    "ActionPlanningRequested",
                    decision_id,
                )
            )
            if claim is None:
                return False
            try:
                uow.execution.validate_claimed_outbox(claim)
                decision = uow.decisions.get(claim.decision_id)
                for action in self._planner(decision):
                    uow.execution.insert_action_if_absent(action)
                uow.execution.mark_outbox_processed(claim.event_id)
                uow.cases.mark_action_planning_complete(decision.case_id)
                uow.commit()
            except Exception as exc:
                uow.rollback()
                with self._uow_factory() as failed_uow:
                    failed_uow.execution.record_outbox_failure(
                        claim.event_id,
                        error_code(exc),
                    )
                    failed_uow.cases.mark_action_planning_failed(claim.case_id)
                    failed_uow.commit()
            return True


class ExecutionService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def create(self, action: ExecutionAction) -> ExecutionAction:
        with self._uow_factory() as uow:
            uow.execution.insert_action_if_absent(action)
            created = uow.execution.get_action(action.action_id)
            uow.commit()
            return created

    @staticmethod
    def _require_transition(
        action: ExecutionAction,
        to_status: ExecutionStatus,
    ) -> None:
        if to_status not in ALLOWED_TRANSITIONS[action.status]:
            raise IllegalExecutionTransition(
                f"illegal execution transition: {action.status.value} -> "
                f"{to_status.value}"
            )

    def _begin_attempt(
        self,
        action_id: str,
        *,
        required_status: ExecutionStatus,
    ) -> ExecutionAttempt:
        with self._uow_factory() as uow:
            action = uow.execution.get_action(action_id)
            if action.status is not required_status:
                self._require_transition(action, ExecutionStatus.IN_PROGRESS)
                raise IllegalExecutionTransition(
                    f"{required_status.value} action required to enter in_progress; "
                    f"current status is {action.status.value}"
                )
            self._require_transition(action, ExecutionStatus.IN_PROGRESS)
            attempts = uow.execution.list_attempts(action_id)
            attempt = ExecutionAttempt(
                attempt_id=f"RL-ATTEMPT-{uuid4()}",
                action_id=action.action_id,
                decision_id=action.decision_id,
                attempt_number=len(attempts) + 1,
                status=ExecutionStatus.IN_PROGRESS,
                started_at=self._clock(),
            )
            changed = action.model_copy(update={"status": ExecutionStatus.IN_PROGRESS})
            event_count = len(uow.execution.list_status_events(action_id))
            uow.execution.insert_attempt(attempt)
            uow.execution.update_action_projection(changed)
            uow.execution.append_status_event(
                self._event(
                    action,
                    ExecutionStatus.IN_PROGRESS,
                    sequence_number=event_count + 1,
                    attempt_id=attempt.attempt_id,
                )
            )
            uow.commit()
            return attempt

    def start(self, action_id: str) -> ExecutionAttempt:
        return self._begin_attempt(
            action_id,
            required_status=ExecutionStatus.PLANNED,
        )

    def retry(self, action_id: str) -> ExecutionAttempt:
        return self._begin_attempt(
            action_id,
            required_status=ExecutionStatus.FAILED,
        )

    def _finish_attempt(
        self,
        action_id: str,
        attempt_id: str,
        to_status: ExecutionStatus,
        *,
        error_code_value: str | None = None,
    ) -> ExecutionAction:
        with self._uow_factory() as uow:
            action = uow.execution.get_action(action_id)
            self._require_transition(action, to_status)
            attempt = uow.execution.get_attempt(attempt_id)
            if (
                attempt.action_id != action_id
                or attempt.status is not ExecutionStatus.IN_PROGRESS
            ):
                raise IllegalExecutionTransition(
                    "transition requires the action's in-progress attempt"
                )
            now = self._clock()
            finished_attempt = attempt.model_copy(
                update={
                    "status": to_status,
                    "completed_at": now,
                    "error_code": error_code_value,
                }
            )
            changed = action.model_copy(update={"status": to_status})
            event_count = len(uow.execution.list_status_events(action_id))
            uow.execution.update_attempt(finished_attempt)
            uow.execution.update_action_projection(changed)
            uow.execution.append_status_event(
                self._event(
                    action,
                    to_status,
                    sequence_number=event_count + 1,
                    attempt_id=attempt_id,
                    error_code_value=error_code_value,
                    occurred_at=now,
                )
            )
            uow.commit()
            return changed

    def complete(self, action_id: str, attempt_id: str) -> ExecutionAction:
        return self._finish_attempt(
            action_id,
            attempt_id,
            ExecutionStatus.COMPLETED,
        )

    def fail(
        self,
        action_id: str,
        attempt_id: str,
        error_code: str,
    ) -> ExecutionAction:
        return self._finish_attempt(
            action_id,
            attempt_id,
            ExecutionStatus.FAILED,
            error_code_value=error_code,
        )

    def cancel(
        self,
        action_id: str,
        attempt_id: str | None = None,
    ) -> ExecutionAction:
        with self._uow_factory() as uow:
            action = uow.execution.get_action(action_id)
            self._require_transition(action, ExecutionStatus.CANCELLED)
            now = self._clock()
            if action.status is ExecutionStatus.IN_PROGRESS:
                attempts = uow.execution.list_attempts(action_id)
                current = attempts[-1] if attempts else None
                if (
                    current is None
                    or current.status is not ExecutionStatus.IN_PROGRESS
                    or (attempt_id is not None and current.attempt_id != attempt_id)
                ):
                    raise IllegalExecutionTransition(
                        "cancellation requires the action's in-progress attempt"
                    )
                uow.execution.update_attempt(
                    current.model_copy(
                        update={
                            "status": ExecutionStatus.CANCELLED,
                            "completed_at": now,
                        }
                    )
                )
                attempt_id = current.attempt_id
            changed = action.model_copy(update={"status": ExecutionStatus.CANCELLED})
            event_count = len(uow.execution.list_status_events(action_id))
            uow.execution.update_action_projection(changed)
            uow.execution.append_status_event(
                self._event(
                    action,
                    ExecutionStatus.CANCELLED,
                    sequence_number=event_count + 1,
                    attempt_id=attempt_id,
                    occurred_at=now,
                )
            )
            uow.commit()
            return changed

    def history(self, action_id: str) -> tuple[ExecutionStatusEvent, ...]:
        with self._uow_factory() as uow:
            return uow.execution.list_status_events(action_id)

    def attempts(self, action_id: str) -> tuple[ExecutionAttempt, ...]:
        with self._uow_factory() as uow:
            return uow.execution.list_attempts(action_id)

    def _event(
        self,
        action: ExecutionAction,
        to_status: ExecutionStatus,
        *,
        sequence_number: int,
        attempt_id: str | None = None,
        error_code_value: str | None = None,
        occurred_at: datetime | None = None,
    ) -> ExecutionStatusEvent:
        return ExecutionStatusEvent(
            execution_event_id=f"RL-EXECUTION-EVENT-{uuid4()}",
            action_id=action.action_id,
            decision_id=action.decision_id,
            sequence_number=sequence_number,
            from_status=action.status,
            to_status=to_status,
            attempt_id=attempt_id,
            error_code=error_code_value,
            occurred_at=occurred_at or self._clock(),
        )
