# Fabric SQL Database

The opt-in live persistence adapter uses the same canonical repository and unit-of-work contract as SQLite. It connects through ODBC Driver 18 with an Entra access token; connection strings contain no user password.

- `001_operational_schema.sql` creates the complete operational schema in `app` and records an incomplete Task 12 schema version.
- `002_analytics_views.sql` creates read-only Decision-linked projections and the `analytics.case_command_center` and `analytics.action_outcomes` views, then publishes live-ready schema version 12.

These scripts are intentionally not run at application startup. An approved deployment process can call `integrations.fabric.schema.apply_fabric_schema(engine)` to split `GO` batches and apply both files in order. Every object and version publication is idempotent, so the operation is safe to retry after a completed batch or to invoke twice. Apply it only to an explicitly selected Fabric SQL Database. Live tests remain skipped unless both `SUPPLY_RESPONSE_FABRIC_SQL_SERVER` and `SUPPLY_RESPONSE_FABRIC_SQL_DATABASE` are set; setting only one fails test collection before any connection attempt.

Live local authentication also requires `SUPPLY_RESPONSE_CREDENTIAL_MODE=azure_cli` and `SUPPLY_RESPONSE_ALLOWED_TENANT_ID`. Azure hosting uses `SUPPLY_RESPONSE_CREDENTIAL_MODE=managed_identity`. The runtime fails startup on invalid configuration, identity, connectivity, or schema version; it never falls back to SQLite.

## Saved-analysis reporting

The additive `analytics.saved_analyses`, `saved_options`, `saved_records`,
`saved_record_evidence`, and `case_reporting` views serve the case/analysis
reporting contract, using the internal `analytics.report_scalar` validation function.
They do not change operational schema version 12 or the
four-view application health contract. The report deployment must check all
five added views, the validation function, and the columns consumed by its model
before refreshing it. The SQL script creates the function before dependent views
and creates the compatibility decision projection before the case-reporting view.

Record pages filter exact case, analysis, family and record ID. Option pages
filter exact case, analysis and option ID. No/multiple selections are a report
selection state, not SQL totals. Zero matched rows mean unavailable; duplicate
identities are excluded. Missing an analysis from an imported model alone does
not establish refresh lag: say it is unavailable unless the app's known saved
analysis and model refresh metadata establish that the report has not caught up.

Use an explicitly provisioned, fresh disposable local SQL Server database named
`supply_response_projection_test_` followed by a unique suffix. Configure only
`SUPPLY_RESPONSE_LOCAL_REPORTING_SQL_URL` as a `mssql+pyodbc` URL with explicit
localhost host and database fields, ODBC Driver 18, and local test credentials.
Do not configure this test through the Fabric live variables. Run:

    uv run --extra dev pytest tests/integrations/test_saved_analysis_reporting_sql.py -rs

A skipped module means SQL execution is outstanding. Before report deployment,
run the complete module on a supported SQL Server 2017-or-later test engine
(compatibility level >=130), retaining its output. SQL Server's support for the
actual host architecture must be established before provisioning; a working
Docker daemon on ARM is not evidence of a supported SQL Server runtime.
Then use the approved release process to
apply both packaged scripts in order to the explicitly selected Fabric SQL
Database and perform read-only exact-case/analysis query comparisons there.
Never substitute SQLite, a Python arithmetic oracle, or regex assertions for
the T-SQL execution gate. A later Fabric gate verifies platform equivalence;
the local engine verifies queries, types, JSON handling and fixture results.

Release SQL first, check new views and consumed columns, then update the existing
semantic model/report and activate app links together. Preserve report/model IDs
and permissions. Roll back the report/model and deactivate new links first;
the additive views may remain. Do not downgrade the operational version or alter
saved payloads as part of rollback.
