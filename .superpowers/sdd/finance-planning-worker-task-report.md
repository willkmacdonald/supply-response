# Planning worker currentness task report

## Outcome and scope

Implemented the bounded planning-worker currentness increment from base `17d9b45`, consuming the independently accepted currentness helper and ExecutionService through `7de52e1`.

- `ActionPlanningWorker` guards the planning transaction before planning and uses a separate guarded recovery transaction for independent-Finance failures.
- Stale planning returns `False` and conditionally retires only its outbox event with `EXECUTION_PROPOSAL_STALE`.
- Lost/stale recovery rolls back before event-only bookkeeping; current recovery conditionally records the original error and updates its Case.
- Outbox claims exclude terminal-stale events in both candidate selection and conditional UPDATE.
- `record_outbox_failure_if_current` compares the full processing state and never steals active, processed, terminal, or changed work.
- Legacy recovery retains the existing error/Case behavior.

Only `ActionPlanningWorker`, the narrow persistence port/constant and SQL repository methods, the focused test, and this report changed. ExecutionService, playback, API/auth/UI, schema, planner options, tenant/live integrations, mail, deployment, and activation were untouched.

## TDD evidence

Initial RED, before any production edit:

```text
.venv/bin/python -m pytest tests/finance/test_planning_worker_currentness.py -q -m 'not fabric_live' -o addopts=''
ImportError: cannot import name 'EXECUTION_PROPOSAL_STALE_ERROR'
1 error in 0.25s
```

Intermediate behavioral RED after the contract/repository patch but before replacing the worker:

```text
9 failed, 7 passed in 1.27s
```

The nine failures covered all stale claim variants, missing current guard generation, replacement during recovery, partial-plan recovery, lost conditional bookkeeping, stale recovery CAS, and integrity-error propagation. The constant, conditional repository method, terminal claim filters, and UPDATE recheck were added in one patch, so this intermediate run demonstrates the old worker failures but does not independently demonstrate claim-filter RED. This is an explicit ordering deviation, not a retrospective TDD claim.

First complete GREEN:

```text
16 passed in 1.24s
```

## Acceptance mapping

- `test_stale_worker_retires_event_without_success_and_never_reclaims`: all automatic/unattempted/Decision-specific claim variants retire stale work once, report no success, and cannot reclaim it.
- `test_current_planning_commits_one_guard_and_exact_plan`: one guard generation, exact five-action plan/journals, Case progression, processed event, callback after commit, and replay no-write behavior.
- `test_replacement_between_failed_attempt_and_recovery_preserves_new_case`: failed planning transaction exits before replacement; stale recovery preserves all newer Case rows and records only terminal event bookkeeping.
- `test_current_failure_recovery_commits_one_guard_and_rolls_back_partial_plan`: partial planning rolls back; a distinct recovery UoW guards once, records the original conflict, updates only the Case projection, and never calls the success callback.
- `test_lost_conditional_bookkeeping_rolls_back_recovery_guard_without_case_write`: a lost conditional event UPDATE causes no commit, rolls back the recovery guard, and cannot update the Case.
- `test_recovery_guard_cas_rollback_precedes_event_only_transaction`: a stale recovery guard rolls back before the separate terminal event-only transaction.
- `test_recovery_integrity_error_is_not_staleness`: integrity failure propagates unchanged and is recorded under the original planner error rather than stale.
- `test_conditional_bookkeeping_never_overwrites_terminal_or_active_rows`: processed, terminal-stale, and unexpired claimed rows are exact no-writes.
- `test_two_terminal_bookkeepers_increment_once`: two real file-SQLite connections yield one conditional winner and exactly one terminal attempt increment; only driver-coded SQLite BUSY/LOCKED is an allowed loser.
- `test_claim_update_rechecks_terminal_exclusion_after_candidate_selection`: all three claim methods recheck the complete terminal exclusion in their UPDATE after candidate selection.

Existing legacy action-planning and decision-outbox suites provide the preserved corrupt-event, planner-error projection, claim expiry, and canonical-payload compatibility coverage.

## Verification

```text
.venv/bin/python -m pytest tests/finance/test_planning_worker_currentness.py -q -m 'not fabric_live' -o addopts=''
16 passed in 1.24s

.venv/bin/python -m pytest tests/execution/test_action_planning.py tests/persistence/test_decision_outbox.py tests/finance -q -m 'not fabric_live' -o addopts=''
279 passed, 11 skipped in 12.56s

.venv/bin/pyright --pythonpath .venv/bin/python services/execution/worker.py services/persistence/ports.py services/persistence/store.py tests/finance/test_planning_worker_currentness.py
0 errors, 0 warnings, 0 informations

.venv/bin/ruff check services/execution/worker.py services/persistence/ports.py services/persistence/store.py tests/finance/test_planning_worker_currentness.py
All checks passed!

.venv/bin/ruff format --check services/execution/worker.py services/persistence/ports.py services/persistence/store.py tests/finance/test_planning_worker_currentness.py
4 files already formatted

git diff --check
passed
```

Every pytest command excluded `fabric_live`; no live calls ran. Ruff did not require the permitted BLE001 annotations under the repository's scoped rule selection, so none were added. Frozen fixtures were unchanged.

## Self-review and remaining boundary

The planning transaction and recovery transaction never share a failed UoW. Conditional-loss and staleness paths exit without committing the guard CAS. Only `StaleProposal`-derived currentness is terminal-stale; integrity and unrelated operational failures remain distinct. Candidate and UPDATE predicates share the same event type, availability, processed, claim readiness, Decision scope, unattempted, and terminal-stale filters.

No known concerns remain in this bounded increment. This is not independent-Finance activation, native Fabric concurrency proof, playback protection, authenticated retry behavior, or all-option execution support.
