# Proposal-Bound Planning Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Protect ActionPlanningWorker's planning and failure-projection writes with current proposal approval, and terminally retire stale events without damaging newer work.

**Architecture:** The existing planning transaction gets one guard before planning. Independent failure recovery gets its own guard before any Case update; unsuccessful recovery rolls back before a separate conditional event-only transaction. A narrow compare-and-update bookkeeping method and shared claim filters protect processed, terminal, and concurrently claimed events.

**Tech Stack:** Python, SQLAlchemy UoW, existing outbox columns, pytest/file SQLite.

## Global Constraints

- Helper `72ee91e` and ExecutionService through `7de52e1` are independently accepted. Parent verified 497 tests passed, 11 intentional skips and 15 live tests deselected. Preserve the accepted ExecutionService edits in the shared worker file.
- Production scope: ActionPlanningWorker in `services/execution/worker.py`; narrow outbox methods in `services/persistence/store.py`; constant and port signature in `services/persistence/ports.py`. Focused tests only in `tests/finance/test_planning_worker_currentness.py`.
- Intentional catch-all handlers at this worker fault boundary may use narrowly placed, explanatory BLE001 suppressions on the new handler lines; do not globally disable lint rules or change unrelated handlers.
- No ExecutionService, playback, interactive auth, API, option expansion, schema, provider effects, tenant/live calls, deployment, or activation.
- No combined-only finalization restriction or event suppression. Existing planner unsupported-option errors remain explicit, and all-option execution remains required before activation.
- Preserve legacy failure projection semantics, canonical payloads and historical reads. Do not classify corruption/operational failure as proposal staleness.
- Every pytest command excludes `fabric_live`. Native Fabric concurrency remains a separate authorized gate.

## Pinned outcomes and ordering

- Reserved `last_error` is `EXECUTION_PROPOSAL_STALE`. A stale initial attempt returns `False` after conditional terminal bookkeeping. All automatic and explicit claim variants then return no work for that exact event. `False` never means planning succeeded.
- This Boolean contract is worker-internal only. The existing API retry caller ignores the Boolean; its separate integration task must map stale/no-work to an explicit conflict or no-work outcome before activation. This draft does not claim that HTTP behavior is already safe or complete.
- Terminal transition increments attempt_count only once. Repeated terminal bookkeeping, already-processed rows, and a concurrent unexpired claim return `False` without writes or recounting. Do not overwrite a terminal code with an ordinary error.
- Initial claim/actions/processed marker/Case progress/guard share one transaction; stale failure rolls it all back. The original UoW must exit before recovery opens another UoW.
- Recovery for an independent Decision reads event state, guards fresh currentness, conditionally records the original error, updates only the matching Case, then commits. If the conditional event update loses, exit without commit so the guard rolls back too.
- A stale recovery guard rolls back, then a fresh UoW records only terminal event bookkeeping. A non-stale recovery error also rolls back, permits fresh event-only bookkeeping under the original error code, and propagates; it is not silently renamed stale. No retries or savepoints.
- Legacy recovery keeps its old error code/Case behavior. Since legacy events never acquire this new terminal code, adding terminal exclusion to the old failure method does not change valid legacy behavior.

### Task 1: Guard planning and make stale-event bookkeeping conditional

**Files:** `services/execution/worker.py`, `services/persistence/store.py`, `services/persistence/ports.py`, and `tests/finance/test_planning_worker_currentness.py`.

**Consumes:** accepted `guard_execution_current(uow, decision_id) -> Decision` and `ExecutionProposalStale`; `OutboxClaim`; existing `OutboxProcessingState(event_id, claim_status, processed_at, attempt_count, last_error)`; unchanged planner and existing UoW rollback-on-exit.

**Produces:** `EXECUTION_PROPOSAL_STALE_ERROR = "EXECUTION_PROPOSAL_STALE"` and `ExecutionStore.record_outbox_failure_if_current(event_id: str, *, expected: OutboxProcessingState, error_code: str) -> bool`. `True` means one conditional bookkeeping transition occurred, never successful planning. Public worker method signatures remain unchanged.

- [ ] **Step 1: Write the focused fixture and tests before production changes.**

Create `tests/finance/test_planning_worker_currentness.py` with this code:

```python
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError

import services.execution.worker as worker_module
from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import CorpusScope, DecisionKind, IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.execution import OutboxClaimStatus
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.execution.currentness import ExecutionProposalStale
from services.execution.planner import plan_actions
from services.execution.worker import ActionPlanningWorker
from services.finance.contracts import FinalizeProposalCommand, ResolveFinanceCommand, SubmitProposalCommand
from services.finance.decisions import FinanceDecisionService
from services.finance.identity import BoundFinanceActors
from services.finance.service import FinanceService
from services.persistence.ports import UnitOfWork, EXECUTION_PROPOSAL_STALE_ERROR
from services.persistence.sqlite import sqlite_store
from services.persistence.store import PersistenceIntegrityError
from services.persistence.tables import metadata, outbox_events

NOW = datetime.fromisoformat('2026-09-01T14:02:00+00:00')

def proposal(ctx):
    with ctx.factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)

def snapshot(ctx):
    with ctx.store.engine.connect() as connection:
        return {table.name: tuple(dict(row) for row in connection.execute(
            select(table).order_by(*table.primary_key.columns)).mappings())
            for table in metadata.sorted_tables}

def event_state(ctx):
    with ctx.factory() as uow:
        return uow.execution.get_outbox_state(ctx.event_id)

@pytest.fixture
def ctx(tmp_path):
    tenant, aid, tid = ('11111111-1111-4111-8111-111111111111',
        '22222222-2222-4222-8222-222222222222', '33333333-3333-4333-8333-333333333333')
    actors = BoundFinanceActors(tenant_id=UUID(tenant), alex_object_id=UUID(aid), taylor_object_id=UUID(tid))
    alex = IdentitySnapshot(persona_id='RL-PERSONA-ALEX', source_id='RL-ENTRA-ALEX',
        identity_source=IdentitySource.ENTRA, tenant_id=tenant, object_id=aid,
        effective_roles=('material_planner', 'response_approver'))
    taylor = IdentitySnapshot(persona_id='RL-PERSONA-TAYLOR', source_id='RL-ENTRA-TAYLOR',
        identity_source=IdentitySource.ENTRA, tenant_id=tenant, object_id=tid,
        effective_roles=('finance_approver',))
    store = sqlite_store(f"sqlite:///{tmp_path / 'planning-guard.db'}")
    factory = cast(Callable[[], UnitOfWork], store.uow_factory)
    case, source = instantiate_rl001(case_id='RL-CASE-PLANNING-GUARD',
        purpose=CasePurpose.AUTOMATED_TEST, runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE)
    analysis = analyze_case(AnalyzeCaseCommand(analysis_id='RL-ANALYSIS-PLANNING-GUARD',
        case=case, corpus=CorpusScope.DEMO_CORPUS, operational_snapshot=source,
        evidence_items=build_rl001_evidence(source, analysis_id='RL-ANALYSIS-PLANNING-GUARD', retrieved_at=NOW),
        analysis_started_at=NOW, created_at=NOW, calculation_version='rl001-options-v1'))
    store.create_case(case, source)
    store.save_analysis(analysis)
    moments = iter(NOW + timedelta(minutes=index) for index in range(1, 100))
    clock = lambda: next(moments)
    finance = FinanceService(factory, actors=actors, clock=clock)
    context = SimpleNamespace(store=store, factory=factory, case=case,
        finance=finance, alex=alex, clock=clock)
    submitted = finance.submit(SubmitProposalCommand(case_id=case.case_id,
        expected=proposal(context).token, option_id='RL-OPTION-COMBINED', idempotency_key='submit'), alex)
    current = proposal(context)
    assert submitted.review is not None and current.review_revision is not None
    finance.resolve(ResolveFinanceCommand(review_id=submitted.review.review_id,
        expected=current.token, expected_review_revision=current.review_revision,
        approved=True, reason=None, idempotency_key='approve'), taylor)
    context.decision = FinanceDecisionService(factory, actors=actors,
        clock=clock).finalize(FinalizeProposalCommand(
            case_id=case.case_id, expected=proposal(context).token,
            kind=DecisionKind.APPROVED, idempotency_key='finalize'), alex)
    with factory() as uow:
        context.event_id = uow.execution.list_outbox(decision_id=context.decision.decision_id)[0].event_id
    yield context
    store.engine.dispose()

def replace(ctx):
    return ctx.finance.submit(SubmitProposalCommand(case_id=ctx.case.case_id,
        expected=proposal(ctx).token, option_id='RL-OPTION-TRANSFER', idempotency_key='replace'), ctx.alex)

def assert_event_only(before, after, ctx, code, increment=1):
    for name in before.keys() - {'outbox_events'}:
        assert after[name] == before[name], name
    prior = next(row for row in before['outbox_events'] if row['event_id'] == ctx.event_id)
    actual = next(row for row in after['outbox_events'] if row['event_id'] == ctx.event_id)
    assert actual == {**prior, 'claim_status': 'pending', 'claimed_by': None,
        'claimed_at': None, 'claim_expires_at': None,
        'attempt_count': prior['attempt_count'] + increment, 'last_error': code}
    assert tuple(row for row in after['outbox_events'] if row['event_id'] != ctx.event_id) == tuple(
        row for row in before['outbox_events'] if row['event_id'] != ctx.event_id)

@pytest.mark.parametrize('method', ['process_next_outbox', 'process_next_unattempted_outbox', 'process_decision_outbox'])
def test_stale_worker_retires_event_without_success_and_never_reclaims(ctx, method):
    replace(ctx)
    before = snapshot(ctx)
    worker = ActionPlanningWorker(ctx.factory)
    args = (ctx.decision.decision_id,) if method == 'process_decision_outbox' else ()
    assert getattr(worker, method)(*args) is False
    after = snapshot(ctx)
    assert_event_only(before, after, ctx, EXECUTION_PROPOSAL_STALE_ERROR)
    for repeat in (worker.process_next_outbox, worker.process_next_unattempted_outbox,
            lambda: worker.process_decision_outbox(ctx.decision.decision_id)):
        assert repeat() is False
        assert snapshot(ctx) == after

def test_current_planning_commits_one_guard_and_exact_plan(ctx):
    token = proposal(ctx).token
    before = snapshot(ctx)
    planned = plan_actions(ctx.decision)
    observed = []
    worker = ActionPlanningWorker(ctx.factory, after_plan=lambda decision, actions: observed.append((decision, actions)))
    assert worker.process_next_outbox() is True
    assert observed == [(ctx.decision, planned)]
    assert proposal(ctx).token.generation == token.generation + 1
    with ctx.factory() as uow:
        assert set(uow.execution.list_actions(decision_id=ctx.decision.decision_id)) == set(planned)
        assert uow.cases.get_projection(ctx.case.case_id).case.status.value == 'executing'
        assert uow.execution.get_outbox_state(ctx.event_id).processed_at is not None
    after = snapshot(ctx)
    for name in before.keys() - {'case_projection', 'outbox_events', 'execution_actions',
            'action_projection', 'execution_events', 'draft_artifacts'}:
        assert after[name] == before[name]
    for name, expected in [('execution_actions', 5), ('action_projection', 5),
            ('execution_events', 5), ('draft_artifacts', 1)]:
        assert len(after[name]) == len(before[name]) + expected
        assert all(row in after[name] for row in before[name])
        assert all(row['decision_id'] == ctx.decision.decision_id for row in after[name] if row not in before[name])
    assert worker.process_next_outbox() is False
    assert snapshot(ctx) == after

def test_replacement_between_failed_attempt_and_recovery_preserves_new_case(ctx):
    calls, after_replacement = [], []
    def factory():
        calls.append(len(calls) + 1)
        if len(calls) == 2:
            replace(ctx)  # first UoW has exited and rolled back
            after_replacement.append(snapshot(ctx))
        return ctx.factory()
    def fail(decision):
        raise RuntimeError('planner failure')
    assert ActionPlanningWorker(factory, planner=fail).process_next_outbox() is False
    assert len(calls) == 3
    assert_event_only(after_replacement[0], snapshot(ctx), ctx, EXECUTION_PROPOSAL_STALE_ERROR)

def test_current_failure_recovery_commits_one_guard_and_rolls_back_partial_plan(ctx, monkeypatch):
    before, token = snapshot(ctx), proposal(ctx).token
    calls, callbacks = [], []
    real = worker_module.guard_execution_current
    def guard(uow, decision_id):
        calls.append(uow)
        return real(uow, decision_id)
    monkeypatch.setattr(worker_module, 'guard_execution_current', guard)
    def conflicting_plan(decision):
        first = plan_actions(decision)[0]
        conflicting = first.model_copy(update={'created_at': first.created_at + timedelta(seconds=1)})
        return first, conflicting
    worker = ActionPlanningWorker(ctx.factory, planner=conflicting_plan,
        after_plan=lambda *args: callbacks.append(args))
    assert worker.process_next_outbox() is True
    assert len(calls) == 2 and calls[0] is not calls[1]
    assert callbacks == []
    after = snapshot(ctx)
    assert proposal(ctx).token == token.model_copy(update={'generation': token.generation + 1})
    assert_event_only(
        {name: value for name, value in before.items() if name != 'case_projection'},
        {name: value for name, value in after.items() if name != 'case_projection'},
        ctx, 'IMMUTABLE_RECORD_CONFLICT')
    expected_projection = {**before['case_projection'][0],
        'proposal_generation': token.generation + 1}
    actual_projection = dict(after['case_projection'][0])
    expected_projection.pop('updated_at')
    actual_projection.pop('updated_at')
    assert actual_projection == expected_projection
    with ctx.factory() as uow:
        projection = uow.cases.get_projection(ctx.case.case_id)
        assert projection.case.status.value == 'action_planning'
        assert projection.display_status == 'Approved — action planning failed'
        assert uow.execution.list_actions(decision_id=ctx.decision.decision_id) == ()
    assert after['draft_artifacts'] == before['draft_artifacts']
    assert after['execution_events'] == before['execution_events']

def test_lost_conditional_bookkeeping_rolls_back_recovery_guard_without_case_write(ctx, monkeypatch):
    before, calls = snapshot(ctx), []
    real = worker_module.guard_execution_current
    def guard(uow, decision_id):
        calls.append(uow)
        return real(uow, decision_id)
    monkeypatch.setattr(worker_module, 'guard_execution_current', guard)
    with ctx.factory() as uow:
        execution_type, case_type = type(uow.execution), type(uow.cases)
    conditional_calls = []
    def lost(repository, event_id, *, expected, error_code):
        conditional_calls.append((event_id, expected, error_code))
        return False
    def forbidden_case_write(*args, **kwargs):
        raise AssertionError('lost event bookkeeping must not update Case')
    monkeypatch.setattr(execution_type, 'record_outbox_failure_if_current', lost)
    monkeypatch.setattr(case_type, 'mark_action_planning_failed', forbidden_case_write)
    def fail(decision):
        raise RuntimeError('planner failed')
    assert ActionPlanningWorker(ctx.factory, planner=fail).process_next_outbox() is False
    assert len(calls) == 2 and calls[0] is not calls[1]
    assert len(conditional_calls) == 1
    assert conditional_calls[0][0] == ctx.event_id
    assert conditional_calls[0][2] == 'RUNTIME_ERROR'
    assert snapshot(ctx) == before

def test_recovery_guard_cas_rollback_precedes_event_only_transaction(ctx, monkeypatch):
    before = snapshot(ctx)
    real, calls = worker_module.guard_execution_current, []
    def guard(uow, decision_id):
        calls.append(uow)
        decision = real(uow, decision_id)
        if len(calls) == 2:
            raise ExecutionProposalStale('injected lost recovery CAS')
        return decision
    monkeypatch.setattr(worker_module, 'guard_execution_current', guard)
    def fail(decision):
        raise RuntimeError('planner failure')
    assert ActionPlanningWorker(ctx.factory, planner=fail).process_next_outbox() is False
    assert len(calls) == 2 and calls[0] is not calls[1]
    assert_event_only(before, snapshot(ctx), ctx, EXECUTION_PROPOSAL_STALE_ERROR)

def test_recovery_integrity_error_is_not_staleness(ctx, monkeypatch):
    before, calls = snapshot(ctx), []
    real = worker_module.guard_execution_current
    injected = PersistenceIntegrityError('corrupt recovery Decision')
    def guard(uow, decision_id):
        calls.append(uow)
        if len(calls) == 2:
            raise injected
        return real(uow, decision_id)
    monkeypatch.setattr(worker_module, 'guard_execution_current', guard)
    def fail(decision):
        raise RuntimeError('planner failure')
    with pytest.raises(PersistenceIntegrityError) as caught:
        ActionPlanningWorker(ctx.factory, planner=fail).process_next_outbox()
    assert caught.value is injected
    assert_event_only(before, snapshot(ctx), ctx, 'RUNTIME_ERROR')

@pytest.mark.parametrize('terminal', ['processed', 'stale', 'active-claim'])
def test_conditional_bookkeeping_never_overwrites_terminal_or_active_rows(ctx, terminal):
    expected = event_state(ctx)
    with ctx.store.engine.begin() as connection:
        values = ({'processed_at': datetime.now(UTC), 'claim_status': 'processed'}
            if terminal == 'processed' else {'last_error': EXECUTION_PROPOSAL_STALE_ERROR}
            if terminal == 'stale' else {'claim_status': 'claimed',
                'claim_expires_at': datetime.now(UTC) + timedelta(minutes=5)})
        connection.execute(update(outbox_events).where(outbox_events.c.event_id == ctx.event_id).values(**values))
    before = snapshot(ctx)
    with ctx.factory() as uow:
        assert not uow.execution.record_outbox_failure_if_current(ctx.event_id,
            expected=expected, error_code='RUNTIME_ERROR')
        uow.commit()
    assert snapshot(ctx) == before

def test_two_terminal_bookkeepers_increment_once(ctx):
    expected, before, barrier = event_state(ctx), snapshot(ctx), Barrier(2, timeout=5)
    crossed = set()
    def record():
        try:
            with ctx.factory() as uow:
                crossed.add(id(uow.execution._connection))
                barrier.wait()
                changed = uow.execution.record_outbox_failure_if_current(ctx.event_id,
                    expected=expected, error_code=EXECUTION_PROPOSAL_STALE_ERROR)
                uow.commit()
                return changed
        except OperationalError as error:
            code = getattr(error.orig, 'sqlite_errorcode', None)
            if code is not None and (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
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
```

- [ ] **Step 2: Add a focused candidate-to-update race proof for each claim variant.**

Append this test. It deliberately changes the selected row at the SQL update seam on the same disposable connection, rather than waiting while holding a SQLite writer lock; the separate two-connection test above proves actual bookkeeping competition.

```python
@pytest.mark.parametrize('method', ['claim_next_outbox', 'claim_next_unattempted_outbox', 'claim_outbox_for_decision'])
def test_claim_update_rechecks_terminal_exclusion_after_candidate_selection(ctx, monkeypatch, method):
    with ctx.factory() as uow:
        connection = uow.execution._connection
        original, injected = connection.execute, []
        def execute(statement, *args, **kwargs):
            if getattr(statement, 'is_update', False) and statement.table.name == 'outbox_events' and not injected:
                injected.append(True)
                original(update(outbox_events).where(outbox_events.c.event_id == ctx.event_id)
                    .values(last_error=EXECUTION_PROPOSAL_STALE_ERROR))
            return original(statement, *args, **kwargs)
        monkeypatch.setattr(connection, 'execute', execute)
        args = ('ActionPlanningRequested', ctx.decision.decision_id) if method == 'claim_outbox_for_decision' else ('ActionPlanningRequested',)
        assert getattr(uow.execution, method)(*args) is None
        assert injected == [True]
        assert uow.execution.get_outbox_state(ctx.event_id).claim_status is OutboxClaimStatus.PENDING
        # Rollback the test's simulated competing update too.
```

- [ ] **Step 3: Run RED before production changes.**

Run `.venv/bin/python -m pytest tests/finance/test_planning_worker_currentness.py -q -m 'not fabric_live' -o addopts=''`. Initially expect the new constant/port method missing; after defining those, stale-worker, recovery, and second claim-predicate assertions must fail against the old worker/repository behavior. A missing currentness helper is a dependency blocker, not valid RED. Record actual results; do not manufacture retrospective test-first evidence.

- [ ] **Step 4: Add the constant, port, and conditional repository method.**

In `services/persistence/ports.py`, define and expose:

```python
EXECUTION_PROPOSAL_STALE_ERROR = 'EXECUTION_PROPOSAL_STALE'
```

Add to `ExecutionStore`:

```python
    def record_outbox_failure_if_current(
        self, event_id: str, *, expected: OutboxProcessingState, error_code: str
    ) -> bool: ...
```

Import that constant in `store.py`. Add this complete method beside `record_outbox_failure`:

```python
    def record_outbox_failure_if_current(
        self, event_id: str, *, expected: OutboxProcessingState, error_code: str
    ) -> bool:
        if expected.event_id != event_id or not error_code.strip():
            raise ValueError('event identity and nonblank error code are required')
        if expected.processed_at is not None or expected.last_error == EXECUTION_PROPOSAL_STALE_ERROR:
            return False
        now = datetime.now(UTC)
        prior_error = (outbox_events.c.last_error.is_(None) if expected.last_error is None
            else outbox_events.c.last_error == expected.last_error)
        available = or_(
            outbox_events.c.claim_status == OutboxClaimStatus.PENDING.value,
            (outbox_events.c.claim_status == OutboxClaimStatus.CLAIMED.value)
            & (outbox_events.c.claim_expires_at < now),
        )
        result = self._connection.execute(update(outbox_events).where(
            outbox_events.c.event_id == event_id,
            outbox_events.c.processed_at.is_(None),
            outbox_events.c.claim_status == expected.claim_status.value,
            outbox_events.c.attempt_count == expected.attempt_count,
            prior_error, available,
            or_(outbox_events.c.last_error.is_(None),
                outbox_events.c.last_error != EXECUTION_PROPOSAL_STALE_ERROR),
        ).values(claim_status=OutboxClaimStatus.PENDING.value,
            claimed_by=None, claimed_at=None, claim_expires_at=None,
            attempt_count=outbox_events.c.attempt_count + 1, last_error=error_code))
        return result.rowcount == 1
```

In the existing `record_outbox_failure` UPDATE predicate, add the same NULL-safe terminal exclusion:

```python
                or_(outbox_events.c.last_error.is_(None),
                    outbox_events.c.last_error != EXECUTION_PROPOSAL_STALE_ERROR),
```

In `_claim_outbox`, add that exclusion to `filters`, and replace the UPDATE's repeated partial predicates with the complete shared filters:

```python
                .where(outbox_events.c.event_id == candidate['event_id'], *filters)
```

This includes the original event type, available time, processed state, claim readiness, optional Decision scope, and unattempted-only condition on BOTH candidate and UPDATE. No canonical payload edits, processing-state type expansion, or schema changes are necessary.

- [ ] **Step 5: Replace only ActionPlanningWorker's transaction method and add its two recovery helpers.**

Add imports for `WorkflowVersion`, `OutboxClaim`, `EXECUTION_PROPOSAL_STALE_ERROR`, and the accepted helper/error. Keep constructor and three public entrypoints unchanged. Replace `_process_outbox` and add the following methods before ExecutionService:

```python
    def _process_outbox(self, *, decision_id: str | None, unattempted_only: bool) -> bool:
        claim: OutboxClaim | None = None
        try:
            with self._uow_factory() as uow:
                claim = (uow.execution.claim_outbox_for_decision('ActionPlanningRequested', decision_id)
                    if decision_id is not None else
                    uow.execution.claim_next_unattempted_outbox('ActionPlanningRequested')
                    if unattempted_only else uow.execution.claim_next_outbox('ActionPlanningRequested'))
                if claim is None:
                    return False
                uow.execution.validate_claimed_outbox(claim)
                decision = guard_execution_current(uow, claim.decision_id)
                planned_actions = self._planner(decision)
                for action in planned_actions:
                    uow.execution.insert_action_if_absent(action)
                uow.execution.mark_outbox_processed(claim.event_id)
                uow.cases.mark_action_planning_complete(decision.case_id)
                uow.commit()
        except Exception as error:
            if claim is None:
                raise
            return self._recover_failure(claim, error)
        if self._after_plan is not None:
            self._after_plan(decision, planned_actions)
        return True

    def _event_only_failure(self, claim: OutboxClaim, code: str) -> bool:
        with self._uow_factory() as uow:
            expected = uow.execution.get_outbox_state(claim.event_id)
            changed = uow.execution.record_outbox_failure_if_current(
                claim.event_id, expected=expected, error_code=code)
            if changed:
                uow.commit()
            return changed

    def _recover_failure(self, claim: OutboxClaim, error: Exception) -> bool:
        if isinstance(error, ExecutionProposalStale):
            self._event_only_failure(claim, EXECUTION_PROPOSAL_STALE_ERROR)
            return False
        independent = False
        try:
            with self._uow_factory() as uow:
                case = uow.cases.get_projection(claim.case_id).case
                independent = case.effective_workflow_version is WorkflowVersion.INDEPENDENT_FINANCE
                if not independent:
                    uow.execution.record_outbox_failure(claim.event_id, error_code(error))
                    uow.cases.mark_action_planning_failed(claim.case_id)
                    uow.commit()
                    return True
                expected = uow.execution.get_outbox_state(claim.event_id)
                if expected.processed_at is not None or expected.last_error == EXECUTION_PROPOSAL_STALE_ERROR:
                    return False
                decision = guard_execution_current(uow, claim.decision_id)
                if not uow.execution.record_outbox_failure_if_current(
                        claim.event_id, expected=expected, error_code=error_code(error)):
                    return False
                uow.cases.mark_action_planning_failed(decision.case_id)
                uow.commit()
                return True
        except ExecutionProposalStale:
            self._event_only_failure(claim, EXECUTION_PROPOSAL_STALE_ERROR)
            return False
        except Exception:
            if independent:
                self._event_only_failure(claim, error_code(error))
            raise
```

The UoW exits before each recovery catch, including conditional failure returns; its guard mutation is not committed when no event transition occurred. `after_plan` stays after successful commit and outside failure recovery, preserving callback semantics. No failed transaction is reused.

- [ ] **Step 6: Verify the focused increment and legacy compatibility.**

Run the focused command from Step 3 to GREEN. Then run `.venv/bin/python -m pytest tests/execution/test_action_planning.py tests/persistence/test_decision_outbox.py tests/finance -q -m 'not fabric_live' -o addopts=''`. Existing legacy tests specifically retain planning-error and corrupt Decision/outbox failure projection behavior; do not rewrite those baselines to accommodate the new independent branch.

Run scoped `.venv/bin/pyright --pythonpath .venv/bin/python services/execution/worker.py services/persistence/ports.py services/persistence/store.py tests/finance/test_planning_worker_currentness.py`, Ruff check/format check, and `git diff --check`. Reconcile typed test repository inspection through local casts rather than changing shared Protocol mutability. Record actual RED/GREEN, exact recovery transaction order, race outcomes, no-write repeats, dependency SHAs, and existing warnings in `.superpowers/sdd/finance-planning-worker-task-report.md`.

- [ ] **Step 7: Commit only this bounded increment and request independent review.**

Run `git add services/execution/worker.py services/persistence/ports.py services/persistence/store.py tests/finance/test_planning_worker_currentness.py` and `git commit -m 'feat: guard planning and retire stale outbox work safely'`. Exclude parent scratch plans and unrelated ExecutionService work. Review the immutable diff before playback/auth/API work or activation.

## Acceptance boundary

Self-review completed after independent helper approval at `72ee91e`: the consumed helper names match; the shared fixture clock is monotonic across Finance submission/resolution/finalization/replacement; normal failure recovery, stale recovery, conditional-event loss, and integrity propagation have explicit tests. Parent has read the complete draft and subsequent recovery-test additions and adopted this bounded task after ExecutionService acceptance. This is not a release-ready workflow or a claim of native Fabric isolation. Conditional bookkeeping deliberately does not steal an active claim; if another worker owns it, the current attempt reports no work and that owner reaches its own guarded outcome. No unbounded retry/scheduler redesign is included.
