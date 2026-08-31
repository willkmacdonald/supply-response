from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select, update

from data.domain import CaseStatus
from services.execution.planner import plan_actions
from services.execution.worker import ActionPlanningWorker
from services.persistence.tables import decisions, outbox_events


def test_combined_decision_creates_exactly_five_bounded_actions(
    approved_combined_decision,
):
    actions = plan_actions(approved_combined_decision)
    assert [(a.kind, a.owner_persona_id) for a in actions] == [
        ("prepare_alpha_recovery_draft", "RL-PERSONA-ALEX"),
        ("coordinate_alpha_expedited_partial", "RL-PERSONA-ALEX"),
        ("transfer_dallas_to_chicago", "RL-PERSONA-ALEX"),
        ("resequence_priority_production", "RL-PERSONA-ALEX"),
        ("update_disruption_status", None),
    ]
    assert all(a.decision_id == approved_combined_decision.decision_id for a in actions)
    assert not any("beta" in a.kind for a in actions)


def test_action_ids_are_deterministic_for_reprocessing(approved_combined_decision):
    first = plan_actions(approved_combined_decision)
    second = plan_actions(approved_combined_decision)

    assert [action.action_id for action in first] == [
        action.action_id for action in second
    ]
    assert len({action.action_id for action in first}) == 5


def test_draft_artifact_id_is_stable_across_idempotent_reprocessing(
    planning_context,
):
    planned = plan_actions(planning_context.decision)
    draft_action = planned[0]

    with planning_context.uow_factory() as uow:
        assert all(uow.execution.insert_action_if_absent(action) for action in planned)
        first = uow.execution.get_draft_artifact(draft_action.action_id)
        uow.commit()

    with planning_context.uow_factory() as uow:
        assert not any(
            uow.execution.insert_action_if_absent(action) for action in planned
        )
        reprocessed = uow.execution.get_draft_artifact(draft_action.action_id)
        uow.commit()

    assert first == reprocessed
    assert first.artifact_id == draft_action.draft_artifact_id


def test_two_workers_claim_one_event_and_create_actions_once(planning_context):
    barrier = Barrier(2)

    def process() -> bool:
        barrier.wait()
        return ActionPlanningWorker(planning_context.uow_factory).process_next_outbox()

    with ThreadPoolExecutor(max_workers=2) as executor:
        processed = tuple(executor.map(lambda _: process(), range(2)))

    assert sorted(processed) == [False, True]
    with planning_context.uow_factory() as uow:
        actions = uow.execution.list_actions(
            decision_id=planning_context.decision.decision_id
        )
        projection = uow.cases.get_projection(planning_context.decision.case_id)
    assert len(actions) == 5
    assert projection.case.status is CaseStatus.EXECUTING


def test_recovery_request_is_a_permanently_unsent_draft(planning_context):
    assert (
        ActionPlanningWorker(planning_context.uow_factory).process_next_outbox() is True
    )

    with planning_context.uow_factory() as uow:
        action = next(
            item
            for item in uow.execution.list_actions(
                decision_id=planning_context.decision.decision_id
            )
            if item.kind == "prepare_alpha_recovery_draft"
        )
        artifact = uow.execution.get_draft_artifact(action.action_id)

    assert artifact.artifact_kind == "alpha_recovery_request"
    assert artifact.sent is False


def test_planning_failure_updates_only_failure_state_and_case_projection(
    planning_context,
):
    immutable_decision = planning_context.decision

    def fail_planning(decision):
        del decision
        raise RuntimeError("sensitive planning details")

    worker = ActionPlanningWorker(
        planning_context.uow_factory,
        planner=fail_planning,
    )

    assert worker.process_next_outbox() is True

    with planning_context.uow_factory() as uow:
        assert uow.decisions.get(immutable_decision.decision_id) == immutable_decision
        event = uow.execution.list_outbox(decision_id=immutable_decision.decision_id)[0]
        state = uow.execution.get_outbox_state(event.event_id)
        projection = uow.cases.get_projection(immutable_decision.case_id)
        actions = uow.execution.list_actions(decision_id=immutable_decision.decision_id)
    assert state.attempt_count == 1
    assert state.last_error == "RUNTIME_ERROR"
    assert projection.display_status == "Approved — action planning failed"
    assert projection.case.status is CaseStatus.ACTION_PLANNING
    assert actions == ()


@pytest.mark.parametrize("corrupt_record", ["outbox", "decision"])
def test_claimed_validation_failure_is_durably_projected(
    planning_context,
    corrupt_record,
):
    immutable_decision = planning_context.decision
    with planning_context.uow_factory() as uow:
        event_id = uow.execution.list_outbox(
            decision_id=immutable_decision.decision_id
        )[0].event_id

    target = outbox_events if corrupt_record == "outbox" else decisions
    target_id = (
        event_id if corrupt_record == "outbox" else immutable_decision.decision_id
    )
    id_column = (
        target.c.event_id if corrupt_record == "outbox" else target.c.decision_id
    )
    with planning_context.store.engine.begin() as connection:
        connection.execute(
            update(target).where(id_column == target_id).values(payload_json="{")
        )

    assert (
        ActionPlanningWorker(planning_context.uow_factory).process_next_outbox() is True
    )

    with planning_context.uow_factory() as uow:
        state = uow.execution.get_outbox_state(event_id)
        projection = uow.cases.get_projection(immutable_decision.case_id)
        actions = uow.execution.list_actions(decision_id=immutable_decision.decision_id)
    with planning_context.store.engine.connect() as connection:
        persisted_corruption = connection.scalar(
            select(target.c.payload_json).where(id_column == target_id)
        )

    assert state.attempt_count == 1
    assert state.last_error == "PERSISTENCE_INTEGRITY_ERROR"
    assert projection.display_status == "Approved — action planning failed"
    assert projection.case.status is CaseStatus.ACTION_PLANNING
    assert actions == ()
    assert persisted_corruption == "{"


def test_failure_after_first_action_insert_rolls_back_partial_plan(planning_context):
    def conflicting_plan(decision):
        actions = plan_actions(decision)
        conflicting_second = actions[1].model_copy(
            update={"action_id": actions[0].action_id}
        )
        return actions[0], conflicting_second

    worker = ActionPlanningWorker(
        planning_context.uow_factory,
        planner=conflicting_plan,
    )

    assert worker.process_next_outbox() is True

    with planning_context.uow_factory() as uow:
        event = uow.execution.list_outbox(
            decision_id=planning_context.decision.decision_id
        )[0]
        state = uow.execution.get_outbox_state(event.event_id)
        assert (
            uow.execution.list_actions(
                decision_id=planning_context.decision.decision_id
            )
            == ()
        )
    assert state.attempt_count == 1
    assert state.last_error == "IMMUTABLE_RECORD_CONFLICT"

    assert (
        ActionPlanningWorker(planning_context.uow_factory).process_next_outbox() is True
    )
    with planning_context.uow_factory() as uow:
        assert (
            len(
                uow.execution.list_actions(
                    decision_id=planning_context.decision.decision_id
                )
            )
            == 5
        )
