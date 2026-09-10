# Power BI display-value correction report

## Status

Implementation is complete locally and included in the scoped task commit described
in the parent handoff. No push, deployment, publication, receipt activation, live
case/analysis/decision request, approval, simulation, or permission change was made.

## Bounded correction

- Added read-only SQL display projections for the six canonical option kinds, five
  action kinds, four web-rendered action states, ten outcome metrics, and the two
  observation kinds. Comparisons are case-sensitive and length-sensitive; unknown
  values use explicit not-recognized labels.
- Kept all original fields and UTF-16LE identity keys. Main option/action/chart
  visuals use display aliases; Source details retains raw option names/kinds,
  blocker/role codes, action kinds/statuses, metrics, observation kinds, and keys.
- Removed unknown blocker/role codes from main prose while projecting only validated
  raw scalar code lists into Source details. No JSON payload entered the model.
- Added `RelatedColumnDetails.GroupByColumns` for option/action aliases at their
  existing composite identity grain, and for metric/observation aliases with their
  raw grouping fields. No relationship, import-mode, source-row, numeric, unit,
  variance, selection, state, scope, or visibility-gate change was made.
- Grouped option labels are extracted only behind the existing exact-one-row guard
  using `CONCATENATEX`, not `SELECTEDVALUE`, `FIRST`, or `MAX`. Current action and
  observation summaries retain their current-decision/multiple-state semantics and
  derive a single distinct SQL display label with `SELECTCOLUMNS`.
- The Actions and outcomes chart was reduced from 284px to 176px high to fit a
  96px raw outcome Source-details table beneath it. Native fit/render review remains
  a release gate.

## TDD and verification

RED:

```text
.venv/bin/python -m pytest tests/fabric/test_report_generators.py -q --tb=short
```

Result: 6 expected failures/52 passes for missing friendly bindings, display
columns, grouping metadata, and exact-row grouped scalar extraction. Follow-up RED
checks covered raw diagnostic bindings, exact trailing-space handling,
production-order OTIF wording, and distinct SQL status/observation labels.

GREEN focused result: `60 passed` for the generator suite. The locked TOM parser
deserialized the final model, verified compatibility level >= 1400, and asserted
the exact ordered grouping references for every column. A serializer probe was
used to confirm TOM 19.114.8's supported TMDL syntax (`relatedColumnDetails` with
repeated `groupByColumn` entries); temporary probe code was removed.

All three supported checks exited 0:

```text
.venv/bin/python -m fabric.report_pages --check fabric/power-bi/SupplyResponse.Report/definition
.venv/bin/python -m fabric.report_model --check fabric/power-bi/SupplyResponse.SemanticModel/definition fabric/reporting/queries
.venv/bin/python -m fabric.report_contract --check
```

Final artifact digest:
`63b06875255245e3ac1897ec352dfa68d7807b1aa9d6b3969f69b35a7f21e4bc`.

Parent fresh verification ran the complete bounded reporting suite with network
access for its locked NuGet restore: `186 passed` (60 generator, 86 project, 40
activation), with only the existing Starlette/httpx deprecation warning. In this
agent's sandboxed run, the same suite's isolated deploy dry-run child intentionally
omitted `NUGET_PACKAGES` and could not reach nuget.org; the exact failed test was
rerun with network escalation and passed:

```text
NUGET_PACKAGES=/Users/willmacdonald/.nuget/packages .venv/bin/python -m pytest \
  tests/fabric/test_power_bi_project.py::test_deploy_dry_run_is_deterministic_and_does_not_authenticate \
  -q --tb=short
```

Both this agent and parent received `succeeded`, 0 errors, 0 warnings from offline
author validation. Parent also freshly passed all three generator/model/digest
checks and `git diff --check`.

The local SQL integration module collected successfully but all 138 cases skipped
because `SUPPLY_RESPONSE_LOCAL_REPORTING_SQL_URL` is not configured. This is not a
PASS. Parent-owned execution on the fresh dedicated test VM is pending explicit
upload/run approval. The isolated runner needs exactly these four synced files:

- `fabric/reporting/queries/SavedOptions.sql`
- `fabric/reporting/queries/ActionOutcomes.sql`
- `fabric/report_model.py` (the SQL type/order oracle imports `TYPES`)
- `tests/integrations/test_saved_analysis_reporting_sql.py`

## Explicit limitations

The TOM check proves static model parsing and grouping references; it does not
execute DAX. The offline author validates PBIR shape without native Power BI data
or rendering. Native Power BI-generated-query identity grouping, visual fit/render,
and exact record navigation acceptance remain unavailable and unclaimed. Actual
SQL execution was subsequently completed by the parent; see the addendum below.

## Parent runtime addendum

User specifically approved transfer of the four files above and synthetic testing
on private `supply-response-test.exe.xyz`. The first actual run exposed error 8711
(69 passed, 1 failed) from the paired ordered STRING_AGG calls in SavedOptions.
A new 12-item readable/raw list regression reproduced the error; separating the
raw aggregate into its own scalar CROSS APPLY fixed it while preserving the same
validation and numeric ordering. Final formatted source/test hashes match the
isolated remote copy. All **139 SQL cases passed in 16.70s** and the runner removed
its fresh database. All **186 local reporting tests** and all three artifact
checks also passed. Independent `sql_aggregate_review` approved with no findings.
Final corrected artifact digest:
`b723bb1c8dd4daec9bfb500339dace6907729931f39df2f6dd360d49c0050be4`.
Full evidence: `docs/reviews/2026-09-09-planner-spec-conformance.md`.
No live data, push, merge, deployment, publication or receipt activation occurred.
Native Power BI/DAX, fit, access and exact navigation remain unverified.
