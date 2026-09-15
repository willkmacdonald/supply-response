# Repeatable Presenter Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every presenter-initiated inbox check produce a fresh, source-bound disruption journey while retaining only the current presenter case and its three most recent historical presenter cases.

**Architecture:** The inbox-check response mints an opaque presenter-run identifier, and case creation hashes that identifier together with the validated Outlook message identity. A focused persistence module creates the new presenter case and prunes expired presenter-case aggregates in one database transaction. The React client only carries the server-issued identifier between the check and analysis clicks; it does not clear or manufacture business state.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, SQLite, Microsoft Fabric SQL, React, TypeScript, Vitest, pytest.

## Global Constraints

- A successful `POST /api/inbox/check` creates a new opaque presenter-run identifier; a failed check creates no usable run or case.
- The same validated Outlook message under different presenter-run identifiers creates different Case Instances.
- Retries and concurrent case-creation requests within one presenter run return the same Case Instance.
- A fresh presenter case starts without an Analysis Version, Finance Review, Taylor approval, Alex Decision, execution record, draft, playback, or outcome.
- Retain the current presenter case plus the three most recent historical presenter cases.
- Permanently prune only live showcase cases with a bound supplier email, including legacy inbound cases without an explicit presenter-run identifier.
- Automated-test cases, fallback cases, live showcase cases without a supplier email, operational source data, and the traditional Power BI reporting dataset are never retention targets.
- Case creation and retention pruning must commit or roll back together.
- Remove **Open case dashboard** while preserving **Explore in Power BI** and exact card-level supporting-data links.
- Use tests first for every behavior change and commit each independently reviewed task.

---

## File map

- `data/domain/cases.py`: owns the optional immutable `presenter_run_id` attached to a Case Instance.
- `integrations/workiq/inbox.py`: retains the provider-facing inbox result without application run state.
- `apps/api/app/contracts.py`: adds the presenter-run identifier to the API-facing inbox and case responses.
- `apps/api/app/routes/inbox.py`: mints run identifiers, revalidates email, derives case identity, and calls the atomic presenter-case persistence operation.
- `services/persistence/presenter_runs.py`: owns presenter-case selection, retention planning, aggregate deletion order, and row-count reporting.
- `services/persistence/store.py`: supplies transactional case insertion and public preview/apply methods without changing ordinary case creation.
- `services/persistence/ports.py`: documents the presenter-case store interface used by the API and cleanup command.
- `scripts/prune_presenter_runs.py`: previews or explicitly applies the bounded first-deployment cleanup.
- `apps/web/src/types.ts`, `apps/web/src/api.ts`, `apps/web/src/components/InboxCheck.tsx`: carry the server-issued run identifier from inbox check to case creation.
- `apps/web/src/components/CaseHeader.tsx`: removes the redundant exact-case dashboard link.
- `README.md`, `docs/ROADMAP.md`, `CONTEXT.md`: explain repeatable presenter runs, the four-history cap, and the intended Power BI entry points.

---

### Task 1: Server-issued presenter-run identity

**Files:**

- Modify: `data/domain/cases.py`
- Modify: `apps/api/app/contracts.py`
- Modify: `apps/api/app/routes/inbox.py`
- Modify: `tests/domain/test_rl001_contract.py`
- Modify: `tests/api/test_inbox.py`
- Modify: `tests/api/test_inbound_cases.py`

**Interfaces:**

- Produces: `PRESENTER_RUN_PATTERN = r"^RL-RUN-[0-9a-f]{32}$"` in `data.domain.cases`.
- Produces: `InboxCheckResponse.presenter_run_id: str` without changing provider-facing `InboxCheck`.
- Produces: `CaseInstance.presenter_run_id: str | None` and `CaseResponse.presenter_run_id: str | None`.
- Changes: `CreateInboundCaseRequest` requires `presenter_run_id`, `internet_message_id`, and `review_fingerprint`.
- Consumes later: Task 2 calls `store.create_presenter_case(case, snapshot)` after the API derives the new case identity.

- [ ] **Step 1: Add failing domain and API contract tests**

Add tests proving that the server—not the client UI—creates the run identity and that Case identity changes across runs:

```python
def test_successive_checks_mint_distinct_presenter_runs(app, client, services):
    setup_inbox(app, services)
    first = client.post("/api/inbox/check", json={})
    second = client.post("/api/inbox/check", json={})
    assert first.status_code == second.status_code == 200
    assert re.fullmatch(PRESENTER_RUN_PATTERN, first.json()["presenter_run_id"])
    assert first.json()["presenter_run_id"] != second.json()["presenter_run_id"]


def test_same_email_is_fresh_across_runs_and_idempotent_within_run(
    app, client, services, tmp_path
):
    _, _, payload = setup(app, services, tmp_path)
    run_a = {**payload, "presenter_run_id": "RL-RUN-" + "a" * 32}
    run_b = {**payload, "presenter_run_id": "RL-RUN-" + "b" * 32}
    first = client.post("/api/inbox/cases", json=run_a)
    retry = client.post("/api/inbox/cases", json=run_a)
    second = client.post("/api/inbox/cases", json=run_b)
    assert first.status_code == retry.status_code == second.status_code == 200
    assert retry.json()["case_id"] == first.json()["case_id"]
    assert second.json()["case_id"] != first.json()["case_id"]
    assert second.json()["presenter_run_id"] == run_b["presenter_run_id"]
    assert second.json()["current_analysis_id"] is None
    assert second.json()["current_decision_id"] is None
    assert second.json()["status"] == "open"
```

Also extend the untrusted-request test so missing or malformed `presenter_run_id` returns the private `422 INVALID_INBOUND_REQUEST` response, and extend the concurrent request test so both requests use the same run identifier.

- [ ] **Step 2: Run the focused tests and verify the contract is red**

Run:

```bash
uv run pytest tests/domain/test_rl001_contract.py tests/api/test_inbox.py tests/api/test_inbound_cases.py -q
```

Expected: failures show `presenter_run_id` is absent from the models and requests, and two checks/case creations still reuse the old identity.

- [ ] **Step 3: Add the immutable run field and server response field**

In `data/domain/cases.py`, add the shared format near `WorkflowVersion`, add the field after `supplier_email`, remove it from serialized JSON when absent, and add the exact same-Case guard immediately after `changed = type(self).model_validate(values)`:

```python
from pydantic import Field

PRESENTER_RUN_PATTERN = r"^RL-RUN-[0-9a-f]{32}$"

presenter_run_id: str | None = Field(
    default=None,
    pattern=PRESENTER_RUN_PATTERN,
)

if self.presenter_run_id is None:
    payload.pop("presenter_run_id", None)

if (
    changed.presenter_run_id != self.presenter_run_id
    and changed.case_id == self.case_id
):
    raise ValueError("presenter_run_id changes require a different case_id")
```

In `apps/api/app/contracts.py`, add the API-facing response and expose the optional Case lineage field:

```python
from pydantic import Field
from data.domain.cases import PRESENTER_RUN_PATTERN
from integrations.workiq.inbox import InboxCheck

class InboxCheckResponse(InboxCheck):
    presenter_run_id: str = Field(pattern=PRESENTER_RUN_PATTERN)

presenter_run_id: str | None = Field(
    default=None,
    pattern=PRESENTER_RUN_PATTERN,
)
```

- [ ] **Step 4: Mint the run and include it in inbound Case identity**

In `apps/api/app/routes/inbox.py`, change the check decorator to `@router.post("/api/inbox/check", response_model=InboxCheckResponse)` and use UUID4 hex only after a successful provider result:

```python
from uuid import uuid4
from apps.api.app.contracts import InboxCheckResponse
from data.domain.cases import PRESENTER_RUN_PATTERN

class CreateInboundCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presenter_run_id: str = Field(pattern=PRESENTER_RUN_PATTERN)
    internet_message_id: str = Field(min_length=3, max_length=998)
    review_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")

provider_result = InboxCheck.model_validate(
    await services.inbox_service.check_inbox(
        actor=actor,
        checked_at=services.clock(),
    )
)
result = InboxCheckResponse(
    **provider_result.model_dump(),
    presenter_run_id=f"RL-RUN-{uuid4().hex}",
)

key = json.dumps(
    [
        actor.tenant_id,
        actor.object_id,
        source.internet_message_id,
        request.presenter_run_id,
    ],
    separators=(",", ":"),
)

values = {
    **live.case.model_dump(),
    "supplier_email": source,
    "presenter_run_id": request.presenter_run_id,
}
```

Update `_matching_case` to require `case.presenter_run_id == presenter_run_id`, while retaining all existing tenant, mailbox, stable-message, fingerprint, and parsed-fact checks. For this task, continue using `create_case`; Task 2 replaces only this presenter path with its transactional retention variant.

- [ ] **Step 5: Run focused tests and the API/domain regression set**

Run:

```bash
uv run pytest tests/domain/test_rl001_contract.py tests/api/test_inbox.py tests/api/test_inbound_cases.py tests/api/test_case_lifecycle.py tests/persistence/test_inbound_binding.py -q
```

Expected: all selected tests pass, including distinct cross-run Case IDs and same-run idempotency.

- [ ] **Step 6: Commit Task 1**

```bash
git add data/domain/cases.py apps/api/app/contracts.py apps/api/app/routes/inbox.py tests/domain/test_rl001_contract.py tests/api/test_inbox.py tests/api/test_inbound_cases.py
git commit -m "feat: create fresh presenter run identities"
```

---

### Task 2: Atomic presenter-case retention and bounded cleanup

**Files:**

- Create: `services/persistence/presenter_runs.py`
- Create: `tests/persistence/test_presenter_runs.py`
- Create: `scripts/prune_presenter_runs.py`
- Modify: `services/persistence/store.py`
- Modify: `services/persistence/ports.py`
- Modify: `apps/api/app/routes/inbox.py`
- Modify: `tests/api/test_inbound_cases.py`
- Modify: `tests/persistence/test_fabric_sql.py`

**Interfaces:**

- Consumes: `CaseInstance.presenter_run_id` from Task 1.
- Produces: immutable `PresenterRetentionPlan(current_case_id, retained_case_ids, pruned_case_ids)`.
- Produces: immutable `PresenterRetentionResult(plan, deleted_rows)`.
- Produces: `SqlAlchemyStore.create_presenter_case(case, snapshot, *, historical_limit=3) -> PresenterRetentionResult`.
- Produces: `SqlAlchemyStore.preview_presenter_retention(*, historical_limit=3) -> PresenterRetentionPlan`.
- Produces: `SqlAlchemyStore.apply_presenter_retention(plan) -> PresenterRetentionResult`, which rejects a stale plan.

- [ ] **Step 1: Write failing retention selection and aggregate deletion tests**

Create `tests/persistence/test_presenter_runs.py` with a `PopulatedPresenterStore` fixture object containing `store`, `current_case`, `current_snapshot`, `three_recent_presenter_cases`, `oldest_presenter_case`, `unbound_showcase_case`, and `automated_test_case`. Build those records with `instantiate_rl001`; bind presenter cases with the existing `source()` fixture helper; set explicit, distinct run IDs for the four new-format cases; leave the oldest presenter case without a run ID to exercise legacy eligibility; and insert one valid descendant row in every aggregate table through existing store/repository APIs or FK-valid SQLAlchemy inserts.

The fixture must include:

- five live showcase cases with `supplier_email` bindings, the newest one passed as current;
- one live automated-test case;
- one fallback showcase case in a separate fallback store test;
- one live showcase case without a supplier-email binding; and
- dependent analysis, evidence, selection, Finance review, approval, Decision, outbox, action, projection, draft, attempt, event, playback, and observation rows for the oldest presenter case.

The core expectations are:

```python
def test_create_presenter_case_keeps_current_plus_three_and_deletes_aggregate(
    populated_presenter_store: PopulatedPresenterStore,
):
    fixture = populated_presenter_store
    result = fixture.store.create_presenter_case(
        fixture.current_case,
        fixture.current_snapshot,
    )
    assert result.plan.current_case_id == fixture.current_case.case_id
    assert result.plan.retained_case_ids[0] == fixture.current_case.case_id
    assert len(result.plan.retained_case_ids) == 4
    assert result.plan.pruned_case_ids == (fixture.oldest_presenter_case.case_id,)
    assert set(fixture.store.list_cases(purpose=CasePurpose.SHOWCASE)) == {
        fixture.current_case,
        *fixture.three_recent_presenter_cases,
        fixture.unbound_showcase_case,
    }
    for table in PRESENTER_AGGREGATE_DELETE_ORDER:
        assert aggregate_row_count(
            fixture.store.engine,
            table,
            fixture.oldest_presenter_case.case_id,
        ) == 0
    assert fixture.store.get_case(fixture.automated_test_case.case_id) == (
        fixture.automated_test_case
    )


def test_pruning_failure_rolls_back_new_case_and_history(
    populated_presenter_store: PopulatedPresenterStore,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = populated_presenter_store
    before = case_ids(fixture.store)
    monkeypatch.setattr(
        presenter_runs,
        "delete_presenter_aggregates",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced")),
    )
    with pytest.raises(RuntimeError, match="forced"):
        fixture.store.create_presenter_case(
            fixture.current_case,
            fixture.current_snapshot,
        )
    assert case_ids(fixture.store) == before


def test_apply_rejects_a_changed_preview(
    populated_presenter_store: PopulatedPresenterStore,
):
    fixture = populated_presenter_store
    preview = fixture.store.preview_presenter_retention(historical_limit=3)
    fixture.store.create_presenter_case(
        fixture.current_case,
        fixture.current_snapshot,
    )
    with pytest.raises(PresenterRetentionPlanChanged):
        fixture.store.apply_presenter_retention(preview)
```

Use the shared SQLAlchemy table objects to count descendants; do not weaken foreign keys or rely on database cascade behavior.

- [ ] **Step 2: Run the persistence test and verify it is red**

Run:

```bash
uv run pytest tests/persistence/test_presenter_runs.py -q
```

Expected: import failures identify the absent retention types and store methods.

- [ ] **Step 3: Implement deterministic retention planning**

Create `services/persistence/presenter_runs.py` with focused immutable results:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PresenterRetentionPlan:
    current_case_id: str
    retained_case_ids: tuple[str, ...]
    pruned_case_ids: tuple[str, ...]

@dataclass(frozen=True)
class PresenterRetentionResult:
    plan: PresenterRetentionPlan
    deleted_rows: dict[str, int]

class PresenterRetentionPlanChanged(PersistenceError):
    pass
```

Implement `plan_presenter_retention(connection, store, *, current_case_id, historical_limit)` by selecting live showcase rows ordered by `recorded_at DESC, case_id DESC`, decoding each immutable `payload_json`, and keeping only rows whose decoded Case has `supplier_email is not None`. Always place `current_case_id` first, then retain the first three eligible historical IDs excluding current. Legacy supplier-bound cases with `presenter_run_id is None` remain eligible.

Reject a current Case that is not live, showcase, and supplier-bound. Reject a negative `historical_limit`.

- [ ] **Step 4: Implement explicit aggregate deletion order**

Define this deletion order in `services/persistence/presenter_runs.py` and record each statement's row count:

```python
PRESENTER_AGGREGATE_DELETE_ORDER = (
    "case_projection",
    "outcome_observations",
    "draft_artifacts",
    "execution_attempts",
    "execution_events",
    "action_projection",
    "playbacks",
    "outbox_events",
    "approval_satisfactions",
    "execution_actions",
    "case_proposal_selections",
    "finance_review_revisions",
    "decisions",
    "evidence_items",
    "analysis_versions",
    "analysis_claims",
    "operational_snapshots",
    "case_instances",
)
```

Build subqueries for `analysis_id`, `decision_id`, `action_id`, and `playback_id` before deleting their parents. Delete only descendants of `plan.pruned_case_ids`. For self-referencing proposal selections, first set `expected_selection_id` to `NULL` for target rows, then delete those target rows. No statement may target operational source or `reporting.*` tables.

- [ ] **Step 5: Refactor case insertion and add atomic store operations**

In `services/persistence/store.py`, extract the three current inserts into a connection-scoped helper:

```python
def _insert_case_connection(
    self,
    connection: Connection,
    case: CaseInstance,
    snapshot: OperationalSnapshot,
) -> None:
    connection.execute(insert(case_instances).values(case_id=case.case_id, template_id=case.template_id, purpose=case.purpose.value, runtime_mode=case.runtime_mode.value, status=case.status.value, scenario_effective_time=case.scenario_effective_time, payload_json=serialize_model(case)))
    connection.execute(insert(operational_snapshots).values(case_id=snapshot.case_id, runtime_mode=snapshot.runtime_mode.value, scenario_effective_time=snapshot.scenario_effective_time, analysis_horizon_start=snapshot.analysis_horizon_start, analysis_horizon_end=snapshot.analysis_horizon_end.isoformat(), payload_json=serialize_model(snapshot)))
    connection.execute(insert(case_projection).values(case_id=case.case_id, purpose=case.purpose.value, runtime_mode=case.runtime_mode.value, status=case.status.value, scenario_effective_time=case.scenario_effective_time, payload_json=serialize_model(case)))
```

Keep `create_case` behavior unchanged by calling the helper inside `engine.begin()`. Add:

```python
def create_presenter_case(
    self,
    case: CaseInstance,
    snapshot: OperationalSnapshot,
    *,
    historical_limit: int = 3,
) -> PresenterRetentionResult:
    self._validate_new_case(case, snapshot)
    try:
        with self.engine.begin() as connection:
            self._insert_case_connection(connection, case, snapshot)
            plan = plan_presenter_retention(
                connection,
                self,
                current_case_id=case.case_id,
                historical_limit=historical_limit,
            )
            return delete_presenter_aggregates(connection, plan)
    except IntegrityError as error:
        raise ImmutableRecordConflict(f"case already exists: {case.case_id}") from error
```

Add preview/apply methods. `apply_presenter_retention` must recompute the plan in the same transaction and raise `PresenterRetentionPlanChanged` unless it exactly matches the supplied preview before deleting anything.

Add the three methods to `CaseStore` in `services/persistence/ports.py` using the exact signatures above.

- [ ] **Step 6: Connect inbound creation and preserve concurrency behavior**

Change only the new-case branch in `apps/api/app/routes/inbox.py`:

```python
try:
    services.store.create_presenter_case(case, live.snapshot)
except ImmutableRecordConflict:
    if not _matching_case(
        services,
        case_id,
        source,
        presenter_run_id=request.presenter_run_id,
    ):
        raise InboundEmailError("INBOUND_EMAIL_CONFLICT") from None
```

Extend `tests/api/test_inbound_cases.py` to create and approve/analyze an earlier run, create another run from the same email, and assert the second response is `open` with null current pointers and a different Case ID. Then force the new run's analysis call to fail and assert the new source-bound Case remains retrievable with null current pointers while the retained earlier Case still returns only its own Decision. Preserve the existing two-request same-run race test. This covers failed-analysis retry behavior and honest reopening of retained history without borrowing state.

- [ ] **Step 7: Add the preview-first maintenance command**

Create `scripts/prune_presenter_runs.py` with two explicit modes:

```python
parser.add_argument("--apply", action="store_true")
settings = Settings()
store = build_store(settings)
plan = store.preview_presenter_retention(historical_limit=3)
print(json.dumps(asdict(plan), indent=2, sort_keys=True))
if args.apply:
    result = store.apply_presenter_retention(plan)
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
```

The default command is read-only. `--apply` uses the exact preview object as a compare-and-apply guard. Add a test that runs the command's main function against SQLite and proves preview leaves all rows intact while apply leaves four eligible presenter cases.

- [ ] **Step 8: Verify SQLite behavior, Fabric SQL compilation, and regressions**

Run:

```bash
uv run pytest tests/persistence/test_presenter_runs.py tests/persistence/test_sqlite_store.py tests/persistence/test_fabric_sql.py tests/api/test_inbound_cases.py -q
uv run ruff check services/persistence/presenter_runs.py services/persistence/store.py services/persistence/ports.py apps/api/app/routes/inbox.py scripts/prune_presenter_runs.py tests/persistence/test_presenter_runs.py tests/api/test_inbound_cases.py
uv run pyright services/persistence/presenter_runs.py services/persistence/store.py services/persistence/ports.py apps/api/app/routes/inbox.py scripts/prune_presenter_runs.py
```

Expected: all focused tests pass; SQL compilation exercises both SQLite and MSSQL dialects; lint and type checks report no errors.

- [ ] **Step 9: Commit Task 2**

```bash
git add services/persistence/presenter_runs.py services/persistence/store.py services/persistence/ports.py apps/api/app/routes/inbox.py scripts/prune_presenter_runs.py tests/persistence/test_presenter_runs.py tests/persistence/test_fabric_sql.py tests/api/test_inbound_cases.py
git commit -m "feat: retain four presenter case histories"
```

---

### Task 3: Carry run identity through the web flow and remove the redundant dashboard link

**Files:**

- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/components/InboxCheck.tsx`
- Modify: `apps/web/src/components/InboxCheck.test.tsx`
- Modify: `apps/web/src/components/CaseHeader.tsx`
- Modify: `apps/web/src/components/reportCardLinks.test.tsx`
- Modify: `apps/web/src/components/LiveSafety.test.tsx`
- Verify: `apps/web/src/components/PlanningRoutes.test.tsx`

**Interfaces:**

- Consumes: `InboxCheckResult.presenter_run_id` and `CaseInstance.presenter_run_id` from Task 1.
- Changes: `api.createCaseFromEmail(presenterRunId, internetMessageId, reviewFingerprint)`.
- Preserves: `PlanningRoutes` continues to own **Explore in Power BI**.

- [ ] **Step 1: Write failing UI and API-call tests**

Add a valid run identifier to the inbox fixture:

```typescript
const result = {
  presenter_run_id: "RL-RUN-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  checked_at: "2026-09-14T05:00:00Z",
  incomplete: false,
  messages: [{
    message_id: "new-message",
    subject: "[Supply Response Demo] RL-001 | Supplier Alpha | Run A",
    sender: "will@willmacdonald.com",
    received_at: "2026-09-14T04:59:00Z",
    excerpt: "RL-MAT-10247 shipment is delayed.",
    citation_url: "https://outlook.office365.com/mail/deeplink/read/new-message",
  }],
};
```

Change the create assertion to:

```typescript
expect(create).toHaveBeenCalledWith(
  result.presenter_run_id,
  "<run-a@example.com>",
  "a".repeat(64),
);
```

In `reportCardLinks.test.tsx` and `LiveSafety.test.tsx`, assert the header never renders `Open case dashboard`, then retain the existing assertions proving `Explore in Power BI` and exact card links have their correct destinations.

- [ ] **Step 2: Run the focused frontend tests and verify they are red**

Run:

```bash
npm test -- --run src/components/InboxCheck.test.tsx src/components/reportCardLinks.test.tsx src/components/LiveSafety.test.tsx src/components/PlanningRoutes.test.tsx
```

Working directory: `apps/web`.

Expected: the create-call signature and obsolete header-link expectations fail.

- [ ] **Step 3: Carry the server-issued run identifier**

Update the TypeScript contracts:

```typescript
export interface CaseInstance {
  presenter_run_id?: string | null;
}

export interface InboxCheckResult {
  presenter_run_id: string;
  checked_at: string;
  incomplete: boolean;
  messages: InboxMessage[];
}
```

Update the API and component call:

```typescript
createCaseFromEmail: (
  presenterRunId: string,
  internetMessageId: string,
  reviewFingerprint: string,
): Promise<CaseInstance> => post("/api/inbox/cases", {
  presenter_run_id: presenterRunId,
  internet_message_id: internetMessageId,
  review_fingerprint: reviewFingerprint,
}),

const created = await api.createCaseFromEmail(
  result.presenter_run_id,
  message.internet_message_id,
  message.review_fingerprint,
);
```

Do not store the run identifier in local storage, URL state, or a client-generated value. If the page reloads before analysis, the presenter checks email again and receives a new run.

- [ ] **Step 4: Remove only the redundant header action**

Delete the `buildReportUrl` import, snapshot matching calculation, and `powerBiUrl` rendering from `CaseHeader.tsx`. Keep scenario time and Power BI availability messaging. Do not change `PlanningRoutes` or card-level report navigation.

- [ ] **Step 5: Run frontend regressions and build**

Run from `apps/web`:

```bash
npm test
npm run build
```

Expected: the full frontend suite and production build pass. The tests prove the obsolete link is absent and both intended Power BI navigation classes remain.

- [ ] **Step 6: Commit Task 3**

```bash
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/components/InboxCheck.tsx apps/web/src/components/InboxCheck.test.tsx apps/web/src/components/CaseHeader.tsx apps/web/src/components/reportCardLinks.test.tsx apps/web/src/components/LiveSafety.test.tsx apps/web/src/components/PlanningRoutes.test.tsx
git commit -m "fix: start a fresh case from each inbox check"
```

---

### Task 4: Document, validate, preview cleanup, and prepare the release

**Files:**

- Modify: `README.md`
- Modify: `docs/ROADMAP.md`
- Modify: `CONTEXT.md`
- Create: `docs/reviews/2026-09-14-repeatable-presenter-runs.md`
- Modify only if required by verified deployment inputs: `.azure/deployment-plan.md`

**Interfaces:**

- Consumes: all behavior and commands from Tasks 1–3.
- Produces: an evidence-backed release record that distinguishes local verification, cleanup preview, deployed state, and live browser acceptance.

- [ ] **Step 1: Update domain and presenter documentation**

Add this definition to `CONTEXT.md` immediately after **Supplier Email Check**:

```markdown
**Presenter Run**:
A presenter-initiated response journey created from one successful Supplier Email Check. A new Presenter Run may reuse the same Reviewed Supplier Email but always creates a new Case Instance with no inherited approvals, Decisions, or execution state. The current run and three prior presenter runs are retained.
_Avoid_: Resetting a Case Instance, reusing an old approval, global approval
```

Update `README.md` so the presenter walkthrough says:

1. open the bare application URL;
2. click **Check email for disruptions**;
3. review the found email and click **Analyze this disruption**;
4. expect a fresh Case ID and a new Taylor review;
5. use **Explore in Power BI** for the traditional comparison.

Update `docs/ROADMAP.md` to mark repeatable presenter-run implementation as locally verified only after the tests pass. Record the retained-history limit and the still-pending live deployment/browser gates without claiming them complete.

- [ ] **Step 2: Run the complete local verification set**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
npm test
npm run build
```

Run the npm commands from `apps/web`. Record exact pass/skip counts and any intentional live-test exclusions in the review document.

- [ ] **Step 3: Preview the live cleanup without deleting anything**

With the live deployment environment loaded, run:

```bash
uv run python scripts/prune_presenter_runs.py
```

Expected: JSON lists the current presenter Case ID, the three historical Case IDs that will remain, every older presenter Case ID proposed for pruning, and no deletion counts. Save the exact preview output in the review document. Verify every proposed Case is `showcase`, `live`, and supplier-email-bound before proceeding.

- [ ] **Step 4: Review the immutable release diff**

Inspect:

```bash
git diff HEAD~4..HEAD --check
git status --short
git log -5 --oneline
```

Confirm the diff contains no Power BI report-definition changes, no operational source-data deletes, and no changes to authentication or tenant permissions.

- [ ] **Step 5: Commit documentation and release evidence**

```bash
git add README.md docs/ROADMAP.md CONTEXT.md docs/reviews/2026-09-14-repeatable-presenter-runs.md .azure/deployment-plan.md
git commit -m "docs: record repeatable presenter run validation"
```

Omit `.azure/deployment-plan.md` from the staging command if verified deployment inputs did not require a change.

- [ ] **Step 6: Stop at the deployment boundary and report exact evidence**

Report the cleanup preview, local test/build results, and commit IDs. Deployment and permanent cleanup application remain explicit release actions. When deployment is authorized, validate Azure readiness, deploy the reviewed image, rerun the preview, apply that exact preview with `--apply`, and verify the live database contains exactly four eligible presenter cases.

The live browser acceptance must then demonstrate two consecutive checks of the same marked email from the bare URL. The Case IDs must differ, and tab 4 in the second run must wait for a new Taylor review even if Taylor and Alex approved the first run.

---

## Plan self-review

- Every approved design requirement maps to a task and an automated or live acceptance check.
- Run identity names and call signatures match across Python, JSON, TypeScript, and tests.
- Retention is server-side, transactional, bounded to presenter cases, and previewed before permanent cleanup.
- The plan preserves within-run idempotency and immutable historical approvals rather than clearing old records.
- The redundant case-header Power BI link is removed without altering the traditional comparison or exact evidence links.
- Deployment, cleanup application, and live acceptance are not represented as complete by local test results.
