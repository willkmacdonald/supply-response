import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier, local
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

import services.persistence.proposals as proposals_module
from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import (
    CorpusScope,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
    StandingAuthorization,
)
from data.domain.evidence import IdentitySource
from data.domain.execution import ExecutionStatus
from data.domain.finance import FinanceReview, FinanceReviewStatus
from data.domain.proposals import SelectionReceipt
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import DecisionService
from services.execution import worker
from services.execution.currentness import ExecutionProposalStale
from services.execution.planner import plan_actions
from services.execution.worker import ExecutionService, IllegalExecutionTransition
from services.finance.contracts import (
    FinalizeProposalCommand,
    ResolveFinanceCommand,
    SubmitProposalCommand,
)
from services.finance.decisions import FinanceDecisionService
from services.finance.identity import BoundFinanceActors
from services.finance.service import FinanceCommandConflict, FinanceService
from services.persistence.ports import UnitOfWork
from services.persistence.proposals import StaleProposal
from services.persistence.sqlite import sqlite_store
from services.persistence.store import ImmutableRecordConflict, serialize_model
from services.persistence.tables import metadata

NOW = datetime.fromisoformat("2026-09-01T14:10:00+00:00")


def state(ctx):
    with ctx.factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)


def rows(ctx):
    with ctx.store.engine.connect() as connection:
        return {
            table.name: tuple(
                connection.execute(select(table).order_by(*table.primary_key.columns))
            )
            for table in metadata.sorted_tables
        }


@pytest.fixture(params=(WorkflowVersion.INDEPENDENT_FINANCE, WorkflowVersion.LEGACY))
def ctx(tmp_path, request):
    tenant, aid, tid = (
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
        "33333333-3333-4333-8333-333333333333",
    )
    actors = BoundFinanceActors(
        tenant_id=UUID(tenant), alex_object_id=UUID(aid), taylor_object_id=UUID(tid)
    )
    alex = IdentitySnapshot(
        persona_id="RL-PERSONA-ALEX",
        source_id="RL-ENTRA-ALEX",
        identity_source=IdentitySource.ENTRA,
        tenant_id=tenant,
        object_id=aid,
        effective_roles=("material_planner", "response_approver"),
    )
    taylor = IdentitySnapshot(
        persona_id="RL-PERSONA-TAYLOR",
        source_id="RL-ENTRA-TAYLOR",
        identity_source=IdentitySource.ENTRA,
        tenant_id=tenant,
        object_id=tid,
        effective_roles=("finance_approver",),
    )
    store = sqlite_store(f"sqlite:///{tmp_path / 'execution-service.db'}")
    factory = cast(Callable[[], UnitOfWork], store.uow_factory)
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-SERVICE-GUARD",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=request.param,
    )
    analysis = analyze_case(
        AnalyzeCaseCommand(
            analysis_id="RL-ANALYSIS-SERVICE-GUARD",
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot,
                analysis_id="RL-ANALYSIS-SERVICE-GUARD",
                retrieved_at=NOW,
            ),
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
            analysis_started_at=NOW,
            created_at=NOW,
            calculation_version="rl001-options-v1",
        )
    )
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    moments = iter(NOW + timedelta(minutes=n) for n in range(1, 100))
    clock = lambda: next(moments)
    finance = FinanceService(factory, actors=actors, clock=clock)
    context = SimpleNamespace(
        store=store,
        factory=factory,
        case=case,
        analysis=analysis,
        alex=alex,
        taylor=taylor,
        finance=finance,
        independent=request.param is WorkflowVersion.INDEPENDENT_FINANCE,
    )
    if context.independent:
        submitted = finance.submit(
            SubmitProposalCommand(
                case_id=case.case_id,
                option_id="RL-OPTION-COMBINED",
                expected=state(context).token,
                idempotency_key="submit",
            ),
            alex,
        )
        current = state(context)
        assert submitted.review is not None
        assert current.review_revision is not None
        finance.resolve(
            ResolveFinanceCommand(
                review_id=submitted.review.review_id,
                expected=current.token,
                expected_review_revision=current.review_revision,
                approved=True,
                reason=None,
                idempotency_key="approve",
            ),
            taylor,
        )
        decision = FinanceDecisionService(factory, actors=actors, clock=clock).finalize(
            FinalizeProposalCommand(
                case_id=case.case_id,
                expected=state(context).token,
                kind=DecisionKind.APPROVED,
                idempotency_key="finalize",
            ),
            alex,
        )
    else:
        decision = DecisionService(factory, clock=clock).record(
            RecordDecisionCommand(
                case_id=case.case_id,
                analysis_id=analysis.analysis_id,
                selected_option_id="RL-OPTION-COMBINED",
                kind=DecisionKind.APPROVED,
                idempotency_key="legacy",
            ),
            alex,
        )
    context.decision = decision
    context.action = next(
        action
        for action in plan_actions(decision, analysis)
        if action.draft_artifact_id is not None
    )
    context.service = ExecutionService(factory, clock=clock)
    yield context
    store.engine.dispose()


def replacement(ctx):
    return SubmitProposalCommand(
        case_id=ctx.case.case_id,
        option_id="RL-OPTION-TRANSFER",
        expected=state(ctx).token,
        idempotency_key="replace",
    )


def prepare(ctx, operation):
    sibling = next(
        action
        for action in plan_actions(ctx.decision, ctx.analysis)
        if action.action_id != ctx.action.action_id
    )
    ctx.service.create(sibling)
    sibling_attempt = ctx.service.start(sibling.action_id)
    ctx.service.fail(sibling.action_id, sibling_attempt.attempt_id, "SIBLING_HISTORY")
    if operation != "create":
        ctx.service.create(ctx.action)
    if operation in ("retry", "complete", "fail", "cancel"):
        ctx.attempt = ctx.service.start(ctx.action.action_id)
    if operation == "retry":
        ctx.service.fail(ctx.action.action_id, ctx.attempt.attempt_id, "RETRYABLE")


def invoke(ctx, operation):
    if operation == "create":
        return ctx.service.create(ctx.action)
    if operation in ("start", "retry"):
        return getattr(ctx.service, operation)(ctx.action.action_id)
    if operation == "fail":
        return ctx.service.fail(ctx.action.action_id, ctx.attempt.attempt_id, "STOPPED")
    return getattr(ctx.service, operation)(ctx.action.action_id, ctx.attempt.attempt_id)


ADVANCING = ("create", "start", "retry", "complete")
EXECUTION_TABLES = {
    "execution_actions",
    "action_projection",
    "execution_attempts",
    "execution_events",
    "draft_artifacts",
}


def assert_execution_delta(before, after, operation, ctx, result):
    increments = {
        "create": (1, 1, 0, 1, 1),
        "start": (0, 0, 1, 1, 0),
        "retry": (0, 0, 1, 1, 0),
        "complete": (0, 0, 0, 1, 0),
    }[operation]
    names = (
        "execution_actions",
        "action_projection",
        "execution_attempts",
        "execution_events",
        "draft_artifacts",
    )
    for name, increment in zip(names, increments, strict=True):
        assert len(after[name]) == len(before[name]) + increment
    for name in before.keys() - EXECUTION_TABLES - {"case_projection"}:
        assert after[name] == before[name]
    for name in ("execution_actions", "execution_events", "draft_artifacts"):
        assert all(row in after[name] for row in before[name])
    for name in EXECUTION_TABLES:
        outside_before = tuple(
            row
            for row in before[name]
            if row._mapping["action_id"] != ctx.action.action_id
        )
        outside_after = tuple(
            row
            for row in after[name]
            if row._mapping["action_id"] != ctx.action.action_id
        )
        assert outside_after == outside_before
        for row in after[name]:
            if row not in before[name]:
                assert row._mapping["action_id"] == ctx.action.action_id
                assert row._mapping["decision_id"] == ctx.decision.decision_id
    if operation == "complete":
        untouched = tuple(
            row
            for row in before["execution_attempts"]
            if row._mapping["attempt_id"] != ctx.attempt.attempt_id
        )
        assert (
            tuple(
                row
                for row in after["execution_attempts"]
                if row._mapping["attempt_id"] != ctx.attempt.attempt_id
            )
            == untouched
        )
        changed = [
            row._mapping
            for row in after["execution_attempts"]
            if row._mapping["attempt_id"] == ctx.attempt.attempt_id
        ]
        assert len(changed) == 1
        assert changed[0]["status"] == ExecutionStatus.COMPLETED.value
    else:
        assert all(
            row in after["execution_attempts"] for row in before["execution_attempts"]
        )
        added = [
            row._mapping
            for row in after["execution_attempts"]
            if row not in before["execution_attempts"]
        ]
        if operation in ("start", "retry"):
            assert len(added) == 1
            assert added[0]["attempt_id"] == result.attempt_id
            assert added[0]["payload_json"] == serialize_model(result)
        else:
            assert added == []
    added_events = [
        row._mapping
        for row in after["execution_events"]
        if row not in before["execution_events"]
    ]
    assert len(added_events) == 1
    with ctx.factory() as uow:
        event = uow.execution.list_status_events(ctx.action.action_id)[-1]
        assert added_events[0]["payload_json"] == serialize_model(event)
        expected_attempt_id = (
            result.attempt_id
            if operation in ("start", "retry")
            else ctx.attempt.attempt_id
            if operation == "complete"
            else None
        )
        assert event.attempt_id == expected_attempt_id
    if operation == "create":
        added_actions = [
            row._mapping
            for row in after["execution_actions"]
            if row not in before["execution_actions"]
        ]
        assert len(added_actions) == 1
        assert added_actions[0]["payload_json"] == serialize_model(ctx.action)
        added_drafts = [
            row._mapping
            for row in after["draft_artifacts"]
            if row not in before["draft_artifacts"]
        ]
        assert len(added_drafts) == 1
        assert added_drafts[0]["artifact_id"] == ctx.action.draft_artifact_id


def assert_projection_delta(before, after, *, generation, selection_id):
    prior = dict(before["case_projection"][0]._mapping)
    actual = dict(after["case_projection"][0]._mapping)
    expected = {
        **prior,
        "proposal_generation": generation,
        "current_selection_id": selection_id,
    }
    expected.pop("updated_at")
    actual.pop("updated_at")
    assert actual == expected


@pytest.mark.parametrize("operation", ADVANCING)
def test_each_advancing_transaction_has_one_fresh_guard(ctx, operation):
    prepare(ctx, operation)
    before, token = rows(ctx), state(ctx).token
    result = invoke(ctx, operation)
    after = rows(ctx)
    assert_execution_delta(before, after, operation, ctx, result)
    assert state(ctx).token == token.model_copy(
        update={"generation": token.generation + int(ctx.independent)}
    )
    assert_projection_delta(
        before,
        after,
        generation=token.generation + int(ctx.independent),
        selection_id=token.selection_id,
    )
    with ctx.factory() as uow:
        action = uow.execution.get_action(ctx.action.action_id)
        expected = {
            "create": ExecutionStatus.PLANNED,
            "start": ExecutionStatus.IN_PROGRESS,
            "retry": ExecutionStatus.IN_PROGRESS,
            "complete": ExecutionStatus.COMPLETED,
        }[operation]
        assert action.status is expected
        if operation in ("start", "retry"):
            assert uow.execution.get_attempt(result.attempt_id) == result
        else:
            assert action == result


@pytest.mark.parametrize("operation", ADVANCING)
def test_stale_advance_writes_nothing(ctx, operation):
    if not ctx.independent:
        pytest.skip("legacy has no new currentness policy")
    prepare(ctx, operation)
    ctx.finance.submit(replacement(ctx), ctx.alex)
    before = rows(ctx)
    with pytest.raises(ExecutionProposalStale):
        invoke(ctx, operation)
    assert rows(ctx) == before


def test_identical_historical_create_receipt_is_no_write_and_conflicts_survive(
    ctx, monkeypatch
):
    ctx.service.create(ctx.action)
    ctx.service.start(ctx.action.action_id)
    if ctx.independent:
        ctx.finance.submit(replacement(ctx), ctx.alex)
    before = rows(ctx)

    def forbidden(*args, **kwargs):
        raise AssertionError("historical receipt must not guard or commit")

    monkeypatch.setattr(worker, "guard_execution_current", forbidden)
    with ctx.factory() as uow:
        monkeypatch.setattr(type(uow), "commit", forbidden)
        expected = uow.execution.get_action(ctx.action.action_id)
    assert ctx.service.create(ctx.action) == expected
    conflicting = ctx.action.model_copy(
        update={"created_at": ctx.action.created_at + timedelta(seconds=1)}
    )
    with pytest.raises(ImmutableRecordConflict):
        ctx.service.create(conflicting)
    assert rows(ctx) == before


@pytest.mark.parametrize("operation", ADVANCING)
def test_failure_after_guard_rolls_back_all_rows_and_generation(
    ctx, monkeypatch, operation
):
    prepare(ctx, operation)
    before = rows(ctx)
    real = worker.guard_execution_current
    injected = RuntimeError("after guard")

    def fail(uow, decision_id):
        real(uow, decision_id)
        raise injected

    monkeypatch.setattr(worker, "guard_execution_current", fail)
    with pytest.raises(RuntimeError) as caught:
        invoke(ctx, operation)
    assert caught.value is injected
    assert rows(ctx) == before


@pytest.mark.parametrize("operation", ("fail", "cancel"))
def test_historical_cleanup_stays_exact_target_and_never_guards(
    ctx, monkeypatch, operation
):
    prepare(ctx, operation)
    if ctx.independent:
        ctx.finance.submit(replacement(ctx), ctx.alex)
    before = rows(ctx)

    def forbidden(*args, **kwargs):
        raise AssertionError("historical cleanup must not guard")

    monkeypatch.setattr(worker, "guard_execution_current", forbidden)
    result = invoke(ctx, operation)
    after = rows(ctx)
    assert result.action_id == ctx.action.action_id
    expected = (
        ExecutionStatus.FAILED if operation == "fail" else ExecutionStatus.CANCELLED
    )
    assert result.status is expected
    for name in before.keys() - {
        "action_projection",
        "execution_attempts",
        "execution_events",
    }:
        assert after[name] == before[name]
    for name in ("action_projection", "execution_attempts", "execution_events"):
        outside_before = tuple(
            row
            for row in before[name]
            if row._mapping["action_id"] != ctx.action.action_id
        )
        outside_after = tuple(
            row
            for row in after[name]
            if row._mapping["action_id"] != ctx.action.action_id
        )
        assert outside_after == outside_before
    assert all(row in after["execution_events"] for row in before["execution_events"])
    added_events = [
        row._mapping
        for row in after["execution_events"]
        if row not in before["execution_events"]
    ]
    assert len(added_events) == 1
    with ctx.factory() as uow:
        stored = uow.execution.get_action(ctx.action.action_id)
        attempts = uow.execution.list_attempts(ctx.action.action_id)
        event = uow.execution.list_status_events(ctx.action.action_id)[-1]
        assert stored == result
        assert len(attempts) == 1
        assert attempts[0].attempt_id == ctx.attempt.attempt_id
        assert attempts[0].status is result.status
        assert event.action_id == ctx.action.action_id
        assert event.decision_id == ctx.decision.decision_id
        assert event.attempt_id == ctx.attempt.attempt_id
        assert event.from_status is ExecutionStatus.IN_PROGRESS
        assert event.to_status is expected
        assert event.error_code == ("STOPPED" if operation == "fail" else None)
    target_projection = next(
        row._mapping
        for row in after["action_projection"]
        if row._mapping["action_id"] == ctx.action.action_id
    )
    target_attempt = next(
        row._mapping
        for row in after["execution_attempts"]
        if row._mapping["attempt_id"] == ctx.attempt.attempt_id
    )
    assert target_projection["decision_id"] == ctx.decision.decision_id
    assert target_projection["status"] == expected.value
    assert target_projection["payload_json"] == serialize_model(result)
    assert target_attempt["action_id"] == ctx.action.action_id
    assert target_attempt["decision_id"] == ctx.decision.decision_id
    assert target_attempt["status"] == expected.value
    assert target_attempt["payload_json"] == serialize_model(attempts[0])
    assert added_events[0]["action_id"] == ctx.action.action_id
    assert added_events[0]["decision_id"] == ctx.decision.decision_id
    assert added_events[0]["payload_json"] == serialize_model(event)


def test_invalid_transition_and_wrong_attempt_leave_every_row_unchanged(ctx):
    ctx.service.create(ctx.action)
    before = rows(ctx)
    with pytest.raises(IllegalExecutionTransition):
        ctx.service.retry(ctx.action.action_id)
    assert rows(ctx) == before
    attempt = ctx.service.start(ctx.action.action_id)
    other = next(
        action
        for action in plan_actions(ctx.decision, ctx.analysis)
        if action.action_id != ctx.action.action_id
    )
    ctx.service.create(other)
    other_attempt = ctx.service.start(other.action_id)
    before = rows(ctx)
    with pytest.raises(IllegalExecutionTransition):
        ctx.service.complete(ctx.action.action_id, other_attempt.attempt_id)
    assert rows(ctx) == before
    assert ctx.service.attempts(ctx.action.action_id) == (attempt,)
    ctx.service.history(ctx.action.action_id)
    assert rows(ctx) == before


@pytest.mark.parametrize("operation", ADVANCING)
def test_advancing_transaction_races_replacement_without_loser_residue(
    ctx, monkeypatch, operation
):
    if not ctx.independent:
        pytest.skip("new protocol concurrency applies to independent policy")
    prepare(ctx, operation)
    command = replacement(ctx)
    before, token = rows(ctx), state(ctx).token
    barrier, local_state, crossed = Barrier(2, timeout=5), local(), set()
    with ctx.factory() as uow:
        execution_type = type(uow.execution)
    original_insert = execution_type.insert_action_if_absent
    original_action = execution_type.get_action
    original_state = proposals_module.SqlAlchemyProposalRepository.get_state

    def meet(repository):
        if getattr(local_state, "first", False):
            local_state.first = False
            crossed.add(id(repository._connection))
            barrier.wait()

    def insert(repository, action):
        meet(repository)
        return original_insert(repository, action)

    def action(repository, action_id):
        value = original_action(repository, action_id)
        meet(repository)
        return value

    def current(repository, case_id):
        value = original_state(repository, case_id)
        meet(repository)
        return value

    monkeypatch.setattr(execution_type, "insert_action_if_absent", insert)
    monkeypatch.setattr(execution_type, "get_action", action)
    monkeypatch.setattr(
        proposals_module.SqlAlchemyProposalRepository, "get_state", current
    )

    def run(call):
        local_state.first = True
        try:
            return ("success", call())
        except (ExecutionProposalStale, StaleProposal, FinanceCommandConflict) as error:
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
        left = pool.submit(run, lambda: invoke(ctx, operation))
        right = pool.submit(run, lambda: ctx.finance.submit(command, ctx.alex))
        results = (left.result(timeout=15), right.result(timeout=15))
    monkeypatch.undo()
    assert len(crossed) == 2
    assert sum(kind == "success" for kind, _ in results) == 1
    after, durable = rows(ctx), state(ctx)
    assert durable.token.generation == token.generation + 1
    if results[0][0] == "success":
        assert_execution_delta(before, after, operation, ctx, results[0][1])
        assert durable.token.selection_id == token.selection_id
        with ctx.factory() as uow:
            result = cast(Any, results[0][1])
            if operation in ("start", "retry"):
                assert uow.execution.get_attempt(result.attempt_id) == result
            else:
                assert uow.execution.get_action(result.action_id) == result
    else:
        receipt = cast(Any, results[1][1])
        assert durable.selection == receipt.selection
        assert durable.selection.proposal.option_id == "RL-OPTION-TRANSFER"
        assert durable.review is None
        assert (
            len(after["case_proposal_selections"])
            == len(before["case_proposal_selections"]) + 1
        )
        assert (
            len(after["finance_review_revisions"])
            == len(before["finance_review_revisions"]) + 1
        )
        added_selections = [
            row._mapping
            for row in after["case_proposal_selections"]
            if row not in before["case_proposal_selections"]
        ]
        assert len(added_selections) == 1
        saved_receipt = SelectionReceipt.model_validate_json(
            added_selections[0]["payload_json"]
        )
        assert saved_receipt.selection == receipt.selection
        assert saved_receipt.expected == command.expected
        assert (
            saved_receipt.idempotency_key == f"finance-submit:{command.idempotency_key}"
        )
        assert added_selections[0]["selection_id"] == receipt.selection.selection_id
        added_reviews = [
            row._mapping
            for row in after["finance_review_revisions"]
            if row not in before["finance_review_revisions"]
        ]
        assert len(added_reviews) == 1
        for name in before.keys() - {
            "case_projection",
            "case_proposal_selections",
            "finance_review_revisions",
        }:
            assert after[name] == before[name]
        with ctx.factory() as uow:
            old = ctx.decision.proposal_approval.review
            assert old is not None
            review, revision = uow.finance_reviews.get_latest(old.review_id)
            expected_review = FinanceReview.model_validate(
                {
                    **old.model_dump(),
                    "status": FinanceReviewStatus.SUPERSEDED,
                    "superseded_at": receipt.selection.submitted_at,
                }
            )
            assert review == expected_review
            assert revision == ctx.decision.proposal_approval.review_revision + 1
            assert added_reviews[0]["review_id"] == old.review_id
            assert added_reviews[0]["revision"] == revision
            assert added_reviews[0]["payload_json"] == serialize_model(expected_review)
            assert added_reviews[0]["idempotency_key"] == (
                f"selection-supersede:{receipt.selection.selection_id}"
            )
    with ctx.factory() as uow:
        projection = uow.cases.get_projection(ctx.case.case_id)
        assert projection.current_decision_id == ctx.decision.decision_id
        assert projection.current_analysis_id == ctx.decision.analysis_id
        assert projection.current_analysis_hash == ctx.decision.analysis_material_hash
    assert_projection_delta(
        before,
        after,
        generation=token.generation + 1,
        selection_id=durable.token.selection_id,
    )
