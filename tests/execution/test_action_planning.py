from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select, update

from data.domain import CaseStatus
from data.domain.decisions import DecisionKind
from data.domain.execution import ExecutionActionKind
from services.execution.planner import plan_actions
from services.execution.worker import ActionPlanningWorker
from services.persistence.tables import decisions, outbox_events

EXPECTED = {
    "RL-OPTION-EXPEDITE": (
        "prepare_alpha_recovery_draft",
        "coordinate_alpha_expedited_partial",
        "update_disruption_status",
    ),
    "RL-OPTION-TRANSFER": (
        "prepare_alpha_recovery_draft",
        "transfer_dallas_to_chicago",
        "update_disruption_status",
    ),
    "RL-OPTION-RESEQUENCE": (
        "prepare_alpha_recovery_draft",
        "resequence_priority_production",
        "update_disruption_status",
    ),
    "RL-OPTION-COMBINED": tuple(kind.value for kind in ExecutionActionKind),
}


def decision_for_option(planning_context, option_id):
    option = next(
        option
        for option in planning_context.analysis.response_options
        if option.option_id == option_id
    )
    return planning_context.decision.model_copy(
        update={"selected_option_id": option_id, "selected_option": option}
    )


@pytest.mark.parametrize("option_id, expected_kinds", EXPECTED.items())
def test_approved_option_creates_only_its_applicable_actions(
    planning_context,
    option_id,
    expected_kinds,
):
    decision = decision_for_option(planning_context, option_id)

    actions = plan_actions(decision, planning_context.analysis)

    assert tuple(action.kind for action in actions) == expected_kinds
    assert all(action.decision_id == decision.decision_id for action in actions)
    assert actions[0].kind == "prepare_alpha_recovery_draft"
    assert actions[-1].kind == "update_disruption_status"
    assert actions[0].execution_mode == "communication_preparation"
    assert all(action.purpose and action.expected_result for action in actions)
    assert all(action.execution_mode == "simulation" for action in actions[1:])
    assert all(action.owner_persona_id == "RL-PERSONA-ALEX" for action in actions[:-1])
    assert actions[-1].owner_persona_id is None


@pytest.mark.parametrize(
    "option_id, action_kind, expected_text",
    (
        (
            "RL-OPTION-EXPEDITE",
            "coordinate_alpha_expedited_partial",
            ("3,000", "September 6, 2026", "$7.50 per unit"),
        ),
        (
            "RL-OPTION-TRANSFER",
            "transfer_dallas_to_chicago",
            ("1,500", "Dallas", "Chicago", "September 5, 2026"),
        ),
        (
            "RL-OPTION-RESEQUENCE",
            "resequence_priority_production",
            ("RL-CO-DEMO-2",),
        ),
    ),
)
def test_option_action_text_uses_the_approved_snapshot(
    planning_context,
    option_id,
    action_kind,
    expected_text,
):
    decision = decision_for_option(planning_context, option_id)

    action = next(
        action
        for action in plan_actions(decision, planning_context.analysis)
        if action.kind == action_kind
    )
    display_text = f"{action.purpose} {action.expected_result}"

    assert all(value in display_text for value in expected_text)


def test_action_ids_are_deterministic_for_reprocessing(planning_context):
    first = plan_actions(planning_context.decision, planning_context.analysis)
    second = plan_actions(planning_context.decision, planning_context.analysis)

    assert [action.action_id for action in first] == [
        action.action_id for action in second
    ]
    assert len({action.action_id for action in first}) == 5


def test_draft_artifact_id_is_stable_across_idempotent_reprocessing(
    planning_context,
):
    planned = plan_actions(planning_context.decision, planning_context.analysis)
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

    def fail_planning(decision, analysis):
        del decision, analysis
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
    def conflicting_plan(decision, analysis):
        actions = plan_actions(decision, analysis)
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


@pytest.mark.parametrize(
    "invalid_decision",
    (
        lambda context: decision_for_option(context, "RL-OPTION-NO-MITIGATION"),
        lambda context: decision_for_option(context, "RL-OPTION-BETA"),
        lambda context: context.decision.model_copy(
            update={"kind": DecisionKind.REJECTED}
        ),
        lambda context: context.decision.model_copy(
            update={"selected_option_id": None, "selected_option": None}
        ),
    ),
    ids=("baseline", "alternate-supplier", "rejected", "absent-option"),
)
def test_invalid_decisions_are_not_planned_or_inserted(
    planning_context,
    invalid_decision,
):
    with pytest.raises(ValueError):
        plan_actions(invalid_decision(planning_context), planning_context.analysis)

    with planning_context.uow_factory() as uow:
        assert (
            uow.execution.list_actions(
                decision_id=planning_context.decision.decision_id
            )
            == ()
        )


@pytest.mark.parametrize("mismatch", ("analysis_id", "material_hash"))
def test_decision_analysis_mismatch_is_not_planned_or_inserted(
    planning_context,
    mismatch,
):
    analysis = (
        planning_context.analysis.model_copy(
            update={"analysis_id": "RL-ANALYSIS-OTHER"}
        )
        if mismatch == "analysis_id"
        else planning_context.analysis.model_copy(update={"material_hash": "different"})
    )

    with pytest.raises(ValueError):
        plan_actions(planning_context.decision, analysis)

    with planning_context.uow_factory() as uow:
        assert (
            uow.execution.list_actions(
                decision_id=planning_context.decision.decision_id
            )
            == ()
        )
