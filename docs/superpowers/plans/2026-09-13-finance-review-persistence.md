# Durable Finance Review Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist immutable `FinanceReview` snapshots as append-only, idempotent revisions with optimistic concurrency, while preserving UnitOfWork rollback semantics on SQLite and Fabric SQL.

**Architecture:** Add one `finance_review_revisions` table keyed by `(review_id, revision)` and a focused repository that never commits or uses savepoints. A narrow `append_finance_review` persistence facade owns the transaction: on uniqueness contention it lets the entire losing UnitOfWork roll back, then opens a fresh UnitOfWork to distinguish identical replay, idempotency misuse, and stale revision. Historical tables and Decisions are untouched.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy Core, SQLite, SQL Server/Fabric SQL, Alembic, pytest.

## Global constraints

- Persistence only: no API, auth, final Decision, UI, reporting, readiness, schema-version publication, or activation.
- Use committed `data/domain/finance.py` types unchanged; optional approval notes remain in canonical `payload_json`.
- Every state transition is an insert. Never update/delete a Finance review revision.
- Do not use `Connection.begin_nested()`. A verified in-memory SQLite probe showed that releasing that savepoint can leave the inserted row durable despite a later outer rollback under the current transaction mode.
- Do not change broad SQLite engine transaction configuration in this increment.
- Repository methods never commit. Contention recovery always occurs after the losing outer UoW exits/rolls back, using a fresh UoW.
- Same key + same fingerprint + identical complete requested review returns the winner. Same key with any mismatch raises `FinanceReviewIdempotencyConflict`. A different-key stale revision raises `FinanceReviewRevisionConflict`.
- Existing Alembic revisions remain frozen. Fabric SQL changes are additive and idempotent, but must not run against live state in this task.

## Exact interfaces

Add to `services/persistence/ports.py`:

```python
class FinanceReviewStore(Protocol):
    def get_latest(self, review_id: str) -> tuple[FinanceReview, int]: ...

    def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> tuple[FinanceReview, int, str] | None: ...

    def append(
        self,
        review: FinanceReview,
        *,
        expected_revision: int | None,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[FinanceReview, int]: ...
```

Add `finance_reviews: FinanceReviewStore` to `UnitOfWork`.

Create this facade in `services/persistence/finance_reviews.py`:

```python
def append_finance_review(
    uow_factory: UnitOfWorkFactory,
    review: FinanceReview,
    *,
    expected_revision: int | None,
    idempotency_key: str,
    request_fingerprint: str,
) -> tuple[FinanceReview, int]: ...
```

The fingerprint identifies the lifecycle command, not merely the proposal.
Define `UnitOfWorkFactory = Callable[[], UnitOfWork]` locally in the focused
persistence module, following the existing Decision service alias. Do not import
the Decision service to obtain this type. `recorded_at` is the latest lifecycle
timestamp: superseded time, else reviewed time, else submitted time; normalize
the duplicated SQL timestamp to UTC for writing/comparison while retaining the
original canonical snapshot. Validate option membership and evaluated cost
against the immutable bound analysis in addition to case/hash lineage.

## Files

- Create `services/persistence/finance_reviews.py`: repository, conflicts, transition/integrity validation, and transaction-owning append facade.
- Create `migrations/versions/0007_finance_review_revisions.py`: frozen additive migration.
- Modify `services/persistence/tables.py`: table metadata.
- Modify `services/persistence/ports.py`: protocol/UoW member.
- Modify `services/persistence/store.py`: only local repository construction in `SqlAlchemyUnitOfWork.__enter__`.
- Modify `fabric/sql/001_operational_schema.sql`: additive table/index artifact without version changes.
- Modify persistence and store-contract tests.

---

### Task 1: Deliver complete append-only storage

This is one review/commit boundary: metadata, repository, UoW wiring, migration,
Fabric artifact, and SQLite tests land together so no completed task leaves
runtime metadata ahead of an existing-database migration.

**Files:**

- Create: `services/persistence/finance_reviews.py`
- Create: `migrations/versions/0007_finance_review_revisions.py`
- Modify: `services/persistence/tables.py`
- Modify: `services/persistence/ports.py`
- Modify: `services/persistence/store.py`
- Modify: `fabric/sql/001_operational_schema.sql`
- Test: `tests/persistence/test_sqlite_store.py`
- Test: `tests/persistence/test_fabric_sql.py`

- [ ] **Step 1: Write all failing storage tests**

Add `finance_review_revisions` to the exact metadata table assertion and verify:

```python
def test_finance_review_revision_schema_is_append_only_and_bound():
    table = finance_review_revisions
    assert [c.name for c in table.primary_key.columns] == ["review_id", "revision"]
    assert {fk.target_fullname for fk in table.c.case_id.foreign_keys} == {"case_instances.case_id"}
    assert {fk.target_fullname for fk in table.c.analysis_id.foreign_keys} == {"analysis_versions.analysis_id"}
    assert {c.name for c in table.constraints} >= {
        "uq_finance_review_revisions_idempotency_key",
        "ck_finance_review_revisions_revision_positive",
    }
```

Using real persisted fallback Case/Analysis fixtures and the committed pure
Finance lifecycle helpers, add tests for:

```python
def test_uncommitted_first_append_rolls_back(finance_context):
    store, pending = finance_context
    with store.uow_factory() as uow:
        assert uow.finance_reviews.append(
            pending, expected_revision=None,
            idempotency_key="submit-rollback", request_fingerprint="a" * 64
        ) == (pending, 1)
        uow.rollback()
    with store.uow_factory() as uow, pytest.raises(RecordNotFound):
        uow.finance_reviews.get_latest(pending.review_id)


def test_uncommitted_resolved_append_rolls_back(finance_context):
    store, pending = finance_context
    approved = approved_review(pending)
    append_finance_review(store.uow_factory, pending, expected_revision=None,
        idempotency_key="submit-kept", request_fingerprint="b" * 64)
    with store.uow_factory() as uow:
        assert uow.finance_reviews.append(
            approved, expected_revision=1,
            idempotency_key="approve-rollback", request_fingerprint="c" * 64
        ) == (approved, 2)
        uow.rollback()
    with store.uow_factory() as uow:
        assert uow.finance_reviews.get_latest(pending.review_id) == (pending, 1)


def test_failed_append_has_no_partial_persistence(finance_context):
    store, pending = finance_context
    append_finance_review(store.uow_factory, pending, expected_revision=None,
        idempotency_key="submit-stale", request_fingerprint="d" * 64)
    approved = approved_review(pending)
    append_finance_review(store.uow_factory, approved, expected_revision=1,
        idempotency_key="approve-kept", request_fingerprint="e" * 64)
    with pytest.raises(FinanceReviewRevisionConflict):
        append_finance_review(store.uow_factory, rejected_review(pending),
            expected_revision=1, idempotency_key="reject-stale",
            request_fingerprint="f" * 64)
    with store.engine.connect() as connection:
        rows = connection.execute(
            select(finance_review_revisions)
            .where(finance_review_revisions.c.review_id == pending.review_id)
            .order_by(finance_review_revisions.c.revision)
        ).mappings().all()
    assert [row["revision"] for row in rows] == [1, 2]
    assert [row["status"] for row in rows] == ["pending", "approved"]
```

Also test full three-snapshot preservation through supersession; sequential
identical replay; same key with different fingerprint; same key/fingerprint with
different full review; first state not pending; changed proposal/submitter/
submitted time; illegal status transitions; no transition after superseded; and
duplicated-column tampering producing `PersistenceIntegrityError`.

The three-snapshot assertion must explicitly prove that an approved or rejected
snapshot's `reviewed_by`, `reviewed_at`, and `reason` are identical on its later
superseded snapshot. Parameterize `expected_revision` with `True`, `False`, `0`,
and `-1`; booleans must be rejected even though Python treats them as integers,
and non-positive integers must be rejected before any SQL executes.

Add a focused facade-classification test. Monkeypatch only the low-level
repository `append` to raise a retained non-unique `IntegrityError`, call the
facade while no replay exists and the current revision still equals the expected
revision, assert the exact original exception object is re-raised, then query the
table and assert no row was stored:

```python
def test_facade_preserves_unclassified_integrity_error(
    finance_context, monkeypatch
):
    store, pending = finance_context
    original = IntegrityError("insert", {}, RuntimeError("foreign key failure"))

    def fail_append(self, review, **kwargs):
        del self, review, kwargs
        raise original

    monkeypatch.setattr(SqlAlchemyFinanceReviewRepository, "append", fail_append)
    with pytest.raises(IntegrityError) as caught:
        append_finance_review(
            store.uow_factory, pending, expected_revision=None,
            idempotency_key="non-unique-error", request_fingerprint="9" * 64)
    assert caught.value is original
    with store.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(
            finance_review_revisions)) == 0
```

Migration tests must expect head `0007_finance_review_revisions`, prove upgrade
creates the table, downgrade to `0006` removes only it, prove a historical
Case/Analysis/Decision round-trips unchanged after upgrade, and prove the new
revision does not import runtime metadata. Fabric artifact tests assert exact
table, composite PK, unique key, revision/JSON checks, FKs, and indexes.

- [ ] **Step 2: Verify RED without any live marker**

```bash
uv run pytest tests/persistence/test_sqlite_store.py -k finance_ -q
uv run pytest tests/persistence/test_fabric_sql.py -k finance_review -q
```

Expected: missing metadata, repository, and migration failures.

- [ ] **Step 3: Add table metadata and port**

Add after `analysis_versions`:

```python
finance_review_revisions = Table(
    "finance_review_revisions", metadata,
    Column("review_id", String(128), primary_key=True),
    Column("revision", Integer, primary_key=True),
    Column("case_id", String(128), ForeignKey("case_instances.case_id", ondelete="RESTRICT"), nullable=False, index=True),
    Column("analysis_id", String(128), ForeignKey("analysis_versions.analysis_id", ondelete="RESTRICT"), nullable=False, index=True),
    Column("analysis_material_hash", String(64), nullable=False, index=True),
    Column("option_id", String(128), nullable=False, index=True),
    Column("status", String(32), nullable=False, index=True),
    Column("idempotency_key", String(256), nullable=False),
    Column("request_fingerprint", String(64), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
    UniqueConstraint("idempotency_key", name="uq_finance_review_revisions_idempotency_key"),
    CheckConstraint("revision > 0", name="revision_positive"),
)
```

Add the exact port/UoW interfaces stated above.

- [ ] **Step 4: Implement focused repository and facade**

Define `FinanceReviewIdempotencyConflict` and
`FinanceReviewRevisionConflict` in `finance_reviews.py`. The repository:

- Pydantic-decodes full snapshots and validates every duplicated column, positive
  revision, lowercase 64-hex fingerprint, recorded timestamp, and immutable
  Case/Analysis/hash lineage.
- Allows pending→approved/rejected/superseded and approved/rejected→superseded;
  it preserves review ID, proposal, submitter, and submitted time exactly.
- `get_latest` orders by revision descending; `get_by_idempotency_key` reads the
  unique row.
- Low-level `append` performs pre-read replay checks, expected-revision checks,
  then one plain `connection.execute(insert(...))`. It does not catch
  `IntegrityError`, begin a savepoint, commit, or roll back.
- It rejects `expected_revision` when it is a bool or a non-positive integer;
  `None` is valid only for the first append.

The transaction-owning facade must be exact:

```python
def append_finance_review(uow_factory, review, *, expected_revision,
                          idempotency_key, request_fingerprint):
    try:
        with uow_factory() as uow:
            result = uow.finance_reviews.append(
                review, expected_revision=expected_revision,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint)
            uow.commit()
            return result
    except IntegrityError as error:
        # __exit__ has rolled back the entire losing transaction before this read.
        with uow_factory() as recovery:
            replay = recovery.finance_reviews.get_by_idempotency_key(idempotency_key)
            if replay is not None:
                stored, revision, fingerprint = replay
                if fingerprint == request_fingerprint and stored == review:
                    return stored, revision
                raise FinanceReviewIdempotencyConflict(
                    "Finance idempotency key was used for another request"
                ) from error
            try:
                _, actual_revision = recovery.finance_reviews.get_latest(review.review_id)
            except RecordNotFound:
                actual_revision = None
            if actual_revision != expected_revision:
                raise FinanceReviewRevisionConflict(
                    f"expected revision {expected_revision}; current revision is {actual_revision}"
                ) from error
        raise
```

The final bare `raise` is essential: when there is no idempotent winner and the
current revision still equals the caller's expectation, the uniqueness race
explanation is disproven. Preserve the original FK/check/other integrity error
instead of masking it as stale revision.

Sequential pre-read replay must likewise require both matching fingerprint and
complete `FinanceReview`, not just the key. Import the repository locally inside
`SqlAlchemyUnitOfWork.__enter__` and instantiate `self.finance_reviews`; this is
the only `store.py` change.

- [ ] **Step 5: Add frozen migration and additive Fabric SQL**

Create `0007_finance_review_revisions.py`, down-revision
`0006_playback_terminal_failure`, explicitly
mirroring all columns/constraints/indexes without importing runtime metadata.
Upgrade returns if the table exists; downgrade drops only it.

Add the equivalent guarded `app.finance_review_revisions` object after
`app.analysis_versions` in `001_operational_schema.sql`, with `nvarchar`, `int`,
`datetimeoffset(6)`, `ISJSON`, both FKs, composite PK, unique idempotency key,
positive-revision check, and indexes for case, analysis, hash, option, status,
and recorded time. Keep published versions 11/12 unchanged; activation is out of
scope and exact object verification remains a later gate.

- [ ] **Step 6: Verify the independently complete storage task**

```bash
uv run pytest tests/domain/test_finance_review.py tests/persistence/test_sqlite_store.py tests/persistence/test_fabric_sql.py -q
uv run ruff check services/persistence migrations/versions/0007_finance_review_revisions.py tests/persistence/test_sqlite_store.py tests/persistence/test_fabric_sql.py
uv run pyright services/persistence
```

Expected: all commands exit 0, including both direct rollback tests and the
failed-append/no-partial-persistence test.

- [ ] **Step 7: Commit one complete storage unit**

```bash
git add services/persistence/finance_reviews.py services/persistence/tables.py services/persistence/ports.py services/persistence/store.py migrations/versions/0007_finance_review_revisions.py fabric/sql/001_operational_schema.sql tests/persistence/test_sqlite_store.py tests/persistence/test_fabric_sql.py
git commit -m "feat(persistence): store finance review revisions"
```

---

### Task 2: Prove cross-database contention contract

**Files:**

- Modify: `tests/integration/test_store_contract.py`

- [ ] **Step 1: Write portable competing-writer tests**

Reuse `_persist_analysis(store)`. Persist pending revision 1, derive approved and
rejected snapshots, then race two calls to the facade using
`ThreadPoolExecutor(max_workers=2)` and `Barrier(2)`. Do not add synchronization
hooks to production signatures. If alignment beyond the worker-side barrier is
needed, monkeypatch/wrap the repository from the test and synchronize there.

Assert:

- different keys/fingerprints: exactly one returns revision 2, exactly one raises
  `FinanceReviewRevisionConflict`, latest is revision 2, stored revisions are
  exactly `[1, 2]`;
- same key/fingerprint/complete review: both callers return the same revision 2,
  and only one revision-2 row exists;
- same key but different review/fingerprint: one wins and the other raises
  `FinanceReviewIdempotencyConflict`;
- no losing transaction leaves any partial row.

Do not accept `OperationalError`, timeout, two different winners, or a third
row. For opted-in Fabric cleanup, delete only this test's unique review ID.

- [ ] **Step 2: Run SQLite-only contract**

```bash
uv run pytest tests/integration/test_store_contract.py -k finance_review -m 'not fabric_live' -q
```

Expected: all Finance contract tests pass without invoking
`configured_fabric_store` or `apply_fabric_schema`.

- [ ] **Step 3: Run complete non-live gate**

```bash
uv run pytest tests/domain/test_finance_review.py tests/persistence/test_sqlite_store.py tests/persistence/test_fabric_sql.py tests/integration/test_store_contract.py -m 'not fabric_live' -q
uv run ruff check services/persistence migrations/versions/0007_finance_review_revisions.py tests/persistence/test_sqlite_store.py tests/integration/test_store_contract.py
uv run pyright services/persistence
```

Expected: all commands exit 0. The marker exclusion is mandatory.

- [ ] **Step 4: Record, but do not run, the parent-owned native gate**

```bash
uv run pytest tests/integration/test_store_contract.py -k finance_review -m fabric_live -q
```

This may call `apply_fabric_schema`; it requires separate authorization and an
approved isolated Fabric test database. A skip is outstanding evidence.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_store_contract.py
git commit -m "test(persistence): prove finance review contention"
```

## Deferred service boundaries

1. This log orders states for one `review_id`; it does not choose the current
   proposal/review among multiple reviews for a case. Current-proposal freshness
   and superseding older reviews remain lifecycle/projection concerns.
2. A planning selection is not synonymous with a Finance review. The committed
   helper creates reviews only above $20,000; Alex may choose a below-threshold
   alternative after rejection without a Finance record.
3. Versions remain 11/12, so version alone cannot prove the additive table
   exists. Exact object presence is a later activation gate; this increment does
   not change readiness or activate Finance flows.
