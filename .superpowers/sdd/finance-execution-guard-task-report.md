# Execution-currentness helper task report

## Outcome and scope

Implementation commit: `d9d3143`.

Implemented the bounded execution-currentness helper only:

- `check_execution_current` performs a read-only exact binding check for an approved Decision.
- `guard_execution_current` performs one proposal-generation CAS in the caller's Unit of Work and never commits, opens a connection, or retries.
- Legacy Decisions return without proposal reads or writes.
- The helper is intentionally not wired to any execution caller and is **not enforcement** by itself.

No callers, workers, APIs, authentication, UI, schema, email, deployment, live integration, or activation behavior changed. All feasible proposal options remain supported through the parameterized combined and transfer fixtures.

## TDD evidence

RED, run before `services/execution/currentness.py` existed:

```text
.venv/bin/python -m pytest tests/finance/test_execution_currentness.py -q -m 'not fabric_live' -o addopts=''
ERROR tests/finance/test_execution_currentness.py
ModuleNotFoundError: No module named 'services.execution.currentness'
1 error in 0.21s
```

First GREEN after adding the helper:

```text
23 passed, 3 skipped in 1.43s
```

The three skips are the intentional Cartesian-fixture exclusions: the two exact-review variants apply only to the high-cost option, and unexpected-review validation applies only to the low-cost option.

## Acceptance mapping

- `test_check_is_read_only_and_guard_uses_fresh_generation`: read-only check; exact token returned; independent guard advances exactly one generation per call; no journal/outbox/execution row changes.
- `test_guard_rolls_back_with_its_caller`: the caller can roll back the CAS; projection and all counted rows remain unchanged.
- `test_changed_binding_is_stale_but_history_stays_readable[selection]`: changed current selection is stale while the historical Decision remains readable.
- `test_changed_binding_is_stale_but_history_stays_readable[same-hash-analysis]`: same-material-hash replacement analysis is stale by exact analysis identity.
- `test_changed_binding_is_stale_but_history_stays_readable[decision]`: changed current Decision binding is stale without corrupting history.
- `test_exact_review_binding_is_checked[revision]`: exact Finance review revision is required.
- `test_exact_review_binding_is_checked[snapshot]`: exact immutable Finance review snapshot is required.
- `test_cas_failure_is_dedicated_stale_and_not_committed`: a proposal CAS loss maps to `ExecutionProposalStale`, preserves its cause, and commits nothing.
- `test_unrelated_database_errors_are_not_disguised[PersistenceIntegrityError]`: persisted corruption propagates unchanged.
- `test_unrelated_database_errors_are_not_disguised[OperationalError]`: unrelated database errors propagate unchanged.
- `test_low_cost_unexpected_review_is_stale`: low-cost evidence cannot acquire an unexpected Finance review.
- `test_rejected_decision_is_never_execution_current`: rejected Decisions cannot authorize execution.
- `test_legacy_guard_never_reads_or_mutates_proposals`: legacy behavior is preserved and proposal ports are not touched.

Every parameterized lifecycle/currentness test ran for both `RL-OPTION-COMBINED` and `RL-OPTION-TRANSFER` unless its named review precondition intentionally selected one branch.

## Final verification

```text
.venv/bin/python -m pytest tests/finance/test_execution_currentness.py -q -m 'not fabric_live' -o addopts=''
23 passed, 3 skipped

.venv/bin/python -m pytest tests/finance -q -m 'not fabric_live' -o addopts=''
178 passed, 3 skipped in 7.18s

.venv/bin/pyright --pythonpath .venv/bin/python services/execution/currentness.py tests/finance/test_execution_currentness.py
0 errors, 0 warnings, 0 informations

.venv/bin/ruff check services/execution/currentness.py tests/finance/test_execution_currentness.py
All checks passed!

.venv/bin/ruff format --check services/execution/currentness.py tests/finance/test_execution_currentness.py
2 files already formatted

git diff --check
passed
```

All pytest commands excluded `fabric_live`; no live calls ran. The accepted finalizer dependency was present at dispatch base `fcf4a07` (accepted finalizer lineage `75558c5`). The frozen legacy fixture was not modified.

## Self-review

- Only `StaleProposal` is translated; integrity and database failures remain distinguishable.
- The second state read closes the read-window before returning the token; the subsequent guard is the single mutation/CAS.
- Exact Decision, analysis id/hash, selection, review snapshot, and review revision bindings are compared.
- No internal transaction ownership was introduced.
- No known concerns remain. Caller wiring and activation are deliberately deferred.
