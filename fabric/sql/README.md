# Fabric SQL Database

The opt-in live persistence adapter uses the same canonical repository and unit-of-work contract as SQLite. It connects through ODBC Driver 18 with an Entra access token; connection strings contain no user password.

- `001_operational_schema.sql` creates the complete operational schema in `app` and records an incomplete Task 12 schema version.
- `002_analytics_views.sql` creates read-only Decision-linked projections and the `analytics.case_command_center` and `analytics.action_outcomes` views, then publishes live-ready schema version 12.

These scripts are intentionally not run at application startup. An approved deployment process can call `integrations.fabric.schema.apply_fabric_schema(engine)` to split `GO` batches and apply both files in order. Every object and version publication is idempotent, so the operation is safe to retry after a completed batch or to invoke twice. Apply it only to an explicitly selected Fabric SQL Database. Live tests remain skipped unless both `SUPPLY_RESPONSE_FABRIC_SQL_SERVER` and `SUPPLY_RESPONSE_FABRIC_SQL_DATABASE` are set; setting only one fails test collection before any connection attempt.

Live local authentication also requires `SUPPLY_RESPONSE_CREDENTIAL_MODE=azure_cli` and `SUPPLY_RESPONSE_ALLOWED_TENANT_ID`. Azure hosting uses `SUPPLY_RESPONSE_CREDENTIAL_MODE=managed_identity`. The runtime fails startup on invalid configuration, identity, connectivity, or schema version; it never falls back to SQLite.
