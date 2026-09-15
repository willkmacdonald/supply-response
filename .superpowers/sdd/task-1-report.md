# Task 1 report: option-aware action planning

## Status

DONE

## Implementation

- Extended `ExecutionAction` with backward-compatible optional `purpose`, `expected_result`, and `execution_mode` display metadata.
- Changed `plan_actions` to require the immutable approved `AnalysisVersion`, reject rejected/non-executable/absent/mismatched options, parse `operational_snapshot_json`, and build only the action kinds for expedite, transfer, resequence, or combined.
- Kept deterministic action and draft artifact ID formulas unchanged.
- Added snapshot-derived action text for Alpha's 3,000-unit September 6 expedite at $7.50 per unit, the 1,500-unit Dallas-to-Chicago September 5 transfer, the priority customer order targeted by resequencing, and the disruption status update.
- Kept preparation/coordinated actions owned by Alex, the status update system-owned, draft preparation labeled `communication_preparation`, and simulated coordination/status actions labeled `simulation`.
- Updated `ActionPlanningWorker` to load the Decision's approved Analysis within the claimed transaction and pass the same Decision/Analysis pair through the planner and automated-test `after_plan` seam.
- Configured the API composition worker for both legacy and independent-finance workflows.
- Exposed independent action-planning retry while retaining `INDEPENDENT_EXECUTION_DEFERRED` for individual action retry and playback.
- Updated existing planner consumers and fault-injection test doubles for the intentional two-argument planner interface.

## Files

- `.superpowers/sdd/task-1-report.md`
- `data/domain/execution.py`
- `services/execution/planner.py`
- `services/execution/worker.py`
- `apps/api/app/dependencies.py`
- `apps/api/app/test_support.py`
- `apps/api/app/routes/cases.py`
- `apps/api/app/routes/execution.py`
- `tests/execution/conftest.py`
- `tests/execution/test_action_planning.py`
- `tests/finance/test_planning_worker_currentness.py`
- `tests/api/test_finance_journey.py`
- `tests/finance/test_execution_service_currentness.py`
- `tests/api/test_failure_contracts.py`
- `tests/api/test_runtime_progression.py`
- `tests/integration/test_store_contract.py`

## TDD evidence

### RED

Before production changes:

```text
.venv/bin/python -m pytest tests/execution/test_action_planning.py tests/finance/test_planning_worker_currentness.py -q -o addopts=''
21 failed, 21 passed in 2.74s
```

The failures were the expected missing-feature failures: `plan_actions` accepted only one argument, and the worker called two-argument planner test doubles with only a Decision.

### GREEN

After the first implementation pass, the same suite reported 2 content failures and 40 passes. Those failures identified snapshot labels rendered as `Dal`/`Chi` and the need to derive the resequence target from snapshot priority when no order was fully protected in the predicted outcome. After the bounded correction:

```text
.venv/bin/python -m pytest tests/execution/test_action_planning.py tests/finance/test_planning_worker_currentness.py -q -o addopts=''
42 passed in 2.85s
```

Final required focused verification:

```text
.venv/bin/python -m pytest tests/execution/test_action_planning.py tests/finance/test_planning_worker_currentness.py tests/api/test_finance_journey.py -q -o addopts=''
43 passed, 1 warning in 3.16s
```

## Regression and quality verification

```text
.venv/bin/python -m pytest tests/execution tests/finance tests/api -q -o addopts=''
347 passed, 11 skipped, 1 warning in 28.95s

.venv/bin/python -m pytest tests/integration/test_store_contract.py -q -o addopts=''
17 passed, 15 skipped in 1.00s

.venv/bin/ruff check <all changed Python files>
All checks passed!

uv run pyright <changed production Python files>
0 errors, 0 warnings, 0 informations
```

## Self-review

- Confirmed the option-to-action sequences exactly match the approved Task 1 brief.
- Confirmed baseline, alternate supplier, rejected, absent-option, and Decision/Analysis mismatch cases raise `ValueError` before any action insertion.
- Confirmed deterministic action/draft IDs are unchanged and retry/reprocessing remains idempotent.
- Confirmed the Analysis is loaded inside the worker's claimed transaction and the Decision/Analysis pair reaches both test seams unchanged.
- Confirmed an independent expedite Decision remains pending until final Alex approval is processed, can fail planning once, exposes planning retry, and completes with exactly three option-specific actions.
- Confirmed independent individual-action retry and playback both still return `INDEPENDENT_EXECUTION_DEFERRED`.
- Confirmed no deployment, tenant permission change, email send, or live-data mutation was performed, and `.pnpm-store/` was not touched.

## Concerns

- No functional concerns. The focused and broader API suites emit the pre-existing Starlette `TestClient`/httpx deprecation warning. Pyright also reports that a newer tool version is available; neither affects this task.
