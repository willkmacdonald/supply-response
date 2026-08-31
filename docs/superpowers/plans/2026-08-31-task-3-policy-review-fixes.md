# Task 3 Policy Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all evidence, authority, authorization, clock, hashing, provenance, canonicalization, and deep-immutability findings from the Task 3 review.

**Architecture:** Keep authority and validation state in immutable domain contracts, with policy services deriving trusted results from typed source/case inputs. Build `AnalysisMaterial` only from canonical immutable projections of validated inputs, and make `create_analysis_version` the provenance boundary that rejects mixed cases or modes before hashing.

**Tech Stack:** Python 3.12, Pydantic 2 frozen models, pytest, SHA-256.

## Global Constraints

- Work directly on `main`; do not touch or stage root `uv.lock`.
- Stay within Task 3 evidence/approval/analysis policy; add no persistence, ranking, agent authority, or execution.
- Use explicit fictional `RL-` identifiers in tests.
- Evaluate business validity only against required `scenario_effective_time`; never substitute retrieval time.
- Preserve `services/policy/thresholds.py` unchanged.

---

### Task 1: Typed Evidence Authority, Conflict Provenance, and Clock Policy

**Files:**
- Modify: `data/domain/evidence.py`
- Modify: `services/policy/evidence.py`
- Test: `tests/analysis/test_evidence_and_approvals.py`

**Interfaces:**
- Consumes: typed `EvidenceItem`, `EvidenceConflict`, `ConflictResolution`, `RuntimeMode`, and explicit Scenario Effective Time.
- Produces: per-item `EvidenceItemValidation`, aggregate `EvidenceValidation`, and consumption-time-validated Conflict Resolutions.

- [ ] **Step 1: Write failing policy tests**

Add focused tests proving forged/empty/agent actor provenance cannot clear a conflict; source-system authority cannot be self-asserted; contextual evidence cannot satisfy required gates; future-effective and exact-expiry items block; missing explicit scenario time is rejected; source/retrieval order and retrieval-health policy are enforced; required live Work IQ items require timestamps, nonblank source/excerpt, and navigable HTTP(S) citation; contextual Work IQ items remain visibly non-authoritative.

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/analysis/test_evidence_and_approvals.py -q`

Expected: focused assertion/validation failures against the current permissive contracts.

- [ ] **Step 3: Implement immutable typed evidence policy**

Add enums/models for source system, authority field, freshness state, business-validity state, uncertainty state, retrieval health, actor provenance, and per-item validation. Make validation derive authority from source system and Evidence kind, require explicit Scenario Effective Time, use a half-open validity interval (`effective_at <= t < expires_at`), and require a versioned current-analysis retrieval-health input for operational evidence.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest tests/analysis/test_evidence_and_approvals.py -q`

Expected: all evidence authority/conflict/clock tests pass.

---

### Task 2: Target-Bound Standing Authorization

**Files:**
- Modify: `data/domain/decisions.py`
- Modify: `data/domain/analysis.py`
- Modify: `services/policy/approvals.py`
- Test: `tests/analysis/test_evidence_and_approvals.py`

**Interfaces:**
- Consumes: concrete `ResponseOption`, target `CaseInstance`, requested external side effects, total response cost, and Scenario Effective Time.
- Produces: option- and analysis-bound `ApprovalSatisfaction` containing an immutable snapshot of every authorization condition.

- [ ] **Step 1: Write failing boundary tests**

Add tests for typed option kind (with no ID inference), non-Demo-Corpus target rejection, all three forbidden effects, exact/elevated cost boundaries, pre-window time, disallowed option kind, and material-planner remaining unsatisfied when only Taylor is supplied.

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/analysis/test_evidence_and_approvals.py -q`

Expected: failures because the existing permit method lacks case/effect/typed-kind inputs.

- [ ] **Step 3: Implement target-bound policy**

Add typed `ResponseOptionKind` on `ResponseOption`, typed corpus/case scope, immutable `AuthorizationConditions`, and an `ApprovalTarget` carrying the concrete Case Instance, requested effects, total cost, and Scenario Effective Time. Evaluate Taylor only when all conditions match, and snapshot conditions into the satisfaction.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest tests/analysis/test_evidence_and_approvals.py -q`

Expected: all authorization boundary tests pass.

---

### Task 3: Canonical Deeply Immutable Analysis Material and Provenance Boundary

**Files:**
- Modify: `data/domain/analysis.py`
- Modify: `services/analysis/service.py`
- Test: `tests/analysis/test_evidence_and_approvals.py`
- Modify: `.superpowers/sdd/task-3-report.md` (ignored evidence report)

**Interfaces:**
- Consumes: one target `CaseInstance`, concrete `OperationalSnapshot`, validated evidence/conflicts/resolutions, response options, and Standing Authorizations.
- Produces: deeply immutable, canonical `AnalysisMaterial`, deterministic `analysis_material_hash`, and immutable `AnalysisVersion`.

- [ ] **Step 1: Write failing material/provenance tests**

Add tests proving mixed case/mode input rejection, unresolved conflict and validation state hash changes, full authorization-condition hash changes under reused IDs, input-order-independent hashes, duplicate stable-ID rejection, nested mutation rejection, and hash consistency after attempted mutation.

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/analysis/test_evidence_and_approvals.py -q`

Expected: failures for missing provenance checks, incomplete material, mutable nested values, and duplicate/order handling.

- [ ] **Step 3: Implement canonical immutable projections**

Replace nested dict/list material with frozen typed operational/evidence/conflict/validation/authorization projections or a canonical JSON scalar. Sort every unordered collection by its full stable key, reject duplicate stable IDs, include required scopes/conflicts/per-item validation/blocking state/authorization conditions in material, and require `create_analysis_version(case=..., snapshot=...)` provenance agreement.

- [ ] **Step 4: Verify Task 1–3 and repository gates**

Run:

```text
.venv/bin/pytest tests/analysis/test_evidence_and_approvals.py -q
.venv/bin/pytest tests/analysis/test_rl001_options.py tests/domain/test_rl001_contract.py -q
.venv/bin/pytest -q
git diff --check
```

Expected: every command exits 0; record exact results and any warnings in `.superpowers/sdd/task-3-report.md`.

- [ ] **Step 5: Commit**

Stage only Task 3 code/tests/report-plan files (never `uv.lock`) and commit with subject `fix(policy): enforce evidence and authorization boundaries`.
