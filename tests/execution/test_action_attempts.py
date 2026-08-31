import pytest

from data.domain.execution import ExecutionStatus
from services.execution.worker import IllegalExecutionTransition


def test_failed_action_retries_without_rewriting_history(
    execution_service,
    planned_action,
):
    action = execution_service.create(planned_action)
    first = execution_service.start(action.action_id)
    failed = execution_service.fail(
        action.action_id,
        first.attempt_id,
        "RL-TEST-FAILURE",
    )
    retry = execution_service.retry(action.action_id)
    completed = execution_service.complete(action.action_id, retry.attempt_id)

    assert completed.status.value == "completed"
    assert [
        event.to_status.value for event in execution_service.history(action.action_id)
    ] == ["planned", "in_progress", "failed", "in_progress", "completed"]
    assert first.attempt_id != retry.attempt_id
    attempts = execution_service.attempts(action.action_id)
    assert [(attempt.attempt_number, attempt.status.value) for attempt in attempts] == [
        (1, "failed"),
        (2, "completed"),
    ]
    assert attempts[0].error_code == "RL-TEST-FAILURE"
    assert failed.status is ExecutionStatus.FAILED


def test_only_declared_status_transitions_are_allowed(
    execution_service,
    planned_action,
):
    action = execution_service.create(planned_action)

    with pytest.raises(IllegalExecutionTransition, match="planned -> completed"):
        execution_service.complete(action.action_id, "RL-ATTEMPT-MISSING")

    cancelled = execution_service.cancel(action.action_id)
    assert cancelled.status is ExecutionStatus.CANCELLED
    with pytest.raises(IllegalExecutionTransition, match="cancelled -> in_progress"):
        execution_service.retry(action.action_id)
