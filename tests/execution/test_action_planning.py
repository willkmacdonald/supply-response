from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from data.domain import CaseStatus
from services.execution.planner import plan_actions
from services.execution.worker import ActionPlanningWorker


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
