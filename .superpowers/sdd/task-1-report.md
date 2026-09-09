# Task 1 report: immutable analysis base

## Changes

- Added `analytics.report_scalar`, a strict JSON scalar validation helper for text, flags, non-negative integers, fixed two-decimal money, ISO dates, and ISO instants.
- Added `analytics.saved_analyses`, projecting one row per immutable `app.analysis_versions` record with separately reported payload and snapshot availability.
- Snapshot extraction is guarded against non-object payload roots and root extraction row multiplication; malformed or identity-mismatched snapshots fail closed.
- Added the Task 1 SQL acceptance module. Future `saved_options` tests remain in the module for Task 2 and are not implemented by this task.
- Advanced static analytics-view inventory expectations from four to five views.

## RED/GREEN verification

The required local command was run before and after SQL authoring:

```text
uv run --extra dev pytest tests/integrations/test_saved_analysis_reporting_sql.py -rs
42 skipped in 0.10s
```

The local SQL execution gate was not configured, so SQL semantics were skipped rather than reported as passing. An attempt to sync the scoped test to the authorized remote SQL VM for the missing-view RED checkpoint was rejected by the environment's source-upload safety review. The parent harness owner has the VM path and can perform that checkpoint.

Static contract tests after implementation:

```text
uv run --extra dev pytest tests/integrations/test_fabric_sql_scripts.py tests/integrations/test_saved_analysis_reporting_sql.py -rs
11 passed, 42 skipped in 0.10s
```

## Scope and deviations

Only `fabric/sql/002_analytics_views.sql`, `tests/integrations/test_saved_analysis_reporting_sql.py`, and additive expectations in `tests/integrations/test_fabric_sql_scripts.py` were changed. No saved-options view, infrastructure, credentials, health contract, or operational script was changed.

The supplied base view used `OPENJSON(a.payload_json) WITH` directly. This implementation wraps root extraction in an aggregate and requires an object root so a malformed array or duplicate parent extraction cannot multiply rows at the case/analysis grain.

## Concerns

- A real SQL Server run remains required before release; the local environment has no SQL URL and the remote source sync was blocked by policy.
- The future `saved_options` assertions are expected to remain red until Task 2 adds that view.

## Controller real-engine verification (after checkpoint 65502a3)

Controller synced this module first to the unchanged 67ddbb6 remote SQL source,
then ran `../.venv/bin/python run-reporting-tests.py -q
tests/integrations/test_saved_analysis_reporting_sql.py -k
"snapshot_is_full_length or strict_scalar_semantics or missing_duplicate_or_malformed"
--tb=short`. RED: 30 failed, 12 deselected; missing analytics.saved_analyses and
analytics.report_scalar, as expected. Synced checkpoint SQL and repeated exactly
the same command: GREEN, 30 passed, 12 deselected in 0.83s. Both executions used
fresh dedicated databases, applied packaged scripts twice, and removed only their
own generated test database afterward. SQL2022 x86_64 dedicated VM; no live calls.
The preceding remote-policy obstacle is resolved for controller-owned uploads.
