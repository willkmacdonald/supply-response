# Playback Currentness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guard new playback, draft fill, and simulated observation/completion transactions while preserving historical receipts and terminal outcomes.

**Architecture:** Reuse the accepted same-UoW helper at each actual success-advancing write, not historical reads. Fresh completion verifies the complete persisted action set. A narrow conditional playback terminal update prevents concurrent historical failure cleanup from being overwritten by completion.

**Tech Stack:** Existing Python services, SQLAlchemy, file SQLite, pytest.

## Global Constraints

- Parent adopted this bounded task after independent acceptance of helper `72ee91e`, ExecutionService through `7de52e1`, and queued planning `a7e2d96`. Parent fresh regression passed 513 tests, with 11 intentional skips and 15 live tests excluded. The complete draft and all added self-review tests were read before adoption.
- Scope: `services/execution/playback.py`, `SqlAlchemyExecutionRepository.update_playback` in `services/persistence/store.py`, and `tests/finance/test_playback_currentness.py` only. The narrow repository expansion was explicitly approved because a SELECT followed by unconditional UPDATE cannot protect concurrent failure/completion.
- No ExecutionService changes, API/auth composition, option expansion, mail adapter, schemas, live calls, deployment, or activation.
- Preserve existing `_authorize` ordering and Decision.actor equality. Exact configured identity remains a separate required gate, not something this task claims to provide.
- Preserve PRODUCTION_STEPS, _OUTCOMES, draft subject/body, deterministic IDs, simulated/synthetic observations and permanently unsent legacy DraftArtifact bytes. All-option simulation and reviewed real email remain separate mandatory gates before activation; simulation is not actual mail delivery or overall real-plan completion.
- Every mutation guard uses fresh state in its existing UoW. No UoW during playback waits, cached token, automatic retry, savepoint, or external effect.
- Historical exact receipts do not guard, commit, or read the clock. Historical failure cleanup remains target-scoped and does not touch current Case/proposal state.
- All pytest runs exclude `fabric_live`; native database concurrency remains a separate authorized gate.

### Task 1: Guard playback writes and make terminal update conditional

**Files:** modify playback service and the single named repository method; create the focused test file.

**Consumes:** `guard_execution_current(uow, decision_id) -> Decision`; `ExecutionProposalStale`; unchanged ExecutionService start/complete; repository `insert_playback_if_absent -> bool`, `fill_draft_artifact -> None`, `list_actions`, `update_playback -> None`; existing `ImmutableRecordConflict`.

**Produces:** unchanged public interfaces. New playback/fill/completion reject stale independent approval. Existing completed/failed playback receipts remain terminal. A concurrent lost terminal update raises existing ImmutableRecordConflict and rolls back the entire caller transaction.

## Ordering and exactness

- Start retains authorization, canonical Decision/actor checks and existing playback return before new work. For a new row, insert first, then guard only if insertion returned True; commit only that branch. This preserves repository concurrent receipt semantics and rolls all insertion work back if stale. No external action occurs before the guard.
- For an already-filled shell, call the existing repository fill method with the fixed expected content, then return without guard/commit. That method validates exact equality and cannot write in its already-filled branch; divergent content retains ImmutableRecordConflict. An empty shell is guarded before filling.
- Completion re-reads its canonical playback and compares immutable identity with the supplied snapshot. Completed/failed history returns unchanged. Only IN_PROGRESS may advance. Re-read canonical actions, require exactly the five expected kinds, complete statuses, and exact immutable equality with the supplied action tuple after normalizing status to PLANNED. Use the newly read action IDs for observations; never trust caller-supplied IDs alone.
- `update_playback` retains its existing validation and adds `status == in_progress` to the actual UPDATE. A zero-row result is a concurrent terminal conflict, never an implicit success. This protects completion against record_failure even though cleanup intentionally does not join proposal-generation CAS.

- [ ] **Step 1: Add the complete focused fixture/test support.**

Create `tests/finance/test_playback_currentness.py`:

```python
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, local

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError

import services.execution.playback as playback_module
from data.domain.execution import PlaybackStatus, ExecutionStatus
from services.execution.currentness import ExecutionProposalStale
from services.execution.playback import PlaybackService, PlaybackStateError, ImmediateClock
from services.execution.worker import ActionPlanningWorker, ExecutionService
from services.finance.contracts import FinalizeProposalCommand, SubmitProposalCommand, ResolveFinanceCommand
from services.finance.decisions import FinanceDecisionService
from services.finance.service import FinanceService
from services.persistence.store import ImmutableRecordConflict, SqlAlchemyExecutionRepository, serialize_model
from services.persistence.tables import metadata, playbacks
from data.domain.decisions import DecisionKind
from tests.finance.test_finance_final_decision import final_ctx  # noqa: F401

# Reuse the accepted disposable independent Case/Analysis/exact-identity fixture.
# It has no selection yet; this file owns its monotonic Finance/playback clock.
@pytest.fixture
def ctx(final_ctx):
    ctx = final_ctx
    ctx.clock = ImmediateClock(ctx.analysis.created_at + timedelta(hours=1))
    def tick():
        now = ctx.clock.now()
        ctx.clock.wait_until(now + timedelta(seconds=1))
        return now
    ctx.finance = FinanceService(ctx.store.uow_factory, actors=ctx.actors, clock=tick)
    selected = ctx.finance.submit(SubmitProposalCommand(case_id=ctx.case.case_id,
        expected=state(ctx).token, option_id='RL-OPTION-COMBINED', idempotency_key='playback-submit'), ctx.alex)
    current = state(ctx)
    assert selected.review is not None and current.review_revision is not None
    ctx.finance.resolve(ResolveFinanceCommand(review_id=selected.review.review_id,
        expected=current.token, expected_review_revision=current.review_revision,
        approved=True, reason=None, idempotency_key='playback-approve'), ctx.taylor)
    ctx.decision = FinanceDecisionService(ctx.store.uow_factory, actors=ctx.actors,
        clock=tick).finalize(FinalizeProposalCommand(case_id=ctx.case.case_id,
            expected=state(ctx).token, kind=DecisionKind.APPROVED,
            idempotency_key='playback-finalize'), ctx.alex)
    assert ActionPlanningWorker(ctx.store.uow_factory).process_next_outbox()
    ctx.service = PlaybackService(ctx.store.uow_factory, clock=ctx.clock)
    return ctx

def state(ctx):
    with ctx.store.uow_factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)

def rows(ctx):
    with ctx.store.engine.connect() as connection:
        return {table.name: tuple(dict(row) for row in connection.execute(
            select(table).order_by(*table.primary_key.columns)).mappings())
            for table in metadata.sorted_tables}

def actions(ctx):
    with ctx.store.uow_factory() as uow:
        return uow.execution.list_actions(decision_id=ctx.decision.decision_id)

def start(ctx):
    return ctx.service.start(ctx.decision.decision_id, ctx.alex)

def replace(ctx):
    return ctx.finance.submit(SubmitProposalCommand(case_id=ctx.case.case_id,
        expected=state(ctx).token, option_id='RL-OPTION-TRANSFER', idempotency_key='replace-playback'), ctx.alex)

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
    if operation == 'start':
        return start(ctx)
    if operation == 'fill':
        return ctx.service._fill_draft(next(a for a in original_actions if a.draft_artifact_id))
    return ctx.service._record_completion(playback, original_actions, ctx.clock)
```

- [ ] **Step 2: Add currentness, history, and rollback tests.**

```python
@pytest.mark.parametrize('operation', ['start', 'fill', 'complete'])
def test_each_playback_write_rejects_stale_approval_without_any_rows(ctx, operation):
    playback = None if operation == 'start' else start(ctx)
    original = actions(ctx)
    if operation == 'complete':
        complete_actions(ctx)
    replace(ctx)
    before = rows(ctx)
    with pytest.raises(ExecutionProposalStale):
        invoke(ctx, operation, playback, original)
    assert rows(ctx) == before

@pytest.mark.parametrize('operation', ['start', 'fill', 'complete'])
def test_each_playback_write_commits_one_fresh_guard(ctx, operation):
    playback = None if operation == 'start' else start(ctx)
    original = actions(ctx)
    if operation == 'complete':
        complete_actions(ctx)
    before, token = rows(ctx), state(ctx).token
    result = invoke(ctx, operation, playback, original)
    after = rows(ctx)
    assert state(ctx).token == token.model_copy(update={'generation': token.generation + 1})
    allowed = {'case_projection', 'playbacks'} if operation == 'start' else {
        'case_projection', 'draft_artifacts'} if operation == 'fill' else {
        'case_projection', 'playbacks', 'outcome_observations'}
    unchanged_except(before, after, allowed)
    if operation == 'complete':
        assert result.status is PlaybackStatus.COMPLETED
        observations = ctx.service.observations(ctx.decision.decision_id)
        assert len(observations) == 10
        assert all(o.synthetic and o.kind.value == 'simulated' for o in observations)
        assert {o.action_id for o in observations} <= {a.action_id for a in original}

@pytest.mark.parametrize('operation', ['start', 'fill', 'complete'])
def test_failure_after_guard_rolls_back_playback_transaction(ctx, monkeypatch, operation):
    playback = None if operation == 'start' else start(ctx)
    original = actions(ctx)
    if operation == 'complete':
        complete_actions(ctx)
    before, real = rows(ctx), playback_module.guard_execution_current
    injected = RuntimeError('after playback guard')
    def guard(uow, decision_id):
        real(uow, decision_id)
        raise injected
    monkeypatch.setattr(playback_module, 'guard_execution_current', guard)
    with pytest.raises(RuntimeError) as caught:
        invoke(ctx, operation, playback, original)
    assert caught.value is injected
    assert rows(ctx) == before

def test_exact_start_and_filled_draft_history_need_no_guard_clock_or_commit(ctx, monkeypatch):
    playback = start(ctx)
    draft_action = next(a for a in actions(ctx) if a.draft_artifact_id)
    ctx.service._fill_draft(draft_action)
    replace(ctx)
    before = rows(ctx)
    def forbidden(*args, **kwargs):
        raise AssertionError('historical receipt must not advance')
    monkeypatch.setattr(playback_module, 'guard_execution_current', forbidden)
    monkeypatch.setattr(ctx.clock, 'now', forbidden)
    with ctx.store.uow_factory() as uow:
        monkeypatch.setattr(type(uow), 'commit', forbidden)
    assert start(ctx) == playback
    ctx.service._fill_draft(draft_action)
    assert rows(ctx) == before

def test_divergent_filled_draft_history_remains_immutable_when_stale(ctx, monkeypatch):
    draft_action = next(a for a in actions(ctx) if a.draft_artifact_id)
    with ctx.store.uow_factory() as uow:
        shell = uow.execution.get_draft_artifact(draft_action.action_id)
        different = shell.model_copy(update={'subject': 'Earlier immutable subject',
            'body': 'Earlier immutable simulated content; never sent.'})
        uow.execution.fill_draft_artifact(different)
        uow.commit()
    replace(ctx)
    before = rows(ctx)
    def forbidden(*args, **kwargs):
        raise AssertionError('filled history conflict must precede guard')
    monkeypatch.setattr(playback_module, 'guard_execution_current', forbidden)
    with pytest.raises(ImmutableRecordConflict, match='insert-only'):
        ctx.service._fill_draft(draft_action)
    assert rows(ctx) == before

def test_terminal_conflict_rolls_back_tentative_observations_and_guard(ctx, monkeypatch):
    playback, original = start(ctx), actions(ctx)
    complete_actions(ctx)
    before, witnessed = rows(ctx), []
    injected = ImmutableRecordConflict('Playback already has a terminal result')
    def lose(repository, completed):
        pending = repository.list_observations(ctx.decision.decision_id)
        witnessed.extend(pending)
        assert len(pending) == 10
        assert completed.playback_id == playback.playback_id
        assert completed.status is PlaybackStatus.COMPLETED
        raise injected
    monkeypatch.setattr(SqlAlchemyExecutionRepository, 'update_playback', lose)
    with pytest.raises(ImmutableRecordConflict) as caught:
        ctx.service._record_completion(playback, original, ctx.clock)
    assert caught.value is injected
    assert len(witnessed) == 10
    assert rows(ctx) == before

def test_failed_playback_remains_failed_and_cleanup_is_target_only(ctx):
    playback = start(ctx)
    original = actions(ctx)
    replace(ctx)
    before = rows(ctx)
    failed = ctx.service.record_failure(playback.playback_id)
    after = rows(ctx)
    unchanged_except(before, after, {'playbacks'})
    assert failed.status is PlaybackStatus.FAILED
    assert ctx.service._record_completion(playback, original, ctx.clock) == failed
    assert ctx.service.run_to_completion(playback.playback_id) == failed
    assert ctx.service.record_failure(playback.playback_id) == failed
    assert rows(ctx) == after

@pytest.mark.parametrize('bad', ['unfinished', 'missing', 'duplicate', 'foreign-id', 'extra-persisted'])
def test_completion_requires_exact_completed_persisted_action_set(ctx, bad):
    playback, original = start(ctx), actions(ctx)
    if bad == 'extra-persisted':
        extra = original[1].model_copy(update={'action_id': 'RL-ACTION-EXTRA-PERSISTED'})
        ExecutionService(ctx.store.uow_factory, clock=ctx.clock.now).create(extra)
    if bad != 'unfinished':
        complete_actions(ctx)
    supplied = original
    if bad == 'missing':
        supplied = original[:-1]
    elif bad == 'duplicate':
        supplied = (*original[:-1], original[0])
    elif bad == 'foreign-id':
        supplied = (original[0].model_copy(update={'action_id': 'RL-ACTION-OTHER'}), *original[1:])
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
        raise AssertionError('completed receipt must not guard or read clock')
    monkeypatch.setattr(playback_module, 'guard_execution_current', forbidden)
    monkeypatch.setattr(ctx.clock, 'now', forbidden)
    assert ctx.service._record_completion(playback, original, ctx.clock) == completed
    assert ctx.service.run_to_completion(playback.playback_id) == completed
    assert rows(ctx) == before
```

- [ ] **Step 3: Add terminal competition and conditional-update seam tests.**

```python
def test_completion_and_historical_failure_have_one_terminal_winner(ctx, monkeypatch):
    playback, original = start(ctx), actions(ctx)
    complete_actions(ctx)
    before, token = rows(ctx), state(ctx).token
    barrier, thread_state, crossed = Barrier(2, timeout=5), local(), set()
    real_get = SqlAlchemyExecutionRepository.get_playback
    def synchronized_get(repository, playback_id):
        value = real_get(repository, playback_id)
        if getattr(thread_state, 'first', False):
            thread_state.first = False
            crossed.add(id(repository._connection))
            barrier.wait()
        return value
    monkeypatch.setattr(SqlAlchemyExecutionRepository, 'get_playback', synchronized_get)
    def run(call):
        thread_state.first = True
        try:
            return ('success', call())
        except ImmutableRecordConflict as error:
            return ('conflict', error)
        except OperationalError as error:
            code = getattr(error.orig, 'sqlite_errorcode', None)
            if code is not None and (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                return ('lock', error)
            barrier.abort()
            raise
        except BaseException:
            barrier.abort()
            raise
    with ThreadPoolExecutor(max_workers=2) as pool:
        left = pool.submit(run, lambda: ctx.service._record_completion(playback, original, ctx.clock))
        right = pool.submit(run, lambda: ctx.service.record_failure(playback.playback_id))
        results = (left.result(timeout=15), right.result(timeout=15))
    monkeypatch.undo()
    assert len(crossed) == 2
    with ctx.store.uow_factory() as uow:
        durable = uow.execution.get_playback(playback.playback_id)
    successful = [result for kind, result in results if kind == 'success']
    assert successful and all(result == durable for result in successful)
    after = rows(ctx)
    unchanged_except(before, after, {'case_projection', 'playbacks', 'outcome_observations'})
    assert len(after['playbacks']) == len(before['playbacks']) == 1
    assert after['playbacks'][0]['payload_json'] == serialize_model(durable)
    added = tuple(row for row in after['outcome_observations'] if row not in before['outcome_observations'])
    assert all(row in after['outcome_observations'] for row in before['outcome_observations'])
    increment = int(durable.status is PlaybackStatus.COMPLETED)
    assert state(ctx).token == token.model_copy(update={'generation': token.generation + increment})
    prior_projection, actual_projection = dict(before['case_projection'][0]), dict(after['case_projection'][0])
    prior_projection['proposal_generation'] += increment
    prior_projection.pop('updated_at')
    actual_projection.pop('updated_at')
    assert actual_projection == prior_projection
    if durable.status is PlaybackStatus.FAILED:
        assert added == ()
    else:
        assert len(added) == 10
        observations = ctx.service.observations(ctx.decision.decision_id)
        assert {row['payload_json'] for row in added} == {serialize_model(o) for o in observations}
        assert {o.metric for o in observations} == {metric for metric, _, _, _ in playback_module._OUTCOMES}
        assert all(o.playback_id == playback.playback_id and o.decision_id == playback.decision_id for o in observations)

def test_terminal_update_rechecks_status_after_validation(ctx, monkeypatch):
    playback = start(ctx)
    completed = playback.model_copy(update={'status': PlaybackStatus.COMPLETED, 'completed_at': ctx.clock.now()})
    failed = playback.model_copy(update={'status': PlaybackStatus.FAILED, 'failed_at': ctx.clock.now(), 'error_code': 'PLAYBACK_EXECUTION_FAILED'})
    with ctx.store.uow_factory() as uow:
        connection, injected = uow.execution._connection, []
        original = connection.execute
        def execute(statement, *args, **kwargs):
            if getattr(statement, 'is_update', False) and statement.table.name == 'playbacks' and not injected:
                injected.append(True)
                original(update(playbacks).where(playbacks.c.playback_id == playback.playback_id).values(
                    status=failed.status.value, failed_at=failed.failed_at,
                    error_code=failed.error_code, payload_json=serialize_model(failed)))
            return original(statement, *args, **kwargs)
        monkeypatch.setattr(connection, 'execute', execute)
        with pytest.raises(ImmutableRecordConflict, match='terminal'):
            uow.execution.update_playback(completed)
        assert injected == [True]
        assert uow.execution.get_playback(playback.playback_id) == failed
        # Exit without commit; simulated competing write is test-local.
```

- [ ] **Step 4: Run RED before changes.**

Run `.venv/bin/python -m pytest tests/finance/test_playback_currentness.py -q -m 'not fabric_live' -o addopts=''`. Expected RED is missing guard calls, stale writes, completion trusting supplied/incomplete action state, historical clock reads, and unconditional terminal UPDATE. Dependency failures are not valid RED. Record actual behavior rather than asserting a predetermined failure count.

- [ ] **Step 5: Apply the minimal service changes.**

Import the helper in `playback.py`. In `start`, replace the unconditional insert/commit pair with:

```python
            inserted = uow.execution.insert_playback_if_absent(playback)
            if inserted:
                guard_execution_current(uow, decision.decision_id)
                uow.commit()
```

Keep its existing early historical receipt return and post-UoW canonical read unchanged. Replace `_fill_draft` completely:

```python
    def _fill_draft(self, action: ExecutionAction) -> None:
        with self._uow_factory() as uow:
            shell = uow.execution.get_draft_artifact(action.action_id)
            filled = shell.model_copy(update={'subject': _DRAFT_SUBJECT, 'body': _DRAFT_BODY})
            if shell.subject is not None:
                uow.execution.fill_draft_artifact(filled)
                return
            guard_execution_current(uow, shell.decision_id)
            uow.execution.fill_draft_artifact(filled)
            uow.commit()
```

In `_record_completion`, remove the pre-UoW `recorded_at` and `action_ids` assignments. Replace the initial block from `current = ...` through the existing Decision/Case reads with:

```python
            current = uow.execution.get_playback(playback.playback_id)
            normalized = playback.model_copy(update={
                'status': current.status, 'completed_at': current.completed_at,
                'failed_at': current.failed_at, 'error_code': current.error_code})
            if normalized != current:
                raise PlaybackStateError('Playback identity differs from canonical record')
            if current.status is not PlaybackStatus.IN_PROGRESS:
                return current
            canonical_actions = uow.execution.list_actions(decision_id=current.decision_id)
            expected_kinds = tuple(step.action_kind for step in PRODUCTION_STEPS)
            if (
                tuple(action.kind.value for action in canonical_actions) != expected_kinds
                or len({action.action_id for action in canonical_actions}) != len(expected_kinds)
                or any(action.status is not ExecutionStatus.COMPLETED for action in canonical_actions)
                or tuple(action.model_copy(update={'status': ExecutionStatus.PLANNED}) for action in actions)
                != tuple(action.model_copy(update={'status': ExecutionStatus.PLANNED}) for action in canonical_actions)
            ):
                raise PlaybackStateError('Playback requires the exact completed Decision action set')
            decision = guard_execution_current(uow, current.decision_id)
            case = uow.cases.get_case(current.case_id)
            recorded_at = clock.now()
            action_ids = {action.kind: action.action_id for action in canonical_actions}
```

Preserve the existing observation-construction loop, completion model, single commit, metrics/constants, and source labels verbatim. `run_to_completion`, `_complete_action`, `record_failure`, public historical reads, and existing authorization logic need no production change.

- [ ] **Step 6: Make only the terminal UPDATE conditional.**

In `SqlAlchemyExecutionRepository.update_playback`, retain existing validation. Assign the current UPDATE result to `result`, replace its WHERE with the following, and add the rowcount check immediately after execute:

```python
            .where(
                playbacks.c.playback_id == playback.playback_id,
                playbacks.c.status == PlaybackStatus.IN_PROGRESS.value,
            )
```

```python
        if result.rowcount != 1:
            raise ImmutableRecordConflict('Playback already has a terminal result')
```

Do not add schema changes or a new port method. If the terminal CAS loses during aggregate completion, the surrounding UoW rolls back tentative observations and proposal generation too. If it loses during cleanup, no other rows were written.

- [ ] **Step 7: Verify and request bounded independent review.**

Run the focused command from Step 4 to GREEN, then `.venv/bin/python -m pytest tests/execution tests/finance -q -m 'not fabric_live' -o addopts=''`. Existing `tests/execution/test_playback.py` protects frozen metric values, permanently unsent draft content, authorization fixture behavior, repeated/concurrent legacy start, and divergent record rejection. Do not regenerate those fixtures or change expected simulation values.

Run scoped Pyright with `.venv/bin/python`, Ruff check/format check, and `git diff --check`. Resolve test fixture typing with concrete narrowing/local factory casts; do not change repository Protocols. Report real RED/GREEN, exact row rollback/terminal race outcomes, dependency commits, and warning provenance in `.superpowers/sdd/finance-playback-currentness-task-report.md`.

Commit only playback service, named repository method, and focused tests with `git commit -m 'feat: guard playback writes and preserve terminal outcomes'` after staging their exact paths. Independent review is required before auth/API, all-option simulation, or reviewed mail work. Parent-owned scratch drafts remain unstaged.

## Acceptance boundary

This bounded plan improves currentness and terminal safety only. It does not implement the complete approved option-execution/mail design, authenticate configured Alex, or make simulation equivalent to sent mail. Those gates remain explicit; no partial independent workflow may be activated from this increment alone.

Self-review completed: the fixture reuses the accepted disposable Case/Analysis setup with a shared monotonic Finance/playback clock; repository names/signatures match inspected source; each actual mutation has a fresh guard; both receipt paths bypass guard/commit/clock; supplied action tuples are checked against freshly completed canonical coverage; divergent filled history and a tentative-observation terminal loss have explicit rollback tests. The accepted narrow status predicate is tested both with real two-connection competition and directly between SELECT validation and UPDATE. No production or test-source files were changed while writing this draft. Parent approved the additions and the queued-planning dependency before adoption; this task still requires its own independent review before the next production increment.
