# Task 7: Fabric reviewed-supplier-email schema report

## Scope delivered

Added only the missing, retry-safe Fabric SQL definitions for:

- `app.supplier_email_deliveries`
- `app.supplier_email_revisions`

The definitions are guarded with `OBJECT_ID` checks, retain operational schema
publication at version 11 (with analytics responsible for version 12), and add
the migration-0009 primary keys, unique constraints, positive-revision checks,
valid-send-status check, foreign keys, and all seven named indexes. No SQL was
applied to a database, and no deployment was performed.

## Test-driven development record

### RED

Command:

```sh
uv run --python 3.12 pytest -q tests/integrations/test_fabric_sql_scripts.py::test_operational_schema_contains_supplier_email_table_contract
```

Observed result: failed as expected because the first required guard,
`IF OBJECT_ID(N'app.supplier_email_deliveries', N'U') IS NULL`, was absent from
the packaged operational schema. The focused test also specifies both table
contracts, required constraints, and migration-named indexes.

### GREEN

Command:

```sh
uv run --python 3.12 pytest -q tests/integrations/test_fabric_sql_scripts.py::test_operational_schema_contains_supplier_email_table_contract
```

Observed result: passed after adding the two guarded table definitions and
their indexes.

## Verification

```sh
uv run --python 3.12 pytest -q tests/integrations/test_fabric_sql_scripts.py tests/integrations/test_fabric_schema.py tests/persistence/test_fabric_sql.py tests/integrations/test_approval_schema_upgrade_sql.py
```

Observed result: 55 passed, 1 skipped. The skipped test requires an explicitly
configured isolated localhost SQL execution gate; no live Fabric connection was
attempted.

```sh
uv run ruff check tests/integrations/test_fabric_sql_scripts.py
```

Observed result: `All checks passed!`

## Notes

The existing Fabric script test had fixed object totals that were already
behind the checked-in schema (20 tables and 36 indexes before this change,
while its expectations were 18 and 26). The contract expectations now reflect
the 22 tables and 43 indexes present after the two requested tables and seven
requested indexes were added.

Only `fabric/sql/001_operational_schema.sql`,
`tests/integrations/test_fabric_sql_scripts.py`, and this report are intended
for the task commit. `.azure/deployment-plan.md` and `.pnpm-store/` were left
untouched and unstaged.
