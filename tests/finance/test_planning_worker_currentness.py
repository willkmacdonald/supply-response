import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError

from data.domain import CasePurpose, CaseStatus, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import (
    CorpusScope,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
    StandingAuthorization,
)
from data.domain.evidence import IdentitySource
from data.domain.execution import OutboxClaimStatus
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import DecisionService
from services.execution import worker as worker_module
from services.execution.currentness import ExecutionProposalStale
from services.execution.planner import plan_actions
from services.execution.worker import ActionPlanningWorker
from services.finance.contracts import (
    FinalizeProposalCommand,
    ResolveFinanceCommand,
    SubmitProposalCommand,
)
from services.finance.decisions import FinanceDecisionService
from services.finance.identity import BoundFinanceActors
from services.finance.service import FinanceService
from services.persistence.ports import EXECUTION_PROPOSAL_STALE_ERROR, UnitOfWork
from services.persistence.sqlite import sqlite_store
from services.persistence.store import PersistenceIntegrityError
from services.persistence.tables import metadata, outbox_events

NOW = datetime.fromisoformat("2026-09-01T14:02:00+00:00")


def proposal(ctx):
    with ctx.factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)


def snapshot(ctx):
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


def event_state(ctx):
    with ctx.factory() as uow:
        return uow.execution.get_outbox_state(ctx.event_id)


@pytest.fixture
def ctx(tmp_path):
    tenant = "11111111-1111-4111-8111-111111111111"
    aid = "22222222-2222-4222-8222-222222222222"
    tid = "33333333-3333-4333-8333-333333333333"
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
    store = sqlite_store(f"sqlite:///{tmp_path / 'planning-guard.db'}")
    factory = cast(Callable[[], UnitOfWork], store.uow_factory)
    case, source = instantiate_rl001(
        case_id="RL-CASE-PLANNING-GUARD",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    analysis = analyze_case(
        AnalyzeCaseCommand(
            analysis_id="RL-ANALYSIS-PLANNING-GUARD",
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=source,
            evidence_items=build_rl001_evidence(
                source,
                analysis_id="RL-ANALYSIS-PLANNING-GUARD",
                retrieved_at=NOW,
            ),
            analysis_started_at=NOW,
            created_at=NOW,
            calculation_version="rl001-options-v1",
        )
    )
    store.create_case(case, source)
    store.save_analysis(analysis)
    moments = iter(NOW + timedelta(minutes=index) for index in range(1, 100))
    clock = lambda: next(moments)
    finance = FinanceService(factory, actors=actors, clock=clock)
    context = SimpleNamespace(
        store=store, factory=factory, case=case, finance=finance, alex=alex, clock=clock
    )
    submitted = finance.submit(
        SubmitProposalCommand(
            case_id=case.case_id,
            expected=proposal(context).token,
            option_id="RL-OPTION-COMBINED",
            idempotency_key="submit",
        ),
        alex,
    )
    current = proposal(context)
    assert submitted.review is not None and current.review_revision is not None
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
    context.decision = FinanceDecisionService(
        factory, actors=actors, clock=clock
    ).finalize(
        FinalizeProposalCommand(
            case_id=case.case_id,
            expected=proposal(context).token,
            kind=DecisionKind.APPROVED,
            idempotency_key="finalize",
        ),
        alex,
    )
    with factory() as uow:
        context.event_id = uow.execution.list_outbox(
            decision_id=context.decision.decision_id
        )[0].event_id
    yield context
    store.engine.dispose()


def replace(ctx):
    return ctx.finance.submit(
        SubmitProposalCommand(
            case_id=ctx.case.case_id,
            expected=proposal(ctx).token,
            option_id="RL-OPTION-TRANSFER",
            idempotency_key="replace",
        ),
        ctx.alex,
    )


def assert_event_only(before, after, ctx, code, increment=1):
    for name in before.keys() - {"outbox_events"}:
        assert after[name] == before[name], name
    prior = next(
        row for row in before["outbox_events"] if row["event_id"] == ctx.event_id
    )
    actual = next(
        row for row in after["outbox_events"] if row["event_id"] == ctx.event_id
    )
    assert actual == {
        **prior,
        "claim_status": "pending",
        "claimed_by": None,
        "claimed_at": None,
        "claim_expires_at": None,
        "attempt_count": prior["attempt_count"] + increment,
        "last_error": code,
    }
    assert tuple(
        row for row in after["outbox_events"] if row["event_id"] != ctx.event_id
    ) == tuple(
        row for row in before["outbox_events"] if row["event_id"] != ctx.event_id
    )


@pytest.mark.parametrize(
    "method",
    (
        "process_next_outbox",
        "process_next_unattempted_outbox",
        "process_decision_outbox",
    ),
)
def test_stale_worker_retires_event_without_success_and_never_reclaims(ctx, method):
    replace(ctx)
    before = snapshot(ctx)
    planning_worker = ActionPlanningWorker(ctx.factory)
    args = (ctx.decision.decision_id,) if method == "process_decision_outbox" else ()
    assert getattr(planning_worker, method)(*args) is False
    after = snapshot(ctx)
    assert_event_only(before, after, ctx, EXECUTION_PROPOSAL_STALE_ERROR)
    repeats = (
        planning_worker.process_next_outbox,
        planning_worker.process_next_unattempted_outbox,
        lambda: planning_worker.process_decision_outbox(ctx.decision.decision_id),
    )
    for repeat in repeats:
        assert repeat() is False
        assert snapshot(ctx) == after


def test_current_planning_commits_one_guard_and_exact_plan(ctx):
    token, before = proposal(ctx).token, snapshot(ctx)
    planned, observed = plan_actions(ctx.decision), []
    planning_worker = ActionPlanningWorker(
        ctx.factory,
        after_plan=lambda decision, actions: observed.append((decision, actions)),
    )
    assert planning_worker.process_next_outbox() is True
    assert observed == [(ctx.decision, planned)]
    assert proposal(ctx).token.generation == token.generation + 1
    with ctx.factory() as uow:
        assert set(
            uow.execution.list_actions(decision_id=ctx.decision.decision_id)
        ) == set(planned)
        assert (
            uow.cases.get_projection(ctx.case.case_id).case.status.value == "executing"
        )
        assert uow.execution.get_outbox_state(ctx.event_id).processed_at is not None
    after = snapshot(ctx)
    changing = {
        "case_projection",
        "outbox_events",
        "execution_actions",
        "action_projection",
        "execution_events",
        "draft_artifacts",
    }
    for name in before.keys() - changing:
        assert after[name] == before[name]
    for name, expected in (
        ("execution_actions", 5),
        ("action_projection", 5),
        ("execution_events", 5),
        ("draft_artifacts", 1),
    ):
        assert len(after[name]) == len(before[name]) + expected
        assert all(row in after[name] for row in before[name])
        assert all(
            row["decision_id"] == ctx.decision.decision_id
            for row in after[name]
            if row not in before[name]
        )
    assert planning_worker.process_next_outbox() is False
    assert snapshot(ctx) == after


@pytest.mark.parametrize(
    "method",
    (
        "process_next_outbox",
        "process_next_unattempted_outbox",
        "process_decision_outbox",
    ),
)
def test_legacy_only_worker_defers_independent_outbox_without_mutation(ctx, method):
    before = snapshot(ctx)
    worker = ActionPlanningWorker(
        ctx.factory, processable_workflow_versions=(WorkflowVersion.LEGACY,)
    )
    args = (ctx.decision.decision_id,) if method == "process_decision_outbox" else ()

    assert getattr(worker, method)(*args) is False
    assert snapshot(ctx) == before
    restarted = ActionPlanningWorker(
        ctx.factory, processable_workflow_versions=(WorkflowVersion.LEGACY,)
    )
    assert restarted.process_next_unattempted_outbox() is False
    assert snapshot(ctx) == before


def test_legacy_only_worker_skips_older_independent_event_and_processes_legacy(ctx):
    case, source = instantiate_rl001(
        case_id="RL-CASE-LEGACY-BEHIND-DEFERRED",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    analysis = analyze_case(
        AnalyzeCaseCommand(
            analysis_id="RL-ANALYSIS-LEGACY-BEHIND-DEFERRED",
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=source,
            evidence_items=build_rl001_evidence(
                source,
                analysis_id="RL-ANALYSIS-LEGACY-BEHIND-DEFERRED",
                retrieved_at=NOW,
            ),
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
            analysis_started_at=NOW,
            created_at=NOW,
            calculation_version="rl001-options-v1",
        )
    )
    ctx.store.create_case(case, source)
    ctx.store.save_analysis(analysis)
    ctx.store.save_case_projection(
        case.model_copy(update={"status": CaseStatus.AWAITING_DECISION})
    )
    legacy = DecisionService(
        ctx.factory, clock=lambda: NOW + timedelta(minutes=10)
    ).record(
        RecordDecisionCommand(
            case_id=case.case_id,
            analysis_id=analysis.analysis_id,
            selected_option_id="RL-OPTION-COMBINED",
            kind=DecisionKind.APPROVED,
            idempotency_key="legacy-behind-deferred",
        ),
        IdentitySnapshot(
            persona_id="RL-PERSONA-ALEX",
            effective_roles=("material_planner", "response_approver"),
            identity_source=IdentitySource.ENTRA,
            source_id="RL-ENTRA-ALEX",
        ),
    )
    independent_before = event_state(ctx)
    worker = ActionPlanningWorker(
        ctx.factory, processable_workflow_versions=(WorkflowVersion.LEGACY,)
    )

    assert worker.process_next_unattempted_outbox() is True
    assert event_state(ctx) == independent_before
    with ctx.factory() as uow:
        assert len(uow.execution.list_actions(decision_id=legacy.decision_id)) == 5


def test_replacement_between_failed_attempt_and_recovery_preserves_new_case(ctx):
    calls, after_replacement = [], []

    def factory():
        calls.append(len(calls) + 1)
        if len(calls) == 2:
            replace(ctx)
            after_replacement.append(snapshot(ctx))
        return ctx.factory()

    def fail(decision):
        raise RuntimeError("planner failure")

    assert ActionPlanningWorker(factory, planner=fail).process_next_outbox() is False
    assert len(calls) == 3
    assert_event_only(
        after_replacement[0], snapshot(ctx), ctx, EXECUTION_PROPOSAL_STALE_ERROR
    )


def test_current_failure_recovery_commits_one_guard_and_rolls_back_partial_plan(
    ctx, monkeypatch
):
    before, token, calls, callbacks = snapshot(ctx), proposal(ctx).token, [], []
    real = worker_module.guard_execution_current

    def guard(uow, decision_id):
        calls.append(uow)
        return real(uow, decision_id)

    monkeypatch.setattr(worker_module, "guard_execution_current", guard)

    def conflicting_plan(decision):
        first = plan_actions(decision)[0]
        return first, first.model_copy(
            update={"created_at": first.created_at + timedelta(seconds=1)}
        )

    planning_worker = ActionPlanningWorker(
        ctx.factory,
        planner=conflicting_plan,
        after_plan=lambda *args: callbacks.append(args),
    )
    assert planning_worker.process_next_outbox() is True
    assert len(calls) == 2 and calls[0] is not calls[1]
    assert callbacks == []
    after = snapshot(ctx)
    assert proposal(ctx).token == token.model_copy(
        update={"generation": token.generation + 1}
    )
    assert_event_only(
        {name: value for name, value in before.items() if name != "case_projection"},
        {name: value for name, value in after.items() if name != "case_projection"},
        ctx,
        "IMMUTABLE_RECORD_CONFLICT",
    )
    expected_projection = {
        **before["case_projection"][0],
        "proposal_generation": token.generation + 1,
    }
    actual_projection = dict(after["case_projection"][0])
    expected_projection.pop("updated_at")
    actual_projection.pop("updated_at")
    assert actual_projection == expected_projection
    with ctx.factory() as uow:
        projection = uow.cases.get_projection(ctx.case.case_id)
        assert projection.case.status.value == "action_planning"
        assert projection.display_status == "Approved — action planning failed"
        assert uow.execution.list_actions(decision_id=ctx.decision.decision_id) == ()
    assert after["draft_artifacts"] == before["draft_artifacts"]
    assert after["execution_events"] == before["execution_events"]


def test_lost_conditional_bookkeeping_rolls_back_recovery_guard_without_case_write(
    ctx, monkeypatch
):
    before, calls = snapshot(ctx), []
    real = worker_module.guard_execution_current

    def guard(uow, decision_id):
        calls.append(uow)
        return real(uow, decision_id)

    monkeypatch.setattr(worker_module, "guard_execution_current", guard)
    with ctx.factory() as uow:
        execution_type, case_type = type(uow.execution), type(uow.cases)
    conditional_calls = []

    def lost(repository, event_id, *, expected, error_code):
        conditional_calls.append((event_id, expected, error_code))
        return False

    def forbidden_case_write(*args, **kwargs):
        raise AssertionError("lost event bookkeeping must not update Case")

    monkeypatch.setattr(execution_type, "record_outbox_failure_if_current", lost)
    monkeypatch.setattr(case_type, "mark_action_planning_failed", forbidden_case_write)

    def fail(decision):
        raise RuntimeError("planner failed")

    assert (
        ActionPlanningWorker(ctx.factory, planner=fail).process_next_outbox() is False
    )
    assert len(calls) == 2 and calls[0] is not calls[1]
    assert len(conditional_calls) == 1
    assert conditional_calls[0][0] == ctx.event_id
    assert conditional_calls[0][2] == "RUNTIME_ERROR"
    assert snapshot(ctx) == before


def test_recovery_guard_cas_rollback_precedes_event_only_transaction(ctx, monkeypatch):
    before, real, calls = snapshot(ctx), worker_module.guard_execution_current, []

    def guard(uow, decision_id):
        calls.append(uow)
        decision = real(uow, decision_id)
        if len(calls) == 2:
            raise ExecutionProposalStale("injected lost recovery CAS")
        return decision

    monkeypatch.setattr(worker_module, "guard_execution_current", guard)

    def fail(decision):
        raise RuntimeError("planner failure")

    assert (
        ActionPlanningWorker(ctx.factory, planner=fail).process_next_outbox() is False
    )
    assert len(calls) == 2 and calls[0] is not calls[1]
    assert_event_only(before, snapshot(ctx), ctx, EXECUTION_PROPOSAL_STALE_ERROR)


def test_recovery_integrity_error_is_not_staleness(ctx, monkeypatch):
    before, calls = snapshot(ctx), []
    real = worker_module.guard_execution_current
    injected = PersistenceIntegrityError("corrupt recovery Decision")

    def guard(uow, decision_id):
        calls.append(uow)
        if len(calls) == 2:
            raise injected
        return real(uow, decision_id)

    monkeypatch.setattr(worker_module, "guard_execution_current", guard)

    def fail(decision):
        raise RuntimeError("planner failure")

    with pytest.raises(PersistenceIntegrityError) as caught:
        ActionPlanningWorker(ctx.factory, planner=fail).process_next_outbox()
    assert caught.value is injected
    assert_event_only(before, snapshot(ctx), ctx, "RUNTIME_ERROR")


@pytest.mark.parametrize("terminal", ("processed", "stale", "active-claim"))
def test_conditional_bookkeeping_never_overwrites_terminal_or_active_rows(
    ctx, terminal
):
    expected = event_state(ctx)
    with ctx.store.engine.begin() as connection:
        values = (
            {"processed_at": datetime.now(UTC), "claim_status": "processed"}
            if terminal == "processed"
            else {"last_error": EXECUTION_PROPOSAL_STALE_ERROR}
            if terminal == "stale"
            else {
                "claim_status": "claimed",
                "claim_expires_at": datetime.now(UTC) + timedelta(minutes=5),
            }
        )
        connection.execute(
            update(outbox_events)
            .where(outbox_events.c.event_id == ctx.event_id)
            .values(**values)
        )
    before = snapshot(ctx)
    with ctx.factory() as uow:
        assert not uow.execution.record_outbox_failure_if_current(
            ctx.event_id, expected=expected, error_code="RUNTIME_ERROR"
        )
        uow.commit()
    assert snapshot(ctx) == before


def test_two_terminal_bookkeepers_increment_once(ctx):
    expected, before, barrier, crossed = (
        event_state(ctx),
        snapshot(ctx),
        Barrier(2, timeout=5),
        set(),
    )

    def record():
        try:
            with ctx.factory() as uow:
                crossed.add(id(cast(Any, uow.execution)._connection))
                barrier.wait()
                changed = uow.execution.record_outbox_failure_if_current(
                    ctx.event_id,
                    expected=expected,
                    error_code=EXECUTION_PROPOSAL_STALE_ERROR,
                )
                uow.commit()
                return changed
        except OperationalError as error:
            code = getattr(error.orig, "sqlite_errorcode", None)
            if code is not None and (code & 0xFF) in (
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            ):
                return False
            barrier.abort()
            raise
        except BaseException:
            barrier.abort()
            raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(record) for _ in range(2)]
        results = [item.result(timeout=15) for item in futures]
    assert len(crossed) == 2 and sorted(results) == [False, True]
    assert_event_only(before, snapshot(ctx), ctx, EXECUTION_PROPOSAL_STALE_ERROR)


@pytest.mark.parametrize(
    "method",
    ("claim_next_outbox", "claim_next_unattempted_outbox", "claim_outbox_for_decision"),
)
def test_claim_update_rechecks_terminal_exclusion_after_candidate_selection(
    ctx, monkeypatch, method
):
    with ctx.factory() as uow:
        execution = cast(Any, uow.execution)
        connection = execution._connection
        original, injected = connection.execute, []

        def execute(statement, *args, **kwargs):
            if (
                getattr(statement, "is_update", False)
                and statement.table.name == "outbox_events"
                and not injected
            ):
                injected.append(True)
                original(
                    update(outbox_events)
                    .where(outbox_events.c.event_id == ctx.event_id)
                    .values(last_error=EXECUTION_PROPOSAL_STALE_ERROR)
                )
            return original(statement, *args, **kwargs)

        monkeypatch.setattr(connection, "execute", execute)
        args = (
            ("ActionPlanningRequested", ctx.decision.decision_id)
            if method == "claim_outbox_for_decision"
            else ("ActionPlanningRequested",)
        )
        assert getattr(execution, method)(*args) is None
        assert injected == [True]
        assert (
            uow.execution.get_outbox_state(ctx.event_id).claim_status
            is OutboxClaimStatus.PENDING
        )
