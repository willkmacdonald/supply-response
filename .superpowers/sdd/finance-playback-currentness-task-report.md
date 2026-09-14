# Playback currentness task report

## Outcome and scope

Implemented the bounded playback safeguards from base `b0dc14c`, following accepted helper, ExecutionService, and queued-planning dependencies through `a7e2d96`.

- New playback creation, empty draft fill, and aggregate completion each perform one fresh same-UoW currentness guard.
- Exact existing playback and filled-draft receipts return without guard, commit, or clock access.
- Completion validates canonical playback identity and the exact five completed persisted actions before creating observations.
- Completed and failed playback history remains terminal and readable after proposal replacement.
- `update_playback` now performs a terminal status CAS; a concurrent loss raises the existing `ImmutableRecordConflict`, rolling back observations and proposal generation with the caller transaction.

Only `services/execution/playback.py`, `SqlAlchemyExecutionRepository.update_playback`, the focused test, and this report changed. Worker/outbox behavior, ExecutionService, API/auth/UI, schemas, options, mail, tenant/live integrations, deployment, and activation were untouched.

## TDD evidence

Behavioral RED ran with the complete focused test before production edits:

```text
.venv/bin/python -m pytest tests/finance/test_playback_currentness.py -q -m 'not fabric_live' -o addopts=''
19 failed, 2 passed in 3.85s
```

Failures covered all three stale writes, all missing guard generation/rollback seams, both historical receipt seams, failed terminal replay, all five exact-action-set variants, completed receipt handling, and the unconditional terminal UPDATE.

First GREEN:

```text
21 passed in 3.71s
```

Final focused rerun after formatting/fixture typing cleanup:

```text
21 passed in 3.80s
```

## Acceptance mapping

- `test_each_playback_write_rejects_stale_approval_without_any_rows`: start/fill/completion reject stale independent approval and preserve every row.
- `test_each_playback_write_commits_one_fresh_guard`: each actual write advances exactly one generation and only its allowed aggregate rows; completion produces the exact synthetic observation set.
- `test_failure_after_guard_rolls_back_playback_transaction`: injected post-guard failure rolls back proposal generation and all tentative playback/draft/observation writes for each mutation.
- `test_exact_start_and_filled_draft_history_need_no_guard_clock_or_commit`: exact historical playback and draft receipts require neither currentness nor clock/commit.
- `test_divergent_filled_draft_history_remains_immutable_when_stale`: immutable draft mismatch is detected before currentness and writes nothing.
- `test_terminal_conflict_rolls_back_tentative_observations_and_guard`: an injected terminal CAS loss observes ten transaction-local observations, then rolls them and the guard back.
- `test_failed_playback_remains_failed_and_cleanup_is_target_only`: historical failure cleanup changes only the playback and every later completion/failure replay returns the same failed receipt without writes.
- `test_completion_requires_exact_completed_persisted_action_set`: unfinished, missing, duplicate, foreign-id, and extra-persisted variants all reject without writes.
- `test_completed_receipt_remains_readable_after_replacement`: completed receipt replay works after replacement without guard or clock.
- `test_completion_and_historical_failure_have_one_terminal_winner`: two real file-SQLite transactions produce one durable terminal value; completed wins retain exactly ten canonical observations and one generation, failed wins retain none and no generation, and unrelated database errors propagate.
- `test_terminal_update_rechecks_status_after_validation`: the repository UPDATE rechecks `in_progress` after validation and raises the established conflict when a terminal row wins.

## Verification

```text
.venv/bin/python -m pytest tests/finance/test_playback_currentness.py -q -m 'not fabric_live' -o addopts=''
21 passed in 3.80s

.venv/bin/python -m pytest tests/execution tests/finance -q -m 'not fabric_live' -o addopts=''
272 passed, 11 skipped in 16.92s

.venv/bin/pyright --pythonpath .venv/bin/python services/execution/playback.py services/persistence/store.py tests/finance/test_playback_currentness.py
0 errors, 0 warnings, 0 informations

.venv/bin/ruff check services/execution/playback.py services/persistence/store.py tests/finance/test_playback_currentness.py
All checks passed!

.venv/bin/ruff format --check services/execution/playback.py services/persistence/store.py tests/finance/test_playback_currentness.py
3 files already formatted

git diff --check
passed
```

Every pytest command excluded `fabric_live`; no live calls ran. Frozen playback constants, metrics, drafts, identifiers, and legacy fixtures were unchanged.

## Self-review and remaining boundary

Every new advancing mutation uses its existing UoW and owns no nested connection, retry, or external effect. Historical terminal paths return before clock/guard. Completion uses freshly loaded action IDs and validates exact normalized immutable equality, completion statuses, order, uniqueness, and expected kinds. Terminal conflict remains the existing exception type and rolls back the full caller transaction.

No known concerns remain in this bounded increment. This does not authenticate configured Alex, expand option execution, send mail, prove Fabric-native concurrency, expose APIs, or activate independent Finance execution.
