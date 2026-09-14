# ExecutionService currentness task report

## Outcome and scope

Implemented the bounded `ExecutionService` wiring against dispatch base `f1c06a1` and accepted helper review `72ee91e`:

- new action creation guards in the same transaction after a successful insert and before commit;
- start and retry guard after transition validation and before attempt creation;
- completion guards after action/attempt validation and before timestamps or writes;
- identical stored creation receipts return without guard or commit;
- fail, cancel, history, and attempts remain historical exact-target operations without currentness guards.

Only `ExecutionService` methods/import in `services/execution/worker.py`, the focused test, and this report changed. `ActionPlanningWorker`, persistence/schema, planner options, playback, API/auth/UI, email, live integrations, deployment, and activation were not changed.

## TDD evidence

Behavioral RED was run before editing `worker.py`; the accepted helper imported successfully:

```text
.venv/bin/python -m pytest tests/finance/test_execution_service_currentness.py -q -m 'not fabric_live' -o addopts=''
26 failed, 6 passed, 8 skipped in 2.58s
```

The failures included all four missing independent generation advances, all four stale advances writing instead of raising, the absent guard seam in receipt/rollback/cleanup tests, and all four races allowing both operations to succeed.

First production GREEN:

```text
32 passed, 8 skipped in 2.94s
```

Final focused rerun after assertion completion:

```text
32 passed, 8 skipped in 3.00s
```

The eight skips are intentional: four stale and four race variants do not apply to legacy policy.

## Acceptance mapping

- `test_each_advancing_transaction_has_one_fresh_guard`: create/start/retry/complete each advance exactly one independent proposal generation, preserve legacy generation, create the exact expected execution journal delta, and retain the correct durable action/attempt.
- `test_stale_advance_writes_nothing`: each independent advancing operation rejects replaced selection history and preserves every database row.
- `test_identical_historical_create_receipt_is_no_write_and_conflicts_survive`: an exact stored receipt bypasses guard and commit even when stale; an immutable conflict remains a conflict.
- `test_failure_after_guard_rolls_back_all_rows_and_generation`: injected failure after the real guard rolls back action rows and the proposal CAS for every advancing operation and both workflow versions.
- `test_historical_cleanup_stays_exact_target_and_never_guards`: fail/cancel work on stale history, never guard, mutate only the target attempt/projection/event, and preserve nonvacuous sibling history.
- `test_invalid_transition_and_wrong_attempt_leave_every_row_unchanged`: validation errors occur before guard/write; read-only history and attempt queries mutate nothing.
- `test_advancing_transaction_races_replacement_without_loser_residue`: real two-connection create/start/retry/complete races synchronize at the first transaction read, allow exactly one durable winner and one generation increment, reject unrelated database exceptions, preserve the complete losing side, verify exact execution results or exact replacement selection/review supersession journals, and compare the full Case projection except its asserted generation/selection/update timestamp.

The advancing and rollback fixtures run both independent-Finance and legacy workflows. Each race ran the independent workflow against a real file SQLite database. Only driver-coded SQLite `BUSY`/`LOCKED` contention is classified as an allowed race loser; other `OperationalError` and non-database exceptions abort and propagate.

## Verification

```text
.venv/bin/python -m pytest tests/finance/test_execution_service_currentness.py -q -m 'not fabric_live' -o addopts=''
32 passed, 8 skipped in 3.00s

.venv/bin/python -m pytest tests/finance tests/execution -q -m 'not fabric_live' -o addopts=''
234 passed, 11 skipped in 10.60s

.venv/bin/pyright --pythonpath .venv/bin/python services/execution/worker.py tests/finance/test_execution_service_currentness.py
0 errors, 0 warnings, 0 informations

.venv/bin/ruff check --ignore BLE001 services/execution/worker.py tests/finance/test_execution_service_currentness.py
All checks passed!

.venv/bin/ruff format --check services/execution/worker.py tests/finance/test_execution_service_currentness.py
2 files already formatted

git diff --check
passed
```

All pytest commands excluded `fabric_live`; no live calls ran. Ruff's scoped invocation retains the existing `BLE001` exclusion solely because the untouched `ActionPlanningWorker` intentionally catches `Exception` in this shared file. No broad lint cleanup or unrelated production edit was made. Frozen fixtures were unchanged.

The normal commit hook was attempted and blocked on that same inherited
`services/execution/worker.py:90` `BLE001`. Parent verified the staged nine-line
service delta, prohibited changing the unrelated `ActionPlanningWorker` line,
and authorized a one-command `core.hooksPath=/dev/null` commit after the manual
scoped checks above. No persistent hook configuration was changed; the focused
test file passed unfiltered Ruff and `worker.py` passed with only `BLE001`
ignored.

## Self-review and remaining boundary

The guard is called exactly once only for advancing transactions that will commit. It reuses the existing Unit of Work and owns no commit, connection, savepoint, or retry. Insert-before-guard is limited to new transaction-local creation so stale inserts roll back. Validation remains before guard where specified, and exact replay returns before guard/commit.

No known concerns remain in this bounded increment. This does not activate independent execution and does not guard `ActionPlanningWorker`, playback, or external effects; those remain separate required gates.

## Independent-review correction

The test-only follow-up at base `2731943` tightened
`test_historical_cleanup_stays_exact_target_and_never_guards`: it now compares
all sibling action projection, attempt, and event rows exactly; proves the prior
event journal is an immutable prefix; requires exactly one new target event with
the exact action, Decision, attempt, transition, and failure-code fields; and
compares the target projection and attempt canonical payloads with the returned
domain values. Production code was unchanged. The corrected focused suite passed
`32 passed, 8 skipped in 3.05s`.
