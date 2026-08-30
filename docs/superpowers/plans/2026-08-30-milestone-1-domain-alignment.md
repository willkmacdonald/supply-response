# Milestone 1 Domain Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the GitHub brief and evaluation contracts, make disruptions plant-aware, attach stable qualification and approval metadata to scenarios, and commit an exact 2026 baseline result without importing the donor branch's persistence, UI, Fabric, or agent architecture.

**Architecture:** Local `main` contracts remain authoritative. Donor artifacts are copied or adapted into focused local files, with Pydantic models carrying immutable domain state and deterministic services remaining independent of FastAPI and persistence. Every behavior change starts with a failing test and ends with a focused commit.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, pytest, React, TypeScript, Vite, Vitest, JSON evaluation fixtures.

## Global Constraints

- Work from branch `codex/integrate-github-core`, whose base is local commit `83bf7f67ffcfd3eb64c1302f949d9a7cb6c2d329`.
- Read donor content from `github/main` at `27de461e16e5b7a2dd32181d6e9b7c114e91da87` and `github/copilot/scaffold-supply-response-core-app` at `2075e1fef9d4444cdb988222a711ba38ed9e9cba`.
- Python remains compatible with 3.12 and uses bounded dependency ranges.
- Currency and financial calculations use `Decimal`; JSON represents exact money as strings.
- All fictional identifiers and communications use the `RL-` prefix.
- No LLM performs authoritative arithmetic.
- Supplier Beta remains non-executable without an approved qualification.
- Do not merge unrelated histories or cherry-pick the donor implementation commit.
- Do not add SQLite, new UI screens, Fabric runtime integration, Work IQ, Foundry, or LLM adapters in this milestone.
- Keep Python tests, frontend tests, and the frontend production build passing after each task.

## File Map

- `Supply-Response-Project-Brief.md`: immutable project requirements copied from GitHub `main`.
- `evaluations/datasets/evaluation_cases.json`: ten stable evaluation-case descriptors linked to executable test nodes.
- `evaluations/expected-results/rl-001.json`: exact 2026 baseline result with string-encoded money.
- `tests/test_evaluation_assets.py`: integrity and known-answer verification for the JSON artifacts.
- `data/schemas/models.py`: canonical disruption, qualification, and scenario contracts.
- `data/synthetic/generator.py`: canonical 2026 disruption and qualification fixtures.
- `services/scenarios/evaluator.py`: stable constraint, evidence, and approval metadata.
- `apps/api/app/main.py`: plant-aware analysis orchestration.
- `apps/web/src/types.ts`: browser-visible disruption contract.
- `tests/test_api.py`: API-level plant propagation tests.
- `tests/test_evaluation_cases.py`: qualification and approval metadata tests.
- `docs/architecture/portable-core.md`: links and Milestone 1 architecture decisions.

---

### Task 1: Import the brief and executable evaluation-case catalog

**Files:**
- Create: `Supply-Response-Project-Brief.md`
- Create: `evaluations/datasets/evaluation_cases.json`
- Create: `tests/test_evaluation_assets.py`

**Interfaces:**
- Consumes: Git blob `github/main:Supply-Response-Project-Brief.md`.
- Produces: JSON object `{version: str, cases: list[EvaluationCase]}` where every case has `id`, `name`, `input`, `expected`, and `test`.

- [ ] **Step 1: Add the failing asset-integrity tests**

Create `tests/test_evaluation_assets.py` with:

```python
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "Supply-Response-Project-Brief.md"
EVALUATION_CASES = ROOT / "evaluations/datasets/evaluation_cases.json"


def test_project_brief_preserves_core_requirements():
    text = BRIEF.read_text(encoding="utf-8")
    assert "## Acceptance criteria" in text
    assert "## Evaluation cases" in text
    assert "Scenario 5 must be marked **not executable**" in text
    assert "The prototype must not create a real PO or financial commitment." in text


def test_evaluation_catalog_is_complete_and_linked_to_tests():
    payload = json.loads(EVALUATION_CASES.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert payload["version"] == "1.0.0"
    assert [case["id"] for case in cases] == [
        f"RL-EVAL-{index:03d}" for index in range(1, 11)
    ]

    required_keys = {"id", "name", "input", "expected", "test"}
    for case in cases:
        assert set(case) == required_keys
        test_path, test_name = case["test"].split("::", maxsplit=1)
        source = (ROOT / test_path).read_text(encoding="utf-8")
        assert f"def {test_name}(" in source, case["id"]
```

- [ ] **Step 2: Run the asset tests to verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_evaluation_assets.py -q
```

Expected: both tests fail with `FileNotFoundError` because the brief and catalog do not exist.

- [ ] **Step 3: Add the exact GitHub project brief**

Read the immutable source with:

```bash
git show 27de461e16e5b7a2dd32181d6e9b7c114e91da87:Supply-Response-Project-Brief.md
```

Use `apply_patch` to create `Supply-Response-Project-Brief.md` with that blob verbatim. Do not copy the donor branch's README in its place.

- [ ] **Step 4: Add the complete evaluation catalog**

Create `evaluations/datasets/evaluation_cases.json` with:

```json
{
  "version": "1.0.0",
  "cases": [
    {
      "id": "RL-EVAL-001",
      "name": "Confirmed supplier recovery date",
      "input": "The disruption has a confirmed recovery date.",
      "expected": "The expedite scenario removes the unconfirmed-recovery uncertainty.",
      "test": "tests/test_evaluation_cases.py::test_confirmed_recovery_date_removes_that_uncertainty"
    },
    {
      "id": "RL-EVAL-002",
      "name": "Unconfirmed recovery date",
      "input": "The remaining supplier recovery date is missing.",
      "expected": "The uncertainty is preserved rather than inferred.",
      "test": "tests/test_evaluation_cases.py::test_unconfirmed_recovery_date_is_preserved_as_uncertainty"
    },
    {
      "id": "RL-EVAL-003",
      "name": "Partial shipment",
      "input": "Supplier Alpha offers a positive partial shipment.",
      "expected": "The expedite scenario is executable only when the partial quantity is positive.",
      "test": "tests/test_evaluation_cases.py::test_partial_shipment_controls_expedite_feasibility"
    },
    {
      "id": "RL-EVAL-004",
      "name": "Conflicting collaboration and operational dates",
      "input": "The communicated date differs from the operational date.",
      "expected": "The conflict is surfaced explicitly.",
      "test": "tests/test_remaining_evaluation_cases.py::test_conflicting_email_and_operational_dates_are_detected"
    },
    {
      "id": "RL-EVAL-005",
      "name": "Alternate supplier approved",
      "input": "Supplier Beta has an approved qualification for the part.",
      "expected": "The alternate-source scenario is executable.",
      "test": "tests/test_evaluation_cases.py::test_alternate_supplier_approved_is_executable"
    },
    {
      "id": "RL-EVAL-006",
      "name": "Alternate supplier not approved",
      "input": "Supplier Beta is not approved for the part.",
      "expected": "The alternate-source scenario is blocked with qualification evidence.",
      "test": "tests/test_evaluation_cases.py::test_alternate_supplier_not_approved_is_not_executable"
    },
    {
      "id": "RL-EVAL-007",
      "name": "Inventory available at another plant",
      "input": "Another plant has sufficient usable inventory.",
      "expected": "The transfer feasibility check returns true.",
      "test": "tests/test_remaining_evaluation_cases.py::test_inventory_available_at_another_plant"
    },
    {
      "id": "RL-EVAL-008",
      "name": "No feasible mitigation",
      "input": "Only backlog is executable.",
      "expected": "The scenario set reports no feasible mitigation.",
      "test": "tests/test_remaining_evaluation_cases.py::test_no_feasible_mitigation"
    },
    {
      "id": "RL-EVAL-009",
      "name": "Premium freight above approval threshold",
      "input": "Premium freight exceeds the configured finance threshold.",
      "expected": "Finance approval is required.",
      "test": "tests/test_evaluation_cases.py::test_premium_freight_above_threshold_requires_approval"
    },
    {
      "id": "RL-EVAL-010",
      "name": "Missing or stale collaboration evidence",
      "input": "Qualification evidence is missing or older than the accepted age.",
      "expected": "The evidence is classified as stale.",
      "test": "tests/test_remaining_evaluation_cases.py::test_missing_or_stale_collaboration_evidence"
    }
  ]
}
```

- [ ] **Step 5: Run the asset tests and full Python suite**

Run:

```bash
.venv/bin/pytest tests/test_evaluation_assets.py -q
.venv/bin/pytest -q
```

Expected: 20 tests pass, with the existing Starlette deprecation warning permitted.

- [ ] **Step 6: Commit the imported requirements and catalog**

```bash
git add Supply-Response-Project-Brief.md evaluations/datasets/evaluation_cases.json tests/test_evaluation_assets.py
git commit -m "docs: import project brief and evaluation catalog"
```

---

### Task 2: Make disruption analysis plant-aware

**Files:**
- Modify: `data/schemas/models.py:118-129`
- Modify: `data/synthetic/generator.py:106-112`
- Modify: `apps/api/app/main.py:53-60`
- Modify: `apps/web/src/types.ts:3-14`
- Modify: `tests/test_evaluation_cases.py:9-12`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `Disruption.plant_id: str` from API and synthetic fixtures.
- Produces: `calculate_exposure(..., plant_id=case.disruption.plant_id)` with no hardcoded plant fallback.

- [ ] **Step 1: Add failing schema and API tests**

In the `disruption()` fixture in `tests/test_evaluation_cases.py`, add:

```python
plant_id="RL-PLANT-CHI",
```

In `tests/test_api.py`, add:

```python
def test_analysis_uses_the_disruption_plant():
    disruption = DATASET.disruptions[0].model_copy(
        update={"plant_id": "RL-PLANT-DAL"}
    )
    response = client.post(
        "/api/cases",
        json={"disruption": disruption.model_dump(mode="json")},
    )
    case_id = response.json()["case_id"]

    analysis = client.post(f"/api/cases/{case_id}/analyze")

    assert response.status_code == 201
    assert analysis.status_code == 200
    assert analysis.json()["exposure"]["usable_inventory"] == 1500
```

- [ ] **Step 2: Run targeted tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_api.py::test_analysis_uses_the_disruption_plant tests/test_evaluation_cases.py -q
```

Expected: model construction or response validation fails because `Disruption` has no `plant_id`, or the API returns Chicago's usable inventory rather than `1500`.

- [ ] **Step 3: Add the required domain field and canonical fixture value**

In `data/schemas/models.py`, define `Disruption` as:

```python
class Disruption(FrozenModel):
    disruption_id: str
    supplier_id: str
    po_line_id: str
    part_id: str
    plant_id: str
    original_quantity: int = Field(gt=0)
    original_due_date: date
    partial_quantity: int = Field(ge=0)
    partial_due_date: date | None = None
    recovery_date: date | None = None
    source_ref: str
```

In `data/synthetic/generator.py`, replace the canonical disruption construction with the same values plus:

```python
plant_id="RL-PLANT-CHI"
```

- [ ] **Step 4: Remove the hardcoded API plant and update the frontend contract**

In `apps/api/app/main.py`, change the exposure call to:

```python
exposure = calculate_exposure(
    scenario_id="RL-SCENARIO-BASELINE",
    part_id=d.part_id,
    plant_id=d.plant_id,
    inventory_positions=DATASET.inventory_positions,
    receipts=receipts,
    transfers=[],
    bom_components=DATASET.bom_components,
    production_orders=DATASET.production_orders,
    customer_orders=DATASET.customer_orders,
    assumptions=("Only confirmed receipts are included",),
    remaining_uncertainty=("Remaining supplier recovery date is unconfirmed",)
    if d.recovery_date is None
    else (),
)
```

In `apps/web/src/types.ts`, add the required field after `part_id`:

```typescript
plant_id: string;
```

- [ ] **Step 5: Run backend and frontend contract verification**

Run:

```bash
.venv/bin/pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
```

Expected: 21 Python tests pass, one frontend test passes, and Vite completes a production build.

- [ ] **Step 6: Commit plant-aware analysis**

```bash
git add data/schemas/models.py data/synthetic/generator.py apps/api/app/main.py apps/web/src/types.ts tests/test_evaluation_cases.py tests/test_api.py
git commit -m "feat: make disruption analysis plant-aware"
```

---

### Task 3: Add qualification evidence and scenario approval metadata

**Files:**
- Modify: `data/schemas/models.py:109-139`
- Modify: `data/synthetic/generator.py:106-110`
- Modify: `services/scenarios/evaluator.py:1-20`
- Modify: `tests/test_evaluation_cases.py`

**Interfaces:**
- Consumes: `QualityQualification.evidence_ref`, audit state, first-article state, and expected decision date.
- Produces: immutable `ResponseScenario.constraint_codes`, `evidence_refs`, and `required_approver_roles` tuples.

- [ ] **Step 1: Add failing qualification and approval assertions**

Extend `tests/test_evaluation_cases.py` with:

```python
def test_blocked_alternate_supplier_carries_stable_evidence_metadata():
    beta = build_initial_scenarios(
        disruption(), [qualification(QualificationStatus.NOT_APPROVED)]
    )[4]
    assert beta.constraint_codes == ("QUALITY_NOT_APPROVED",)
    assert beta.evidence_refs == ("RL-QUALITY-001",)
    assert beta.required_approver_roles == ("material_planner",)


def test_expedite_above_threshold_names_finance_approver():
    expedite = build_initial_scenarios(
        disruption(), [qualification(QualificationStatus.NOT_APPROVED)]
    )[1]
    assert expedite.response_cost == Decimal("22500.00")
    assert expedite.required_approver_roles == (
        "material_planner",
        "finance_approver",
    )
```

- [ ] **Step 2: Run the new tests to verify attribute failure**

Run:

```bash
.venv/bin/pytest tests/test_evaluation_cases.py::test_blocked_alternate_supplier_carries_stable_evidence_metadata tests/test_evaluation_cases.py::test_expedite_above_threshold_names_finance_approver -q
```

Expected: both tests fail because the metadata fields do not exist.

- [ ] **Step 3: Extend the canonical immutable models**

Change `QualityQualification` in `data/schemas/models.py` to:

```python
class QualityQualification(FrozenModel):
    qualification_id: str
    supplier_id: str
    part_id: str
    status: QualificationStatus
    effective_date: date | None = None
    evidence_ref: str
    audit_complete: bool | None = None
    first_article_complete: bool | None = None
    expected_decision_date: date | None = None
```

Add these fields to `ResponseScenario` after `constraint_violations`:

```python
constraint_codes: tuple[str, ...] = ()
evidence_refs: tuple[str, ...] = ()
required_approver_roles: tuple[str, ...] = ()
```

- [ ] **Step 4: Enrich canonical qualifications**

In `data/synthetic/generator.py`, construct Alpha with:

```python
audit_complete=True,
first_article_complete=True,
expected_decision_date=None,
```

Construct Beta with:

```python
audit_complete=False,
first_article_complete=False,
expected_decision_date=date(2026, 9, 15),
```

- [ ] **Step 5: Generate stable scenario metadata**

In `services/scenarios/evaluator.py`, import:

```python
from services.policy.thresholds import requires_finance_approval
```

Add above `build_initial_scenarios`:

```python
def _approval_roles(response_cost: Decimal = Decimal("0")) -> tuple[str, ...]:
    roles = ["material_planner"]
    if requires_finance_approval(response_cost):
        roles.append("finance_approver")
    return tuple(roles)
```

Inside `build_initial_scenarios`, calculate:

```python
expedite_cost = Decimal(disruption.partial_quantity) * Decimal("7.50")
beta_codes = () if beta_ok else ("QUALITY_NOT_APPROVED",)
beta_evidence = (beta.evidence_ref,) if beta else ()
```

Pass `_approval_roles()` to scenarios 1, 3, 4, 5, and 6. Pass `_approval_roles(expedite_cost)` and `response_cost=expedite_cost` to scenario 2. Pass `constraint_codes=beta_codes` and `evidence_refs=beta_evidence` to scenario 5.

- [ ] **Step 6: Run scenario and API regression tests**

Run:

```bash
.venv/bin/pytest tests/test_evaluation_cases.py tests/test_api.py -q
.venv/bin/pytest -q
```

Expected: 23 Python tests pass and blocked-scenario approval still returns HTTP 409 without an action-ledger entry.

- [ ] **Step 7: Commit evidence and approval metadata**

```bash
git add data/schemas/models.py data/synthetic/generator.py services/scenarios/evaluator.py tests/test_evaluation_cases.py
git commit -m "feat: add scenario evidence and approval metadata"
```

---

### Task 4: Commit the exact 2026 RL-001 baseline

**Files:**
- Create: `evaluations/expected-results/rl-001.json`
- Modify: `tests/test_evaluation_assets.py`

**Interfaces:**
- Consumes: canonical seed-42 dataset, canonical RL-001 disruption, and `calculate_exposure`.
- Produces: timestamp-independent JSON baseline with exact money strings.

- [ ] **Step 1: Add the failing known-answer test and helper**

Append to `tests/test_evaluation_assets.py`:

```python
from data.schemas.models import TimedQuantity
from data.synthetic.generator import generate_dataset
from services.exposure.calculator import calculate_exposure


EXPECTED_RL_001 = ROOT / "evaluations/expected-results/rl-001.json"


def _baseline_result() -> dict[str, object]:
    dataset = generate_dataset(seed=42)
    disruption = dataset.disruptions[0]
    receipts = [
        TimedQuantity(
            date=disruption.partial_due_date,
            quantity=disruption.partial_quantity,
            source_id=disruption.source_ref,
        )
    ]
    exposure = calculate_exposure(
        scenario_id="RL-SCENARIO-BASELINE",
        part_id=disruption.part_id,
        plant_id=disruption.plant_id,
        inventory_positions=dataset.inventory_positions,
        receipts=receipts,
        transfers=[],
        bom_components=dataset.bom_components,
        production_orders=dataset.production_orders,
        customer_orders=dataset.customer_orders,
        assumptions=("Only confirmed receipts are included",),
        remaining_uncertainty=("Remaining supplier recovery date is unconfirmed",),
    )
    return {
        "disruption_id": disruption.disruption_id,
        "plant_id": disruption.plant_id,
        "calculation_version": exposure.metadata.calculation_version,
        "usable_inventory": exposure.usable_inventory,
        "projected_balances": [
            {
                "date": point.date.isoformat(),
                "balance": point.projected_balance,
            }
            for point in exposure.projected_inventory
        ],
        "first_stockout_date": exposure.first_stockout_date.isoformat()
        if exposure.first_stockout_date
        else None,
        "maximum_shortage_quantity": exposure.maximum_shortage_quantity,
        "affected_production_order_ids": list(
            exposure.affected_production_order_ids
        ),
        "affected_customer_order_line_ids": list(
            exposure.affected_customer_order_line_ids
        ),
        "revenue_at_risk": str(exposure.revenue_at_risk),
        "margin_at_risk": str(exposure.margin_at_risk),
        "otif_lines_at_risk": exposure.otif_lines_at_risk,
        "response_cost": str(exposure.response_cost),
        "revenue_protected": str(exposure.revenue_protected),
        "remaining_uncertainty": list(exposure.remaining_uncertainty),
        "source_data_lineage": list(exposure.metadata.source_data_lineage),
    }


def test_rl_001_matches_exact_2026_baseline():
    expected = json.loads(EXPECTED_RL_001.read_text(encoding="utf-8"))
    assert _baseline_result() == expected
```

- [ ] **Step 2: Run the known-answer test to verify file failure**

Run:

```bash
.venv/bin/pytest tests/test_evaluation_assets.py::test_rl_001_matches_exact_2026_baseline -q
```

Expected: `FileNotFoundError` for `evaluations/expected-results/rl-001.json`.

- [ ] **Step 3: Add the exact baseline fixture**

Create `evaluations/expected-results/rl-001.json` with:

```json
{
  "disruption_id": "RL-DISRUPTION-001",
  "plant_id": "RL-PLANT-CHI",
  "calculation_version": "exposure-v1",
  "usable_inventory": 2107,
  "projected_balances": [
    {"date": "2026-09-05", "balance": 107},
    {"date": "2026-09-06", "balance": 3107},
    {"date": "2026-09-08", "balance": 707},
    {"date": "2026-09-23", "balance": -3429}
  ],
  "first_stockout_date": "2026-09-23",
  "maximum_shortage_quantity": 3429,
  "affected_production_order_ids": ["RL-MO-000072"],
  "affected_customer_order_line_ids": [
    "RL-CO-0000072",
    "RL-CO-0000197",
    "RL-CO-0000322",
    "RL-CO-0000447"
  ],
  "revenue_at_risk": "89691",
  "margin_at_risk": "52290",
  "otif_lines_at_risk": 4,
  "response_cost": "0",
  "revenue_protected": "0",
  "remaining_uncertainty": [
    "Remaining supplier recovery date is unconfirmed"
  ],
  "source_data_lineage": [
    "RL-001",
    "RL-INV-000247",
    "RL-INV-DEMO-CHI",
    "RL-MO-000072",
    "RL-MO-DEMO-1",
    "RL-MO-DEMO-2"
  ]
}
```

- [ ] **Step 4: Run exact-result and full regression tests**

Run:

```bash
.venv/bin/pytest tests/test_evaluation_assets.py -q
.venv/bin/pytest -q
```

Expected: 24 Python tests pass. The timestamp is intentionally excluded from the committed known-answer contract.

- [ ] **Step 5: Commit the known-answer contract**

```bash
git add evaluations/expected-results/rl-001.json tests/test_evaluation_assets.py
git commit -m "test: add exact RL-001 baseline"
```

---

### Task 5: Document Milestone 1 and run all gates

**Files:**
- Modify: `docs/architecture/portable-core.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the imported brief, evaluation catalog, and exact baseline.
- Produces: discoverable links and an accurate description of plant-aware analysis and scenario metadata.

- [ ] **Step 1: Update architecture documentation**

Append to `docs/architecture/portable-core.md`:

```markdown

## Milestone 1 domain alignment

- Disruptions carry the affected plant explicitly; analysis has no hardcoded plant fallback.
- Scenario results carry stable constraint codes, evidence references, and required approver roles.
- The ten evaluation cases are cataloged in `evaluations/datasets/evaluation_cases.json` and linked to executable pytest nodes.
- The timestamp-independent 2026 RL-001 result is guarded by `evaluations/expected-results/rl-001.json`.
- Financial values remain `Decimal` in Python and exact strings in committed JSON results.
- The baseline freezes the current seed-42 behavior; any later fixture normalization must update the known-answer contract explicitly.

The complete product requirements are preserved in `Supply-Response-Project-Brief.md`.
```

- [ ] **Step 2: Add concise README links**

After the repository-layout section in `README.md`, add:

```markdown
## Project references

- [Project brief](Supply-Response-Project-Brief.md)
- [Portable-core architecture](docs/architecture/portable-core.md)
- [Evaluation catalog](evaluations/datasets/evaluation_cases.json)
- [RL-001 known-answer result](evaluations/expected-results/rl-001.json)
```

- [ ] **Step 3: Run the complete verification suite**

Run:

```bash
.venv/bin/pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
git diff --check
git status --short
```

Expected:

- 24 Python tests pass with only the known Starlette deprecation warning.
- One Vitest test passes.
- TypeScript and Vite production build succeeds.
- `git diff --check` exits zero.
- `git status --short` lists only the two intended documentation modifications before commit.

- [ ] **Step 4: Review milestone scope**

Run:

```bash
git diff --stat 1803fa5..HEAD
git diff --name-status 1803fa5..HEAD
```

Expected: changes are limited to the files named in this plan; there are no SQLite, SQLAlchemy, new UI component, Fabric runtime, Work IQ, Foundry, or LLM implementation files.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md docs/architecture/portable-core.md
git commit -m "docs: describe milestone one domain alignment"
```

- [ ] **Step 6: Verify the committed milestone**

Run:

```bash
.venv/bin/pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
git diff --check HEAD
git status --short --branch
```

Expected: all tests and build pass, diff check exits zero, and the branch is clean.
