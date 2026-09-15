import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, local
from typing import Any, cast

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError

from data.domain.decisions import DecisionKind
from data.domain.execution import PlaybackStatus
from services.execution import playback as playback_module
from services.execution.currentness import ExecutionProposalStale
from services.execution.playback import (
    ImmediateClock,
    PlaybackService,
    PlaybackStateError,
)
from services.execution.worker import ActionPlanningWorker, ExecutionService
from services.finance.contracts import (
    FinalizeProposalCommand,
    ResolveFinanceCommand,
    SubmitProposalCommand,
)
from services.finance.decisions import FinanceDecisionService
from services.finance.service import FinanceService
from services.persistence.store import (
    ImmutableRecordConflict,
    SqlAlchemyExecutionRepository,
    serialize_model,
)
from services.persistence.tables import metadata, playbacks
from tests.finance.test_finance_final_decision import final_ctx  # noqa: F401


def prepare_context(context, option_id):
    context.clock = ImmediateClock(context.analysis.created_at + timedelta(hours=1))

    def tick():
        now = context.clock.now()
        context.clock.wait_until(now + timedelta(seconds=1))
        return now

    context.finance = FinanceService(
        context.store.uow_factory, actors=context.actors, clock=tick
    )
    selected = context.finance.submit(
        SubmitProposalCommand(
            case_id=context.case.case_id,
            expected=state(context).token,
            option_id=option_id,
            idempotency_key=f"playback-submit-{option_id}",
        ),
        context.alex,
    )
    current = state(context)
    if selected.review is not None:
        assert current.review_revision is not None
        context.finance.resolve(
            ResolveFinanceCommand(
                review_id=selected.review.review_id,
                expected=current.token,
                expected_review_revision=current.review_revision,
                approved=True,
                reason=None,
                idempotency_key=f"playback-approve-{option_id}",
            ),
            context.taylor,
        )
    context.decision = FinanceDecisionService(
        context.store.uow_factory, actors=context.actors, clock=tick
    ).finalize(
        FinalizeProposalCommand(
            case_id=context.case.case_id,
            expected=state(context).token,
            kind=DecisionKind.APPROVED,
            idempotency_key="playback-finalize",
        ),
        context.alex,
    )
    assert ActionPlanningWorker(context.store.uow_factory).process_next_outbox()
    context.service = PlaybackService(context.store.uow_factory, clock=context.clock)
    return context


@pytest.fixture
def ctx(request):
    return prepare_context(request.getfixturevalue("final_ctx"), "RL-OPTION-COMBINED")


@pytest.fixture(
    params=(
        "RL-OPTION-EXPEDITE",
        "RL-OPTION-TRANSFER",
        "RL-OPTION-RESEQUENCE",
        "RL-OPTION-COMBINED",
    )
)
def option_ctx(request):
    return prepare_context(request.getfixturevalue("final_ctx"), request.param)


def state(ctx):
    with ctx.store.uow_factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)


def rows(ctx):
    with ctx.store.engine.connect() as connection:
        return {
            table.name: tuple(
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            )
            for table in metadata.sorted_tables
        }


def actions(ctx):
    with ctx.store.uow_factory() as uow:
        return uow.execution.list_actions(decision_id=ctx.decision.decision_id)


def start(ctx):
    return ctx.service.start(ctx.decision.decision_id, ctx.alex)


def replace(ctx):
    return ctx.finance.submit(
        SubmitProposalCommand(
            case_id=ctx.case.case_id,
            expected=state(ctx).token,
            option_id="RL-OPTION-TRANSFER",
            idempotency_key="replace-playback",
        ),
        ctx.alex,
    )


def complete_actions(ctx):
    execution = ExecutionService(ctx.store.uow_factory, clock=ctx.clock.now)
    for action in actions(ctx):
        attempt = execution.start(action.action_id)
        if action.draft_artifact_id is not None:
            ctx.service._fill_draft(action)
        execution.complete(action.action_id, attempt.attempt_id)


def unchanged_except(before, after, names):
    for name in before.keys() - set(names):
        assert after[name] == before[name], name


def invoke(ctx, operation, playback, original_actions):
    if operation == "start":
        return start(ctx)
    if operation == "fill":
        return ctx.service._fill_draft(
            next(action for action in original_actions if action.draft_artifact_id)
        )
    return ctx.service._record_completion(playback, original_actions, ctx.clock)


EXPECTED_ACTION_KINDS = {
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
    "RL-OPTION-COMBINED": (
        "prepare_alpha_recovery_draft",
        "coordinate_alpha_expedited_partial",
        "transfer_dallas_to_chicago",
        "resequence_priority_production",
        "update_disruption_status",
    ),
}


def test_playback_completes_exact_option_plan_with_predicted_simulated_results(
    option_ctx,
):
    planned = actions(option_ctx)
    assert (
        tuple(action.kind.value for action in planned)
        == EXPECTED_ACTION_KINDS[option_ctx.decision.selected_option_id]
    )

    completed = option_ctx.service.run_to_completion(
        start(option_ctx).playback_id,
        clock=option_ctx.clock,
    )

    assert completed.status is PlaybackStatus.COMPLETED
    assert all(action.status.value == "completed" for action in actions(option_ctx))
    predicted = option_ctx.decision.selected_option.predicted
    assert predicted is not None
    expected = {
        "uncovered_part_demand": (str(predicted.uncovered_part_demand), "units"),
        "response_cost": (str(predicted.response_cost), "USD"),
        "revenue_at_risk": (str(predicted.revenue_at_risk), "USD"),
        "margin_at_risk": (str(predicted.margin_at_risk), "USD"),
        "otif_loss_percentage": (str(predicted.otif_loss_percentage), "percent"),
    }
    observations = option_ctx.service.observations(option_ctx.decision.decision_id)
    assert {
        item.metric: (item.observed_value, item.unit) for item in observations
    } == expected
    assert all(
        item.predicted_value == item.observed_value
        and item.source_reference.startswith("Simulated")
        and item.synthetic
        and item.kind.value == "simulated"
        for item in observations
    )
    metrics = {item.metric for item in observations}
    if option_ctx.decision.selected_option_id == "RL-OPTION-TRANSFER":
        assert "alpha_expedited_quantity" not in metrics
    if option_ctx.decision.selected_option_id == "RL-OPTION-EXPEDITE":
        assert "dallas_transfer_quantity" not in metrics
    if option_ctx.decision.selected_option_id == "RL-OPTION-RESEQUENCE":
        assert not {"alpha_expedited_quantity", "dallas_transfer_quantity"} & metrics

    draft = option_ctx.service.draft(
        option_ctx.decision.decision_id, "alpha_recovery_request"
    )
    assert draft.sent is False
    assert "fictional demo" in draft.body.lower()
    assert option_ctx.case.case_id in draft.body
    if option_ctx.decision.selected_option_id == "RL-OPTION-TRANSFER":
        assert "approved transfer and production resequencing response" in draft.body
        assert "supplier shipment was ordered" not in draft.body.lower()


@pytest.mark.parametrize("operation", ("start", "fill", "complete"))
def test_each_playback_write_rejects_stale_approval_without_any_rows(ctx, operation):
    playback = None if operation == "start" else start(ctx)
    original = actions(ctx)
    if operation == "complete":
        complete_actions(ctx)
    replace(ctx)
    before = rows(ctx)
    with pytest.raises(ExecutionProposalStale):
        invoke(ctx, operation, playback, original)
    assert rows(ctx) == before


@pytest.mark.parametrize("operation", ("start", "fill", "complete"))
def test_each_playback_write_commits_one_fresh_guard(ctx, operation):
    playback = None if operation == "start" else start(ctx)
    original = actions(ctx)
    if operation == "complete":
        complete_actions(ctx)
    before, token = rows(ctx), state(ctx).token
    result = invoke(ctx, operation, playback, original)
    after = rows(ctx)
    assert state(ctx).token == token.model_copy(
        update={"generation": token.generation + 1}
    )
    allowed = (
        {"case_projection", "playbacks"}
        if operation == "start"
        else {"case_projection", "draft_artifacts"}
        if operation == "fill"
        else {"case_projection", "playbacks", "outcome_observations"}
    )
    unchanged_except(before, after, allowed)
    if operation == "complete":
        assert result.status is PlaybackStatus.COMPLETED
        observations = ctx.service.observations(ctx.decision.decision_id)
        assert len(observations) == 5
        assert all(
            item.synthetic and item.kind.value == "simulated" for item in observations
        )
        assert {item.action_id for item in observations} <= {
            action.action_id for action in original
        }


@pytest.mark.parametrize("operation", ("start", "fill", "complete"))
def test_failure_after_guard_rolls_back_playback_transaction(
    ctx, monkeypatch, operation
):
    playback = None if operation == "start" else start(ctx)
    original = actions(ctx)
    if operation == "complete":
        complete_actions(ctx)
    before, real = rows(ctx), playback_module.guard_execution_current
    injected = RuntimeError("after playback guard")

    def guard(uow, decision_id):
        real(uow, decision_id)
        raise injected

    monkeypatch.setattr(playback_module, "guard_execution_current", guard)
    with pytest.raises(RuntimeError) as caught:
        invoke(ctx, operation, playback, original)
    assert caught.value is injected
    assert rows(ctx) == before


def test_exact_start_and_filled_draft_history_need_no_guard_clock_or_commit(
    ctx, monkeypatch
):
    playback = start(ctx)
    draft_action = next(action for action in actions(ctx) if action.draft_artifact_id)
    ctx.service._fill_draft(draft_action)
    replace(ctx)
    before = rows(ctx)

    def forbidden(*args, **kwargs):
        raise AssertionError("historical receipt must not advance")

    monkeypatch.setattr(playback_module, "guard_execution_current", forbidden)
    monkeypatch.setattr(ctx.clock, "now", forbidden)
    with ctx.store.uow_factory() as uow:
        monkeypatch.setattr(type(uow), "commit", forbidden)
    assert start(ctx) == playback
    ctx.service._fill_draft(draft_action)
    assert rows(ctx) == before


def test_divergent_filled_draft_history_remains_immutable_when_stale(ctx, monkeypatch):
    draft_action = next(action for action in actions(ctx) if action.draft_artifact_id)
    with ctx.store.uow_factory() as uow:
        shell = uow.execution.get_draft_artifact(draft_action.action_id)
        different = shell.model_copy(
            update={
                "subject": "Earlier immutable subject",
                "body": "Earlier immutable simulated content; never sent.",
            }
        )
        uow.execution.fill_draft_artifact(different)
        uow.commit()
    replace(ctx)
    before = rows(ctx)

    def forbidden(*args, **kwargs):
        raise AssertionError("filled history conflict must precede guard")

    monkeypatch.setattr(playback_module, "guard_execution_current", forbidden)
    with pytest.raises(ImmutableRecordConflict, match="insert-only"):
        ctx.service._fill_draft(draft_action)
    assert rows(ctx) == before


def test_terminal_conflict_rolls_back_tentative_observations_and_guard(
    ctx, monkeypatch
):
    playback, original = start(ctx), actions(ctx)
    complete_actions(ctx)
    before, witnessed = rows(ctx), []
    injected = ImmutableRecordConflict("Playback already has a terminal result")

    def lose(repository, completed):
        pending = repository.list_observations(ctx.decision.decision_id)
        witnessed.extend(pending)
        assert len(pending) == 5
        assert completed.playback_id == playback.playback_id
        assert completed.status is PlaybackStatus.COMPLETED
        raise injected

    monkeypatch.setattr(SqlAlchemyExecutionRepository, "update_playback", lose)
    with pytest.raises(ImmutableRecordConflict) as caught:
        ctx.service._record_completion(playback, original, ctx.clock)
    assert caught.value is injected
    assert len(witnessed) == 5
    assert rows(ctx) == before


def test_failed_playback_remains_failed_and_cleanup_is_target_only(ctx):
    playback, original = start(ctx), actions(ctx)
    replace(ctx)
    before = rows(ctx)
    failed = ctx.service.record_failure(playback.playback_id)
    after = rows(ctx)
    unchanged_except(before, after, {"playbacks"})
    assert failed.status is PlaybackStatus.FAILED
    assert ctx.service._record_completion(playback, original, ctx.clock) == failed
    assert ctx.service.run_to_completion(playback.playback_id) == failed
    assert ctx.service.record_failure(playback.playback_id) == failed
    assert rows(ctx) == after


@pytest.mark.parametrize(
    "bad", ("unfinished", "missing", "duplicate", "foreign-id", "extra-persisted")
)
def test_completion_requires_exact_completed_persisted_action_set(ctx, bad):
    playback, original = start(ctx), actions(ctx)
    if bad == "extra-persisted":
        extra = original[1].model_copy(
            update={"action_id": "RL-ACTION-EXTRA-PERSISTED"}
        )
        ExecutionService(ctx.store.uow_factory, clock=ctx.clock.now).create(extra)
    if bad != "unfinished":
        complete_actions(ctx)
    supplied = original
    if bad == "missing":
        supplied = original[:-1]
    elif bad == "duplicate":
        supplied = (*original[:-1], original[0])
    elif bad == "foreign-id":
        supplied = (
            original[0].model_copy(update={"action_id": "RL-ACTION-OTHER"}),
            *original[1:],
        )
    before = rows(ctx)
    with pytest.raises(PlaybackStateError):
        ctx.service._record_completion(playback, supplied, ctx.clock)
    assert rows(ctx) == before


def test_completed_receipt_remains_readable_after_replacement(ctx, monkeypatch):
    playback = start(ctx)
    completed = ctx.service.run_to_completion(playback.playback_id, clock=ctx.clock)
    original = actions(ctx)
    replace(ctx)
    before = rows(ctx)

    def forbidden(*args, **kwargs):
        raise AssertionError("completed receipt must not guard or read clock")

    monkeypatch.setattr(playback_module, "guard_execution_current", forbidden)
    monkeypatch.setattr(ctx.clock, "now", forbidden)
    assert ctx.service._record_completion(playback, original, ctx.clock) == completed
    assert ctx.service.run_to_completion(playback.playback_id) == completed
    assert rows(ctx) == before


def test_completion_and_historical_failure_have_one_terminal_winner(ctx, monkeypatch):
    playback, original = start(ctx), actions(ctx)
    complete_actions(ctx)
    before, token = rows(ctx), state(ctx).token
    barrier, thread_state, crossed = Barrier(2, timeout=5), local(), set()
    real_get = SqlAlchemyExecutionRepository.get_playback

    def synchronized_get(repository, playback_id):
        value = real_get(repository, playback_id)
        if getattr(thread_state, "first", False):
            thread_state.first = False
            crossed.add(id(repository._connection))
            barrier.wait()
        return value

    monkeypatch.setattr(SqlAlchemyExecutionRepository, "get_playback", synchronized_get)

    def run(call):
        thread_state.first = True
        try:
            return ("success", call())
        except ImmutableRecordConflict as error:
            return ("conflict", error)
        except OperationalError as error:
            code = getattr(error.orig, "sqlite_errorcode", None)
            if code is not None and (code & 0xFF) in (
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            ):
                return ("lock", error)
            barrier.abort()
            raise
        except BaseException:
            barrier.abort()
            raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        left = pool.submit(
            run,
            lambda: ctx.service._record_completion(playback, original, ctx.clock),
        )
        right = pool.submit(
            run, lambda: ctx.service.record_failure(playback.playback_id)
        )
        results = (left.result(timeout=15), right.result(timeout=15))
    monkeypatch.undo()
    assert len(crossed) == 2
    with ctx.store.uow_factory() as uow:
        durable = uow.execution.get_playback(playback.playback_id)
    successful = [result for kind, result in results if kind == "success"]
    assert successful and all(result == durable for result in successful)
    after = rows(ctx)
    unchanged_except(
        before, after, {"case_projection", "playbacks", "outcome_observations"}
    )
    assert len(after["playbacks"]) == len(before["playbacks"]) == 1
    assert after["playbacks"][0]["payload_json"] == serialize_model(durable)
    added = tuple(
        row
        for row in after["outcome_observations"]
        if row not in before["outcome_observations"]
    )
    assert all(
        row in after["outcome_observations"] for row in before["outcome_observations"]
    )
    increment = int(durable.status is PlaybackStatus.COMPLETED)
    assert state(ctx).token == token.model_copy(
        update={"generation": token.generation + increment}
    )
    prior_projection = dict(before["case_projection"][0])
    actual_projection = dict(after["case_projection"][0])
    prior_projection["proposal_generation"] += increment
    prior_projection.pop("updated_at")
    actual_projection.pop("updated_at")
    assert actual_projection == prior_projection
    if durable.status is PlaybackStatus.FAILED:
        assert added == ()
    else:
        assert len(added) == 5
        observations = ctx.service.observations(ctx.decision.decision_id)
        assert {row["payload_json"] for row in added} == {
            serialize_model(item) for item in observations
        }
        assert {item.metric for item in observations} == {
            metric
            for metric, _, _ in playback_module.predicted_observations(ctx.decision)
        }
        assert all(
            item.playback_id == playback.playback_id
            and item.decision_id == playback.decision_id
            for item in observations
        )


def test_terminal_update_rechecks_status_after_validation(ctx, monkeypatch):
    playback = start(ctx)
    completed = playback.model_copy(
        update={"status": PlaybackStatus.COMPLETED, "completed_at": ctx.clock.now()}
    )
    failed = playback.model_copy(
        update={
            "status": PlaybackStatus.FAILED,
            "failed_at": ctx.clock.now(),
            "error_code": "PLAYBACK_EXECUTION_FAILED",
        }
    )
    with ctx.store.uow_factory() as uow:
        execution = cast(Any, uow.execution)
        connection, injected = execution._connection, []
        original = connection.execute

        def execute(statement, *args, **kwargs):
            if (
                getattr(statement, "is_update", False)
                and statement.table.name == "playbacks"
                and not injected
            ):
                injected.append(True)
                original(
                    update(playbacks)
                    .where(playbacks.c.playback_id == playback.playback_id)
                    .values(
                        status=failed.status.value,
                        failed_at=failed.failed_at,
                        error_code=failed.error_code,
                        payload_json=serialize_model(failed),
                    )
                )
            return original(statement, *args, **kwargs)

        monkeypatch.setattr(connection, "execute", execute)
        with pytest.raises(ImmutableRecordConflict, match="terminal"):
            uow.execution.update_playback(completed)
        assert injected == [True]
        assert uow.execution.get_playback(playback.playback_id) == failed
