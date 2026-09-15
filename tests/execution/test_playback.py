from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local

import pytest

from services.execution.playback import ImmediateClock, PlaybackService
from services.execution.worker import ActionPlanningWorker
from services.persistence.store import (
    ImmutableRecordConflict,
    SqlAlchemyExecutionRepository,
)
from tests.execution.conftest import APPROVED_DECISION_ID, alex_identity

EXPECTED = {
    "uncovered_part_demand": ("2300", "2300"),
    "response_cost": ("24750.00", "24750.00"),
    "revenue_at_risk": ("375000.00", "375000.00"),
    "margin_at_risk": ("125000.00", "125000.00"),
    "otif_loss_percentage": ("50", "50"),
}


@pytest.fixture
def playback_service(planning_context):
    assert ActionPlanningWorker(planning_context.uow_factory).process_next_outbox()
    return PlaybackService(planning_context.uow_factory)


def test_playback_appends_only_the_frozen_simulated_observations(playback_service):
    playback = playback_service.start(APPROVED_DECISION_ID, alex_identity())
    playback_service.run_to_completion(playback.playback_id, clock=ImmediateClock())
    observations = playback_service.observations(APPROVED_DECISION_ID)
    assert {
        o.metric: (o.predicted_value, o.observed_value) for o in observations
    } == EXPECTED
    assert all(o.kind.value == "simulated" and o.synthetic for o in observations)
    assert all(o.source_reference.startswith("Simulated") for o in observations)


def test_repeated_start_returns_existing_playback(playback_service):
    first = playback_service.start(APPROVED_DECISION_ID, alex_identity())
    second = playback_service.start(APPROVED_DECISION_ID, alex_identity())
    assert second.playback_id == first.playback_id


def test_concurrent_start_returns_one_playback(playback_service, monkeypatch):
    insert_boundary = Barrier(2)
    lookup_state = local()
    original_lookup = SqlAlchemyExecutionRepository.get_playback_for_decision

    def synchronized_lookup(repository, decision_id):
        playback = original_lookup(repository, decision_id)
        lookup_state.count = getattr(lookup_state, "count", 0) + 1
        if lookup_state.count == 2 and playback is None:
            insert_boundary.wait()
        return playback

    monkeypatch.setattr(
        SqlAlchemyExecutionRepository,
        "get_playback_for_decision",
        synchronized_lookup,
    )

    def start():
        return playback_service.start(APPROVED_DECISION_ID, alex_identity())

    with ThreadPoolExecutor(max_workers=2) as executor:
        playbacks = tuple(executor.map(lambda _: start(), range(2)))

    assert len({item.playback_id for item in playbacks}) == 1


def test_playback_conflict_does_not_accept_a_divergent_record(
    playback_service,
    planning_context,
):
    canonical = playback_service.start(APPROVED_DECISION_ID, alex_identity())
    divergent = canonical.model_copy(update={"playback_id": "RL-PLAYBACK-DIVERGENT"})

    with (
        planning_context.uow_factory() as uow,
        pytest.raises(ImmutableRecordConflict, match="different Playback"),
    ):
        uow.execution.insert_playback_if_absent(divergent)


def test_playback_completes_an_unsent_alpha_draft(playback_service):
    playback_service.run_to_completion(
        playback_service.start(APPROVED_DECISION_ID, alex_identity()).playback_id,
        clock=ImmediateClock(),
    )
    draft = playback_service.draft(APPROVED_DECISION_ID, "alpha_recovery_request")
    assert draft.subject == "RL-001 supplier communication draft"
    assert "fictional demo" in draft.body.lower()
    assert "RL-CASE-EXECUTION-1" in draft.body
    assert "Combine expedite, transfer, and resequencing" in draft.body
    assert draft.sent is False
