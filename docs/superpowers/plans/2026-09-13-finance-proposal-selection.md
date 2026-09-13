# Durable Proposal Selection and Case Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the current explicitly submitted response per case, atomically supersede its Finance review when replaced or reanalyzed, and expose a case-wide concurrency guard for later Finance resolution and final Decision services.

**Architecture:** Add an immutable selection journal and a generation/pointer pair to the existing case projection. A focused repository publishes selections within its caller's UoW; every new-workflow analysis publication uses the same conditional projection update and clears the selection. Review revision storage remains append-only and distinct from case selection.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy Core, SQLite, Alembic, SQL Server/Fabric SQL artifacts, pytest.

## Task 1: Durable selection, concurrency guard and analysis invalidation

Parent-reviewed September 13, 2026 after compatibility acceptance at `f449d7f`.
This single task implements the approved workflow's current-proposal boundary.

### Preconditions and review boundary

Read against accepted storage commit `0f23db5` and the policy contract in `docs/superpowers/plans/2026-09-13-finance-policy-compatibility.md`. Execute after the policy task passes review; `WorkflowVersion.INDEPENDENT_FINANCE`, `CaseInstance.effective_workflow_version`, and explicit `instantiate_rl001(workflow_version=...)` are consumed here.

This is **one reviewable task**, with smaller implementation steps below. Metadata, frozen migration, Fabric DDL, repository and analysis invalidation land together. A schema-only task is not useful independently, and publishing selections before analysis invalidation would create an unsafe intermediate capability. Do not activate routes or add application services in this increment.

The accepted `FinanceReviewStore` signatures are:

```python
get_latest(review_id: str) -> tuple[FinanceReview, int]
get_by_idempotency_key(key: str) -> tuple[FinanceReview, int, str] | None
append(review: FinanceReview, *, expected_revision: int | None,
       idempotency_key: str, request_fingerprint: str) -> tuple[FinanceReview, int]
```

`UnitOfWork.finance_reviews` is built by `SqlAlchemyUnitOfWork.__enter__` using the same connection as `cases`, `decisions`, and `execution`. Repository methods never commit. `append_finance_review(...)` owns an outer transaction and must **not** be called here. Accepted storage reconstructs pure lifecycle transitions, verifies the hashed option against the outer option, verifies actual evaluated cost and immutable analysis/Case provenance, and requires complete snapshot equality on replay.

## Global constraints

- No baseline regeneration: reuse frozen `tests/finance/fixtures/legacy-policy.json` adopted from `.superpowers/sdd/finance-legacy-baseline.patch`. Do not create binary fixtures.
- Do not change canonical Case/Analysis/Decision shapes or hashes; generation/pointer are relational projection fields only.
- A selection is the case's current explicitly submitted option. A FinanceReview is optional: `response_cost <= 20000` requires no review. Actual cost and all material come from immutable analysis.
- A submitted selection binds case policy, immutable analysis ID/hash and option, authenticated submitter snapshot and server time. Analysis hash binds evidence/constraints/side effects; do not duplicate caller-owned versions of them.
- A single review ID belongs to one selection. Rejected unchanged resubmission must later use a fresh selection ID and review ID. It never reuses the old review.
- A case generation advances for selection publication, new analysis publication, and future Finance/final Decision guards, including operations that leave pointer unchanged. Case-wide generation is independent of per-review revision.
- No repository commits, savepoints, broad SQLite transaction reconfiguration, production test hooks, live calls or schema-version publication.
- Every test command includes `-m 'not fabric_live'`. Compiled Fabric SQL is not live concurrency proof.

## Files

- Create `data/domain/proposals.py`: immutable token/selection/receipt/state types with strict local validation.
- Create `services/persistence/proposals.py`: guarded selection journal and narrow SQL update primitive.
- Modify `services/persistence/ports.py`: `ProposalStore`, UoW member, exact review revision lookup.
- Modify `services/persistence/finance_reviews.py`: `get_revision` only, reusing existing `_from_row`.
- Modify `services/persistence/tables.py`: journal table, projection columns/constraints/index.
- Modify `services/persistence/store.py`: UoW wiring and new-workflow `_save_analysis_connection` integration.
- Create `migrations/versions/0008_case_proposal_selection.py`: frozen table/projection migration, down revision `0007_finance_review_revisions`.
- Modify `fabric/sql/001_operational_schema.sql`: matching additive guarded DDL; no version changes.
- Create `tests/finance/test_proposal_selection.py`: fixtures, lineage, selection, guard and supersession tests.
- Modify `tests/finance/test_workflow_policy.py`: migrate its runtime-read compatibility test to `head` before seeding/reading through current repositories; keep the same frozen payload/hash assertions. Current metadata cannot read missing 0008 columns on an unupgraded 0007 schema. Separate reflected-schema tests below prove the actual 0007→0008 upgrade.
- Modify `tests/persistence/test_sqlite_store.py`, `tests/persistence/test_fabric_sql.py`: schema/migration/artifact assertions.
- Modify `tests/integration/test_store_contract.py`: parameterized adapter races using existing `store_factory`; exclude its Fabric parameter in this task's runs.

## Exact interfaces

In `data/domain/proposals.py`, import `FinanceProposal`, `FinanceReview`, `IdentitySnapshot`, `WorkflowVersion`, `FrozenModel`, Pydantic validators/Field/StrictInt/ConfigDict and `datetime`:

```python
class ProposalToken(FrozenModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    generation: StrictInt = Field(ge=0)
    analysis_id: str | None
    analysis_material_hash: str | None
    selection_id: str | None

class ProposalSelection(FrozenModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    selection_id: str
    proposal: FinanceProposal
    workflow_version: WorkflowVersion
    submitted_by: IdentitySnapshot
    submitted_at: datetime
    finance_review_id: str | None

class SelectionReceipt(FrozenModel):
    selection: ProposalSelection
    expected: ProposalToken
    idempotency_key: str
    request_fingerprint: str

class ProposalState(FrozenModel):
    token: ProposalToken
    selection: ProposalSelection | None
    review: FinanceReview | None
    review_revision: int | None
```

Validators: IDs nonblank/max 128; token hash lowercase 64-hex when present; analysis ID/hash both NULL or neither; selection pointer requires non-NULL analysis; selection time timezone-aware; selection policy must be independent Finance; review ID present iff actual proposal cost strictly exceeds 20000. Receipt key nonblank/max 256 and fingerprint lowercase 64-hex. Strict generation rejects booleans. All state combinations are consistent: missing selection implies no review; selected low-cost proposal implies no review/revision; selected high-cost proposal has a review matching its ID/proposal and positive revision.

`ProposalStore` and `SqlAlchemyProposalRepository` expose:

```python
def get_state(self, case_id: str) -> ProposalState: ...
def get_selection(self, selection_id: str) -> ProposalSelection: ...
def get_by_idempotency_key(self, key: str) -> SelectionReceipt | None: ...
def publish(self, receipt: SelectionReceipt) -> ProposalSelection: ...
def guard_current(self, case_id: str, *, expected: ProposalToken) -> ProposalToken: ...
```

`publish` does not return a live token: replay returns the original immutable selection even after supersession, while `get_state` separately returns current state. This prevents mixing replay result with a new review timestamp/status.

Add `get_revision(self, review_id: str, revision: int) -> FinanceReview` to the accepted review repository/port. Reject bool/nonpositive revision before SQL; select exact composite key, `RecordNotFound` if absent, return `_from_row(row)[0]`. This must work for historical revisions after supersession.

Errors in `services/persistence/proposals.py`: `StaleProposal(RuntimeError)`, `SelectionIdempotencyConflict(RuntimeError)`. Use existing `RecordNotFound` and `PersistenceIntegrityError` for absence/corruption. Unclassified SQL errors propagate unchanged after UoW rollback.

## Step 1: Add complete failing fixtures/tests before implementation

- [ ] Reuse policy fixture construction from `tests/finance/test_workflow_policy.py` as a reference but put a local `selection_context` fixture in the new test module; do not import its private helpers. The fixture creates a temporary **file** SQLite store, a real new-workflow RL001 Case and snapshot, real evidence and `analyze_case`, then calls `create_case` and `save_analysis`. Analysis start is `2026-09-01T09:01:00-05:00`; selection times start at `2026-09-01T14:02:00+00:00`.
- [ ] Fixture actor is exact ENTRA Alex (`RL-PERSONA-ALEX`, `RL-ENTRA-ALEX`, roles material_planner/response_approver), tenant `11111111-1111-4111-8111-111111111111`, object `22222222-2222-4222-8222-222222222222`. Taylor has same tenant, object `33333333-3333-4333-8333-333333333333`, persona/source Taylor and only finance_approver. These feed existing pure lifecycle validation; this persistence increment does not prove runtime auth binding.
- [ ] Define a test-only `receipt(context, option_id, selection_id, review_id, expected)` helper which finds the real hashed option, takes `option.predicted.response_cost`, constructs `FinanceProposal`, and then `ProposalSelection`. It returns a `SelectionReceipt` with deterministic test key and `sha256` of canonical JSON containing selection and **expected token**. A companion `persist(context, receipt)` opens a UoW, appends `submit_finance_review(...)` when review ID exists (key `pending:<selection_id>` and fingerprint from full pending snapshot), calls `uow.proposals.publish(receipt)`, and commits. No fixture calls transaction-owning append facade inside another UoW.
- [ ] Add these first red assertions, using the fixture helpers above:

```python
def test_initial_publication_and_pointer(selection_context):
    ctx = selection_context
    with ctx.store.uow_factory() as uow:
        state = uow.proposals.get_state(ctx.case.case_id)
    assert state.token.generation == 1  # first new-workflow analysis publication
    assert state.selection is None
    command = receipt(ctx, 'RL-OPTION-COMBINED', 'selection-1', 'review-1', state.token)
    assert persist(ctx, command) == command.selection
    with ctx.store.uow_factory() as uow:
        current = uow.proposals.get_state(ctx.case.case_id)
    assert current.token.generation == 2
    assert current.selection == command.selection
    assert current.review.status is FinanceReviewStatus.PENDING
    assert current.review_revision == 1

def test_transfer_replaces_rejected_review_without_new_review(selection_context):
    ctx = selection_context
    first = ctx.publish_combined()
    with ctx.store.uow_factory() as uow:
        state = uow.proposals.get_state(ctx.case.case_id)
        rejected = resolve_finance_review(review=state.review,
            current_proposal=state.selection.proposal, actor=ctx.taylor,
            approved=False, reason='Budget 10000', now=first.submitted_at + timedelta(minutes=1))
        uow.finance_reviews.append(rejected, expected_revision=1,
            idempotency_key='reject-1', request_fingerprint='b' * 64)
        uow.proposals.guard_current(ctx.case.case_id, expected=state.token)
        uow.commit()
    second = ctx.publish_transfer()
    with ctx.store.uow_factory() as uow:
        state = uow.proposals.get_state(ctx.case.case_id)
        original = uow.finance_reviews.get_revision(first.finance_review_id, 2)
        superseded, revision = uow.finance_reviews.get_latest(first.finance_review_id)
    assert state.selection == second
    assert state.review is None
    assert original == rejected
    assert superseded.status is FinanceReviewStatus.SUPERSEDED
    assert superseded.reason == 'Budget 10000'
    assert revision == 3
```

`ctx.publish_combined/publish_transfer` are thin wrappers around `receipt`, current `get_state().token` and `persist`, using sequential fixed test IDs/times. They must not hide review resolution or mutate analysis material.

- [ ] Add parameterized tests for exact 20000/20000.01 requirement using domain receipt values, plus real analysis cost binding on persistence. Actual source fields are `SupplyReceiptOption.quantity` and `incremental_cost_per_unit`; expedite cost is their product in `services/analysis/options.py`. Before persisting the source snapshot/building analysis, use this fixture variation and select `RL-OPTION-EXPEDITE` (do not edit a hashed result):

```python
assert snapshot.alpha_expedite is not None
snapshot = snapshot.model_copy(update={
    'alpha_expedite': snapshot.alpha_expedite.model_copy(update={
        'quantity': 1, 'incremental_cost_per_unit': Decimal(target_cost),
    }),
})
# target_cost parameter is '20000.00' or '20000.01'; rebuild evidence and analysis.
```
- [ ] Run `uv run pytest tests/finance/test_proposal_selection.py -q -m 'not fabric_live'`; expect missing domain/repository/UoW errors. This first RED precedes metadata implementation.

## Step 2: Add schema, frozen migration and Fabric DDL as one unit

`case_proposal_selections` table columns and constraints (explicit names in frozen migration):

| Column | Type / nullability |
| --- | --- |
| selection_id | String(128), primary key |
| case_id | String(128), FK case_instances.case_id RESTRICT, not null |
| analysis_id | String(128), FK analysis_versions.analysis_id RESTRICT, not null |
| analysis_material_hash | String(64), not null |
| workflow_version | String(64), not null |
| finance_review_id | String(128), nullable |
| finance_review_revision | Integer, nullable; paired with ID and fixed to 1 |
| expected_generation | Integer, not null, nonnegative |
| expected_selection_id | String(128), nullable; FK to this journal selection_id RESTRICT |
| idempotency_key | String(256), unique, not null |
| request_fingerprint | String(64), not null |
| submitted_at | DateTime(timezone=True), not null |
| payload_json | Text, not null; canonical SelectionReceipt JSON |

Use `payload_json` for the full immutable receipt, not selection alone: expected token remains durably comparable for low-level replay even if a caller supplies the same fingerprint for a changed expected generation. `get_selection` extracts `.selection`. Duplicated analysis fields also cover `receipt.expected.analysis_id/hash`, which must equal the selected proposal's binding.

- [ ] Add composite FK `(finance_review_id, finance_review_revision)` to `finance_review_revisions(review_id, revision)`, `RESTRICT`. Check `(finance_review_id IS NULL AND finance_review_revision IS NULL) OR (finance_review_id IS NOT NULL AND finance_review_revision IS NOT NULL AND finance_review_revision = 1)`. A SQL CHECK involving NULL must explicitly test both branches; the explicit second `IS NOT NULL` is necessary because SQL CHECK accepts UNKNOWN.
- [ ] Add `expected_generation >= 0` and `workflow_version = 'independent-finance-v1'` checks. Add indexes on case_id, analysis_id and submitted_at. Add a **filtered unique** index `uq_case_proposal_selections_finance_review_id` with `finance_review_id IS NOT NULL` for both SQLite and SQL Server; ordinary SQL Server UNIQUE on a nullable column permits only one NULL and would break multiple low-cost selections.
- [ ] Add projection columns `proposal_generation INTEGER NOT NULL DEFAULT 0` and nullable `current_selection_id String(128)` FK to `case_proposal_selections.selection_id RESTRICT`, plus generation nonnegative check and pointer index. Keep these out of Case canonical payload. Legacy rows receive only the relational default; no JSON updates.
- [ ] Migration 0008 uses explicit `sa.Column`/constraint/index definitions, no runtime metadata import. Create selection table before adding projection FK. Use `op.batch_alter_table('case_projection')` for SQLite-compatible FK/check changes; preserve existing outbound analysis/Decision/Case FKs and indexes. Add default with `server_default=sa.text('0')`. Downgrade removes projection pointer FK/index, check and both columns before dropping journal. Downgrade does not delete or rewrite Finance review revisions or historical Case/Analysis/Decision rows. Verify preserved foreign keys and `PRAGMA foreign_key_check` after migration with runtime enforcement enabled; do not add a disabling pragma.
- [ ] Fabric DDL is inserted after Finance review table exists and after projection creation for projection alterations. Use schema `app`, `nvarchar(128/256/64)`, `int`, `datetimeoffset`, `nvarchar(max)` and `CHECK (ISJSON(payload_json)=1)`. Guard table creation with `OBJECT_ID`, each column with `COL_LENGTH`, each named constraint via `sys.check_constraints/sys.foreign_keys`, and indexes via `sys.indexes`. Existing database addition for generation uses `NOT NULL CONSTRAINT df_case_projection_proposal_generation DEFAULT (0) WITH VALUES`; pointer starts NULL. Include filtered unique index with `WHERE finance_review_id IS NOT NULL`. Do not update schema publication constants.
- [ ] Update exact metadata/migration head tests in `tests/persistence/test_sqlite_store.py` and artifact checks in `test_fabric_sql.py`. Run `uv run pytest tests/persistence/test_sqlite_store.py tests/persistence/test_fabric_sql.py -q -m 'not fabric_live'`. Expected green schema tests after metadata/migration/DDL are implemented together; repository tests remain red until Step 3.

## Step 3: Implement guarded repository and exact historical review lookup

- [ ] Add strict value models and `get_revision` from the contracts. Add `ProposalStore` and `UnitOfWork.proposals`; instantiate repository with the existing UoW connection via local import alongside Finance repository.
- [ ] Implement canonical receipt decoder validating all duplicated columns, aware timestamp equivalence in UTC, expected token/proposal equality, immutable Case policy, analysis material hash, and exact `AnalysisResponseOptionMaterial.from_option(outer_option)` equality. Selected option must be executable, active mitigation, predicted and free of blocking codes. Reject baseline and infeasible Beta. A high-cost receipt must bind exact review revision 1, whose pending proposal, submitter and submitted time equal selection; a low-cost receipt must have no review ID. Historical receipt reads validate pending revision 1, not current/latest status.
- [ ] Add this private SQL primitive in the focused repository module; it is not a public callback or test hook. New-workflow analysis publication uses it too:

```python
def _null_safe(column, value):
    return column.is_(None) if value is None else column == value

def _cas_projection(connection, *, case_id, expected, values):
    result = connection.execute(update(case_projection).where(
        case_projection.c.case_id == case_id,
        case_projection.c.proposal_generation == expected.generation,
        _null_safe(case_projection.c.current_analysis_id, expected.analysis_id),
        _null_safe(case_projection.c.current_analysis_hash, expected.analysis_material_hash),
        _null_safe(case_projection.c.current_selection_id, expected.selection_id),
    ).values(**values, proposal_generation=expected.generation + 1))
    if result.rowcount != 1:
        raise StaleProposal('Case analysis or proposal changed')
```

Give the real function typed `Connection`, `str`, `ProposalToken`, and `Mapping[str, Any]` arguments; it returns `None`. Before execution whitelist `values` keys to `current_analysis_id`, `current_analysis_hash`, `current_selection_id`, `status`, `payload_json`, `updated_at`; reject any other key. Callers cannot override generation/case ID. A driver reporting unknown rowcount fails closed rather than assuming success. Compile tests assert this WHERE on SQLite and MSSQL dialects.

- [ ] `get_state`: load validated Case projection and token through this connection, load pointed receipt (assert same case and analysis), load latest review when present, then reread token. Use `SqlAlchemyCaseRepository(...).get_projection`, which uses the passed connection; do not call its `get_case` delegation to `store.get_case`, which opens another connection. If token changed, raise `StaleProposal` so callers retry in a new UoW; no busy loop. Return a state only if tokens match. Once later services guard every mutation, this avoids mixing an old generation with a new review. A commit after the final read simply makes the returned token stale for the next command, which is expected.
- [ ] `get_by_idempotency_key` returns the decoded complete receipt or None. `publish` checks this first: identical full receipt returns original selection, including after later supersession; any change including expected generation/selection, key fingerprint, submitter/time or proposal raises `SelectionIdempotencyConflict`. No clock/UUID generation in this repository. Future application services must do command-level replay lookup before generating server values.
- [ ] For a new receipt, verify current token equality and new-workflow policy; require current analysis pair non-NULL and equal receipt binding. If Finance review ID exists, `get_latest` must still be revision 1 pending and unselected elsewhere. Insert the receipt; CAS pointer to its selection ID using its expected token; append superseded snapshot of the formerly selected review when there was one; return selection. No commit. Use `supersede_finance_review(now=receipt.selection.submitted_at)` so backward server time raises and rolls the operation back, never silently clamps timestamps.
- [ ] Internal supersession key is `selection-supersede:<selection_id>` (ID max 128 keeps key below 256); fingerprint hashes canonical `{operation, selection_id, prior_review_id, prior_revision, superseded_at}`. Append with actual prior review revision. If old review is already superseded while still current, treat as persistence inconsistency; current pointer is authoritative and cannot silently carry terminal superseded state. New pending review append precedes `publish` in the same UoW so its FK exists; callers must allow any failure to exit/rollback the complete UoW.
- [ ] `guard_current` validates current new-workflow state and then invokes the same CAS with unchanged pointer and `updated_at=datetime.now(UTC)`; returns token with generation +1. It does not resolve any Finance review or write Decision/outbox. Later services pair this guard and their own append in one UoW.

## Step 4: Integrate every new-analysis publication atomically

- [ ] At `_save_analysis_connection` entry, before first insert, load the immutable case and for independent Finance cases capture the projection/token on this same connection. Legacy branch preserves existing behavior/output. First analysis token has both analysis fields NULL, selection NULL and generation 0.
- [ ] Keep analysis/evidence/satisfaction inserts and existing projected Case/status validation. Replace only the new-workflow final unconditional projection update: build replacement analysis ID/hash and pointer NULL, CAS against captured token, then append prior current review's superseded snapshot in the same transaction. Use `datetime.now(UTC)` once for update and supersession; pure helper checks chronology. Namespaced key `analysis-supersede:<analysis.analysis_id>` and canonical operation fingerprint include former review ID/revision and exact server time. Both `save_analysis` and `complete_analysis_claim` share this path.
- [ ] A new analysis ID invalidates selection even when material hash is identical. Clear pointer for any new analysis publication. Preserve historical current Decision ID; existing changed-hash `REANALYSIS_REQUIRED` behavior remains and, for new workflow, same-hash/new-ID publication after a Decision also marks reanalysis required because its exact proposal binding is no longer current. Do not rewrite old Decisions or review revisions.
- [ ] A zero-row CAS or supersession failure propagates; inserted analysis/evidence, selection pointer and superseded review all roll back. `complete_analysis_claim` must not consume/delete its claim on failed publication; existing delete follows `_save_analysis_connection` and remains in the same transaction. Do not catch conflict and reload state to overwrite the winner.
- [ ] `save_case_projection` and status-only repository updates do not touch generation/pointer and cannot change workflow version (policy task already protects provenance). They remain outside this proposal protocol because they do not change selected material or review; their existing status-write race behavior is not expanded here.

## Step 5: Finish failure, replay, migration and concurrency tests

- [ ] Receipt integrity: same key changed expected generation with deliberately identical supplied fingerprint conflicts; same key changed full selection conflicts; exact replay after rejection/supersession returns old selection; current-state retrieval returns new state separately. Different key reusing selection ID or review ID fails. Multiple NULL review IDs work. Pending review from another case/analysis/option/cost/actor/time fails. Foreign/absent pointer tampering fails.
- [ ] Transaction rollback: after initial publish, explicit rollback leaves no selection/pointer/review; after replacement rollback keeps original selection and original review revision; failed supersede (clock before reviewed_at) rolls back new review + receipt + pointer. Inject repository failure only with monkeypatch in tests, not new production callbacks. Assert exact counts of selection journal, finance revisions, analyses/evidence, Decisions, satisfactions and outbox.
- [ ] Analysis invalidation: pending, approved and rejected current reviews each gain one superseded revision, retaining approved/rejected actor/time/reason; below-threshold selection clears without any Finance row. Same-hash new-ID analysis invalidates too. The test creates new analysis by rebuilding from source inputs with another analysis ID; never edits outer analysis without recomputing all material. Explicit rollback/failure leaves old analysis/token/review intact. Complete-analysis-claim failure retains the existing claim.
- [ ] Real two-connection file SQLite tests use `Barrier(2)` before repository operations/first CAS, not after one connection has acquired its write lock; every barrier wait has `timeout=5`, every future result has `timeout=15`, and unexpected exceptions abort the barrier. Two different selections at one token yield one durable winner and one stale/constraint loser; rollback loser before checking winner. Concurrent analysis publication versus selection yields one valid ordering, with stale selection unable to become current against old analysis. Equal-token competing `guard_current` calls yield one generation increment. If SQLite reports lock contention, roll it back and classify it as a retryable contender failure, then assert durable one-winner state; do not claim its lock error proves portable CAS semantics. Add sequential stale-token tests and compiled MSSQL predicates as separate evidence.
- [ ] For deterministic rollback at late CAS, monkeypatch the focused SQL primitive in the test to raise `StaleProposal` after existing inserts and assert all writes rolled back. This tests rollback independently of platform scheduling; it is not the concurrency proof. Avoid barriers where SQLite's first writer waits for a second writer that cannot acquire its lock.
- [ ] Migration proof starts `alembic upgrade ... 0007_finance_review_revisions` in `tmp_path`, seeds frozen legacy payloads and Finance review snapshots using reflected predecessor tables as shown below (no current runtime repository or `create_all` against the old schema), captures raw payload/hash strings, upgrades to 0008, and only then reopens with current `SqliteStore`. Generation=0/pointer=NULL for legacy rows; all captured JSON/hash values unchanged. Downgrade to 0007 and upgrade again with no selected new-case data proves prior schema/rows preserved. Add a separate empty-schema downgrade structural test; do not imply downgrade with live selections retains selection history.
- [ ] Assert 0008 migration has no runtime metadata imports, all prior FK/index definitions survive SQLite batch migration, and Fabric artifact contains table/composite FK/paired NULL check/filtered unique index/default/backfill/guarded alterations. No live DDL execution.
- [ ] Run:

```bash
uv run pytest tests/finance/test_proposal_selection.py tests/finance/test_workflow_policy.py tests/persistence/test_sqlite_store.py tests/persistence/test_fabric_sql.py -q -m 'not fabric_live'
uv run pytest tests/persistence/test_decision_outbox.py tests/integration/test_store_contract.py tests/api/test_case_lifecycle.py -q -m 'not fabric_live'
git diff --check
```

Expected: all local tests pass, legacy Decisions/routes stay unchanged, no selected runtime path is activated. Confirm counts/hash assertions, not just success responses.
- [ ] Implementer verifies and makes a scoped commit of this coherent boundary with `feat: persist current proposal selections atomically`, then submits that immutable commit for independent review. Apply scoped fixes, rerun affected checks and obtain re-review before acceptance. Do not commit the next Finance service or final Decision increment with it.

## Accepted decisions and verification boundaries

1. **Accepted design refinement:** `publish(receipt)` replaces earlier separate `append_selection`/`advance` public methods so replacement and supersession cannot be forgotten by application callers. `guard_current` retains the narrow later resolution/finalization seam. Parent approved these interfaces.
2. **Replay shape:** full receipt persists expected token; a caller cannot reuse the same opaque fingerprint with a changed expected version. Later service idempotency must lookup this original receipt before generating UUID/time, and final status remains a separate query.
3. **One review per selection:** filtered unique review-ID index prevents silent review reuse and permits arbitrary below-threshold selections. This is intentional stronger durability than an application-only query.
4. **Analysis semantics:** new ID invalidates current proposal even at same hash, and marks a post-Decision case reanalysis-required under the new version. Legacy behavior is unchanged.
5. **Persistence versus authorization:** this layer validates committed pure actor shape, lineage and transitions; exact tenant/object runtime binding remains the subsequent application/auth work. It does not authorize Taylor from a display name or fallback persona.
6. **Read coherence:** token reread may yield `StaleProposal` during change; API callers will translate/refetch in the later plan. No polling loop is added here.
7. **Fabric proof:** migration/artifact compilation and SQLite tests are necessary but insufficient for SQL Server rowcount/isolation behavior. Keep real adapter concurrent-selection/analysis acceptance as a release gate with separately authorized live execution.
8. **Resolved expansion:** concrete fixture helpers, frozen migration and guarded DDL follow below. Source cost fields were checked against `data/domain/operations.py` and `services/analysis/options.py`. Parent approved `publish(SelectionReceipt)`/`guard_current`, full receipt replay and the filtered unique review-ID index.

## Concrete fixture helpers for Step 1

Place this code at the top of `tests/finance/test_proposal_selection.py`; later test imports extend it. These helpers replace the shorthand definitions earlier in this plan.

```python
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import CorpusScope, IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceProposal, FinanceReviewStatus
from data.domain.proposals import ProposalSelection, SelectionReceipt
from data.synthetic.rl001 import instantiate_rl001, build_rl001_evidence
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.persistence.sqlite import sqlite_store
from services.persistence.store import serialize_model
from services.persistence.tables import (
    case_proposal_selections, finance_review_revisions,
    analysis_versions, evidence_items, decisions, approval_satisfactions, outbox_events,
)
from services.policy.finance_review import submit_finance_review, resolve_finance_review

START = datetime.fromisoformat('2026-09-01T09:01:00-05:00')
SUBMITTED = datetime.fromisoformat('2026-09-01T14:02:00+00:00')

def fingerprint(value):
    return hashlib.sha256(serialize_model(value).encode()).hexdigest()

def actor(taylor=False):
    return IdentitySnapshot(
        persona_id='RL-PERSONA-TAYLOR' if taylor else 'RL-PERSONA-ALEX',
        source_id='RL-ENTRA-TAYLOR' if taylor else 'RL-ENTRA-ALEX',
        effective_roles=('finance_approver',) if taylor else ('material_planner', 'response_approver'),
        identity_source=IdentitySource.ENTRA,
        tenant_id='11111111-1111-4111-8111-111111111111',
        object_id='33333333-3333-4333-8333-333333333333' if taylor else '22222222-2222-4222-8222-222222222222',
        display_name='Taylor' if taylor else 'Alex',
    )

def build_analysis(case, snapshot, analysis_id):
    return analyze_case(AnalyzeCaseCommand(
        analysis_id=analysis_id, case=case, corpus=CorpusScope.DEMO_CORPUS,
        operational_snapshot=snapshot,
        evidence_items=build_rl001_evidence(snapshot, analysis_id=analysis_id, retrieved_at=START),
        analysis_started_at=START, created_at=START,
        calculation_version='rl001-options-v1',
    ))

@dataclass
class SelectionContext:
    store: object
    case: object
    snapshot: object
    analysis: object
    serial: int = 0
    alex: IdentitySnapshot = field(default_factory=actor)
    taylor: IdentitySnapshot = field(default_factory=lambda: actor(True))

    def state(self):
        with self.store.uow_factory() as uow:
            return uow.proposals.get_state(self.case.case_id)

    def publish_option(self, option_id):
        self.serial += 1
        high = next(o for o in self.analysis.response_options if o.option_id == option_id).predicted.response_cost > Decimal('20000')
        command = receipt(self, option_id, f'selection-{self.serial}',
            f'review-{self.serial}' if high else None, self.state().token,
            submitted_at=SUBMITTED + timedelta(minutes=2 * self.serial))
        return persist(self, command)

    def publish_combined(self):
        return self.publish_option('RL-OPTION-COMBINED')

    def publish_transfer(self):
        return self.publish_option('RL-OPTION-TRANSFER')

@pytest.fixture
def selection_context(tmp_path):
    store = sqlite_store(f'sqlite:///{tmp_path / "selection.db"}')
    case, snapshot = instantiate_rl001(
        case_id='RL-CASE-SELECTION', purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    analysis = build_analysis(case, snapshot, 'RL-ANALYSIS-SELECTION-1')
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    yield SelectionContext(store, case, snapshot, analysis)
    store.engine.dispose()

def receipt(ctx, option_id, selection_id, review_id, expected, *, submitted_at=SUBMITTED):
    option = next(o for o in ctx.analysis.response_options if o.option_id == option_id)
    selection = ProposalSelection(
        selection_id=selection_id,
        proposal=FinanceProposal(case_id=ctx.case.case_id,
            analysis_id=ctx.analysis.analysis_id,
            analysis_material_hash=ctx.analysis.material_hash,
            option_id=option_id, response_cost=option.predicted.response_cost),
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
        submitted_by=ctx.alex, submitted_at=submitted_at, finance_review_id=review_id,
    )
    material = json.dumps({'selection': selection.model_dump(mode='json'),
        'expected': expected.model_dump(mode='json')}, sort_keys=True, separators=(',', ':'))
    return SelectionReceipt(selection=selection, expected=expected,
        idempotency_key=f'publish:{selection_id}',
        request_fingerprint=hashlib.sha256(material.encode()).hexdigest())

def append_pending(uow, command):
    selection = command.selection
    if selection.finance_review_id is not None:
        pending = submit_finance_review(review_id=selection.finance_review_id,
            proposal=selection.proposal, actor=selection.submitted_by,
            now=selection.submitted_at)
        uow.finance_reviews.append(pending, expected_revision=None,
            idempotency_key=f'pending:{selection.selection_id}',
            request_fingerprint=fingerprint(pending))

def persist(ctx, command):
    with ctx.store.uow_factory() as uow:
        append_pending(uow, command)
        result = uow.proposals.publish(command)
        uow.commit()
        return result

def counts(store):
    with store.engine.connect() as connection:
        return {table.name: connection.scalar(select(func.count()).select_from(table))
            for table in (case_proposal_selections, finance_review_revisions,
                analysis_versions, evidence_items, decisions, approval_satisfactions, outbox_events)}
```

The rejection test uses `now=first.submitted_at + timedelta(minutes=1)` and the transfer is submitted one minute after that. No test resolves before submission; this resolves the earlier shorthand clock contradiction.

Add this exact rollback test; the failed CAS occurs **after** the new pending review and immutable receipt have been inserted:

```python
def test_late_cas_failure_rolls_back_pending_receipt_and_pointer(selection_context, monkeypatch):
    import services.persistence.proposals as module
    from services.persistence.proposals import StaleProposal
    ctx = selection_context
    before_state, before_counts = ctx.state(), counts(ctx.store)
    command = receipt(ctx, 'RL-OPTION-COMBINED', 'late-failure', 'late-review', before_state.token)
    def fail_cas(connection, **kwargs):
        assert connection.scalar(select(func.count()).select_from(case_proposal_selections)) == 1
        assert connection.scalar(select(func.count()).select_from(finance_review_revisions)) == 1
        raise StaleProposal('injected late CAS failure')
    monkeypatch.setattr(module, '_cas_projection', fail_cas)
    with pytest.raises(StaleProposal):
        persist(ctx, command)
    assert counts(ctx.store) == before_counts
    assert ctx.state() == before_state
```

Use this bounded concurrency harness for two low-cost submissions; each starts before its first write. A later test repeats with high-cost submissions and asserts losing pending review rollback.

```python
def test_two_selections_have_one_winner(selection_context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.exc import IntegrityError, OperationalError
    from services.persistence.proposals import StaleProposal
    ctx = selection_context
    expected = ctx.state().token
    commands = [receipt(ctx, 'RL-OPTION-TRANSFER', f'race-{i}', None, expected) for i in (1, 2)]
    barrier = Barrier(2)
    def contender(command):
        try:
            barrier.wait(timeout=5)
            return persist(ctx, command)
        except (StaleProposal, IntegrityError) as error:
            return error
        except OperationalError as error:
            if 'locked' not in str(error).lower():
                barrier.abort()
                raise
            return error
        except BaseException:
            barrier.abort()
            raise
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(contender, command) for command in commands]
        results = [future.result(timeout=15) for future in futures]
    winners = [r for r in results if isinstance(r, ProposalSelection)]
    assert len(winners) == 1
    assert ctx.state().selection == winners[0]
    assert ctx.state().token.generation == expected.generation + 1
    assert counts(ctx.store)['case_proposal_selections'] == 1
```

## Frozen migration for Step 2

Create `migrations/versions/0008_case_proposal_selection.py` with this content. The explicit frozen definitions must also match runtime metadata; do not import them from runtime into the migration.

```python
"""Add immutable proposal selections and case generation."""
import sqlalchemy as sa
from alembic import op

revision = '0008_case_proposal_selection'
down_revision = '0007_finance_review_revisions'
branch_labels = None
depends_on = None

JOURNAL = 'case_proposal_selections'
PAIR = '(finance_review_id IS NULL AND finance_review_revision IS NULL) OR (finance_review_id IS NOT NULL AND finance_review_revision IS NOT NULL AND finance_review_revision = 1)'
PROJECTION_FK = 'fk_case_projection_current_selection_id_case_proposal_selections'
PROJECTION_CHECK = 'ck_case_projection_proposal_generation_nonnegative'

def upgrade():
    inspector = sa.inspect(op.get_bind())
    if JOURNAL not in inspector.get_table_names():
        op.create_table(JOURNAL,
            sa.Column('selection_id', sa.String(128), nullable=False),
            sa.Column('case_id', sa.String(128), nullable=False),
            sa.Column('analysis_id', sa.String(128), nullable=False),
            sa.Column('analysis_material_hash', sa.String(64), nullable=False),
            sa.Column('workflow_version', sa.String(64), nullable=False),
            sa.Column('finance_review_id', sa.String(128), nullable=True),
            sa.Column('finance_review_revision', sa.Integer(), nullable=True),
            sa.Column('expected_generation', sa.Integer(), nullable=False),
            sa.Column('expected_selection_id', sa.String(128), nullable=True),
            sa.Column('idempotency_key', sa.String(256), nullable=False),
            sa.Column('request_fingerprint', sa.String(64), nullable=False),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('payload_json', sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint('selection_id', name='pk_case_proposal_selections'),
            sa.UniqueConstraint('idempotency_key', name='uq_case_proposal_selections_idempotency_key'),
            sa.CheckConstraint(PAIR, name=op.f('ck_case_proposal_selections_review_pair')),
            sa.CheckConstraint('expected_generation >= 0', name=op.f('ck_case_proposal_selections_generation_nonnegative')),
            sa.CheckConstraint("workflow_version = 'independent-finance-v1'", name=op.f('ck_case_proposal_selections_policy')),
            sa.ForeignKeyConstraint(['case_id'], ['case_instances.case_id'], ondelete='RESTRICT', name='fk_case_proposal_selections_case_id_case_instances'),
            sa.ForeignKeyConstraint(['analysis_id'], ['analysis_versions.analysis_id'], ondelete='RESTRICT', name='fk_case_proposal_selections_analysis_id_analysis_versions'),
            sa.ForeignKeyConstraint(['expected_selection_id'], ['case_proposal_selections.selection_id'], ondelete='RESTRICT', name='fk_case_proposal_selections_expected_selection_id_case_proposal_selections'),
            sa.ForeignKeyConstraint(['finance_review_id', 'finance_review_revision'], ['finance_review_revisions.review_id', 'finance_review_revisions.revision'], ondelete='RESTRICT', name='fk_case_proposal_selections_finance_review'),
        )
    existing_indexes = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(JOURNAL)}
    for column in ('case_id', 'analysis_id', 'submitted_at'):
        name = f'ix_case_proposal_selections_{column}'
        if name not in existing_indexes:
            op.create_index(name, JOURNAL, [column])
    if 'uq_case_proposal_selections_finance_review_id' not in existing_indexes:
        op.create_index('uq_case_proposal_selections_finance_review_id', JOURNAL,
            ['finance_review_id'], unique=True,
            sqlite_where=sa.text('finance_review_id IS NOT NULL'),
            mssql_where=sa.text('finance_review_id IS NOT NULL'))
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('case_projection')}
    fks = {f['name'] for f in inspector.get_foreign_keys('case_projection')}
    checks = {c['name'] for c in inspector.get_check_constraints('case_projection')}
    if not {'proposal_generation', 'current_selection_id'} <= columns or PROJECTION_FK not in fks or PROJECTION_CHECK not in checks:
        with op.batch_alter_table('case_projection') as batch:
            if 'proposal_generation' not in columns:
                batch.add_column(sa.Column('proposal_generation', sa.Integer(), nullable=False, server_default=sa.text('0')))
            if 'current_selection_id' not in columns:
                batch.add_column(sa.Column('current_selection_id', sa.String(128), nullable=True))
            if PROJECTION_FK not in fks:
                batch.create_foreign_key(PROJECTION_FK, JOURNAL, ['current_selection_id'], ['selection_id'], ondelete='RESTRICT')
            if PROJECTION_CHECK not in checks:
                batch.create_check_constraint(op.f(PROJECTION_CHECK), 'proposal_generation >= 0')
    indexes = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('case_projection')}
    if 'ix_case_projection_current_selection_id' not in indexes:
        op.create_index('ix_case_projection_current_selection_id', 'case_projection', ['current_selection_id'])

def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('case_projection')}
    fks = {f['name'] for f in inspector.get_foreign_keys('case_projection')}
    checks = {c['name'] for c in inspector.get_check_constraints('case_projection')}
    indexes = {i['name'] for i in inspector.get_indexes('case_projection')}
    if 'ix_case_projection_current_selection_id' in indexes:
        op.drop_index('ix_case_projection_current_selection_id', table_name='case_projection')
    if {'proposal_generation', 'current_selection_id'} & columns:
        with op.batch_alter_table('case_projection') as batch:
            if PROJECTION_FK in fks:
                batch.drop_constraint(PROJECTION_FK, type_='foreignkey')
            if PROJECTION_CHECK in checks:
                batch.drop_constraint(op.f(PROJECTION_CHECK), type_='check')
            if 'current_selection_id' in columns:
                batch.drop_column('current_selection_id')
            if 'proposal_generation' in columns:
                batch.drop_column('proposal_generation')
    if JOURNAL in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(JOURNAL)
```

Runtime metadata uses the same column/constraint declarations without `sa.` prefixes and with `CheckConstraint` local names `review_pair`, `generation_nonnegative`, `policy` to respect the existing naming convention. Add `ForeignKeyConstraint` to imports. The filtered unique `Index` supplies both `sqlite_where=text(...)` and `mssql_where=text(...)`. Projection uses `CheckConstraint('proposal_generation >= 0', name='proposal_generation_nonnegative')`. No JSON check is added to SQLite because the accepted SQLite schema does not require JSON1; Fabric adds its existing ISJSON convention.

## Exact Fabric DDL and batch ordering

Insert this journal section after existing Finance review table/index batches. Existing `app.case_instances` and `app.analysis_versions` precede it.

```sql
IF OBJECT_ID(N'app.case_proposal_selections', N'U') IS NULL
BEGIN
CREATE TABLE app.case_proposal_selections (
    selection_id nvarchar(128) NOT NULL,
    case_id nvarchar(128) NOT NULL,
    analysis_id nvarchar(128) NOT NULL,
    analysis_material_hash nvarchar(64) NOT NULL,
    workflow_version nvarchar(64) NOT NULL,
    finance_review_id nvarchar(128) NULL,
    finance_review_revision int NULL,
    expected_generation int NOT NULL,
    expected_selection_id nvarchar(128) NULL,
    idempotency_key nvarchar(256) NOT NULL,
    request_fingerprint nvarchar(64) NOT NULL,
    submitted_at datetimeoffset(6) NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_case_proposal_selections PRIMARY KEY (selection_id),
    CONSTRAINT uq_case_proposal_selections_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT ck_case_proposal_selections_review_pair CHECK ((finance_review_id IS NULL AND finance_review_revision IS NULL) OR (finance_review_id IS NOT NULL AND finance_review_revision IS NOT NULL AND finance_review_revision = 1)),
    CONSTRAINT ck_case_proposal_selections_generation_nonnegative CHECK (expected_generation >= 0),
    CONSTRAINT ck_case_proposal_selections_policy CHECK (workflow_version = N'independent-finance-v1'),
    CONSTRAINT ck_case_proposal_selections_payload_json CHECK (ISJSON(payload_json) = 1),
    CONSTRAINT fk_case_proposal_selections_case_id_case_instances FOREIGN KEY (case_id) REFERENCES app.case_instances (case_id),
    CONSTRAINT fk_case_proposal_selections_analysis_id_analysis_versions FOREIGN KEY (analysis_id) REFERENCES app.analysis_versions (analysis_id),
    CONSTRAINT fk_case_proposal_selections_expected_selection_id_case_proposal_selections FOREIGN KEY (expected_selection_id) REFERENCES app.case_proposal_selections (selection_id),
    CONSTRAINT fk_case_proposal_selections_finance_review FOREIGN KEY (finance_review_id, finance_review_revision) REFERENCES app.finance_review_revisions (review_id, revision)
);
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_proposal_selections') AND name = N'ix_case_proposal_selections_case_id')
    CREATE INDEX ix_case_proposal_selections_case_id ON app.case_proposal_selections (case_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_proposal_selections') AND name = N'ix_case_proposal_selections_analysis_id')
    CREATE INDEX ix_case_proposal_selections_analysis_id ON app.case_proposal_selections (analysis_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_proposal_selections') AND name = N'ix_case_proposal_selections_submitted_at')
    CREATE INDEX ix_case_proposal_selections_submitted_at ON app.case_proposal_selections (submitted_at);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_proposal_selections') AND name = N'uq_case_proposal_selections_finance_review_id')
    CREATE UNIQUE INDEX uq_case_proposal_selections_finance_review_id ON app.case_proposal_selections (finance_review_id) WHERE finance_review_id IS NOT NULL;
GO
```

Insert these separate batches after existing `app.case_projection` CREATE block and before its existing index block. `integrations.fabric.schema.split_go_batches` executes one transaction per GO batch; new column references therefore compile after their ALTER has executed on both existing and fresh schemas. Do not combine the ALTER batches with the following constraint/index statements.

```sql
IF COL_LENGTH(N'app.case_projection', N'proposal_generation') IS NULL
    ALTER TABLE app.case_projection ADD proposal_generation int NOT NULL CONSTRAINT df_case_projection_proposal_generation DEFAULT (0) WITH VALUES;
GO
IF COL_LENGTH(N'app.case_projection', N'current_selection_id') IS NULL
    ALTER TABLE app.case_projection ADD current_selection_id nvarchar(128) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(N'app.case_projection') AND name = N'ck_case_projection_proposal_generation_nonnegative')
    ALTER TABLE app.case_projection ADD CONSTRAINT ck_case_projection_proposal_generation_nonnegative CHECK (proposal_generation >= 0);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID(N'app.case_projection') AND name = N'fk_case_projection_current_selection_id_case_proposal_selections')
    ALTER TABLE app.case_projection ADD CONSTRAINT fk_case_projection_current_selection_id_case_proposal_selections FOREIGN KEY (current_selection_id) REFERENCES app.case_proposal_selections (selection_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_projection') AND name = N'ix_case_projection_current_selection_id')
    CREATE INDEX ix_case_projection_current_selection_id ON app.case_projection (current_selection_id);
GO
```

Artifact tests use `split_go_batches` to assert each ALTER-ADD-column batch precedes every constraint/index batch mentioning that column, and that column addition and constraint/index creation are not the same batch. The checked-in artifact is a recoverable sequence of additive batches, not one all-or-nothing schema transaction; runtime activation remains separately gated.

## Concrete reflected 0007 fixture and upgrade proof

Add these helpers/tests to `tests/persistence/test_sqlite_store.py`. Use local imports to avoid changing its existing fixtures. `put` filters against **reflected predecessor columns**, never current runtime tables; full canonical strings are taken from the frozen fixture. Current model decoding is allowed because policy compatibility already proves those canonical models retain legacy shape.

```python
def _seed_reflected_finance_legacy(engine):
    import json
    from pathlib import Path
    import sqlalchemy as sa
    from data.domain.cases import CaseInstance
    from data.domain.analysis import AnalysisVersion
    from data.domain.decisions import Decision
    from data.domain.execution import ActionPlanningRequested
    from data.domain.finance import FinanceProposal
    from data.domain.decisions import IdentitySnapshot
    from data.domain.evidence import IdentitySource
    from data.synthetic.rl001 import OperationalSnapshot
    from services.persistence.store import serialize_model
    from services.policy.finance_review import submit_finance_review
    from datetime import datetime
    from hashlib import sha256

    raw = json.loads(Path('tests/finance/fixtures/legacy-policy.json').read_text())
    case = CaseInstance.model_validate_json(raw['case'])
    projected = CaseInstance.model_validate_json(raw['projected_case'])
    snapshot = OperationalSnapshot.model_validate_json(raw['snapshot'])
    analysis = AnalysisVersion.model_validate_json(raw['analysis'])
    decision = Decision.model_validate_json(raw['decision'])
    reflected = sa.MetaData()
    reflected.reflect(bind=engine)
    assert 'proposal_generation' not in reflected.tables['case_projection'].c
    with engine.begin() as connection:
        def put(name, model, *, canonical=None, **extra):
            table = reflected.tables[name]
            fields = {**model.model_dump(mode='python'), **extra,
                'payload_json': canonical if canonical is not None else serialize_model(model)}
            connection.execute(table.insert().values(**{
                key: value for key, value in fields.items() if key in table.c
            }))
        put('case_instances', case, canonical=raw['case'])
        put('operational_snapshots', snapshot, canonical=raw['snapshot'],
            analysis_horizon_end=snapshot.analysis_horizon_end.isoformat())
        put('analysis_versions', analysis, canonical=raw['analysis'],
            runtime_mode=analysis.material.runtime_mode.value)
        for evidence in analysis.evidence_items:
            put('evidence_items', evidence, analysis_id=analysis.analysis_id)
        for satisfaction in analysis.approval_satisfactions:
            put('approval_satisfactions', satisfaction, decision_id=None)
        put('decisions', decision, canonical=raw['decision'])
        for satisfaction in decision.approval_satisfactions:
            put('approval_satisfactions', satisfaction, decision_id=decision.decision_id)
        event = ActionPlanningRequested.for_decision(decision)
        put('outbox_events', event)
        put('case_projection', projected, canonical=raw['projected_case'],
            current_analysis_id=analysis.analysis_id,
            current_analysis_hash=analysis.material_hash,
            current_decision_id=decision.decision_id)
        option = next(o for o in analysis.response_options if o.option_id == 'RL-OPTION-COMBINED')
        pending = submit_finance_review(review_id='legacy-migration-review',
            proposal=FinanceProposal(case_id=case.case_id, analysis_id=analysis.analysis_id,
                analysis_material_hash=analysis.material_hash, option_id=option.option_id,
                response_cost=option.predicted.response_cost),
            actor=IdentitySnapshot(persona_id='RL-PERSONA-ALEX', source_id='RL-ENTRA-ALEX',
                identity_source=IdentitySource.ENTRA,
                effective_roles=('material_planner', 'response_approver'),
                tenant_id='11111111-1111-4111-8111-111111111111',
                object_id='22222222-2222-4222-8222-222222222222'),
            now=datetime.fromisoformat('2026-09-01T14:02:00+00:00'))
        put('finance_review_revisions', pending, revision=1, case_id=case.case_id,
            analysis_id=analysis.analysis_id, analysis_material_hash=analysis.material_hash,
            option_id=option.option_id, recorded_at=pending.submitted_at,
            idempotency_key='legacy-migration-review-key',
            request_fingerprint=sha256(serialize_model(pending).encode()).hexdigest())
    return raw, case.case_id, analysis.analysis_id, decision.decision_id

def _raw_legacy_payloads(engine):
    import sqlalchemy as sa
    reflected = sa.MetaData()
    reflected.reflect(bind=engine)
    names = ('case_instances', 'operational_snapshots', 'case_projection',
        'analysis_versions', 'evidence_items', 'decisions', 'approval_satisfactions',
        'outbox_events', 'finance_review_revisions')
    with engine.connect() as connection:
        return {name: tuple(connection.scalars(sa.select(reflected.tables[name].c.payload_json)
            .order_by(*reflected.tables[name].primary_key.columns))) for name in names}

def test_selection_upgrade_preserves_frozen_0007_records(tmp_path, monkeypatch):
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from data.domain import RuntimeMode
    from services.persistence.sqlite import SqliteStore, build_sqlite_engine
    from services.persistence.store import serialize_model
    from services.analysis.service import analysis_material_hash

    # migrations/env.py otherwise lets a process environment URL override Config.
    monkeypatch.delenv('SUPPLY_RESPONSE_DATABASE_URL', raising=False)
    url = f'sqlite:///{tmp_path / "legacy-selection-upgrade.db"}'
    config = Config('migrations/alembic.ini')
    config.set_main_option('sqlalchemy.url', url)
    command.upgrade(config, '0007_finance_review_revisions')
    engine = build_sqlite_engine(url)
    raw, case_id, analysis_id, decision_id = _seed_reflected_finance_legacy(engine)
    before = _raw_legacy_payloads(engine)
    old_fks = {f['name'] for f in sa.inspect(engine).get_foreign_keys('case_projection')}
    old_indexes = {i['name'] for i in sa.inspect(engine).get_indexes('case_projection')}
    engine.dispose()
    command.upgrade(config, '0008_case_proposal_selection')
    engine = build_sqlite_engine(url)
    assert _raw_legacy_payloads(engine) == before
    assert old_fks <= {f['name'] for f in sa.inspect(engine).get_foreign_keys('case_projection')}
    assert old_indexes <= {i['name'] for i in sa.inspect(engine).get_indexes('case_projection')}
    with engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert connection.exec_driver_sql('SELECT proposal_generation, current_selection_id FROM case_projection').one() == (0, None)
    store = SqliteStore(engine, runtime_mode=RuntimeMode.FALLBACK)
    assert serialize_model(store.get_case(case_id)) == raw['projected_case']
    analysis = store.get_analysis(analysis_id)
    assert serialize_model(analysis) == raw['analysis']
    assert analysis_material_hash(analysis.material) == raw['analysis_material_hash']
    with store.uow_factory() as uow:
        assert serialize_model(uow.decisions.get(decision_id)) == raw['decision']
        assert uow.finance_reviews.get_latest('legacy-migration-review')[1] == 1
    engine.dispose()
    command.downgrade(config, '0007_finance_review_revisions')
    engine = build_sqlite_engine(url)
    assert _raw_legacy_payloads(engine) == before
    assert 'case_proposal_selections' not in sa.inspect(engine).get_table_names()
    assert 'current_selection_id' not in {c['name'] for c in sa.inspect(engine).get_columns('case_projection')}
    engine.dispose()
    command.upgrade(config, '0008_case_proposal_selection')
    engine = build_sqlite_engine(url)
    assert _raw_legacy_payloads(engine) == before
    engine.dispose()
```

The migration connection in current `migrations/env.py` does not install runtime SQLite connection listeners; do not claim its foreign-key pragma is enabled during Alembic execution. This test proves constraints/indexes survive the batch rebuild, checks all references after upgrade with runtime enforcement enabled, and uses no disabling pragma. A migration-engine listener change would be a broader separate task and is not needed here.

In `tests/finance/test_workflow_policy.py`, change the migration target of its runtime-read test from `0007_finance_review_revisions` to `head` and rename it `test_frozen_legacy_rows_read_from_current_migrated_database`. Keep all raw JSON/hash assertions and direct `SqliteStore(build_sqlite_engine(...))` construction. Add the same `monkeypatch.delenv('SUPPLY_RESPONSE_DATABASE_URL', raising=False)` isolation to that test. This is required dependency adjustment, not a change to the compatibility requirement.

## Expansion validation and contradictions resolved

- Parent approved the interface refinement, full receipt replay and filtered unique index; no interface question remains in this draft.
- Fixed the nullable SQL check to reject a present review ID paired with NULL revision. SQL's UNKNOWN truth value made the earlier abbreviated check insufficient.
- Replaced the policy test's unupgraded-schema read with a current-schema read; explicit predecessor migration proof now uses reflected old tables.
- Removed the test clock mismatch between wrapper submission and review time. Supersession still fails closed on backward time.
- Barrier waits are bounded at five seconds; futures at fifteen seconds. High-cost failure tests assert rollback of both pre-CAS pending review and receipt, not merely pointer equality.
- Each new Fabric column is added in its own GO batch before any later constraint/index references it; existing batch splitting conventions are reused.
- Implementer commits the scoped verified patch before independent review; fixes and re-review precede acceptance.
- No baseline regeneration, binary fixture, runtime activation, production edit or live call is part of this planning work.
- Planning validation: all ten complete Python blocks parse; the full frozen migration passed upgrade, repeated upgrade and downgrade against in-memory SQLite. The exact reflected seed helper also ran against an in-memory predecessor-shaped schema: populated upgrade/downgrade preserved every captured raw payload. A read-only deterministic analysis probe confirmed distinct analysis IDs can have the same material hash under the new policy, so the same-hash invalidation fixture is reachable without tampering. These checks do not substitute for the implementation tests above.
