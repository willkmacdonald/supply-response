from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from data.domain.execution import ObservationKind, OutcomeObservation
from services.execution import playback as playback_module
from services.execution.playback import (
    ImmediateClock,
    PlaybackAuthorizationError,
    PlaybackService,
)
from services.execution.worker import ActionPlanningWorker, UnitOfWorkFactory
from services.persistence.sqlite import sqlite_store
from services.persistence.tables import (
    execution_events,
    outcome_observations,
    playbacks,
)
from tests.execution.conftest import APPROVED_DECISION_ID, alex_identity


def _service(planning_context) -> PlaybackService:
    assert ActionPlanningWorker(planning_context.uow_factory).process_next_outbox()
    return PlaybackService(planning_context.uow_factory)


def _observation(**updates) -> OutcomeObservation:
    values = {
        "observation_id": "RL-OBSERVATION-SAFETY",
        "case_id": "RL-CASE-EXECUTION-1",
        "decision_id": APPROVED_DECISION_ID,
        "playback_id": "RL-PLAYBACK-SAFETY",
        "action_id": None,
        "metric": "response_cost",
        "observed_value": "25000",
        "unit": "USD",
        "predicted_value": "24750",
        "scenario_effective_time": datetime.fromisoformat("2026-09-01T09:00:00-05:00"),
        "scenario_timezone": "America/Chicago",
        "recorded_at": datetime(2026, 9, 1, 14, 0, tzinfo=UTC),
        "source_reference": "RL-001 deterministic playback",
        "kind": ObservationKind.SIMULATED,
        "synthetic": True,
    }
    values.update(updates)
    return OutcomeObservation.model_validate(values)


def test_playback_schedule_uses_the_planned_actions_at_two_second_offsets(
    planning_context,
):
    _service(planning_context)
    with planning_context.uow_factory() as uow:
        actions = uow.execution.list_actions(decision_id=APPROVED_DECISION_ID)
    assert hasattr(playback_module, "playback_steps")
    assert [
        (step.offset_seconds, step.action_kind)
        for step in playback_module.playback_steps(actions)
    ] == [(index * 2, action.kind.value) for index, action in enumerate(actions)]


def test_actual_observation_cannot_claim_synthetic_provenance():
    with pytest.raises(ValidationError, match="actual observation cannot be synthetic"):
        _observation(kind=ObservationKind.ACTUAL, synthetic=True)


def test_observation_display_label_is_derived_and_not_caller_controlled():
    observation = _observation()
    assert observation.display_label == "Simulated"
    with pytest.raises(ValidationError, match="display_label"):
        _observation(display_label="Actual")


def test_observation_provenance_is_frozen():
    observation = _observation()
    with pytest.raises(ValidationError, match="frozen"):
        observation.synthetic = False


def test_playback_requires_the_authorized_alex_identity(planning_context):
    service = _service(planning_context)
    with pytest.raises(PlaybackAuthorizationError):
        service.start(
            APPROVED_DECISION_ID,
            alex_identity(effective_roles=("material_planner",)),
        )


def test_rerunning_completed_playback_does_not_rewrite_history(planning_context):
    service = _service(planning_context)
    playback = service.start(APPROVED_DECISION_ID, alex_identity())
    service.run_to_completion(playback.playback_id, clock=ImmediateClock())
    with planning_context.uow_factory() as uow:
        before = {
            action.action_id: uow.execution.list_status_events(action.action_id)
            for action in uow.execution.list_actions(decision_id=APPROVED_DECISION_ID)
        }

    service.run_to_completion(playback.playback_id, clock=ImmediateClock())

    with planning_context.uow_factory() as uow:
        after = {
            action.action_id: uow.execution.list_status_events(action.action_id)
            for action in uow.execution.list_actions(decision_id=APPROVED_DECISION_ID)
        }
    assert after == before
    assert all(
        [event.to_status.value for event in history]
        == ["planned", "in_progress", "completed"]
        for history in after.values()
    )
    assert len(service.observations(APPROVED_DECISION_ID)) == 5


def test_storage_rejects_actual_synthetic_observation(planning_context):
    service = _service(planning_context)
    playback = service.start(APPROVED_DECISION_ID, alex_identity())
    service.run_to_completion(playback.playback_id, clock=ImmediateClock())
    row = _observation(
        observation_id="RL-OBSERVATION-INVALID",
        playback_id=playback.playback_id,
    ).model_dump(mode="python")
    row["kind"] = "actual"
    row["synthetic"] = True
    row["payload_json"] = "{}"

    with (
        pytest.raises(IntegrityError),
        planning_context.store.engine.begin() as connection,
    ):
        connection.execute(insert(outcome_observations).values(**row))


def test_restart_between_approval_and_playback_retains_append_only_history(
    planning_context,
):
    database_url = str(planning_context.store.engine.url)
    planning_context.store.engine.dispose()
    restarted_store = sqlite_store(database_url)
    restarted_factory = cast(UnitOfWorkFactory, restarted_store.uow_factory)
    assert ActionPlanningWorker(restarted_factory).process_next_outbox()
    service = PlaybackService(restarted_factory)
    playback = service.start(APPROVED_DECISION_ID, alex_identity())
    service.run_to_completion(playback.playback_id, clock=ImmediateClock())
    restarted_store.engine.dispose()

    replacement = sqlite_store(database_url)
    replacement_factory = cast(UnitOfWorkFactory, replacement.uow_factory)
    restarted = PlaybackService(replacement_factory)
    observations = restarted.observations(APPROVED_DECISION_ID)
    assert len(observations) == 5
    assert {item.decision_id for item in observations} == {APPROVED_DECISION_ID}
    with replacement.engine.connect() as connection:
        assert set(
            connection.execute(select(outcome_observations.c.decision_id)).scalars()
        ) == {APPROVED_DECISION_ID}
        assert (
            connection.scalar(select(func.count()).select_from(execution_events)) == 15
        )
        assert (
            connection.scalar(
                select(playbacks.c.decision_id).where(
                    playbacks.c.playback_id == playback.playback_id
                )
            )
            == APPROVED_DECISION_ID
        )

    restarted.run_to_completion(playback.playback_id, clock=ImmediateClock())
    with replacement.engine.connect() as connection:
        assert (
            connection.scalar(select(func.count()).select_from(execution_events)) == 15
        )
        assert (
            connection.scalar(select(func.count()).select_from(outcome_observations))
            == 5
        )
