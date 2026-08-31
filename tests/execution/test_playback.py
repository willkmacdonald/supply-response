from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from tests.execution.conftest import APPROVED_DECISION_ID, alex_identity

from services.execution.playback import ImmediateClock, PlaybackService
from services.execution.worker import ActionPlanningWorker


EXPECTED = {
    "alpha_expedited_quantity": ("3000", "2800"),
    "dallas_transfer_quantity": ("1500", "1500"),
    "total_response_arranged_supply": ("4500", "4300"),
    "uncovered_part_demand": ("2300", "2500"),
    "response_cost": ("24750", "25000"),
    "protected_customer_orders": ("1", "1"),
    "revenue_protected": ("580000", "580000"),
    "margin_protected": ("203000", "203000"),
    "otif_loss_percentage": ("50", "50"),
    "remaining_alpha_recovery_date": ("unknown", "2026-09-12"),
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


def test_repeated_start_returns_existing_playback(playback_service):
    first = playback_service.start(APPROVED_DECISION_ID, alex_identity())
    second = playback_service.start(APPROVED_DECISION_ID, alex_identity())
    assert second.playback_id == first.playback_id


def test_concurrent_start_returns_one_playback(playback_service):
    barrier = Barrier(2)

    def start():
        barrier.wait()
        return playback_service.start(APPROVED_DECISION_ID, alex_identity())

    with ThreadPoolExecutor(max_workers=2) as executor:
        playbacks = tuple(executor.map(lambda _: start(), range(2)))

    assert len({item.playback_id for item in playbacks}) == 1


def test_playback_completes_an_unsent_alpha_draft(playback_service):
    playback_service.run_to_completion(
        playback_service.start(APPROVED_DECISION_ID, alex_identity()).playback_id,
        clock=ImmediateClock(),
    )
    draft = playback_service.draft(APPROVED_DECISION_ID, "alpha_recovery_request")
    assert draft.subject == "RL-001 recovery-date confirmation request"
    assert "RL-Supplier Alpha" in draft.body
    assert draft.sent is False
