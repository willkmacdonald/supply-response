# Repeatable presenter runs — local release evidence

**Date:** September 14, 2026 (America/Chicago)

**Status:** Locally verified; deployment, cleanup application, and live browser acceptance pending

**Reviewed code head:** `ed89d3c`

**Feature range:** `a5650be..ed89d3c`

## Observable behavior

- A successful **Check email for disruptions** response receives a new opaque,
  server-issued Presenter Run identifier.
- **Analyze this disruption** binds the reviewed supplier email and Presenter Run
  to a fresh Case Instance. Different Presenter Runs produce different Case IDs,
  while retries and concurrent requests within one run return the same case.
- A new case does not inherit an Analysis Version, Finance Review, Taylor
  approval, Alex Decision, execution action, draft, playback, or outcome.
- Presenter retention keeps the current live showcase supplier-email case plus
  three historical eligible cases and removes expired cases as complete
  aggregates in the same transaction as case creation.
- The case-header **Open case dashboard** action is absent. **Explore in Power
  BI** and exact card-level supporting-data links remain.

These behaviors are implemented locally. They are not claimed as deployed or
accepted in the live browser.

## Commits reviewed

| Commit | Purpose |
|---|---|
| `deebc80` | Approved repeatable presenter-run design |
| `fcc1bef` | Implementation plan |
| `54f35e3` | Server-issued Presenter Run identity |
| `8f9c07b` | Atomic presenter retention and preview command |
| `2863b5c` | Database-level serialization for concurrent retention |
| `64e8898` | Web run propagation and redundant dashboard-link removal |
| `ed89d3c` | Presenter-retention test typing correction |

## Local verification

### Feature-focused Python behavior

Command:

```bash
uv run pytest tests/domain/test_rl001_contract.py tests/api/test_inbox.py \
  tests/api/test_inbound_cases.py tests/api/test_case_lifecycle.py \
  tests/persistence/test_inbound_binding.py \
  tests/persistence/test_presenter_runs.py \
  tests/persistence/test_sqlite_store.py \
  tests/persistence/test_fabric_sql.py -q
```

Result: **117 passed**, no failures or skips. Pytest emitted one existing
Starlette `httpx` test-client deprecation warning.

The Presenter Run production and dedicated test files also passed focused
checks:

```text
Ruff: All checks passed.
Pyright: 0 errors, 0 warnings, 0 informations.
```

The focused check covered the changed API contracts and route, Case domain,
preview CLI, Fabric/SQLite transaction adapters, persistence port, retention
planner, and store.

### Web application

From `apps/web`:

```text
npm test
Test Files  26 passed (26)
Tests       369 passed (369)

npm run build
TypeScript build passed.
Vite transformed 204 modules and completed the production build.
```

No web tests were skipped.

### Repository-wide Python suite

The prescribed command `uv run pytest -q` collected **1,860 tests**:

- **1,631 passed**
- **172 skipped**
- **57 failed**
- **0 collection errors**

The 172 intentional skips were:

| Count | Reason |
|---:|---|
| 139 | Local SQL execution gate not configured |
| 17 | Fabric SQL live settings not configured |
| 4 | Legacy case has no new currentness policy |
| 4 | New concurrency protocol applies to independent policy |
| 2 | Review binding applies to high-cost response |
| 1 | Foundry live settings incomplete; no credential created |
| 1 | Power BI live settings not configured |
| 1 | Low-cost fixture only |
| 1 | Work IQ live settings not configured |
| 1 | Isolated localhost SQL execution gate not configured |
| 1 | Dedicated disposable SQL URL and fictional fixture required |

The 57 failures reproduce the dirty baseline recorded before this feature:

| Count | Existing failure area |
|---:|---|
| 6 | Live diagnostic log-capture ordering |
| 27 | Work IQ `ask` response-shape diagnostics |
| 8 | Work IQ HTTP diagnostics |
| 6 | Work IQ OBO diagnostics |
| 6 | Work IQ normalized-response diagnostics |
| 3 | Stale Fabric operational table/index count assertions |
| 1 | Stale packaged Power BI reporting digest |

These failures are outside the presenter-run implementation and were not
changed or masked.

### Repository-wide quality gates

The required broad checks were run and remain dirty:

- `uv run ruff check .`: **126 errors**; 111 are reported as automatically
  fixable. The counts are 67 `FURB157`, 24 `I001`, 12 `SIM117`, 12 `UP007`,
  5 `UP035`, 2 `B008`, and one each of `UP047`, `FLY002`, `RUF022`, and
  `RUF100`.
- `uv run pyright`: **106 errors**, 0 warnings, 0 informations. The two earlier
  presenter-retention test-fixture findings were fixed in `ed89d3c`; the
  Presenter Run production files, API tests, and dedicated retention tests pass
  the focused Pyright command with **0 errors, 0 warnings, 0 informations**. The
  remaining 106 findings are broader repository typing debt.

No unrelated lint, typing, diagnostic, Fabric schema-count, or reporting-digest
work was included in this release.

## Read-only live cleanup preview

The ignored, documented personal-tenant deployment environment was loaded and
the default preview command was run without `--apply`:

```bash
uv run python scripts/prune_presenter_runs.py
```

Exact output:

```json
{
  "current_case_id": "RL-INBOUND-48f48fb45f22d0f5a0c30e4c301aaf887daae09dacfad264b7e4322f75b3105c",
  "pruned_case_ids": [],
  "retained_case_ids": [
    "RL-INBOUND-48f48fb45f22d0f5a0c30e4c301aaf887daae09dacfad264b7e4322f75b3105c"
  ]
}
```

The preview returned one eligible live showcase supplier-email-bound case and
no historical cases proposed for pruning. Because `pruned_case_ids` is empty,
there are no proposed deletion targets to validate individually. Preview mode
does not emit deletion counts and does not change data. No cleanup was applied.

## Immutable diff and scope review

The feature-range name review contains only Presenter Run domain/API contracts,
persistence and transaction adapters, the preview command, React run propagation
and navigation tests, plus the approved design and plan. It contains:

- no `fabric/power-bi` report-definition changes;
- no operational source-data deletion or traditional-reporting data changes;
- no authentication, Entra application, tenant permission, or role changes;
- no deployment configuration changes; and
- no `.azure/deployment-plan.md` change.

The code change does add explicit deletion statements for expired presenter-case
aggregates only. Tests cover eligibility boundaries, dependent-row deletion,
transaction rollback, stale-plan rejection, and SQLite/Fabric transaction
serialization.

## Release boundary

Nothing was deployed and no live data was deleted in this validation task. The
remaining release steps are explicit:

1. independently review this immutable feature and evidence;
2. validate Azure readiness and deploy the reviewed image;
3. rerun the read-only cleanup preview against the deployed code;
4. if it proposes deletions, verify every proposed case is `showcase`, `live`,
   and supplier-email-bound, then obtain separate authorization before applying
   that exact plan with `--apply`;
5. verify the live database retains no more than the current presenter case plus
   three historical presenter cases; and
6. from the bare application URL, perform two consecutive checks of the same
   marked email, prove that their Case IDs differ, and prove that tab 4 in the
   second run waits for a new Taylor review after Taylor and Alex approve the
   first run.

Local test results, a successful read-only preview, or a healthy deployment do
not substitute for that live browser acceptance.
