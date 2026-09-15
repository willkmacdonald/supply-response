# Repeatable presenter runs — corrected local evidence

**Date:** September 14, 2026 (America/Chicago)

**Status:** Corrected implementation verified locally; deployment, cleanup
application, and live browser acceptance remain pending.

**Correction range:** `24b2f4e..HEAD`

## Observable behavior

- Each successful **Check email for disruptions** response contains a new opaque,
  server-issued `presenter_run_id`. There is no custom Presenter Run receipt,
  signed token, secret-derived credential, or client-side receipt propagation.
- **Analyze this disruption** sends the run ID plus the reviewed email identity.
  Before creating a case, the API re-reads that email through Work IQ and checks
  its tenant, mailbox, immutable message ID, review fingerprint, and disruption
  facts against freshly retrieved operational data.
- Repeating case creation within one run is idempotent. A later check creates a
  different run and a fresh Case Instance for the same supplier email.
- A focused local API/persistence acceptance test drives an earlier run through
  the supported analysis, Finance submission/Taylor approval, Alex decision,
  action planning, execution playback, and outcome services. It captures the
  decoded persisted values and aggregate counts, creates a later run for the
  same supplier email, proves that run has none of those dependent records, and
  proves the earlier header, decoded values, and counts are unchanged.
- The two persistence integrity checks reject a changed `presenter_run_id` both
  when saving a case projection and when reading a corrupted projection.
- Retention previews keep the current eligible presenter case plus the configured
  historical limit and now include a planned deletion count for every table in
  `PRESENTER_AGGREGATE_DELETE_ORDER`, including zero counts.
- Applying a preview retains the existing transaction lock, recomputes the full
  plan and its counts under that lock, and compares planned counts with actual
  deletion row counts. A changed plan or count mismatch raises the existing
  `PresenterRetentionPlanChanged` error and rolls back the transaction.
- The default public `historical_limit`, empty-plan sentinel, retention order,
  schema, lifecycle, and lock design are unchanged.

## Local verification

### Directly affected Python behavior

```bash
uv run pytest tests/domain/test_rl001_contract.py tests/api/test_inbox.py \
  tests/api/test_inbound_cases.py tests/api/test_case_lifecycle.py \
  tests/persistence/test_inbound_binding.py \
  tests/persistence/test_presenter_runs.py \
  tests/persistence/test_sqlite_store.py \
  tests/persistence/test_fabric_sql.py -q
```

Result: **123 passed**. Pytest emitted one existing Starlette `httpx`
test-client deprecation warning.

### Scoped Python quality checks

```bash
uv run ruff check apps/api/app/contracts.py apps/api/app/routes/inbox.py \
  services/persistence/presenter_runs.py services/persistence/store.py \
  tests/api/test_inbox.py tests/api/test_inbound_cases.py \
  tests/persistence/test_fabric_sql.py \
  tests/persistence/test_presenter_runs.py
```

Result: **All checks passed.**

```bash
uv run pyright apps/api/app/contracts.py apps/api/app/routes/inbox.py \
  services/persistence/presenter_runs.py services/persistence/store.py \
  tests/api/test_inbox.py tests/api/test_inbound_cases.py \
  tests/persistence/test_fabric_sql.py \
  tests/persistence/test_presenter_runs.py
```

Result: the changed implementation and its primary API/retention tests report
**0 errors** when scoped without `tests/persistence/test_fabric_sql.py`.
Including that changed adapter test file reports 12 pre-existing type errors in
its older test doubles and unrelated credential tests; the correction adds no
new Pyright finding. Those unrelated findings were recorded rather than fixed.

### Web application

From `apps/web`:

```bash
npm test
npm run build
```

Results: **26 test files passed, 369 tests passed**, and the TypeScript/Vite
production build completed after transforming 204 modules.

## Cleanup preview and release boundary

The corrected preview output includes `current_case_id`, `retained_case_ids`,
`pruned_case_ids`, and `planned_deletions`. `planned_deletions` has one integer
entry for every presenter aggregate table, even when no row is planned for that
table. The apply output additionally includes `deleted_rows` for comparison.

No cleanup was previewed or applied against a live database during this
correction. Nothing was deployed and no live Microsoft or Azure service was
called. A future operator must preview against the reviewed deployed build,
inspect the proposed cases and per-table counts, obtain separate authorization
for live deletion, and only then apply that exact preview.
