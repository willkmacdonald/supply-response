# Supply Response Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the frozen RL-001 Supply Response demonstration from deterministic analysis through an immutable human Decision, bounded execution, Simulated Observations, and live Microsoft 365/Fabric/Foundry/Power BI presentation in the `willmacdonald.com` tenant.

**Architecture:** Preserve the Python deterministic core and place live and fallback capabilities behind identical typed ports. SQLite supplies durable fallback state; a Microsoft Fabric SQL Database supplies transactional live state and mirrors it for Power BI. A React console calls FastAPI, Entra authenticates Alex, Work IQ runs delegated through Alex, and Microsoft Agent Framework invokes Foundry-managed prompt agents while deterministic services retain all arithmetic, feasibility, approval, and ranking authority.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, SQLite, Microsoft Fabric SQL Database, pyodbc/ODBC Driver 18, React, TypeScript, Vite, Vitest, Testing Library, Playwright, MSAL, Microsoft Work IQ A2A v1.0, Microsoft Agent Framework for Python, Microsoft Foundry Agent Service, Power BI PBIP/TMDL/PBIR, `fabric-cicd`, Azure Container Apps, Bicep, pytest.

## Global Constraints

- The frozen contract is `docs/superpowers/specs/2026-08-30-supply-response-demo-contract-design.md`; when older code, fixtures, the project brief, or the earlier Milestone 1 plan differ, the frozen contract controls.
- Canonical terminology is defined in `CONTEXT.md`; do not reintroduce `ResponseScenario`, `ActionLedgerRecord`, or `OutcomeHistory` into new interfaces.
- The canonical Scenario Effective Time is exactly `2026-09-01T09:00:00-05:00[America/Chicago]`; retrieval and recording clocks remain separate wall-clock timestamps.
- Runtime mode is exactly `live` or `fallback`, is immutable per Case Instance, and may never be inferred or silently changed.
- Live acceptance uses real Entra, Work IQ, Fabric, Foundry Agent Service, Microsoft Agent Framework, and Power BI calls over a completely fictional Demo Corpus.
- Fallback uses synthetic Evidence Items and SQLite, is visibly labeled, never starts automatically, and never exposes Power BI as available.
- Work IQ uses delegated authentication in Alex's context; application-only Work IQ authentication is forbidden.
- Work IQ usage is billed through Copilot Credits; Alex must be included in the tenant's enabled usage-based billing plan before the live Work IQ gate runs.
- Initial deployment is single-tenant in `willmacdonald.com`; Microsoft 365, Azure, Fabric, and Foundry must resolve to the same Entra tenant ID.
- Commit no tenant ID, Entra object ID, UPN, client credential, access token, Fabric connection string, Foundry endpoint, workspace ID, or Power BI item ID.
- Stable personas are `RL-PERSONA-ALEX`, `RL-PERSONA-JORDAN`, and `RL-PERSONA-TAYLOR`; deployment bindings are configuration, and authorization uses `tid`, `oid`, plus app-role claims rather than UPN alone.
- Taylor requires no Microsoft 365 product license for the approved app-only flow; Jordan requires Teams access for the live Quality artifact.
- Python remains `>=3.12,<3.14`; monetary arithmetic uses `Decimal`; persisted and JSON money values use fixed decimal strings.
- Agents may retrieve, normalize, summarize, and explain; they may not own arithmetic, feasibility, conflict resolution, Approval Satisfaction, ranking, or Decision mutation.
- Finance approval is required above USD `$20,000`; Taylor's Standing Authorization covers the approved response types up to USD `$25,000` for Scenario Day 0 through Day 14 only.
- Ranking comparator order and thresholds are exact: uncovered demand `500` units, OTIF loss `10` percentage points, revenue risk `$50,000`, margin risk `$25,000`, cost `$10,000`, then exact approval burden, execution risk, and stable Response Option ID.
- Approval burden counts distinct Prerequisite Approval roles and excludes the universal Response Approver; execution risk adds `2` for each unconfirmed external supply/recovery commitment, `1` for a cross-plant movement, `1` for a schedule change, and `1` for each coordinated action after the first.
- Approval atomically appends the immutable Decision and `ActionPlanningRequested`; exactly five combined-response Execution Actions appear within 15 seconds.
- Simulated Execution is explicit, visibly labeled, deterministic, idempotent by Decision ID, lasts 45–60 seconds in production, and never sends externally, edits a purchase order, or makes a commitment.
- Power BI is live-only, contains exactly the required `Command Center` and `Actions and Outcomes` pages, defaults to the latest `showcase` Case Instance, and displays Scenario Effective Time plus projection refresh time.
- Foundry IQ, SOP retrieval, supplier-risk-document retrieval, optional Power BI pages, and Fabric IQ implementation remain out of scope.
- Every behavior change follows red-green-refactor TDD and ends with the focused commit shown in its task.
- Before every commit run the targeted tests, `.venv/bin/pytest`, `npm --prefix apps/web test`, and `npm --prefix apps/web run build` whenever that task can affect their respective surfaces.

## Program Sequence and Review Gates

| Gate | Tasks | Independently demonstrable result |
|---|---|---|
| Milestone 0 | 0 | Frozen contract, glossary, and ADRs committed together |
| Milestone 2 | 1–4 | Exact RL-001 analysis and all ten integrated evaluation cases |
| Milestone 3 | 5–8 | Restart-safe Decision, outbox, actions, retries, and observations in SQLite |
| Milestone 4 | 9–11 | Complete fallback browser journey through simulated outcomes |
| Milestone 5 | 12–13 | Fabric SQL state and two-page Power BI command center agree |
| Milestone 6 | 14–17 | Entra, Work IQ, and Foundry-backed live orchestration work in `willmacdonald.com` |
| Milestone 7 | 18–19 | Azure deployment, privacy/parity/failure/timing gates, and five rehearsals pass |

Do not start a later gate until the prior gate's exit command and reviewer gate pass. Tasks within a gate remain sequential unless their `Interfaces` block says otherwise.

## File Map

### Domain and deterministic core

- `data/domain/common.py`: immutable base model, runtime mode, case purpose, timestamps, and money serialization.
- `data/domain/operations.py`: supplier, part, inventory, BOM, production, customer, transport, qualification, and disruption records.
- `data/domain/evidence.py`: Evidence Item, Authority Scope, conflict, and Conflict Resolution contracts.
- `data/domain/analysis.py`: Analysis Version, Response Option, comparator, ranking trace, and recommendation contracts.
- `data/domain/decisions.py`: persona binding, Standing Authorization, Approval Satisfaction, identity snapshot, and immutable Decision contracts.
- `data/domain/execution.py`: Execution Action, unsent Draft Artifact, attempt/status event, outbox event, playback, and Outcome Observation contracts.
- `data/domain/cases.py`: Demo Template, Case Instance, and lifecycle projection contracts.
- `data/schemas/models.py`: temporary compatibility exports only; removed after all imports move to `data.domain`.
- `data/synthetic/rl001.py`: the one canonical RL-001 Demo Template and frozen simulated observations.
- `data/synthetic/generator.py`: noncanonical scale-fixture generation only.
- `services/analysis/exposure.py`: time-phased component and protected-order arithmetic.
- `services/analysis/options.py`: deterministic option construction and feasibility.
- `services/analysis/ranking.py`: thresholded lexicographic elimination.
- `services/analysis/service.py`: integrated Analysis Version creation and invalidation hashing.
- `services/policy/evidence.py`: freshness, validity, conflict, and authority checks.
- `services/policy/approvals.py`: Standing Authorization and Approval Satisfaction evaluation.

### Persistence, application, and execution

- `services/persistence/ports.py`: repository and unit-of-work protocols shared by SQLite and Fabric SQL.
- `services/persistence/tables.py`: SQLAlchemy Core table metadata used by both databases.
- `services/persistence/sqlite.py`: fallback engine and store.
- `services/persistence/fabric_sql.py`: Fabric SQL engine and Entra access-token injection.
- `services/persistence/store.py`: SQLAlchemy implementation of the shared store and atomic Decision/outbox transaction.
- `migrations/`: Alembic configuration and reviewed schema revisions.
- `services/execution/planner.py`: idempotent five-action creation from `ActionPlanningRequested`.
- `services/execution/playback.py`: clock-injected deterministic 45–60 second simulation.
- `services/execution/worker.py`: outbox polling, claim, retry, and status projection.
- `apps/api/app/settings.py`: validated environment configuration.
- `apps/api/app/dependencies.py`: mode-specific dependency composition.
- `apps/api/app/auth.py`: Entra JWT validation and persona/app-role authorization.
- `apps/api/app/routes/`: health, case, Decision, execution, dashboard, and auth-contract routes.
- `apps/api/app/main.py`: FastAPI assembly and worker lifespan only.

### Web, live adapters, agents, analytics, and infrastructure

- `apps/web/src/auth/`: MSAL configuration, signed-in account, and token acquisition.
- `apps/web/src/components/`: progressive Case workspace sections.
- `apps/web/src/hooks/useCaseWorkspace.ts`: the single workspace state machine.
- `apps/web/src/api.ts` and `types.ts`: typed API boundary.
- `apps/web/e2e/`: Playwright fallback and live smoke journeys.
- `integrations/workiq/client.py`: raw A2A v1.0 client using a delegated OBO token.
- `integrations/workiq/normalizer.py`: Work IQ artifacts and citations to Evidence Items without inference.
- `integrations/workiq/obo.py`: MSAL OBO exchange for `WorkIQAgent.Ask`.
- `integrations/fabric/health.py`: live Fabric SQL health and provenance.
- `agents/*/instructions.md`: immutable Signal, Context, and Decision agent instructions.
- `agents/orchestrator/workflow.py`: Microsoft Agent Framework workflow using Foundry-managed agents.
- `agents/foundry.py`: `FoundryAgent` construction from trusted names, versions, and endpoint configuration.
- `fabric/sql/001_operational_schema.sql`: reviewed live schema and analytics views.
- `fabric/power-bi/SupplyResponse.pbip`: source-controlled Power BI project.
- `fabric/deploy.py`: `fabric-cicd` deployment entry point.
- `infra/main.bicep` and `infra/modules/`: Azure Container Registry, Container Apps, managed identity, Key Vault, and monitoring.
- `infra/entra/`: idempotent CLI scripts and JSON manifests for the API/SPA registrations and app roles.
- `docs/deployment/personal-tenant.md`: exact human-run `willmacdonald.com` setup and verification gates without secrets.
- `docs/demo-script/README.md`: 3–5 minute operator path and 7–10 minute narrated path.

---

### Task 0: Commit the Frozen Contract Package

**Files:**
- Add: `CONTEXT.md`
- Add: `docs/adr/0001-isolate-runtime-provenance-by-case.md`
- Add: `docs/adr/0002-immutable-decisions-with-transactional-outbox.md`
- Add: `docs/adr/0003-use-deterministic-thresholded-lexicographic-ranking.md`
- Add: `docs/adr/0004-map-portable-demo-personas-to-tenant-identities.md`
- Modify: `docs/superpowers/specs/2026-08-30-supply-response-demo-contract-design.md`
- Add: `docs/superpowers/plans/2026-08-30-supply-response-demo-implementation.md`

**Interfaces:**
- Consumes: approved Q1–Q58 design decisions.
- Produces: one versioned Milestone 0 baseline for every later task.

- [ ] **Step 1: Verify the documentation package and relative links**

Run:

```bash
.venv/bin/pytest tests/test_documentation.py -q
test -f docs/superpowers/specs/../../adr/0001-isolate-runtime-provenance-by-case.md
test -f docs/superpowers/specs/../../adr/0002-immutable-decisions-with-transactional-outbox.md
test -f docs/superpowers/specs/../../adr/0003-use-deterministic-thresholded-lexicographic-ranking.md
test -f docs/superpowers/specs/../../adr/0004-map-portable-demo-personas-to-tenant-identities.md
git diff --check
```

Expected: pytest passes; all `test -f` commands and `git diff --check` exit `0`.

- [ ] **Step 2: Verify no deployment identity values entered the package**

Run:

```bash
rg -n -i '[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' CONTEXT.md docs/adr docs/superpowers/specs docs/superpowers/plans | rg -v 'example\.invalid|00000000-0000-0000-0000-000000000000'
```

Expected: no output after the explicit fictional-example/all-zero exclusions.

- [ ] **Step 3: Stage only the frozen package**

Run:

```bash
git add CONTEXT.md docs/adr docs/superpowers/specs/2026-08-30-supply-response-demo-contract-design.md docs/superpowers/plans/2026-08-30-supply-response-demo-implementation.md
git status --short
```

Expected: the glossary, four ADRs, frozen spec, and this plan are staged; unrelated `uv.lock` remains unstaged if still present.

- [ ] **Step 4: Commit Milestone 0**

```bash
git commit -m "docs: freeze supply response demo contract"
```

Expected: one commit contains the complete review package and no tenant binding or unrelated file.

---

### Task 1: Introduce the Canonical Domain Contracts and RL-001 Template

**Files:**
- Create: `data/domain/common.py`
- Create: `data/domain/operations.py`
- Create: `data/domain/cases.py`
- Create: `data/domain/evidence.py`
- Create: `data/domain/analysis.py`
- Create: `data/domain/decisions.py`
- Create: `data/domain/execution.py`
- Create: `data/domain/__init__.py`
- Create: `data/synthetic/rl001.py`
- Modify: `data/schemas/models.py`
- Modify: `data/synthetic/generator.py`
- Create: `tests/domain/test_rl001_contract.py`
- Modify: `evaluations/expected-results/rl-001.json`

**Interfaces:**
- Consumes: existing operational Pydantic records and `generate_dataset(seed=42)`.
- Produces: `build_rl001_template() -> DemoTemplate`, `instantiate_rl001(*, case_id: str, purpose: CasePurpose, runtime_mode: RuntimeMode) -> tuple[CaseInstance, OperationalSnapshot]`, plus immutable domain types imported from `data.domain`.

- [ ] **Step 1: Write the failing canonical-template test**

Create `tests/domain/test_rl001_contract.py` with:

```python
from datetime import datetime
from decimal import Decimal

from data.domain import CasePurpose, RuntimeMode
from data.synthetic.rl001 import build_rl001_template, instantiate_rl001


def test_rl001_template_freezes_the_approved_business_facts():
    template = build_rl001_template()
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-TEST-001",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )

    assert template.template_id == "RL-001"
    assert case.scenario_effective_time == datetime.fromisoformat(
        "2026-09-01T09:00:00-05:00"
    )
    assert case.runtime_mode is RuntimeMode.FALLBACK
    assert snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-CHI") == 4000
    assert snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-DAL") == 1500
    assert [order.component_demand for order in snapshot.production_orders] == [5000, 5800]
    assert [order.customer_priority for order in snapshot.production_orders] == [3, 1]
    assert snapshot.transfer.incremental_cost_per_unit == Decimal("1.50")
    assert snapshot.alpha_expedite.incremental_cost_per_unit == Decimal("7.50")
    assert snapshot.beta_qualification.status.value == "pending"


def test_runtime_mode_is_immutable_on_a_case_instance():
    case, _ = instantiate_rl001(
        case_id="RL-CASE-TEST-002",
        purpose=CasePurpose.REHEARSAL,
        runtime_mode=RuntimeMode.LIVE,
    )
    changed = case.model_copy(update={"runtime_mode": RuntimeMode.FALLBACK})
    assert changed.runtime_mode is RuntimeMode.FALLBACK
    assert case.runtime_mode is RuntimeMode.LIVE
    assert changed.case_id == case.case_id
    # The application service added in Task 5 must reject persisting `changed`.
```

- [ ] **Step 2: Run the new test and verify missing imports**

Run:

```bash
.venv/bin/pytest tests/domain/test_rl001_contract.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'data.domain'`.

- [ ] **Step 3: Add the minimum canonical enums and Case contracts**

Create `data/domain/common.py` and `data/domain/cases.py` with these public contracts:

```python
# data/domain/common.py
from enum import StrEnum
from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class RuntimeMode(StrEnum):
    LIVE = "live"
    FALLBACK = "fallback"


class CasePurpose(StrEnum):
    AUTOMATED_TEST = "automated_test"
    REHEARSAL = "rehearsal"
    SHOWCASE = "showcase"
```

```python
# data/domain/cases.py
from datetime import datetime
from enum import StrEnum
from typing import Literal
from .common import CasePurpose, FrozenModel, RuntimeMode


class CaseStatus(StrEnum):
    OPEN = "open"
    ANALYZING = "analyzing"
    AWAITING_DECISION = "awaiting_decision"
    DECISION_REJECTED = "decision_rejected"
    ACTION_PLANNING = "action_planning"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    REANALYSIS_REQUIRED = "reanalysis_required"
    CLOSED = "closed"


class DemoTemplate(FrozenModel):
    template_id: str
    scenario_effective_time: datetime
    scenario_timezone: Literal["America/Chicago"] = "America/Chicago"


class CaseInstance(FrozenModel):
    case_id: str
    template_id: str
    purpose: CasePurpose
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime
    scenario_timezone: Literal["America/Chicago"] = "America/Chicago"
    status: CaseStatus = CaseStatus.OPEN
```

Move existing operational records into `data/domain/operations.py`; give `QualificationStatus` the exact values `approved`, `pending`, `not_approved`, and `conditional`. Export the public types from `data/domain/__init__.py`.

- [ ] **Step 4: Add the exact RL-001 snapshot builder**

In `data/synthetic/rl001.py`, implement the immutable `OperationalSnapshot` and the two public functions. Use explicit records, never random replacement:

```python
SCENARIO_EFFECTIVE_TIME = datetime.fromisoformat("2026-09-01T09:00:00-05:00")


def build_rl001_template() -> DemoTemplate:
    return DemoTemplate(
        template_id="RL-001",
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
    )


def instantiate_rl001(
    *, case_id: str, purpose: CasePurpose, runtime_mode: RuntimeMode
) -> tuple[CaseInstance, OperationalSnapshot]:
    case = CaseInstance(
        case_id=case_id,
        template_id="RL-001",
        purpose=purpose,
        runtime_mode=runtime_mode,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
    )
    return case, OperationalSnapshot.rl001()
```

`OperationalSnapshot.rl001()` must encode Chicago `4,000`, Dallas `1,500`, component demands `5,000`/`5,800`, customer values `$375,000/$125,000` and `$580,000/$203,000`, priorities `3`/`1`, Alpha `3,000` on September 6 at `$7.50`, the Dallas transfer on September 5 at `$1.50`, unknown remaining Alpha recovery, and Beta `pending` with incomplete audit and first article.

The Analysis Horizon starts at Scenario Effective Time and ends at the later of the affected production/customer due dates. Preserve `scenario_timezone="America/Chicago"` alongside the offset-aware datetime so APIs and UI render the exact fictional business timezone rather than the operator machine's timezone.

- [ ] **Step 5: Preserve compatibility while moving imports**

Replace `data/schemas/models.py` with explicit re-exports from `data.domain` for names still used by current tests. Do not alias the overloaded names `ResponseScenario`, `ActionLedgerRecord`, or `OutcomeHistory`; those remain temporarily defined at the bottom with a `# legacy: remove in Task 4` comment until their callers migrate.

- [ ] **Step 6: Run the domain and existing regression tests**

Run:

```bash
.venv/bin/pytest tests/domain/test_rl001_contract.py -q
.venv/bin/pytest -q
```

Expected: the new template tests pass and the existing 32 tests remain green.

- [ ] **Step 7: Commit the canonical domain foundation**

```bash
git add data/domain data/synthetic/rl001.py data/schemas/models.py data/synthetic/generator.py tests/domain/test_rl001_contract.py evaluations/expected-results/rl-001.json
git commit -m "feat(domain): freeze canonical RL-001 contracts"
```

---

### Task 2: Calculate Every RL-001 Response Option Deterministically

**Files:**
- Create: `services/analysis/exposure.py`
- Create: `services/analysis/options.py`
- Create: `tests/analysis/test_rl001_options.py`
- Modify: `data/domain/analysis.py`
- Modify: `services/exposure/calculator.py`
- Modify: `services/scenarios/evaluator.py`

**Interfaces:**
- Consumes: `OperationalSnapshot` from Task 1.
- Produces: `evaluate_response_options(snapshot: OperationalSnapshot) -> tuple[ResponseOption, ...]` and `calculate_option_outcome(snapshot: OperationalSnapshot, option_id: str) -> PredictedOutcome`.

- [ ] **Step 1: Write the exact known-answer test**

Create `tests/analysis/test_rl001_options.py` with:

```python
from decimal import Decimal
from data.synthetic.rl001 import OperationalSnapshot
from services.analysis.options import evaluate_response_options


EXPECTED = {
    "RL-OPTION-NO-MITIGATION": (False, 6800, 100, "955000", "328000", "0"),
    "RL-OPTION-EXPEDITE": (True, 3800, 100, "955000", "328000", "22500"),
    "RL-OPTION-TRANSFER": (True, 5300, 50, "580000", "203000", "2250"),
    "RL-OPTION-RESEQUENCE": (True, 6800, 100, "955000", "328000", "0"),
    "RL-OPTION-COMBINED": (True, 2300, 50, "375000", "125000", "24750"),
}


def test_rl001_response_options_match_the_frozen_contract():
    options = {item.option_id: item for item in evaluate_response_options(OperationalSnapshot.rl001())}
    for option_id, expected in EXPECTED.items():
        item = options[option_id]
        assert (
            item.executable,
            item.predicted.uncovered_part_demand,
            item.predicted.otif_loss_percentage,
            str(item.predicted.revenue_at_risk),
            str(item.predicted.margin_at_risk),
            str(item.predicted.response_cost),
        ) == expected

    beta = options["RL-OPTION-BETA"]
    assert beta.executable is False
    assert beta.blocking_codes == ("QUALITY_QUALIFICATION_PENDING",)
    assert beta.predicted is None


def test_no_mitigation_excludes_the_optional_alpha_receipt():
    baseline = next(
        item for item in evaluate_response_options(OperationalSnapshot.rl001())
        if item.option_id == "RL-OPTION-NO-MITIGATION"
    )
    assert "RL-ALPHA-OPTIONAL-3000" not in baseline.source_data_lineage
```

- [ ] **Step 2: Run the test to verify the evaluator is absent**

Run:

```bash
.venv/bin/pytest tests/analysis/test_rl001_options.py -q
```

Expected: collection fails because `services.analysis.options` does not exist.

- [ ] **Step 3: Define the option and outcome contracts**

Add to `data/domain/analysis.py`:

```python
class PredictedOutcome(FrozenModel):
    uncovered_part_demand: int
    otif_loss_percentage: int
    revenue_at_risk: Decimal
    margin_at_risk: Decimal
    response_cost: Decimal
    protected_customer_order_ids: tuple[str, ...] = ()


class ResponseOption(FrozenModel):
    option_id: str
    name: str
    executable: bool
    active_mitigation: bool
    predicted: PredictedOutcome | None
    assumptions: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    blocking_codes: tuple[str, ...] = ()
    prerequisite_roles: tuple[str, ...] = ()
    source_data_lineage: tuple[str, ...] = ()
    approval_burden: int = 0
    execution_risk: int = 0
```

- [ ] **Step 4: Implement allocation and option bundles**

In `services/analysis/exposure.py`, implement full/on-time protection as an all-or-nothing allocation ordered by customer priority then stable order ID. In `services/analysis/options.py`, construct exactly six options: no mitigation, Alpha expedite, Dallas transfer, resequence, Beta, and combined. Use the snapshot's quantities/dates/costs; never hardcode the expected output table as a returned constant.

Use one intervention evaluator so all options share the same arithmetic:

```python
def calculate_option_outcome(
    snapshot: OperationalSnapshot,
    *,
    receipts: tuple[TimedQuantity, ...] = (),
    transfers: tuple[TimedQuantity, ...] = (),
    resequence_by_priority: bool = False,
    response_cost: Decimal = Decimal("0"),
) -> PredictedOutcome:
    orders = sorted(
        snapshot.production_orders,
        key=(lambda item: (item.customer_priority, item.production_order_id))
        if resequence_by_priority
        else (lambda item: (item.due_date, item.production_order_id)),
    )
    allocation = allocate_component_supply(
        starting_inventory=snapshot.chicago_usable_inventory,
        receipts=receipts,
        transfers=transfers,
        production_orders=orders,
    )
    protected = tuple(item for item in orders if allocation[item.production_order_id].full_and_on_time)
    return PredictedOutcome(
        uncovered_part_demand=allocation.uncovered_component_units,
        otif_loss_percentage=100 * (len(orders) - len(protected)) // len(orders),
        revenue_at_risk=sum((item.customer_revenue for item in orders if item not in protected), Decimal("0")),
        margin_at_risk=sum((item.customer_margin for item in orders if item not in protected), Decimal("0")),
        response_cost=response_cost,
        protected_customer_order_ids=tuple(item.customer_order_id for item in protected),
    )
```

`evaluate_response_options()` supplies no optional Alpha receipt to baseline/resequence, the Alpha receipt only to expedite, the Dallas movement only to transfer, both to combined, and no predicted outcome to blocked Beta.

For every option, derive `approval_burden` and `execution_risk` from the frozen policy rather than assigning a score literal. A recovery commitment with an unknown date counts as unconfirmed; the Dallas transfer counts as cross-plant; resequencing counts as a schedule change; combined counts each coordinated action after the first.

The combined option must apply transfer, expedite, then priority resequencing and calculate cost as:

```python
combined_cost = (
    Decimal(snapshot.alpha_expedite.quantity)
    * snapshot.alpha_expedite.incremental_cost_per_unit
    + Decimal(snapshot.transfer.quantity)
    * snapshot.transfer.incremental_cost_per_unit
)
assert combined_cost == Decimal("24750.00")
```

- [ ] **Step 5: Run targeted and full deterministic tests**

Run:

```bash
.venv/bin/pytest tests/analysis/test_rl001_options.py -q
.venv/bin/pytest tests/test_exposure.py tests/test_evaluation_cases.py -q
.venv/bin/pytest -q
```

Expected: all tests pass; the exact known-answer table has no tolerance or random ordering.

- [ ] **Step 6: Commit option evaluation**

```bash
git add data/domain/analysis.py services/analysis services/exposure/calculator.py services/scenarios/evaluator.py tests/analysis/test_rl001_options.py
git commit -m "feat(analysis): evaluate frozen RL-001 options"
```

---

### Task 3: Add Evidence, Approval, and Analysis-Version Policy

**Files:**
- Modify: `data/domain/evidence.py`
- Modify: `data/domain/decisions.py`
- Modify: `data/domain/analysis.py`
- Create: `services/policy/evidence.py`
- Create: `services/policy/approvals.py`
- Create: `services/analysis/service.py`
- Create: `tests/analysis/test_evidence_and_approvals.py`

**Interfaces:**
- Consumes: normalized `EvidenceItem` tuples, an `OperationalSnapshot`, and a `StandingAuthorization`.
- Produces: `create_analysis_version(...) -> AnalysisVersion`, `evaluate_approval_satisfaction(...) -> tuple[ApprovalSatisfaction, ...]`, and `analysis_material_hash(...) -> str`.

- [ ] **Step 1: Write failing authority, conflict, and authorization tests**

Create `tests/analysis/test_evidence_and_approvals.py` containing these three tests:

```python
def test_uncited_required_workiq_evidence_blocks_authoritative_analysis():
    evidence = evidence_item(
        kind="source_statement", source_system="work_iq", citation_url=None
    )
    result = validate_required_evidence((evidence,), runtime_mode=RuntimeMode.LIVE)
    assert result.blocking_codes == ("REQUIRED_CITATION_MISSING",)


def test_agent_cannot_resolve_a_feasibility_relevant_conflict():
    conflict = evidence_conflict(feasibility_relevant=True)
    with pytest.raises(PolicyViolation, match="authorized human"):
        resolve_conflict(conflict, actor_roles=("agent",), governing_evidence_id="RL-E-2")


def test_taylor_standing_authorization_satisfies_combined_finance_prerequisite():
    result = evaluate_approval_satisfaction(
        option=combined_option(),
        analysis_id="RL-ANALYSIS-1",
        standing_authorizations=(taylor_authorization(),),
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
    )
    assert [(item.role, item.satisfied) for item in result] == [
        ("finance_approver", True)
    ]
    assert result[0].persona_id == "RL-PERSONA-TAYLOR"
```

The helper constructors live in the same test file and must use only fictional `RL-` data.

- [ ] **Step 2: Run the tests and verify missing policy functions**

Run:

```bash
.venv/bin/pytest tests/analysis/test_evidence_and_approvals.py -q
```

Expected: collection fails on missing Evidence and approval policy imports.

- [ ] **Step 3: Implement exact evidence and approval types**

Define:

```python
class EvidenceKind(StrEnum):
    OPERATIONAL_FACT = "operational_fact"
    SOURCE_STATEMENT = "source_statement"
    PREREQUISITE_APPROVAL = "prerequisite_approval"
    CONTEXTUAL_EVIDENCE = "contextual_evidence"


class ObservationKind(StrEnum):
    ACTUAL = "actual"
    SIMULATED = "simulated"
```

`EvidenceItem` must contain `evidence_id`, `case_id`, `kind`, `authority_scope`, `source_system`, `source_id`, `source_timestamp`, `retrieved_at`, `effective_at`, `expires_at`, `claim`, `excerpt`, `citation_url`, `runtime_mode`, and `synthetic`. `StandingAuthorization` must encode Taylor, allowed option kinds `expedite` and `combined`, maximum `$25,000`, Demo Corpus only, Day 0–14, and every forbidden external side effect.

- [ ] **Step 4: Implement field-scoped validation and immutable analysis hashing**

`services/policy/evidence.py` must return typed blocking codes for missing citations, stale timestamps, expired evidence, unresolved conflicts, and authority-scope mismatch. `analysis_material_hash()` must canonicalize only material fields and use SHA-256:

```python
def analysis_material_hash(payload: AnalysisMaterial) -> str:
    canonical = payload.model_dump_json(
        exclude_none=False,
        by_alias=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

Exclude display-only metadata and retrieval retries with identical normalized content from `AnalysisMaterial`.

Approval satisfaction is explicit and option-bound:

```python
def evaluate_approval_satisfaction(
    *, option: ResponseOption, analysis_id: str,
    standing_authorizations: tuple[StandingAuthorization, ...],
    scenario_effective_time: datetime,
) -> tuple[ApprovalSatisfaction, ...]:
    required = set(option.prerequisite_roles) - {"response_approver", "material_planner"}
    return tuple(
        ApprovalSatisfaction.from_authorization(analysis_id, option, authorization)
        for role in sorted(required)
        for authorization in standing_authorizations
        if authorization.role == role
        and authorization.permits(option, scenario_effective_time)
    )
```

- [ ] **Step 5: Run evidence, approval, and full tests**

Run:

```bash
.venv/bin/pytest tests/analysis/test_evidence_and_approvals.py -q
.venv/bin/pytest -q
```

Expected: all policy tests and the regression suite pass.

- [ ] **Step 6: Commit the policy layer**

```bash
git add data/domain/evidence.py data/domain/decisions.py data/domain/analysis.py services/policy services/analysis/service.py tests/analysis/test_evidence_and_approvals.py
git commit -m "feat(policy): bind evidence and approvals to analysis"
```

---

### Task 4: Rank Options and Integrate All Ten Evaluation Cases

**Files:**
- Create: `services/analysis/ranking.py`
- Modify: `services/analysis/service.py`
- Modify: `evaluations/datasets/evaluation_cases.json`
- Modify: `evaluations/expected-results/rl-001.json`
- Create: `tests/analysis/test_ranking.py`
- Create: `tests/analysis/test_integrated_evaluation_cases.py`
- Modify: `data/schemas/models.py`
- Modify: `apps/api/app/contracts.py`

**Interfaces:**
- Consumes: complete executable `ResponseOption` tuples and policy-versioned evidence.
- Produces: `rank_options(options: tuple[ResponseOption, ...]) -> RankingResult` and `analyze_case(...) -> AnalysisVersion` with a stage-by-stage elimination trace.

- [ ] **Step 1: Write the threshold-elimination test**

Create `tests/analysis/test_ranking.py`:

```python
def test_thresholded_lexicographic_ranking_selects_combined():
    result = rank_options(rl001_options())
    assert result.recommended_option_id == "RL-OPTION-COMBINED"
    assert result.policy_version == "thresholded-lexicographic-v1"
    assert result.stages[0].comparator == "uncovered_part_demand"
    assert result.stages[0].threshold == Decimal("500")
    assert result.stages[0].retained_option_ids == ("RL-OPTION-COMBINED",)
    assert "RL-OPTION-BETA" in result.infeasible_option_ids
    assert "RL-OPTION-NO-MITIGATION" in result.excluded_baseline_ids


def test_threshold_keeps_immaterial_difference_for_next_comparator():
    options = option_pair(uncovered=(2300, 2600), otif=(50, 40))
    result = rank_options(options)
    assert result.stages[0].retained_option_ids == ("RL-A", "RL-B")
    assert result.recommended_option_id == "RL-B"
```

- [ ] **Step 2: Run ranking tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/analysis/test_ranking.py -q
```

Expected: collection fails because `services.analysis.ranking` does not exist.

- [ ] **Step 3: Implement the ordered comparator table**

In `services/analysis/ranking.py`, define one immutable policy constant:

```python
COMPARATORS = (
    Comparator("uncovered_part_demand", Decimal("500"), lower_is_better=True),
    Comparator("otif_loss_percentage", Decimal("10"), lower_is_better=True),
    Comparator("revenue_at_risk", Decimal("50000"), lower_is_better=True),
    Comparator("margin_at_risk", Decimal("25000"), lower_is_better=True),
    Comparator("response_cost", Decimal("10000"), lower_is_better=True),
    Comparator("approval_burden", Decimal("0"), lower_is_better=True),
    Comparator("execution_risk", Decimal("0"), lower_is_better=True),
    Comparator("option_id", Decimal("0"), lower_is_better=True),
)
```

For each numeric comparator, retain every remaining option where `value <= best + threshold`. For the final ID comparator, sort by the raw stable ID and retain exactly the first.

- [ ] **Step 4: Replace helper-only evaluation links with integrated analysis tests**

Create one parameterized test in `tests/analysis/test_integrated_evaluation_cases.py` that loads every `RL-EVAL-*` descriptor, builds its exact operational/evidence override, calls `analyze_case()`, and asserts the frozen expected status, uncertainty, conflict, blocking code, approval requirement, or no-feasible-mitigation result. Update each catalog `test` field to point to that parameterized test's stable node ID or to an explicit wrapper function in the same file.

Use explicit case builders rather than string-based reflection:

```python
CASE_BUILDERS = {
    "RL-EVAL-001": confirmed_recovery_case,
    "RL-EVAL-002": unconfirmed_recovery_case,
    "RL-EVAL-003": partial_shipment_case,
    "RL-EVAL-004": conflicting_dates_case,
    "RL-EVAL-005": beta_approved_case,
    "RL-EVAL-006": beta_pending_case,
    "RL-EVAL-007": transfer_available_case,
    "RL-EVAL-008": no_feasible_mitigation_case,
    "RL-EVAL-009": finance_threshold_case,
    "RL-EVAL-010": stale_evidence_case,
}


@pytest.mark.parametrize("case_id", sorted(CASE_BUILDERS))
def test_integrated_evaluation_case(case_id):
    command, expected = CASE_BUILDERS[case_id]()
    assert summarize(analyze_case(command)) == expected
```

The `RL-EVAL-007`, `008`, and `010` assertions must prove the real option/evidence pipeline invokes transfer availability, no-feasible mitigation, and staleness policy; calling the old standalone helpers is insufficient.

- [ ] **Step 5: Remove overloaded legacy contracts**

Update API contracts to return `ResponseOption` and `AnalysisVersion`. Remove `ResponseScenario`, `ActionLedgerRecord`, and `OutcomeHistory` from `data/schemas/models.py` only after:

```bash
rg -n 'ResponseScenario|ActionLedgerRecord|OutcomeHistory|selected_scenario_id|scenario_id' apps data services tests
```

Expected before deletion: matches exist only in a migration compatibility test that is deleted in the same patch. Expected after deletion: no matches.

- [ ] **Step 6: Run Milestone 2 verification**

Run:

```bash
.venv/bin/pytest tests/analysis -q
.venv/bin/pytest tests/test_evaluation_assets.py -q
.venv/bin/pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
```

Expected: the exact RL-001 bundle and all ten integrated evaluation cases pass; the full Python/frontend regressions and production build pass.

- [ ] **Step 7: Commit and hold the Milestone 2 reviewer gate**

```bash
git add services/analysis data/domain data/schemas/models.py apps/api/app/contracts.py evaluations tests/analysis
git commit -m "feat(analysis): rank integrated response options"
```

Reviewer gate: compare the emitted RL-001 JSON to the frozen table and inspect every elimination stage before beginning persistence.

---

### Task 5: Define Runtime Configuration and Persistence Ports

**Files:**
- Modify: `pyproject.toml`
- Create: `.env.example`
- Create: `apps/api/app/settings.py`
- Create: `services/persistence/ports.py`
- Create: `services/persistence/tables.py`
- Create: `services/persistence/sqlite.py`
- Create: `services/persistence/store.py`
- Create: `migrations/alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/versions/0001_closed_loop_schema.py`
- Create: `tests/persistence/test_sqlite_store.py`

**Interfaces:**
- Consumes: Task 1–4 domain records.
- Produces: `Settings`, `UnitOfWork`, `CaseStore`, and `SqlAlchemyStore`; `build_store(settings: Settings) -> CaseStore` selects exactly one configured runtime mode.

- [ ] **Step 1: Write the failing restart and mode-immutability tests**

Create `tests/persistence/test_sqlite_store.py`:

```python
def test_sqlite_case_survives_store_reconstruction(tmp_path):
    url = f"sqlite:///{tmp_path / 'supply-response.db'}"
    first = sqlite_store(url)
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-1")
    first.create_case(case, snapshot)

    second = sqlite_store(url)
    restored = second.get_case(case.case_id)
    assert restored == case


def test_store_rejects_runtime_mode_change(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'mode.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-2")
    store.create_case(case, snapshot)
    with pytest.raises(RuntimeModeConflict):
        store.save_case_projection(
            case.model_copy(update={"runtime_mode": RuntimeMode.LIVE})
        )
```

- [ ] **Step 2: Run the test and verify persistence is absent**

Run:

```bash
.venv/bin/pytest tests/persistence/test_sqlite_store.py -q
```

Expected: collection fails because `services.persistence` is absent.

- [ ] **Step 3: Add bounded persistence dependencies and validated settings**

Add these runtime dependencies to `pyproject.toml`:

```toml
"alembic>=1.16,<2",
"pydantic-settings>=2.10,<3",
"sqlalchemy>=2.0,<3",
```

Define `Settings` with the `SUPPLY_RESPONSE_` prefix:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SUPPLY_RESPONSE_", extra="ignore")
    runtime_mode: RuntimeMode
    database_url: str
    scenario_effective_time: datetime = SCENARIO_EFFECTIVE_TIME
    allowed_tenant_id: str | None = None
    tenant_domain: str = "willmacdonald.com"
    frontend_origin: str = "http://localhost:5173"

    @model_validator(mode="after")
    def validate_mode_specific_settings(self):
        if self.runtime_mode is RuntimeMode.LIVE and not self.allowed_tenant_id:
            raise ValueError("live mode requires SUPPLY_RESPONSE_ALLOWED_TENANT_ID")
        return self
```

`.env.example` uses only placeholders such as `00000000-0000-0000-0000-000000000000`; it may contain `SUPPLY_RESPONSE_TENANT_DOMAIN=willmacdonald.com`.

- [ ] **Step 4: Define focused store protocols**

`services/persistence/ports.py` must expose exact methods rather than a generic CRUD abstraction:

```python
class CaseStore(Protocol):
    def create_case(self, case: CaseInstance, snapshot: OperationalSnapshot) -> None: ...
    def get_case(self, case_id: str) -> CaseInstance: ...
    def save_analysis(self, analysis: AnalysisVersion) -> None: ...
    def get_analysis(self, analysis_id: str) -> AnalysisVersion: ...
    def save_case_projection(self, case: CaseInstance) -> None: ...
    def list_cases(self, *, purpose: CasePurpose | None = None) -> tuple[CaseInstance, ...]: ...


class UnitOfWork(Protocol):
    cases: CaseStore
    decisions: DecisionStore
    execution: ExecutionStore
    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

- [ ] **Step 5: Create the schema and JSON serialization boundary**

Define separate tables for `case_instances`, `operational_snapshots`, `evidence_items`, `analysis_versions`, `decisions`, `approval_satisfactions`, `outbox_events`, `execution_actions`, `draft_artifacts`, `execution_events`, `execution_attempts`, `playbacks`, and `outcome_observations`. Immutable records use insert-only repository methods; only `case_projection`, `action_projection`, and outbox claim columns may update.

Store complete immutable Pydantic snapshots as canonical JSON plus indexed IDs/status/timestamps. `serialize_model()` must use:

```python
def serialize_model(value: BaseModel) -> str:
    return value.model_dump_json(exclude_none=False, by_alias=True)
```

- [ ] **Step 6: Apply the migration and run persistence tests**

Run:

```bash
.venv/bin/alembic -c migrations/alembic.ini upgrade head
.venv/bin/pytest tests/persistence/test_sqlite_store.py -q
.venv/bin/pytest -q
```

Expected: migration succeeds against a temporary SQLite database; restart and mode-conflict tests pass; the full suite passes.

- [ ] **Step 7: Commit the persistence foundation**

```bash
git add pyproject.toml uv.lock .env.example apps/api/app/settings.py services/persistence migrations tests/persistence/test_sqlite_store.py
git commit -m "feat(persistence): add durable SQLite case store"
```

---

### Task 6: Record Immutable Decisions with a Transactional Outbox

**Files:**
- Modify: `data/domain/decisions.py`
- Modify: `data/domain/execution.py`
- Modify: `services/persistence/ports.py`
- Modify: `services/persistence/store.py`
- Create: `services/decisions/service.py`
- Create: `tests/persistence/test_decision_outbox.py`

**Interfaces:**
- Consumes: `record_decision(command: RecordDecisionCommand, actor: IdentitySnapshot) -> Decision`.
- Produces: one immutable Decision and, only for approval, one `ActionPlanningRequested` outbox event in the same transaction; retrying the same idempotency key returns the existing Decision.

- [ ] **Step 1: Write atomicity, idempotency, and rejection tests**

Create `tests/persistence/test_decision_outbox.py`:

```python
def test_approval_atomically_writes_decision_and_outbox(sqlite_uow):
    command = approved_combined_command(idempotency_key="RL-IDEMPOTENCY-1")
    decision = DecisionService(sqlite_uow).record(command, alex_identity())
    with sqlite_uow() as uow:
        assert uow.decisions.get(decision.decision_id) == decision
        events = uow.execution.list_outbox(decision_id=decision.decision_id)
        assert [(e.event_type, e.decision_id) for e in events] == [
            ("ActionPlanningRequested", decision.decision_id)
        ]


def test_same_idempotency_key_returns_same_decision(sqlite_uow):
    service = DecisionService(sqlite_uow)
    first = service.record(approved_combined_command("RL-IDEMPOTENCY-2"), alex_identity())
    second = service.record(approved_combined_command("RL-IDEMPOTENCY-2"), alex_identity())
    assert second.decision_id == first.decision_id


def test_rejection_is_immutable_and_creates_no_outbox(sqlite_uow):
    decision = DecisionService(sqlite_uow).record(rejection_command(), alex_identity())
    with sqlite_uow() as uow:
        assert decision.kind.value == "rejected"
        assert uow.execution.list_outbox(decision_id=decision.decision_id) == ()


def test_alex_approval_atomically_records_material_planner_satisfaction(sqlite_uow):
    decision = DecisionService(sqlite_uow).record(
        approved_combined_command("RL-IDEMPOTENCY-3"), alex_identity()
    )
    with sqlite_uow() as uow:
        satisfactions = uow.decisions.list_approval_satisfactions(decision.decision_id)
        assert [(item.role, item.persona_id, item.satisfied) for item in satisfactions] == [
            ("finance_approver", "RL-PERSONA-TAYLOR", True),
            ("material_planner", "RL-PERSONA-ALEX", True),
        ]


def test_later_approval_becomes_current_without_rewriting_history(sqlite_uow):
    service = DecisionService(sqlite_uow)
    first = service.record(approved_combined_command("RL-IDEMPOTENCY-4"), alex_identity())
    mark_reanalysis_required(sqlite_uow, first.case_id)
    second = service.record(approved_reanalysis_command("RL-IDEMPOTENCY-5"), alex_identity())
    with sqlite_uow() as uow:
        assert uow.decisions.get(first.decision_id) == first
        assert uow.decisions.get(second.decision_id) == second
        assert uow.cases.get_projection(first.case_id).current_decision_id == second.decision_id
```

- [ ] **Step 2: Run tests and verify the Decision service is absent**

Run:

```bash
.venv/bin/pytest tests/persistence/test_decision_outbox.py -q
```

Expected: collection fails on the missing `services.decisions.service` module.

- [ ] **Step 3: Define the immutable command and Decision snapshot**

`RecordDecisionCommand` includes `case_id`, `analysis_id`, `selected_option_id | None`, `kind`, `idempotency_key`, and rejection reason. `Decision` includes the complete selected Response Option snapshot, evidence IDs, assumptions, constraints, comparator trace, calculation/policy versions, runtime mode, Scenario Effective Time, Approval Satisfactions, actor identity snapshot, and timestamp. The same approval transaction inserts Alex's analysis-bound `material_planner` Approval Satisfaction, revalidates Taylor's existing Finance satisfaction, inserts the Decision, and inserts `ActionPlanningRequested`.

Reject approval unless:

```python
analysis.analysis_id == command.analysis_id
analysis.material_hash == case.current_analysis_hash
option.executable
all(item.satisfied for item in analysis.approval_satisfactions_for(option.option_id))
actor.persona_id == "RL-PERSONA-ALEX"
"response_approver" in actor.effective_roles
```

- [ ] **Step 4: Insert Decision and outbox in one SQLAlchemy transaction**

Implement `DecisionService.record()` with a single unit-of-work context. On unique `idempotency_key` conflict, load and return the existing Decision; never create a second logical record. On any other exception, roll back the Approval Satisfaction, Decision, and outbox inserts together. A material change marks the case `reanalysis_required`; a later approved Decision updates only `case_projection.current_decision_id` and never edits either historical Decision or moves existing actions to the new Decision.

The transaction shape is:

```python
def record(self, command: RecordDecisionCommand, actor: IdentitySnapshot) -> Decision:
    with self._uow_factory() as uow:
        existing = uow.decisions.get_by_idempotency_key(command.idempotency_key)
        if existing:
            return existing
        case = uow.cases.get_case(command.case_id)
        analysis = uow.cases.get_analysis(command.analysis_id)
        self._policy.authorize(command, actor, case, analysis)
        satisfactions = self._policy.materialize_satisfactions(command, actor, analysis)
        decision = Decision.from_command(command, actor, analysis, satisfactions)
        uow.decisions.insert_satisfactions(decision.decision_id, satisfactions)
        uow.decisions.insert(decision)
        if decision.kind is DecisionKind.APPROVED:
            uow.execution.insert_outbox(ActionPlanningRequested.for_decision(decision))
            uow.cases.set_current_decision(case.case_id, decision.decision_id)
        else:
            uow.cases.mark_rejected(case.case_id, decision.decision_id)
        uow.commit()
        return decision
```

- [ ] **Step 5: Test rollback explicitly**

Add a store fault hook used only by tests and assert that raising after Decision insert but before outbox insert leaves neither row. Run:

```bash
.venv/bin/pytest tests/persistence/test_decision_outbox.py -q
.venv/bin/pytest -q
```

Expected: atomicity, idempotency, rejection, and rollback tests pass.

- [ ] **Step 6: Commit Decision/outbox persistence**

```bash
git add data/domain/decisions.py data/domain/execution.py services/persistence services/decisions tests/persistence/test_decision_outbox.py
git commit -m "feat(decisions): persist immutable decisions and outbox"
```

---

### Task 7: Plan Exactly Five Actions and Preserve Attempt History

**Files:**
- Create: `services/execution/planner.py`
- Create: `services/execution/worker.py`
- Modify: `services/persistence/ports.py`
- Modify: `services/persistence/store.py`
- Create: `tests/execution/test_action_planning.py`
- Create: `tests/execution/test_action_attempts.py`

**Interfaces:**
- Consumes: `ActionPlanningRequested` outbox events and immutable Decisions.
- Produces: `plan_actions(decision: Decision) -> tuple[ExecutionAction, ...]`, `process_next_outbox() -> bool`, append-only attempt/status history with a mutable projection, and a `DraftArtifact` contract whose `sent` field is permanently false.

- [ ] **Step 1: Write the exact five-action test**

Create `tests/execution/test_action_planning.py`:

```python
def test_combined_decision_creates_exactly_five_bounded_actions():
    actions = plan_actions(approved_combined_decision())
    assert [(a.kind, a.owner_persona_id) for a in actions] == [
        ("prepare_alpha_recovery_draft", "RL-PERSONA-ALEX"),
        ("coordinate_alpha_expedited_partial", "RL-PERSONA-ALEX"),
        ("transfer_dallas_to_chicago", "RL-PERSONA-ALEX"),
        ("resequence_priority_production", "RL-PERSONA-ALEX"),
        ("update_disruption_status", None),
    ]
    assert all(a.decision_id == approved_combined_decision().decision_id for a in actions)
    assert not any("beta" in a.kind for a in actions)
```

- [ ] **Step 2: Write the failure/retry transition test**

Create `tests/execution/test_action_attempts.py`:

```python
def test_failed_action_retries_without_rewriting_history(execution_service):
    action = execution_service.create(planned_action())
    first = execution_service.start(action.action_id)
    failed = execution_service.fail(action.action_id, first.attempt_id, "RL-TEST-FAILURE")
    retry = execution_service.retry(action.action_id)
    completed = execution_service.complete(action.action_id, retry.attempt_id)

    assert completed.status.value == "completed"
    assert [event.to_status.value for event in execution_service.history(action.action_id)] == [
        "planned", "in_progress", "failed", "in_progress", "completed"
    ]
    assert first.attempt_id != retry.attempt_id
```

- [ ] **Step 3: Run tests and verify planner/service absence**

Run:

```bash
.venv/bin/pytest tests/execution/test_action_planning.py tests/execution/test_action_attempts.py -q
```

Expected: collection fails on missing execution modules.

- [ ] **Step 4: Implement deterministic action IDs and legal transitions**

Generate action IDs with UUIDv5 over `(decision_id, action_kind)` so reprocessing is idempotent. Define only these transitions:

```python
ALLOWED_TRANSITIONS = {
    "planned": {"in_progress", "cancelled"},
    "in_progress": {"completed", "failed", "cancelled"},
    "failed": {"in_progress"},
    "completed": set(),
    "cancelled": set(),
}
```

Every transition appends an `ExecutionStatusEvent`; retry appends a new `ExecutionAttempt` and never edits the failed one.

The status-update action uses `owner_kind="system"` and `owner_persona_id=None`; the other four use `owner_kind="persona"` with Alex's stable persona ID. Do not invent a fourth Demo Persona for the application.

- [ ] **Step 5: Implement safe outbox claiming and planning failure**

`process_next_outbox()` must claim one unprocessed event, load its Decision, insert the deterministic actions, and mark the outbox processed in one transaction. On failure it increments `attempt_count`, records the error code, leaves the Decision unchanged, and exposes `Approved — action planning failed` through the case projection.

```python
def process_next_outbox(self) -> bool:
    with self._uow_factory() as uow:
        event = uow.execution.claim_next_outbox("ActionPlanningRequested")
        if event is None:
            return False
        try:
            decision = uow.decisions.get(event.decision_id)
            for action in plan_actions(decision):
                uow.execution.insert_action_if_absent(action)
            uow.execution.mark_outbox_processed(event.event_id)
            uow.cases.mark_action_planning_complete(decision.case_id)
            uow.commit()
        except Exception as exc:
            uow.rollback()
            with self._uow_factory() as failed_uow:
                failed_uow.execution.record_outbox_failure(event.event_id, error_code(exc))
                failed_uow.cases.mark_action_planning_failed(event.case_id)
                failed_uow.commit()
        return True
```

The recovery-request action owns one deterministic Draft Artifact ID derived from `(decision_id, "alpha_recovery_request")`. Its initial record is an unsent shell with `sent=False`; no repository or API method may change `sent` to true.

- [ ] **Step 6: Run execution and full tests**

Run:

```bash
.venv/bin/pytest tests/execution -q
.venv/bin/pytest -q
```

Expected: exact action set, duplicate-worker idempotency, legal transitions, and retry history tests pass.

- [ ] **Step 7: Commit action planning**

```bash
git add services/execution services/persistence data/domain/execution.py tests/execution
git commit -m "feat(execution): plan bounded actions from decisions"
```

---

### Task 8: Add Deterministic Simulated Execution and Outcome Observations

**Files:**
- Create: `services/execution/playback.py`
- Modify: `services/persistence/ports.py`
- Modify: `services/persistence/store.py`
- Modify: `data/domain/execution.py`
- Create: `tests/execution/test_playback.py`
- Create: `tests/execution/test_observation_safety.py`

**Interfaces:**
- Consumes: `start_playback(decision_id: str, actor: IdentitySnapshot) -> Playback`.
- Produces: idempotent playback, action events, and the ten frozen append-only Simulated Observations.

- [ ] **Step 1: Write the exact outcome and idempotency test**

Create `tests/execution/test_playback.py`:

```python
EXPECTED = {
    "alpha_expedited_quantity": ("3000", "2800"),
    "dallas_transfer_quantity": ("1500", "1500"),
    "total_response_arranged_supply": ("4500", "4300"),
    "uncovered_part_demand": ("2300", "2500"),
    "response_cost": ("24750", "25000"),
    "protected_customer_orders": ("1", "1"),
    "revenue_protected": ("580000", "580000"),
    "margin_protected": ("203000", "203000"),
    "otif_loss_percentage": ("50", "50"),
    "remaining_alpha_recovery_date": ("unknown", "2026-09-12"),
}


def test_playback_appends_only_the_frozen_simulated_observations(playback_service):
    playback = playback_service.start(APPROVED_DECISION_ID, alex_identity())
    playback_service.run_to_completion(playback.playback_id, clock=ImmediateClock())
    observations = playback_service.observations(APPROVED_DECISION_ID)
    assert {o.metric: (o.predicted_value, o.observed_value) for o in observations} == EXPECTED
    assert all(o.kind.value == "simulated" and o.synthetic for o in observations)


def test_repeated_start_returns_existing_playback(playback_service):
    first = playback_service.start(APPROVED_DECISION_ID, alex_identity())
    second = playback_service.start(APPROVED_DECISION_ID, alex_identity())
    assert second.playback_id == first.playback_id


def test_playback_completes_an_unsent_alpha_draft(playback_service):
    playback_service.run_to_completion(
        playback_service.start(APPROVED_DECISION_ID, alex_identity()).playback_id,
        clock=ImmediateClock(),
    )
    draft = playback_service.draft(APPROVED_DECISION_ID, "alpha_recovery_request")
    assert draft.subject == "RL-001 recovery-date confirmation request"
    assert "RL-Supplier Alpha" in draft.body
    assert draft.sent is False
```

- [ ] **Step 2: Run tests and verify playback absence**

Run:

```bash
.venv/bin/pytest tests/execution/test_playback.py -q
```

Expected: collection fails on missing playback service.

- [ ] **Step 3: Implement a clock-injected 50-second production schedule**

Define:

```python
PRODUCTION_STEPS = (
    PlaybackStep(offset_seconds=0, action_kind="prepare_alpha_recovery_draft"),
    PlaybackStep(offset_seconds=10, action_kind="coordinate_alpha_expedited_partial"),
    PlaybackStep(offset_seconds=20, action_kind="transfer_dallas_to_chicago"),
    PlaybackStep(offset_seconds=35, action_kind="resequence_priority_production"),
    PlaybackStep(offset_seconds=50, action_kind="update_disruption_status"),
)
```

`RealClock.wait_until()` sleeps; `ImmediateClock.wait_until()` advances virtual time without sleeping. Only `RealClock` is wired in runtime composition.

- [ ] **Step 4: Enforce simulation permanence**

`OutcomeObservation.kind` and `synthetic` are immutable insert-only fields. Add a repository check constraint that rejects `kind='actual' AND synthetic=1`. API serializers must derive the display label from `kind`; they may not accept a caller-provided label. The first playback step fills the deterministic Alpha Draft Artifact body and completes its action without invoking any mail or Teams send API.

Each observation also persists `decision_id`, optional `action_id`, metric, observed value, unit, predicted baseline, Scenario Effective Time, `scenario_timezone`, wall-clock `recorded_at`, source reference, and permanent synthetic indicator. Missing Decision linkage is a schema error.

- [ ] **Step 5: Run Milestone 3 verification**

Run:

```bash
.venv/bin/pytest tests/persistence tests/execution -q
.venv/bin/pytest -q
```

Expected: restart, atomicity, idempotency, exact action/outcome, history, and safety tests pass without a real-time 50-second test delay.

- [ ] **Step 6: Commit and hold the Milestone 3 reviewer gate**

```bash
git add services/execution services/persistence data/domain/execution.py tests/execution
git commit -m "feat(execution): simulate decision outcomes"
```

Reviewer gate: restart the API between approval and playback, then verify Decision ID linkage and append-only history directly in SQLite.

---

### Task 9: Replace the In-Memory API with the Closed-Loop Application Service

**Files:**
- Modify: `apps/api/app/contracts.py`
- Create: `apps/api/app/dependencies.py`
- Create: `apps/api/app/routes/health.py`
- Create: `apps/api/app/routes/cases.py`
- Create: `apps/api/app/routes/decisions.py`
- Create: `apps/api/app/routes/execution.py`
- Create: `apps/api/app/routes/dashboard.py`
- Modify: `apps/api/app/main.py`
- Modify: `tests/test_api.py`
- Create: `tests/api/test_case_lifecycle.py`
- Create: `tests/api/test_failure_contracts.py`

**Interfaces:**
- Consumes: persistence, analysis, Decision, planning, and playback services from Tasks 4–8.
- Produces: stable `/api/runtime`, `/api/cases`, `/api/cases/{id}/analysis`, `/decisions`, `/actions`, `/drafts`, `/playback`, `/observations`, and `/api/dashboard/cases` contracts.

- [ ] **Step 1: Write the fallback lifecycle API test**

Create `tests/api/test_case_lifecycle.py`:

```python
def test_fallback_case_runs_from_creation_through_observations(client, immediate_clock):
    created = client.post("/api/cases", json={"template_id": "RL-001", "purpose": "automated_test"})
    case_id = created.json()["case_id"]
    analysis = client.post(f"/api/cases/{case_id}/analysis").json()
    assert analysis["recommendation"]["option_id"] == "RL-OPTION-COMBINED"

    decision = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": "RL-API-DECISION-1"},
        json={"analysis_id": analysis["analysis_id"], "kind": "approved", "selected_option_id": "RL-OPTION-COMBINED"},
    ).json()
    run_worker_until_idle()
    actions = client.get(f"/api/decisions/{decision['decision_id']}/actions").json()
    assert len(actions) == 5

    playback = client.post(f"/api/decisions/{decision['decision_id']}/playback").json()
    run_playback(playback["playback_id"], immediate_clock)
    observations = client.get(f"/api/decisions/{decision['decision_id']}/observations").json()
    assert len(observations) == 10
    assert {item["display_label"] for item in observations} == {"Simulated"}
```

- [ ] **Step 2: Run the lifecycle test and verify old routes fail**

Run:

```bash
.venv/bin/pytest tests/api/test_case_lifecycle.py -q
```

Expected: request/route failures because the new contracts do not exist.

- [ ] **Step 3: Implement the response contracts and dependency composition**

Every response includes `runtime_mode`, `scenario_effective_time`, and relevant source/projection timestamps. `/api/runtime` returns:

```json
{
  "runtime_mode": "fallback",
  "work_iq": "synthetic",
  "operational_store": "sqlite",
  "agent_runtime": "local",
  "power_bi_available": false
}
```

`dependencies.py` creates one mode-specific composition at application startup. No request or browser field may override it.

- [ ] **Step 4: Implement stale-analysis, rejection, and planning-failure HTTP semantics**

Use exact status/detail codes:

```python
raise HTTPException(409, detail={"code": "STALE_ANALYSIS", "message": "Create a new Analysis Version before deciding."})
raise HTTPException(409, detail={"code": "OPTION_NOT_EXECUTABLE", "blocking_codes": list(option.blocking_codes)})
raise HTTPException(403, detail={"code": "ROLE_REQUIRED", "role": "response_approver"})
```

Rejection returns `201`, creates no actions, and leaves a new-analysis control available. Planning failure keeps the immutable Decision response successful and exposes `action_planning_status="failed"` plus a retry endpoint.

- [ ] **Step 5: Run API and full tests**

Run:

```bash
.venv/bin/pytest tests/api tests/test_api.py -q
.venv/bin/pytest -q
```

Expected: lifecycle, stale-analysis, rejection, idempotency, and failure-contract tests pass.

- [ ] **Step 6: Commit the closed-loop API**

```bash
git add apps/api/app tests/api tests/test_api.py
git commit -m "feat(api): expose closed-loop case lifecycle"
```

---

### Task 10: Build the Progressive Case Workspace

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Create: `apps/web/src/hooks/useCaseWorkspace.ts`
- Create: `apps/web/src/components/CaseHeader.tsx`
- Create: `apps/web/src/components/EvidencePanel.tsx`
- Create: `apps/web/src/components/ExposurePanel.tsx`
- Create: `apps/web/src/components/OptionComparison.tsx`
- Create: `apps/web/src/components/DecisionPanel.tsx`
- Create: `apps/web/src/components/ExecutionPanel.tsx`
- Create: `apps/web/src/components/OutcomePanel.tsx`
- Create: `apps/web/src/styles.css`
- Modify: `apps/web/src/App.tsx`
- Create: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/api.test.ts`

**Interfaces:**
- Consumes: Task 9 API contracts.
- Produces: one progressive Case workspace from signal through Outcome Observations; no alternate dashboard application or client-selected runtime mode.

- [ ] **Step 1: Add Testing Library and write the failing workspace test**

Add bounded dev dependencies `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, and `jsdom`. Create `App.test.tsx`:

```typescript
it("keeps provenance, decision, execution, and simulated outcomes visible", async () => {
  mockFallbackCaseLifecycle();
  render(<App />);
  expect(await screen.findByText("Fallback mode")).toBeVisible();
  expect(screen.getByText("Scenario time: Sep 1, 2026, 9:00 AM CDT")).toBeVisible();
  await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
  expect(await screen.findByText("Combined response")).toBeVisible();
  await userEvent.click(screen.getByRole("button", {name: "Approve combined response"}));
  expect(await screen.findByText(/Decision RL-DECISION-/)).toBeVisible();
  expect(await screen.findAllByTestId("execution-action")).toHaveLength(5);
  await userEvent.click(screen.getByRole("button", {name: "Start simulated execution"}));
  expect(await screen.findByText("Simulated outcomes")).toBeVisible();
  expect(screen.queryByText("Actual outcomes")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the frontend test and verify the shell fails**

Run:

```bash
npm --prefix apps/web test -- --run App.test.tsx
```

Expected: failure because the current `App` is only a scaffold.

- [ ] **Step 3: Implement typed API methods and workspace state**

Add exact client methods:

```typescript
export const api = {
  runtime: (): Promise<RuntimeStatus> => get("/api/runtime"),
  createCase: (purpose: CasePurpose): Promise<CaseInstance> => post("/api/cases", {template_id: "RL-001", purpose}),
  analyze: (caseId: string): Promise<AnalysisVersion> => post(`/api/cases/${caseId}/analysis`, {}),
  decide: (caseId: string, input: DecisionInput, key: string): Promise<Decision> => post(`/api/cases/${caseId}/decisions`, input, {"Idempotency-Key": key}),
  actions: (decisionId: string): Promise<ExecutionAction[]> => get(`/api/decisions/${decisionId}/actions`),
  startPlayback: (decisionId: string): Promise<Playback> => post(`/api/decisions/${decisionId}/playback`, {}),
  observations: (decisionId: string): Promise<OutcomeObservation[]> => get(`/api/decisions/${decisionId}/observations`),
};
```

`useCaseWorkspace` is the only orchestration hook and exposes `create`, `analyze`, `approve`, `reject`, `retryPlanning`, and `startPlayback` commands plus typed loading/error states.

- [ ] **Step 4: Implement the seven required visible sections**

Render the Case header, cited Evidence Items, exposure/lineage, option comparison with elimination trace, Decision receipt, five actions, the visibly `Unsent draft`, and outcomes. Required labels are exact: `Live mode`, `Fallback mode`, `Simulated`, `Actual`, `Unsent draft`, `Power BI unavailable in fallback`, and `Approved — action planning failed`.

Disable Decision controls when the analysis is stale or blocked. The Beta row remains visible with its exact blocking code and cannot be selected.

`App.tsx` remains a composition root rather than absorbing section logic:

```tsx
export default function App() {
  const workspace = useCaseWorkspace();
  return <main className="case-workspace">
    <CaseHeader runtime={workspace.runtime} caseInstance={workspace.caseInstance} />
    <EvidencePanel analysis={workspace.analysis} />
    <ExposurePanel analysis={workspace.analysis} />
    <OptionComparison analysis={workspace.analysis} onSelect={workspace.selectOption} />
    <DecisionPanel state={workspace} onApprove={workspace.approve} onReject={workspace.reject} />
    <ExecutionPanel actions={workspace.actions} drafts={workspace.drafts} onRetry={workspace.retryPlanning} />
    <OutcomePanel playback={workspace.playback} observations={workspace.observations} onStart={workspace.startPlayback} />
  </main>;
}
```

- [ ] **Step 5: Run frontend tests and production build**

Run:

```bash
npm --prefix apps/web test
npm --prefix apps/web run build
.venv/bin/pytest -q
```

Expected: component/API tests pass, TypeScript is clean, Vite builds, and Python regressions pass.

- [ ] **Step 6: Commit the progressive workspace**

```bash
git add apps/web
git commit -m "feat(web): add progressive decision workspace"
```

---

### Task 11: Prove the Complete Fallback Browser Journey

**Files:**
- Modify: `apps/web/package.json`
- Create: `apps/web/playwright.config.ts`
- Create: `apps/web/e2e/fallback-demo.spec.ts`
- Create: `apps/web/e2e/fallback-failures.spec.ts`
- Create: `scripts/run_fallback_demo.sh`
- Modify: `README.md`

**Interfaces:**
- Consumes: fallback FastAPI/SQLite and the built React workspace.
- Produces: one command that executes the canonical browser journey and failure UX without Microsoft cloud access.

- [ ] **Step 1: Install Playwright and write the failing happy-path test**

Add `@playwright/test` and this script:

```json
"test:e2e": "playwright test"
```

Create `apps/web/e2e/fallback-demo.spec.ts`:

```typescript
test("RL-001 fallback journey reaches simulated outcomes", async ({page}) => {
  await page.goto("/");
  await expect(page.getByText("Fallback mode")).toBeVisible();
  await page.getByRole("button", {name: "Create showcase case"}).click();
  await page.getByRole("button", {name: "Analyze disruption"}).click();
  await expect(page.getByText("Combined response")).toBeVisible();
  await page.getByRole("button", {name: "Approve combined response"}).click();
  await expect(page.getByTestId("decision-receipt")).toContainText("RL-DECISION-");
  await expect(page.getByTestId("execution-action")).toHaveCount(5);
  await page.getByRole("button", {name: "Start simulated execution"}).click();
  await expect(page.getByText("Simulated outcomes")).toBeVisible({timeout: 65_000});
  await expect(page.getByText("Power BI unavailable in fallback")).toBeVisible();
});
```

- [ ] **Step 2: Run the E2E test and verify setup failure**

Run:

```bash
npm --prefix apps/web run test:e2e -- fallback-demo.spec.ts
```

Expected: failure until Playwright web servers and the fallback environment are configured.

- [ ] **Step 3: Configure two local web servers**

`playwright.config.ts` starts:

```typescript
webServer: [
  {command: ".venv/bin/uvicorn apps.api.app.main:app --port 8000", cwd: "../..", url: "http://127.0.0.1:8000/health", reuseExistingServer: true, env: {SUPPLY_RESPONSE_RUNTIME_MODE: "fallback", SUPPLY_RESPONSE_DATABASE_URL: "sqlite:///./.tmp/e2e.db"}},
  {command: "npm run dev -- --host 127.0.0.1", cwd: "apps/web", url: "http://127.0.0.1:5173", reuseExistingServer: true},
],
use: {baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure"},
```

Configure Vite's development proxy so `/api` targets `http://127.0.0.1:8000`.

- [ ] **Step 4: Add failure journeys**

`fallback-failures.spec.ts` covers rejection followed by reanalysis, stale-analysis blocking, planning-failure retry, failed-action retry, and a second idempotent playback click. Each test creates a fresh `automated_test` Case Instance; none resets a prior case.

- [ ] **Step 5: Run the Milestone 4 gate**

Run:

```bash
.venv/bin/pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e
```

Expected: Python, Vitest, build, and all fallback Playwright tests pass. Power BI is never presented as available.

- [ ] **Step 6: Commit and hold the Milestone 4 reviewer gate**

```bash
git add apps/web scripts/run_fallback_demo.sh README.md
git commit -m "test(e2e): prove fallback demo journey"
```

Reviewer gate: run `scripts/run_fallback_demo.sh`, inspect the full browser flow, then approve live integration work.

---

### Task 12: Add the Fabric SQL Database Adapter and Analytics Views

**Files:**
- Modify: `pyproject.toml`
- Create: `services/persistence/fabric_sql.py`
- Create: `integrations/fabric/health.py`
- Create: `fabric/sql/001_operational_schema.sql`
- Create: `fabric/sql/002_analytics_views.sql`
- Create: `tests/integration/test_store_contract.py`
- Create: `tests/integration/test_fabric_sql_live.py`
- Modify: `apps/api/app/dependencies.py`
- Modify: `apps/api/app/routes/health.py`

**Interfaces:**
- Consumes: `CaseStore`/`UnitOfWork` protocols and SQLAlchemy tables from Task 5.
- Produces: `build_fabric_engine(settings: Settings, credential: TokenCredential) -> Engine`, the same store contract against Fabric SQL, and live health/provenance details.

- [ ] **Step 1: Parameterize the store contract tests**

Create `tests/integration/test_store_contract.py` so every persistence behavior runs against SQLite and an opt-in Fabric factory:

```python
@pytest.fixture(params=["sqlite", pytest.param("fabric", marks=pytest.mark.fabric_live)])
def store_factory(request, tmp_path):
    if request.param == "sqlite":
        return lambda: sqlite_store(f"sqlite:///{tmp_path / 'contract.db'}")
    return lambda: fabric_store_from_environment()


def test_case_analysis_decision_outbox_action_and_observation_round_trip(store_factory):
    store = store_factory()
    artifacts = persist_complete_rl001(store)
    assert load_complete_rl001(store) == artifacts
```

Add `fabric_live` to pytest markers and skip it unless `SUPPLY_RESPONSE_FABRIC_SQL_SERVER` and `SUPPLY_RESPONSE_FABRIC_SQL_DATABASE` are present.

- [ ] **Step 2: Run SQLite contract tests and verify they pass before the adapter**

Run:

```bash
.venv/bin/pytest tests/integration/test_store_contract.py -q -m 'not fabric_live'
```

Expected: the SQLite parameter passes; this establishes the adapter contract independently of cloud availability.

- [ ] **Step 3: Add Fabric/identity dependencies and token-based ODBC connection**

Add bounded runtime dependencies:

```toml
"azure-identity>=1.23,<2",
"pyodbc>=5.2,<6",
```

Use ODBC Driver 18 and an Entra token; never put a password in the connection string:

```python
SQL_COPT_SS_ACCESS_TOKEN = 1256


def build_fabric_engine(settings: Settings, credential: TokenCredential) -> Engine:
    quoted = quote_plus(
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={settings.fabric_sql_server};"
        f"Database={settings.fabric_sql_database};"
        "Encrypt=yes;TrustServerCertificate=no;"
    )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quoted}", pool_pre_ping=True)

    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        token = credential.get_token("https://database.windows.net/.default").token
        raw = token.encode("utf-16-le")
        packed = struct.pack(f"<I{len(raw)}s", len(raw), raw)
        cparams["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: packed}

    return engine
```

Local runs use `AzureCliCredential(tenant_id=settings.allowed_tenant_id)`; Azure uses `ManagedIdentityCredential()` selected explicitly by `SUPPLY_RESPONSE_CREDENTIAL_MODE`.

- [ ] **Step 4: Create the live schema and read-only analytics views**

`fabric/sql/001_operational_schema.sql` mirrors migration `0001` with SQL Server types, primary/unique keys, JSON `nvarchar(max)` payloads, and the Decision/outbox transaction. `002_analytics_views.sql` creates:

```sql
CREATE OR ALTER VIEW analytics.case_command_center AS
SELECT c.case_id, c.purpose, c.status, c.runtime_mode,
       c.scenario_effective_time, a.recommended_option_id,
       a.revenue_at_risk, a.otif_loss_percentage,
       d.decision_id, d.kind AS decision_kind, d.decided_at
FROM app.case_projection c
LEFT JOIN app.analysis_projection a ON a.analysis_id = c.current_analysis_id
LEFT JOIN app.decision_projection d ON d.decision_id = c.current_decision_id;
GO

CREATE OR ALTER VIEW analytics.action_outcomes AS
SELECT d.case_id, d.decision_id, d.selected_option_id,
       'action' AS record_type,
       x.action_id, x.kind AS action_kind, x.status AS action_status,
       NULL AS metric, NULL AS predicted_value, NULL AS observed_value,
       NULL AS unit, NULL AS observation_kind,
       d.scenario_effective_time, x.updated_at AS projection_updated_at
FROM app.decisions d
JOIN app.action_projection x ON x.decision_id = d.decision_id
UNION ALL
SELECT d.case_id, d.decision_id, d.selected_option_id,
       'observation' AS record_type,
       o.action_id, NULL, NULL,
       o.metric, o.predicted_value, o.observed_value, o.unit,
       o.kind, o.scenario_effective_time, o.recorded_at
FROM app.decisions d
JOIN app.outcome_observations o ON o.decision_id = d.decision_id;
GO
```

Projection tables are maintained transactionally by the store; the views never infer Decision truth from action state.

- [ ] **Step 5: Wire live mode and health without fallback**

`dependencies.py` must fail startup if live Fabric settings or token acquisition fail. `/api/runtime` returns `operational_store="fabric_sql"` and `power_bi_available=true` only after `SELECT 1` and a schema-version query succeed. It may never catch this failure and instantiate SQLite.

- [ ] **Step 6: Run adapter verification**

Run locally:

```bash
.venv/bin/pytest tests/integration/test_store_contract.py -q -m 'not fabric_live'
.venv/bin/pytest -q
```

After the Fabric SQL Database and identity grant exist, run:

```bash
.venv/bin/pytest tests/integration/test_store_contract.py tests/integration/test_fabric_sql_live.py -q -m fabric_live
```

Expected: the same round-trip contract passes on both databases; Fabric health reports the configured live source.

- [ ] **Step 7: Commit the Fabric adapter**

```bash
git add pyproject.toml uv.lock services/persistence/fabric_sql.py integrations/fabric fabric/sql apps/api/app tests/integration
git commit -m "feat(fabric): add transactional Fabric SQL adapter"
```

---

### Task 13: Build and Deploy the Two-Page Power BI Project

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `fabric/power-bi/SupplyResponse.pbip`
- Create: `fabric/power-bi/SupplyResponse.SemanticModel/definition.pbism`
- Create: `fabric/power-bi/SupplyResponse.SemanticModel/definition/model.tmdl`
- Create: `fabric/power-bi/SupplyResponse.SemanticModel/definition/tables/CaseCommandCenter.tmdl`
- Create: `fabric/power-bi/SupplyResponse.SemanticModel/definition/tables/ActionOutcomes.tmdl`
- Create: `fabric/power-bi/SupplyResponse.Report/definition.pbir`
- Create: `fabric/power-bi/SupplyResponse.Report/definition/pages/pages.json`
- Create: `fabric/power-bi/SupplyResponse.Report/definition/pages/command-center/page.json`
- Create: `fabric/power-bi/SupplyResponse.Report/definition/pages/actions-outcomes/page.json`
- Create: `fabric/deploy.py`
- Create: `tests/fabric/test_power_bi_project.py`
- Create: `tests/fabric/test_power_bi_live.py`

**Interfaces:**
- Consumes: Fabric views `analytics.case_command_center` and `analytics.action_outcomes` from Task 12.
- Produces: one PBIP semantic model/report with `Command Center` and `Actions and Outcomes`, deployed by `python fabric/deploy.py`.

- [ ] **Step 1: Write the failing source-artifact test**

Create `tests/fabric/test_power_bi_project.py`:

```python
def test_power_bi_project_has_only_the_two_required_pages():
    pages = json.loads((ROOT / "fabric/power-bi/SupplyResponse.Report/definition/pages/pages.json").read_text())
    assert [page["displayName"] for page in pages["pageOrder"]] == [
        "Command Center", "Actions and Outcomes"
    ]


def test_semantic_model_exposes_decision_and_simulation_measures():
    text = "\n".join(path.read_text() for path in SEMANTIC_MODEL.rglob("*.tmdl"))
    for required in (
        "Latest Showcase Case", "Current Decision ID", "Revenue At Risk",
        "OTIF Loss %", "Action Completion %", "Observed Variance",
        "Projection Refresh Time", "Scenario Effective Time",
    ):
        assert f"measure '{required}'" in text
```

- [ ] **Step 2: Run the artifact test and verify the PBIP is absent**

Run:

```bash
.venv/bin/pytest tests/fabric/test_power_bi_project.py -q
```

Expected: failures because the PBIP files do not exist.

- [ ] **Step 3: Define the DirectQuery semantic model**

Add a Python 3.12-only deployment optional dependency group so the application can remain compatible with Python 3.13 while the current `fabric-cicd` deployment tool runs in its supported interpreter:

```toml
[project.optional-dependencies]
fabric-deploy = ["fabric-cicd>=0.1,<2"]
```

Use DirectQuery to the Fabric SQL Database so the 60-second gate does not depend on import refresh. `CaseCommandCenter.tmdl` must include:

```tmdl
table CaseCommandCenter
  measure 'Latest Showcase Case' =
    VAR LatestRow = TOPN(1, FILTER(ALL(CaseCommandCenter), CaseCommandCenter[purpose] = "showcase"), CaseCommandCenter[decided_at], DESC, CaseCommandCenter[case_id], DESC)
    RETURN MAXX(LatestRow, CaseCommandCenter[case_id])
  measure 'Current Decision ID' = SELECTEDVALUE(CaseCommandCenter[decision_id])
  measure 'Revenue At Risk' = MAX(CaseCommandCenter[revenue_at_risk])
  measure 'OTIF Loss %' = MAX(CaseCommandCenter[otif_loss_percentage]) / 100
  measure 'Scenario Effective Time' = MAX(CaseCommandCenter[scenario_effective_time])
  partition CaseCommandCenter = m
    mode: directQuery
    source = Sql.Database(Environment.GetEnvironmentVariable("FABRIC_SQL_SERVER"), Environment.GetEnvironmentVariable("FABRIC_SQL_DATABASE"), [Query="SELECT * FROM analytics.case_command_center"])
```

`ActionOutcomes.tmdl` defines `Action Completion %`, `Observed Variance`, and `Projection Refresh Time = MAX(ActionOutcomes[projection_updated_at])` and exposes `observation_kind` for the permanent Simulated label.

- [ ] **Step 4: Define the exact report pages**

The `Command Center` page contains cards for active cases, Revenue At Risk, OTIF Loss %, current Decision status, and time since signal, plus a case table filtered by `purpose="showcase"` and the `Latest Showcase Case` measure. The `Actions and Outcomes` page contains the Decision ID card, action-status table, predicted-versus-observed variance chart, and visible `observation_kind`, Scenario Effective Time, and Projection Refresh Time cards.

Use these page identities and display names in `pages.json`:

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
  "pageOrder": [
    {"name": "command-center", "displayName": "Command Center"},
    {"name": "actions-outcomes", "displayName": "Actions and Outcomes"}
  ],
  "activePageName": "command-center"
}
```

Each `page.json` sets `displayOption="FitToPage"`, `width=1280`, `height=720`, and `refreshInterval=30`. The committed PBIR visual containers bind only these exact query references:

```json
{
  "command-center": [
    "CaseCommandCenter.case_id",
    "CaseCommandCenter.status",
    "CaseCommandCenter.Current Decision ID",
    "CaseCommandCenter.Revenue At Risk",
    "CaseCommandCenter.OTIF Loss %",
    "CaseCommandCenter.Scenario Effective Time"
  ],
  "actions-outcomes": [
    "ActionOutcomes.decision_id",
    "ActionOutcomes.action_kind",
    "ActionOutcomes.action_status",
    "ActionOutcomes.observation_kind",
    "ActionOutcomes.Observed Variance",
    "ActionOutcomes.Projection Refresh Time"
  ]
}
```

The artifact test extracts every PBIR `queryRef`, asserts it is in this allowlist, asserts the page size/refresh values, and asserts no third page exists.

- [ ] **Step 5: Add deterministic deployment**

`fabric/deploy.py` uses `fabric_cicd` and `AzureCliCredential(tenant_id=os.environ["SUPPLY_RESPONSE_ALLOWED_TENANT_ID"])`:

```python
workspace = FabricWorkspace(
    workspace_id=os.environ["SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID"],
    environment="dev",
    repository_directory=str(Path(__file__).parent / "power-bi"),
    item_type_in_scope=["SemanticModel", "Report"],
    token_credential=credential,
)
publish_all_items(workspace)
```

Environment-specific server/database/workspace values remain outside source control.

- [ ] **Step 6: Run artifact and live consistency tests**

Run:

```bash
.venv/bin/pytest tests/fabric/test_power_bi_project.py -q
python fabric/deploy.py
.venv/bin/pytest tests/fabric/test_power_bi_live.py -q -m fabric_live
```

The live test writes a showcase Decision, polls the Power BI query endpoint for at most 60 seconds, and asserts the same `case_id`, `decision_id`, selected option, five actions, ten Simulated Observations, Scenario Effective Time, and a non-null refresh time.

- [ ] **Step 7: Commit and hold the Milestone 5 reviewer gate**

```bash
git add pyproject.toml uv.lock fabric/power-bi fabric/deploy.py tests/fabric
git commit -m "feat(power-bi): add live command center"
```

Reviewer gate: inspect both report pages in the Fabric workspace and compare their Decision ID to the web console.

---

### Task 14: Configure Single-Tenant Entra Authentication and Persona Roles

**Files:**
- Modify: `pyproject.toml`
- Modify: `apps/web/package.json`
- Create: `infra/entra/api-app.json`
- Create: `infra/entra/web-app.json`
- Create: `infra/entra/configure.sh`
- Create: `infra/entra/assign-personas.sh`
- Create: `apps/api/app/auth.py`
- Create: `apps/web/src/auth/msal.ts`
- Create: `apps/web/src/auth/AuthProvider.tsx`
- Create: `tests/auth/test_token_authorization.py`
- Create: `apps/web/src/auth/AuthProvider.test.tsx`
- Create: `docs/deployment/personal-tenant.md`

**Interfaces:**
- Consumes: bearer access tokens issued by the one allowed tenant to the Supply Response API.
- Produces: `AuthenticatedActor`, Alex-only Decision authorization, deployment-specific persona bindings, and a downstream user assertion for Work IQ OBO.

- [ ] **Step 1: Write failing issuer/audience/role tests**

Create `tests/auth/test_token_authorization.py`:

```python
def test_alex_token_maps_stable_persona_and_roles(token_factory, auth_service):
    token = token_factory(tid=TENANT_ID, oid=ALEX_OID, roles=["material_planner", "response_approver"])
    actor = auth_service.authenticate(token)
    assert actor.persona_id == "RL-PERSONA-ALEX"
    assert actor.effective_roles == ("material_planner", "response_approver")


@pytest.mark.parametrize("claim,value", [("tid", "wrong-tenant"), ("aud", "wrong-api")])
def test_wrong_tenant_or_audience_is_rejected(token_factory, auth_service, claim, value):
    token = token_factory(**{claim: value})
    with pytest.raises(AuthenticationError):
        auth_service.authenticate(token)


def test_upn_alone_never_authorizes(token_factory, auth_service):
    token = token_factory(oid="unbound-object", upn="alex@example.invalid", roles=["response_approver"])
    with pytest.raises(AuthorizationError, match="persona binding"):
        auth_service.authenticate(token)
```

- [ ] **Step 2: Run auth tests and verify service absence**

Run:

```bash
.venv/bin/pytest tests/auth/test_token_authorization.py -q
```

Expected: collection fails because `apps.api.app.auth` does not exist.

- [ ] **Step 3: Define two single-tenant registrations**

Use one confidential `Supply Response API` registration and one public `Supply Response Web` SPA registration. The API exposes delegated scope `access_as_user` and app roles:

```json
[
  {"value":"material_planner","displayName":"Material Planner","allowedMemberTypes":["User"]},
  {"value":"response_approver","displayName":"Response Approver","allowedMemberTypes":["User"]},
  {"value":"quality_approver","displayName":"Quality Approver","allowedMemberTypes":["User"]},
  {"value":"finance_approver","displayName":"Finance Approver","allowedMemberTypes":["User"]}
]
```

The API registration receives delegated `WorkIQAgent.Ask`; the Web registration receives delegated `api://<API_APP_ID>/access_as_user`. Both use `AzureADMyOrg`. `configure.sh` resolves the active tenant with `az account show --query tenantId -o tsv`, aborts unless the operator confirms it is the `willmacdonald.com` directory, and writes IDs only to an ignored `.env.tenant` file.

- [ ] **Step 4: Assign persona roles by object ID**

`assign-personas.sh` reads `SUPPLY_RESPONSE_ALEX_OBJECT_ID`, `JORDAN_OBJECT_ID`, and `TAYLOR_OBJECT_ID`; it assigns Alex two roles, Jordan `quality_approver`, and Taylor `finance_approver` on the API service principal. It never searches by display name or commits a UPN.

Resolve each role ID by its exact `value` and assign it to the exact object ID:

```bash
API_SP_ID="$(az ad sp show --id "$SUPPLY_RESPONSE_API_CLIENT_ID" --query id -o tsv)"
assign_role() {
  PERSON_OBJECT_ID="$1"
  ROLE_VALUE="$2"
  ROLE_ID="$(az ad app show --id "$SUPPLY_RESPONSE_API_CLIENT_ID" --query "appRoles[?value=='$ROLE_VALUE'].id | [0]" -o tsv)"
  az rest --method POST --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$API_SP_ID/appRoleAssignedTo" --body "{\"principalId\":\"$PERSON_OBJECT_ID\",\"resourceId\":\"$API_SP_ID\",\"appRoleId\":\"$ROLE_ID\"}"
}
assign_role "$SUPPLY_RESPONSE_ALEX_OBJECT_ID" material_planner
assign_role "$SUPPLY_RESPONSE_ALEX_OBJECT_ID" response_approver
assign_role "$SUPPLY_RESPONSE_JORDAN_OBJECT_ID" quality_approver
assign_role "$SUPPLY_RESPONSE_TAYLOR_OBJECT_ID" finance_approver
```

- [ ] **Step 5: Validate tokens and snapshot identity**

Add `PyJWT[crypto]>=2.10,<3`. `auth.py` caches the tenant OpenID metadata/JWKS, validates signature, issuer `https://login.microsoftonline.com/{tenant_id}/v2.0`, audience, expiry, `tid`, and `oid`, then resolves the stable persona binding from environment configuration. Preserve `upn` and display name only in the immutable Decision identity snapshot.

- [ ] **Step 6: Acquire API tokens in React**

Add `@azure/msal-browser` and `@azure/msal-react`. Configure `PublicClientApplication` from `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_WEB_CLIENT_ID`, `VITE_ENTRA_API_SCOPE`, and the exact redirect URI. `AuthProvider` uses redirect login and `acquireTokenSilent`; `api.ts` adds `Authorization: Bearer` without storing tokens in local storage.

- [ ] **Step 7: Verify identity setup**

Run:

```bash
.venv/bin/pytest tests/auth -q
npm --prefix apps/web test -- --run AuthProvider.test.tsx
./infra/entra/configure.sh --check
./infra/entra/assign-personas.sh --check
```

Expected: unit tests pass; checks report the same tenant ID for the current Azure subscription and both Entra registrations, exact role definitions, and all three object-ID assignments. Taylor has no product-license dependency.

- [ ] **Step 8: Commit identity configuration**

```bash
git add pyproject.toml uv.lock apps/api/app/auth.py apps/web infra/entra tests/auth docs/deployment/personal-tenant.md
git commit -m "feat(identity): bind demo personas to Entra roles"
```

---

### Task 15: Retrieve Cited Microsoft 365 Evidence through Work IQ

**Files:**
- Modify: `pyproject.toml`
- Create: `integrations/workiq/obo.py`
- Create: `integrations/workiq/client.py`
- Create: `integrations/workiq/normalizer.py`
- Create: `integrations/workiq/prompts.py`
- Create: `data/demo-corpus/supplier-alpha-message.md`
- Create: `data/demo-corpus/supplier-beta-quality-message.md`
- Create: `data/fixtures/workiq/supplier-alpha-a2a.json`
- Create: `data/fixtures/workiq/supplier-beta-quality-a2a.json`
- Create: `docs/deployment/demo-corpus.md`
- Create: `tests/integration/test_workiq_contract.py`
- Create: `tests/integration/test_workiq_live.py`

**Interfaces:**
- Consumes: Alex's validated API bearer token as an OBO assertion.
- Produces: `WorkIQEvidencePort.retrieve_supplier_signal(...) -> tuple[EvidenceItem, ...]` and `retrieve_quality_context(...) -> tuple[EvidenceItem, ...]`, using A2A v1.0 at `https://workiq.svc.cloud.microsoft/a2a/`.

- [ ] **Step 1: Write the failing fixture-contract test**

Create `tests/integration/test_workiq_contract.py`:

```python
@pytest.mark.parametrize("fixture_name", ["supplier-alpha-a2a.json", "supplier-beta-quality-a2a.json"])
def test_a2a_response_normalizes_to_cited_evidence(fixture_name):
    payload = json.loads((FIXTURES / fixture_name).read_text())
    items = normalize_a2a_evidence(payload, case_id="RL-CASE-WORKIQ-1", retrieved_at=NOW)
    assert items
    assert all(item.source_system == "work_iq" for item in items)
    assert all(item.source_id and item.source_timestamp for item in items)
    assert all(item.excerpt and item.citation_url for item in items)
    assert all(item.runtime_mode is RuntimeMode.LIVE and not item.synthetic for item in items)


def test_normalizer_does_not_invent_missing_citation():
    payload = a2a_payload_without_citation()
    items = normalize_a2a_evidence(payload, case_id="RL-CASE-WORKIQ-2", retrieved_at=NOW)
    assert items[0].citation_url is None
    assert validate_required_evidence(items, RuntimeMode.LIVE).blocked
```

- [ ] **Step 2: Run the contract test and verify adapter absence**

Run:

```bash
.venv/bin/pytest tests/integration/test_workiq_contract.py -q
```

Expected: collection fails because `integrations.workiq` does not exist.

- [ ] **Step 3: Implement confidential-client OBO**

Move `httpx>=0.28,<1` from dev-only to runtime dependencies, add `msal>=1.32,<2`, and use:

```python
result = confidential_client.acquire_token_on_behalf_of(
    user_assertion=api_access_token,
    scopes=["api://workiq.svc.cloud.microsoft/.default"],
)
if "access_token" not in result:
    raise WorkIQAuthenticationError(result.get("error"), result.get("error_description"))
```

The API registration must already have delegated `WorkIQAgent.Ask` and admin consent. Application-only tokens are rejected before any request.

- [ ] **Step 4: Implement the A2A v1.0 request exactly**

`WorkIQClient.send_message()` posts:

```python
payload = {
    "jsonrpc": "2.0",
    "id": str(uuid4()),
    "method": "SendMessage",
    "params": {"message": {
        "role": "ROLE_USER",
        "messageId": str(uuid4()),
        "parts": [{"text": prompt}],
        "metadata": {"Location": {"timeZoneOffset": -300, "timeZone": "America/Chicago"}},
    }},
}
response = await http.post(
    "https://workiq.svc.cloud.microsoft/a2a/",
    headers={"Authorization": f"Bearer {token}", "A2A-Version": "1.0"},
    json=payload,
    timeout=30.0,
)
```

Require `TASK_STATE_COMPLETED`; persist the opaque `contextId`, artifact IDs, source IDs, timestamps, excerpts, and navigable citation URLs. Treat citation delivery shape as adapter-only and cover it with captured fictional fixtures.

- [ ] **Step 5: Use constrained prompts and reject web-grounded claims**

Prompts name the fictional supplier/order/Quality artifacts and demand JSON facts with source citations. They explicitly prohibit inference and web grounding. The normalizer accepts only claims attached to tenant-source citations; free text without a source becomes contextual, nonauthoritative evidence and blocks the canonical live analysis.

- [ ] **Step 6: Create the purpose-built Microsoft 365 Demo Corpus**

Commit exact fictional source text, not tenant bindings. `supplier-alpha-message.md` states that RL-Supplier Alpha cannot deliver 8,000 units on Scenario Day 2, offers 3,000 units by air on September 6 at `$7.50` per unit, and has no confirmed date for the remaining 5,000. `supplier-beta-quality-message.md` states that RL-Supplier Beta qualification is `pending`, audit and first article are incomplete, and September 15 is the next fictional-scenario review date.

`docs/deployment/demo-corpus.md` directs the operator to:

1. Create an unlicensed shared mailbox with display name `RL-Supplier Alpha`, grant the operator `Send As`, and send the Alpha text from it to Alex's purpose-built mailbox; no sender UPN is committed.
2. Post the Beta Quality text as Jordan in a Teams channel Alex can read.
3. Open both artifacts while signed in as Alex and record only their opaque source IDs in ignored `.env.tenant` configuration.
4. Verify the content includes `DEMO CORPUS — FICTIONAL` and that no real supplier/customer data appears.
5. Leave the artifacts in place across rehearsals; source age does not require regeneration because business validity uses Scenario Effective Time.
6. Enable Work IQ usage-based billing/Copilot Credits for Alex and verify a test A2A request before running application tests.

The application never creates or sends these artifacts. This is a one-time tenant setup operation performed with the purpose-built accounts.

- [ ] **Step 7: Run contract and live retrieval tests**

Run:

```bash
.venv/bin/pytest tests/integration/test_workiq_contract.py -q
.venv/bin/pytest tests/integration/test_workiq_live.py -q -m workiq_live
```

The live test signs Alex in, retrieves the fictional Alpha signal and Jordan-authored Beta Quality item, opens every returned citation URL, and asserts the current retrieval timestamp. It never runs as Taylor or with application-only credentials.

- [ ] **Step 8: Commit the Work IQ adapter and corpus definition**

```bash
git add pyproject.toml uv.lock integrations/workiq data/demo-corpus data/fixtures/workiq docs/deployment/demo-corpus.md tests/integration/test_workiq_contract.py tests/integration/test_workiq_live.py
git commit -m "feat(work-iq): retrieve cited demo evidence"
```

---

### Task 16: Orchestrate Foundry-Managed Agents with Microsoft Agent Framework

**Files:**
- Modify: `pyproject.toml`
- Create: `agents/signal/instructions.md`
- Create: `agents/context/instructions.md`
- Create: `agents/decision/instructions.md`
- Create: `agents/foundry.py`
- Create: `agents/orchestrator/contracts.py`
- Create: `agents/orchestrator/workflow.py`
- Create: `agents/orchestrator/local.py`
- Create: `agents/manifests/signal.json`
- Create: `agents/manifests/context.json`
- Create: `agents/manifests/decision.json`
- Create: `scripts/publish_foundry_agents.py`
- Create: `scripts/verify_foundry_agents.py`
- Create: `tests/agents/test_orchestrator.py`
- Create: `tests/agents/test_foundry_live.py`

**Interfaces:**
- Consumes: `WorkIQEvidencePort`, operational snapshot port, deterministic `analyze_case`, and trusted Foundry agent names/versions.
- Produces: `Orchestrator.analyze(command: AnalyzeCommand) -> AnalysisVersion`; live composition uses `FoundryAgent`, fallback uses deterministic local explainers with the same typed output.

- [ ] **Step 1: Write the failing authority-boundary test**

Create `tests/agents/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_orchestrator_uses_agent_text_only_as_explanation(fake_agents, deterministic_tools):
    fake_agents.decision.response = {
        "recommended_option_id": "RL-OPTION-BETA",
        "explanation": "Choose Beta because it sounds fast."
    }
    result = await build_orchestrator(fake_agents, deterministic_tools).analyze(command())
    assert result.recommendation.option_id == "RL-OPTION-COMBINED"
    assert result.recommendation.explanation_source == "agent"
    assert "RL-OPTION-BETA" not in result.recommendation.authoritative_inputs


@pytest.mark.asyncio
async def test_agent_failure_preserves_evidence_and_deterministic_result(fake_agents, deterministic_tools):
    fake_agents.context.raise_error = TimeoutError("RL-TEST-TIMEOUT")
    with pytest.raises(AgentExplanationUnavailable) as exc:
        await build_orchestrator(fake_agents, deterministic_tools).analyze(command())
    assert exc.value.partial_result.analysis_version is not None
    assert exc.value.partial_result.evidence_items
```

- [ ] **Step 2: Run the tests and verify orchestration absence**

Run:

```bash
.venv/bin/pytest tests/agents/test_orchestrator.py -q
```

Expected: collection fails because the orchestrator modules do not exist.

- [ ] **Step 3: Add current Agent Framework packages and construct Foundry agents**

Add bounded prerelease-compatible dependencies and lock the resolved versions:

```toml
"agent-framework>=1.0.0rc1,<2",
"agent-framework-foundry>=1.0.0rc1,<2",
"azure-ai-projects>=2.3,<3",
```

Construct server-managed prompt agents from trusted configuration:

```python
def foundry_agent(*, name: str, version: str, settings: Settings, credential) -> FoundryAgent:
    return FoundryAgent(
        project_endpoint=settings.foundry_project_endpoint,
        agent_name=name,
        agent_version=version,
        credential=credential,
        timeout=30.0,
    )
```

Use `AzureCliCredential(tenant_id=...)` locally and `ManagedIdentityCredential()` in Azure. Agent names, versions, and endpoints remain trusted server configuration.

- [ ] **Step 4: Freeze agent instructions and tool schemas**

The Signal agent extracts only explicit supplier facts and uncertainties from supplied Evidence Items. The Context agent extracts only explicit Quality/collaboration facts. The Decision agent explains a supplied `AnalysisVersion`; it may not introduce or change comparator values.

Each manifest contains `agent_name`, `model`, `instructions_path`, `description`, and an empty `tools` array. Work IQ retrieval and deterministic tools remain application executors rather than model-visible Foundry tools.

`scripts/publish_foundry_agents.py` publishes a versioned Prompt Agent for each manifest:

```python
project = AIProjectClient(
    endpoint=os.environ["SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT"],
    credential=credential,
)
for manifest_path in sorted(Path("agents/manifests").glob("*.json")):
    manifest = json.loads(manifest_path.read_text())
    created = project.agents.create_version(
        agent_name=manifest["agent_name"],
        description=manifest["description"],
        definition=PromptAgentDefinition(
            model=manifest["model"],
            instructions=Path(manifest["instructions_path"]).read_text(),
            tools=[],
        ),
    )
    print(f"{created.name}={created.version}")
```

The operator copies only the emitted version numbers into ignored deployment configuration. `scripts/verify_foundry_agents.py` reads the three configured name/version pairs through `AIProjectClient`, hashes their instructions, and fails when the hashes or empty-tool contracts differ from the committed manifests.

- [ ] **Step 5: Implement the typed workflow**

Build an Agent Framework workflow whose edges are fixed:

```python
signal = SignalExecutor(work_iq, signal_agent)
context = ContextExecutor(work_iq, context_agent)
analysis = DeterministicAnalysisExecutor(analysis_service)
decision = DecisionExplanationExecutor(decision_agent)

workflow = (
    WorkflowBuilder(start_executor=signal)
    .add_edge(signal, context)
    .add_edge(context, analysis)
    .add_edge(analysis, decision)
    .build()
)
```

Executor outputs are typed Pydantic messages. Only `DeterministicAnalysisExecutor` creates the authoritative Analysis Version. The fallback workflow uses the same Signal/Context contracts with synthetic evidence and a local templated explanation.

- [ ] **Step 6: Run unit and Foundry smoke tests**

Run:

```bash
.venv/bin/pytest tests/agents/test_orchestrator.py -q
.venv/bin/python scripts/publish_foundry_agents.py
.venv/bin/python scripts/verify_foundry_agents.py
.venv/bin/pytest tests/agents/test_foundry_live.py -q -m foundry_live
```

Expected: authority-boundary tests pass; all three committed agent manifests match Foundry; a live fictional request returns explanations while the deterministic RL-001 recommendation remains combined.

- [ ] **Step 7: Commit the agent orchestration**

```bash
git add pyproject.toml uv.lock agents scripts/publish_foundry_agents.py scripts/verify_foundry_agents.py tests/agents
git commit -m "feat(agents): orchestrate Foundry agents safely"
```

---

### Task 17: Compose the Complete Live Case Journey

**Files:**
- Modify: `apps/api/app/dependencies.py`
- Modify: `apps/api/app/routes/cases.py`
- Modify: `apps/api/app/routes/decisions.py`
- Modify: `apps/api/app/routes/health.py`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/components/CaseHeader.tsx`
- Modify: `apps/web/src/components/EvidencePanel.tsx`
- Create: `apps/web/e2e/live-demo.spec.ts`
- Create: `tests/integration/test_live_case_contract.py`
- Modify: `docs/deployment/personal-tenant.md`

**Interfaces:**
- Consumes: Entra actor/token, Work IQ evidence, Foundry workflow, Fabric SQL store, and Power BI URL.
- Produces: the canonical live Detect → Analyze → Decide → Execute → Observe journey with immutable live provenance.

- [ ] **Step 1: Write a composed live-contract test with fakes at network boundaries**

Create `tests/integration/test_live_case_contract.py`:

```python
def test_live_composition_never_mixes_fallback_sources(live_app_with_fakes):
    result = run_complete_case(live_app_with_fakes, alex_token())
    assert result.case.runtime_mode is RuntimeMode.LIVE
    assert {e.source_system for e in result.analysis.evidence_items} == {"work_iq", "fabric_sql"}
    assert all(not e.synthetic for e in result.analysis.required_evidence)
    assert result.runtime.power_bi_available is True
    assert result.decision.identity.persona_id == "RL-PERSONA-ALEX"
    assert len(result.actions) == 5
    assert all(o.kind.value == "simulated" for o in result.observations)


def test_live_source_failure_blocks_instead_of_falling_back(live_app_with_workiq_failure):
    response = live_app_with_workiq_failure.post("/api/cases/RL-CASE/analysis", headers=alex_auth())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "LIVE_SOURCE_UNAVAILABLE"
    assert response.json()["detail"]["new_fallback_case_allowed"] is True
```

- [ ] **Step 2: Run composed tests and verify live dependencies are incomplete**

Run:

```bash
.venv/bin/pytest tests/integration/test_live_case_contract.py -q
```

Expected: failure until live dependency composition and bearer-token forwarding are complete.

- [ ] **Step 3: Compose live dependencies exactly once at startup**

Live mode builds `FabricSqlStore`, `WorkIQClient`, `FoundryOrchestrator`, `DecisionService`, `ActionPlanningWorker`, and `PlaybackService`. Fallback mode builds `SqliteStore`, `SyntheticEvidencePort`, `LocalOrchestrator`, and the same Decision/execution services. Store the mode on every created Case Instance and re-check it whenever loading the case.

```python
def build_dependencies(settings: Settings) -> Dependencies:
    if settings.runtime_mode is RuntimeMode.LIVE:
        credential = build_live_credential(settings)
        store = FabricSqlStore(build_fabric_engine(settings, credential))
        evidence = WorkIQEvidencePort(WorkIQClient(), build_obo_exchange(settings))
        orchestrator = FoundryOrchestrator.from_settings(settings, credential, evidence, store)
        power_bi_url = settings.power_bi_report_url
    else:
        store = SqliteStore.from_url(settings.database_url)
        evidence = SyntheticEvidencePort.from_rl001()
        orchestrator = LocalOrchestrator(evidence, store)
        power_bi_url = None
    return Dependencies(
        store=store,
        orchestrator=orchestrator,
        decisions=DecisionService(store.uow_factory),
        planning_worker=ActionPlanningWorker(store.uow_factory),
        playback=PlaybackService(store.uow_factory, RealClock()),
        power_bi_url=power_bi_url,
    )
```

- [ ] **Step 4: Forward Alex's assertion only to Work IQ OBO**

The route authenticates Alex, passes the original bearer assertion to the Work IQ adapter, and passes only the resulting typed Evidence Items to Foundry/deterministic services. Never send the bearer token to a model, prompt, log, Fabric payload, or Decision snapshot.

- [ ] **Step 5: Expose the live Power BI link and citation links**

The UI shows the configured Power BI report URL only when `/api/runtime.power_bi_available` is true. Evidence citations render as `target="_blank" rel="noreferrer"`; missing required citations disable approval and show `Required live citation missing`.

- [ ] **Step 6: Run the live Playwright journey**

`live-demo.spec.ts` uses a real Alex sign-in storage state created interactively before the run, creates a new `showcase` case, verifies Work IQ citation navigation, waits no more than 90 seconds for analysis, approves combined, waits no more than 15 seconds for five actions, starts playback, waits 65 seconds for observations, then opens Power BI and verifies the same Decision ID within 60 seconds.

Run:

```bash
npm --prefix apps/web run test:e2e -- live-demo.spec.ts
```

Expected: one complete live journey passes; browser traces redact authorization headers.

- [ ] **Step 7: Commit and hold the Milestone 6 reviewer gate**

```bash
git add apps/api/app apps/web tests/integration/test_live_case_contract.py docs/deployment/personal-tenant.md
git commit -m "feat(live): compose Microsoft demo journey"
```

Reviewer gate: inspect live citations, Foundry run traces, Fabric Decision/outbox rows, persona snapshot, actions, observations, and matching Power BI Decision ID.

---

### Task 18: Provision and Deploy the Personal-Tenant Runtime

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `infra/main.bicep`
- Create: `infra/main.bicepparam`
- Create: `infra/modules/registry.bicep`
- Create: `infra/modules/container-apps.bicep`
- Create: `infra/modules/key-vault.bicep`
- Create: `infra/modules/monitoring.bicep`
- Create: `infra/modules/foundry-access.bicep`
- Create: `azure.yaml`
- Create: `scripts/preflight_personal_tenant.sh`
- Create: `scripts/deploy_personal_tenant.sh`
- Create: `tests/deployment/test_infrastructure.py`
- Modify: `docs/deployment/personal-tenant.md`

**Interfaces:**
- Consumes: an Azure subscription, Fabric workspace/SQL Database, Foundry project, and Entra registrations in the same `willmacdonald.com` tenant.
- Produces: one HTTPS Container App serving FastAPI and the built React assets, system-managed identity, Key Vault references, Application Insights, and explicit demo-time scaling.

- [ ] **Step 1: Write failing static infrastructure tests**

Create `tests/deployment/test_infrastructure.py`:

```python
def test_container_app_has_managed_identity_https_and_demo_min_replica():
    template = build_bicep("infra/main.bicep")
    app = resource(template, "Microsoft.App/containerApps")
    assert app["identity"]["type"] == "SystemAssigned"
    assert app["properties"]["configuration"]["ingress"]["external"] is True
    assert app["properties"]["template"]["scale"]["minReplicas"] == "[parameters('minReplicas')]"


def test_no_secret_value_is_a_plain_environment_variable():
    template = build_bicep("infra/main.bicep")
    env = container_environment_variables(template)
    forbidden = {"CLIENT_SECRET", "FABRIC_CONNECTION_STRING", "ACCESS_TOKEN"}
    assert forbidden.isdisjoint(env)
```

- [ ] **Step 2: Run the test and verify infrastructure is absent**

Run:

```bash
.venv/bin/pytest tests/deployment/test_infrastructure.py -q
```

Expected: failures because `infra/main.bicep` is absent.

- [ ] **Step 3: Build one production image**

Use a Node build stage, Python runtime stage, ODBC Driver 18, nonroot user, and one `uvicorn` process. Copy `apps/web/dist` into `apps/api/static`; FastAPI serves it only after `/api` and `/health` routes. The image command is:

```dockerfile
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

- [ ] **Step 4: Provision cost-controlled Azure resources**

`infra/main.bicep` deploys ACR, Log Analytics/Application Insights, Key Vault, Container Apps environment, and one Container App. It does not create Fabric, Power BI, or Entra objects. `minReplicas` defaults to `0` for normal cost control and is set to `1` in the demo parameter file used for rehearsal/showcase windows. `maxReplicas=2` and the API remains idempotent under concurrency.

The Container App module exposes only HTTPS ingress and uses Key Vault references for confidential settings:

```bicep
param minReplicas int = 0
resource app 'Microsoft.App/containerApps@2025-02-02-preview' = {
  name: appName
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
      }
      secrets: [
        {
          name: 'entra-client-secret'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/entra-client-secret'
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'supply-response'
          image: imageName
          env: [
            { name: 'SUPPLY_RESPONSE_RUNTIME_MODE', value: 'live' }
            { name: 'SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET', secretRef: 'entra-client-secret' }
          ]
        }
      ]
      scale: { minReplicas: minReplicas, maxReplicas: 2 }
    }
  }
}
```

Grant the Container App identity Key Vault Secrets User, Fabric SQL database access, and Foundry project access through the documented resource-specific commands. Keep the Work IQ client credential in Key Vault because OBO requires a confidential API client; never expose it to the SPA.

- [ ] **Step 5: Add a same-tenant preflight**

`scripts/preflight_personal_tenant.sh` checks:

```bash
az account show --query tenantId -o tsv
az account show --query id -o tsv
az resource show --ids "$SUPPLY_RESPONSE_FOUNDRY_PROJECT_RESOURCE_ID" --query tenantId -o tsv
```

It also calls the Fabric API with the current credential, reads the workspace/SQL item, and compares the token's `tid` to the Azure tenant ID. It aborts on any mismatch and prints only redacted IDs (first/last four characters).

- [ ] **Step 6: Deploy and smoke-test**

Run:

```bash
az bicep build --file infra/main.bicep
./scripts/preflight_personal_tenant.sh
./scripts/deploy_personal_tenant.sh
curl -fsS "$SUPPLY_RESPONSE_APP_URL/health"
```

Expected: Bicep compiles, preflight proves one tenant, deployment succeeds, and `/health` reports live mode with healthy Fabric/Foundry configuration but does not perform a Work IQ call without Alex.

- [ ] **Step 7: Commit deployment assets**

```bash
git add Dockerfile .dockerignore infra azure.yaml scripts/preflight_personal_tenant.sh scripts/deploy_personal_tenant.sh tests/deployment docs/deployment/personal-tenant.md
git commit -m "feat(deploy): provision personal-tenant runtime"
```

---

### Task 19: Enforce Privacy, Parity, Failure, Timing, and Rehearsal Gates

**Files:**
- Create: `tests/safety/test_demo_corpus.py`
- Create: `tests/safety/test_no_external_actions.py`
- Create: `tests/safety/test_observation_labels.py`
- Create: `tests/parity/test_adapter_parity.py`
- Create: `tests/performance/test_demo_timing.py`
- Create: `tests/performance/test_scale_target.py`
- Create: `scripts/run_acceptance.sh`
- Create: `scripts/run_rehearsal.sh`
- Create: `docs/demo-script/README.md`
- Create: `docs/rehearsals/README.md`
- Create: `docs/decisions/2026-08-30-fabric-iq-go-no-go.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the complete fallback and live deployments.
- Produces: one auditable acceptance command plus timestamped, nonsecret rehearsal result files.

- [ ] **Step 1: Write exhaustive safety tests**

`test_demo_corpus.py` recursively walks Pydantic fixtures, JSON, rendered API snapshots, drafts, and observation text. It allows only `RL-` business identifiers and the three fictional persona display names; it rejects actual tenant UPNs, nonexample email domains, and configured object/tenant IDs.

`test_no_external_actions.py` imports every registered action adapter and asserts:

```python
assert adapter.capabilities <= {
    "create_unsent_draft", "append_internal_status", "simulate_transfer",
    "simulate_receipt", "simulate_resequence"
}
assert not adapter.capabilities & {
    "send_email", "send_teams_message", "modify_purchase_order",
    "create_purchase_order", "make_financial_commitment"
}
```

`test_observation_labels.py` renders API and UI fixtures and proves no Simulated Observation can serialize or display as `Actual`.

- [ ] **Step 2: Prove adapter parity**

`test_adapter_parity.py` normalizes synthetic/Work IQ Evidence Items and SQLite/Fabric domain records, excluding only source-specific IDs and wall-clock retrieval timestamps. Assert identical required fields, Authority Scope, runtime provenance, Analysis Version material hash inputs, and Decision/action/outcome contracts.

```python
def test_fallback_and_live_adapters_share_domain_shape(fallback_bundle, live_bundle):
    assert normalized_schema(fallback_bundle.evidence) == normalized_schema(live_bundle.evidence)
    assert normalized_schema(fallback_bundle.analysis) == normalized_schema(live_bundle.analysis)
    assert normalized_schema(fallback_bundle.decision) == normalized_schema(live_bundle.decision)
    assert normalized_schema(fallback_bundle.actions) == normalized_schema(live_bundle.actions)
    assert normalized_schema(fallback_bundle.observations) == normalized_schema(live_bundle.observations)
    assert fallback_bundle.runtime_mode is RuntimeMode.FALLBACK
    assert live_bundle.runtime_mode is RuntimeMode.LIVE
```

- [ ] **Step 3: Add timing probes around the real boundaries**

`test_demo_timing.py` records:

```python
assert analysis_elapsed <= 90.0
assert action_creation_elapsed <= 15.0
assert 45.0 <= playback_elapsed <= 60.0
assert power_bi_visibility_elapsed <= 60.0
assert operator_workflow_elapsed <= 300.0
```

The live timing marker is opt-in and uses a fresh `rehearsal` Case Instance. The fallback suite uses a real clock only for one timing test; all normal tests retain `ImmediateClock`.

- [ ] **Step 4: Add nonblocking scale measurement**

Generate 250 suppliers, 10,000 parts, 100,000 BOM relationships, multiple plants, 50,000 open customer-order lines, and twelve months of history. Record duration and memory to JSON but mark the test nonblocking; it fails only on correctness, not a performance threshold.

```python
@pytest.mark.scale_nonblocking
def test_demo_scale_remains_correct(tmp_path):
    started = time.perf_counter()
    dataset = generate_demo_scale_dataset(seed=42)
    result = analyze_scale_fixture(dataset)
    elapsed = time.perf_counter() - started
    assert result.calculation_version
    assert result.source_data_lineage
    (tmp_path / "scale-result.json").write_text(json.dumps({"seconds": elapsed, "counts": result.counts}))
```

- [ ] **Step 5: Create the exact acceptance command**

`scripts/run_acceptance.sh` runs:

```bash
.venv/bin/pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e -- fallback-demo.spec.ts fallback-failures.spec.ts
.venv/bin/pytest -q -m 'fabric_live or workiq_live or foundry_live or live_timing'
npm --prefix apps/web run test:e2e -- live-demo.spec.ts
```

It exits on the first failure and writes JUnit/Playwright artifacts under ignored `.artifacts/`.

- [ ] **Step 6: Document and run five rehearsals**

`docs/demo-script/README.md` defines:

- Core 3–5 minute path: create showcase case, analyze, inspect recommendation, approve, see five actions, start simulation, inspect outcomes.
- Full 7–10 minute narration: add architecture/provenance, citations, comparator trace, identity, Fabric, Foundry, and Power BI explanation.
- Timing start: operator selects `Create showcase case`.
- Timing end: web and Power BI show the ten Simulated Observations for the recorded Decision ID.

`scripts/run_rehearsal.sh` creates a new `rehearsal` Case Instance and writes case ID, Decision ID, each gate duration, pass/fail, and operator notes to `docs/rehearsals/YYYY-MM-DD-run-N.json`; it writes no tokens, UPNs, tenant IDs, or source text.

Run five consecutive live rehearsals. Every run must finish the core workflow within five minutes; failed runs are retained rather than overwritten.

- [ ] **Step 7: Record the Fabric IQ gate without expanding scope**

Create `docs/decisions/2026-08-30-fabric-iq-go-no-go.md` with this decision:

```markdown
# Fabric IQ Go/No-Go for the Supply Response Demo

**Decision:** No-Go for the core demonstration.

The frozen acceptance contract is satisfied by Fabric SQL Database, its analytics surface, and Power BI. Fabric IQ remains optional and cannot block release. Reconsider only after the complete live demo passes and a separate specification defines an ontology use case, capacity/cost, permissions, preview risk, test fixtures, and fallback behavior.
```

This decision adds no Fabric IQ adapter, package, infrastructure, or acceptance test. Foundry IQ remains a separate backlog item under the frozen specification.

- [ ] **Step 8: Run the final acceptance gate**

Run:

```bash
./scripts/run_acceptance.sh
git diff --check
git status --short
```

Expected: all unit, integration, browser, safety, parity, live, and timing gates pass; five rehearsal records pass; only intended source/rehearsal files are modified.

- [ ] **Step 9: Commit release hardening**

```bash
git add tests/safety tests/parity tests/performance scripts/run_acceptance.sh scripts/run_rehearsal.sh docs/demo-script docs/rehearsals docs/decisions/2026-08-30-fabric-iq-go-no-go.md README.md
git commit -m "test(release): enforce demo acceptance gates"
```

Final reviewer gate: check every frozen acceptance criterion against the coverage matrix below before using the words “complete demo contract.”

## Frozen Acceptance-Criteria Coverage Matrix

| Criterion | Primary implementation task | Proof |
|---:|---:|---|
| 1 | 15–17 | Live Work IQ Alpha signal, explicit extraction, navigable citation |
| 2 | 2, 12 | Deterministic affected-entity traversal over Fabric snapshot |
| 3 | 1–4 | Exact RL-001 values, versions, lineage, integrated tests |
| 4 | 15–17 | Jordan-authored Beta Quality evidence with citation/validity |
| 5 | 2–4 | Pending qualification blocks Beta and action creation |
| 6 | 2–4 | At least three Feasible Mitigations in RL-001 |
| 7 | 4 | Combined wins through the exact threshold trace |
| 8 | 3–4, 10 | Evidence, assumptions, constraints, approvals, comparators, trace |
| 9 | 6, 14, 17 | Alex Entra role plus separate Finance/Quality prerequisites |
| 10 | 5–6 | Durable append-only idempotent Decision lineage |
| 11 | 6–7, 9 | Atomic Decision/outbox and five actions within 15 seconds |
| 12 | 8–9 | Explicit idempotent playback and frozen observations |
| 13 | 10–11 | Web Decision/actions/predictions/Simulated variance |
| 14 | 12–13 | Same Fabric state in two Power BI pages with timestamps |
| 15 | 5, 9, 17 | Immutable case mode; explicit fallback; no fallback Power BI |
| 16 | 16–17 | Foundry-managed agents in Agent Framework workflow |
| 17 | 3, 9, 15 | Conflicts, stale/missing citations, material change block approval |
| 18 | 14, 19 | Fictional corpus and uncommitted deployment bindings |
| 19 | 17, 19 | 90-second analysis, five ≤5-minute runs, 7–10 minute narration |
| 20 | 4, 19 | Ten integrated evaluation cases through real analysis |

## Current Microsoft Documentation Anchors

Verify these pages again when executing their tasks because Work IQ and Agent Framework are evolving surfaces:

- Work IQ API overview and delegated-only authentication: <https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/api-overview>
- Work IQ A2A v1.0 endpoint, audience, scope, and citations: <https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/a2a/quickstart>
- Microsoft Foundry Agent Service integration for Agent Framework: <https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/agent-services/foundry>
- Agent Framework agents in workflows: <https://learn.microsoft.com/en-us/agent-framework/workflows/agents-in-workflows>
- Fabric SQL Database transactional/OLTP role: <https://learn.microsoft.com/en-us/fabric/database/sql/overview>
- Fabric SQL ODBC connectivity: <https://learn.microsoft.com/en-us/fabric/data-warehouse/how-to-connect>
- Power BI PBIP deployment with `fabric-cicd`: <https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-deploy-fabric-cicd>
- Power BI semantic-model storage modes: <https://learn.microsoft.com/en-us/fabric/data-warehouse/create-semantic-model>
- Azure Container Apps scaling and cost control: <https://learn.microsoft.com/en-us/azure/container-apps/scale-app>

## Execution Notes

- Use `superpowers:using-git-worktrees` before execution if this plan is implemented in an isolated worktree.
- Use a fresh reviewer gate after every task; do not batch commits across milestone boundaries.
- The live markers require deliberate operator setup and must skip with a precise missing-environment reason on ordinary local runs.
- Creating Entra registrations, role assignments, Fabric items, Foundry agents, Azure resources, and Power BI items changes external state. The implementation worker must obtain the user's approval immediately before each first deployment command even though this plan defines those commands.
- Do not implement Foundry IQ or optional Power BI pages while executing this plan.
