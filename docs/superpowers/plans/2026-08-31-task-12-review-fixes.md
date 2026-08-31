# Task 12 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Fabric schema application retry-safe, fail closed on partial live configuration, and prove the full canonical transactional store contract identically on SQLite and opt-in Fabric SQL.

**Architecture:** Keep schema deployment explicit and outside API startup. A small schema utility splits SQL Server `GO` batches and executes each batch transactionally; every DDL batch is independently idempotent so a retry can resume after any completed batch. The existing shared SQLAlchemy store remains the sole domain repository, while parameterized integration tests exercise success, failure, concurrency, replay, and integrity behavior on both adapters.

**Tech Stack:** Python 3.12, SQLAlchemy 2, SQL Server/Fabric SQL DDL, pyodbc, pytest, Pydantic settings.

## Global Constraints

- Work directly on the explicitly approved `main` branch; do not push.
- Use strict RED-GREEN-REFACTOR for every production behavior change.
- Do not connect to Fabric unless both `SUPPLY_RESPONSE_FABRIC_SQL_SERVER` and `SUPPLY_RESPONSE_FABRIC_SQL_DATABASE` exist; neither is currently configured.
- Preserve Driver 18, Entra token, explicit credential, health, no-fallback, and Decision-lineage behavior.
- Do not provision resources, install native ODBC drivers, deploy, or implement Task 13+ journeys.
- Give all shared contract records unique IDs; never require destructive live cleanup.

---

### Task 1: Retry-safe schema application

**Files:**
- Create: `integrations/fabric/schema.py`
- Modify: `fabric/sql/001_operational_schema.sql`
- Modify: `fabric/sql/002_analytics_views.sql`
- Modify: `tests/integrations/test_fabric_sql_scripts.py`
- Create: `tests/integrations/test_fabric_schema.py`
- Modify: `tests/integration/test_fabric_sql_live.py`

**Interfaces:**
- Consumes: a SQLAlchemy `Engine` and the two checked-in SQL scripts.
- Produces: `split_go_batches(sql: str) -> tuple[str, ...]`, `apply_sql_script(engine: Engine, sql: str) -> None`, and `apply_fabric_schema(engine: Engine) -> None`.

- [ ] Add failing tests that enumerate every `CREATE SCHEMA`, `CREATE TABLE`, `CREATE INDEX`, inline constraint, and view and require an existence guard, guarded-table enclosure, or `CREATE OR ALTER` form.
- [ ] Add a failing deterministic simulator test: execute a prefix of batches, restart, then execute both scripts twice; object creation must not collide and final schema version must be 12.
- [ ] Add failing utility tests proving `GO` lines are removed, batches preserve SQL, failures stop later batches, and a retry re-executes guarded batches safely.
- [ ] Run `pytest tests/integrations/test_fabric_sql_scripts.py tests/integrations/test_fabric_schema.py -q` and record the expected failures from unguarded DDL and the missing utility.
- [ ] Implement `split_go_batches` with a case-insensitive line-only `GO` delimiter and execute each nonempty batch in its own `engine.begin()` transaction.
- [ ] Wrap every operational schema/table batch in `IF NOT EXISTS`; wrap every index in `IF NOT EXISTS` against `sys.indexes`; keep constraints inline inside guarded table creation; retain `CREATE OR ALTER VIEW` for views.
- [ ] Replace version inserts/updates with idempotent logic: operational inserts version 11 only when absent and never downgrades 12; analytics advances an existing row to 12 without collision.
- [ ] Add the opt-in live test that invokes `apply_fabric_schema` twice, then checks version 12 and both analytics views.
- [ ] Run the focused schema tests and confirm green.

### Task 2: Fail-closed partial Fabric configuration

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/integration/test_fabric_marker_probe.py`
- Create: `tests/integrations/test_fabric_live_config.py`
- Modify: `tests/integration/test_store_contract.py`

**Interfaces:**
- Consumes: the server/database environment pair.
- Produces: collection behavior where neither value skips live tests, exactly one value raises `pytest.UsageError`, and both values permit collection/execution.

- [ ] Add subprocess tests that run only the side-effect-free marker probe with absent, server-only, database-only, and complete environment pairs.
- [ ] Verify RED: partial pairs currently skip or proceed instead of failing with a clear paired-setting error.
- [ ] Implement a single helper that classifies the pair as `absent`, `partial`, or `complete`; use it in collection and the Fabric store fixture.
- [ ] Keep both-absent behavior as a marker skip and ensure complete configuration does not make the probe connect.
- [ ] Run the focused configuration tests and confirm green.

### Task 3: Full shared transaction contract

**Files:**
- Modify: `tests/integration/test_store_contract.py`

**Interfaces:**
- Consumes: the existing `StoreFactory`, `DecisionService`, `ActionPlanningWorker`, `PlaybackService`, and canonical store exceptions.
- Produces: identical SQLite/Fabric tests for atomic rollback, rejection, idempotency, concurrency, outbox recovery, immutability/integrity, playback concurrency, and completion replay.

- [ ] Refactor the existing successful round-trip setup into unique-ID helpers without changing production behavior; keep the existing test green.
- [ ] Add rollback atomicity using a before-outbox failure hook and assert that neither Decision nor event commits.
- [ ] Add rejected Decision/no-outbox and approved idempotent replay/divergent-conflict tests.
- [ ] Add concurrent same-key Decision creation and assert one canonical Decision and one outbox event.
- [ ] Add outbox claim/failure/targeted retry/global retry assertions, including durable attempt/error state.
- [ ] Add immutable duplicate and direct tamper detection assertions.
- [ ] Add repeated/concurrent playback start and completed replay assertions with stable attempt/event/observation counts.
- [ ] Run `pytest tests/integration/test_store_contract.py -q -m 'not fabric_live'` after each test group and confirm all SQLite parameters pass.

### Task 4: Final verification, report, and commit

**Files:**
- Modify: `.superpowers/sdd/task-12-report.md` (ignored evidence artifact)

**Interfaces:**
- Consumes: all review-fix evidence.
- Produces: appended `## Review Fix` report and one review-fix commit.

- [ ] Run focused non-live schema/config/contract tests.
- [ ] Run the full suite and live-only command; confirm live tests only skip because both required settings are absent.
- [ ] Run changed-scope Ruff/format, production Pyright with the venv interpreter, SQL/static compilation, `uv lock --check`, `pip-audit`, and `git diff --check`.
- [ ] Append exact RED/GREEN commands, results, files, live status, self-review, concerns, and commit to the Task 12 report.
- [ ] Use the verification-before-completion skill, rerun the final gate, and commit with a focused review-fix message.

## Self-Review

- Spec coverage: retry safety, schema utility, double-apply live check, partial-env fail-closed behavior, subprocess marker tests, all requested transaction behaviors, verification, reporting, and commit are assigned above.
- Placeholder scan: no deferred implementation steps or unspecified error handling remain.
- Type consistency: schema utility names and store/config test interfaces are consistent across tasks.

The parent task already selected inline execution, so this plan will be executed in the current session using `superpowers:executing-plans`.
