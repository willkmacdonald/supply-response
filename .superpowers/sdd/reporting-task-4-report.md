# Reporting Task 4 checkpoint

## Scope

Added `analytics.saved_record_evidence`, an optional one-to-one companion to
shipment, transfer, and qualification `saved_records`. Resolution requires
exact evidence/material identity, source identity, operational-fact kind,
runtime/provenance alignment, and unique record/evidence membership. Explicit
null timestamps remain SQL NULL; malformed or omitted timestamp fields remain
unavailable. Fallback rows expose `demo_fixture` provenance.

## TDD checkpoints

Tests were authored locally before implementation. The local SQL integration
gate was not configured, so those tests were skipped locally; the static
inventory test intentionally failed before the view existed.

Parent-observed SQL RED, against base `43f597c` only, on a fresh disposable
database:

```text
wrapper -q tests/integrations/test_saved_analysis_reporting_sql.py -k exact_evidence -x --tb=short
1 failed, 52 deselected in 0.83s
missing analytics.saved_record_evidence
```

Parent-observed SQL GREEN, after syncing this SQL and tests, on a fresh
disposable database:

```text
wrapper -q tests/integrations/test_saved_analysis_reporting_sql.py -x --tb=short
55 passed in 2.05s, exit 0
```

Both disposable databases were removed after execution.

## Local verification

```text
uv run pytest -o addopts='' -q tests/integrations/test_fabric_sql_scripts.py tests/integrations/test_saved_analysis_reporting_sql.py
11 passed, 55 skipped

uv run ruff check tests/integrations/test_saved_analysis_reporting_sql.py
All checks passed!

git diff --check
pass
```

