# Final report findings fix report

## Status

DONE_WITH_CONCERNS. All unblocked corrections are implemented. The protected
customer order option-comparison column remains intentionally unchanged pending
the user's resolution of the conflicting specifications. Updated SQL integration
tests were not run because this worktree has no configured SQL Server gate and
the separately authorized VM upload is controller-owned.

## Changes

- Projected `ranking.no_feasible_mitigation` as a nullable boolean from the exact
  saved analysis. Root/property duplicates, malformed types, invalid source
  identity, and a true flag conflicting with a recommendation remain unavailable.
  Legacy rankings without the new flag retain their recommendation.
- Rendered the explicit no-option answer only for a valid true flag. False,
  missing, null, malformed, duplicate, and conflicting states do not become a
  successful no-option result. Existing exact analysis scope and traditional
  walkthrough suppression remain intact.
- Added baseline parts-still-needed and response-cost facts to the overview and
  recommended order-line service-target exposure to the recommendation copy,
  preserving blank versus zero and avoiding currency assumptions.
- Regenerated the semantic-model artifacts and refreshed the packaged artifact
  digest to `00ed9d955f1e929eefc693a6df57e4ee50ff1261dca38a5be47f1da8c1393eae`.
- Corrected the activation checkpoint and clarified the Stage 6 deployment
  mechanism language in the Power BI README.

## TDD evidence

RED:

```text
.venv/bin/pytest tests/fabric/test_report_generators.py -o addopts='' -q
3 failed, 44 passed
```

The failures were the expected missing nullable boolean projection, missing
baseline comparison facts, and absent explicit no-feasible/recommended OTIF
bindings.

GREEN:

```text
.venv/bin/pytest tests/fabric/test_report_generators.py -o addopts='' -q
47 passed in 2.57s
```

The SQL test cases were authored test-first but are skipped locally without
`SUPPLY_RESPONSE_LOCAL_REPORTING_SQL_URL`; no updated SQL result is claimed.

## Verification

```text
.venv/bin/pytest tests/fabric/test_report_generators.py tests/fabric/test_power_bi_project.py tests/fabric/test_schema_updater.py tests/test_reporting_activation.py -o addopts='' -q
184 passed, 1 inherited StarletteDeprecationWarning in 51.86s

/private/tmp/supply-response-report-tools.Dadda4/node_modules/.bin/powerbi-report-author --out TEMP_JSON validate --no-schema fabric/power-bi/SupplyResponse.Report
succeeded; 0 errors; 0 warnings

.venv/bin/ruff check ...
All checks passed
.venv/bin/ruff format --check ...
4 files already formatted
.venv/bin/python -m fabric.report_pages ... --check
.venv/bin/python -m fabric.report_model ... --check
.venv/bin/python -m fabric.report_contract --check
git diff --check
all passed with no output
```

The first sandboxed full run could not access the locked NuGet package. After an
approved locked restore and validator-enabled test run, the full suite passed.

## Files changed

- `apps/api/app/_reporting_artifact.py`
- `docs/superpowers/plans/2026-09-09-report-activation.md`
- `fabric/power-bi/README.md`
- `fabric/power-bi/SupplyResponse.SemanticModel/definition/tables/CaseCommandCenter.tmdl`
- `fabric/power-bi/SupplyResponse.SemanticModel/definition/tables/SavedAnalyses.tmdl`
- `fabric/report_model.py`
- `fabric/reporting/queries/SavedAnalyses.sql`
- `fabric/sql/002_analytics_views.sql`
- `tests/fabric/test_report_generators.py`
- `tests/integrations/test_saved_analysis_reporting_sql.py`

## Exact files for the controller-owned real SQL run

Upload only these changed files for the SQL test run:

- `fabric/sql/002_analytics_views.sql`
- `fabric/reporting/queries/SavedAnalyses.sql`
- `fabric/report_model.py`
- `tests/integrations/test_saved_analysis_reporting_sql.py`

`fabric/report_model.py` is required because the SQL partition metadata test
imports its declared column/type contract. Generated report/model artifacts,
docs, and the digest module are not needed for that SQL run.

## Concerns and self-review

- The protected-customer-orders column is pending the user's choice and was not
  implemented.
- The new SQL must still pass the authorized real SQL Server integration run;
  Python emulation was neither used nor claimed.
- Native DAX/render/access checks remain release gates. Offline report structure
  validation passed, but this task performed no live calls, deployment, receipt
  issuance, upload, push, or merge.
- Unrelated controller-owned edits in `docs/ROADMAP.md` and
  `docs/superpowers/plans/2026-09-08-planner-experience-delivery.md` were left
  unstaged and are not part of this work.
