# Local-First GitHub Integration Design

**Date:** 2026-08-30
**Status:** Proposed for implementation
**Base:** local `main` at `83bf7f67ffcfd3eb64c1302f949d9a7cb6c2d329`
**Donor:** GitHub `copilot/scaffold-supply-response-core-app` at `2075e1fef9d4444cdb988222a711ba38ed9e9cba`
**Brief:** GitHub `main` at `27de461e16e5b7a2dd32181d6e9b7c114e91da87`

## Goal

Extend the verified local portable core with the strongest parts of the GitHub implementation while preserving deterministic calculations, exact financial types, simple module boundaries, and a working build after every milestone.

## Context

The local and GitHub repositories have unrelated Git histories. No content was overwritten. The local checkout's configured `origin` is a local bundle containing one `main` branch; `origin/HEAD` is a symbolic pointer to `origin/main`, not a second branch. The GitHub repository contains a brief-only `main` branch and an open Copilot implementation branch.

Clean-room verification established the following baseline:

| Implementation | Python tests | Frontend test | Frontend build | npm audit during install |
|---|---:|---:|---:|---:|
| Local `main` | 18 passed | 1 passed | passed | 0 vulnerabilities |
| GitHub donor | 84 passed | 1 passed | failed | 5 vulnerabilities |

The donor build fails because its Vite configuration references Node globals without Node types, mixes Vitest configuration into a Vite-only type, and references a TypeScript project that disables emit. The donor also represents financial values with `float`, uses 2025 fixture dates, and contains optional Azure OpenAI code without declaring the `openai` package. Work IQ retrieval remains a deterministic fallback.

Pre-implementation review found that the local generator created `RL-MAT-10247` twice and `RL-PO-000001` twice. The original seed-42 shortage depended on random rows sharing the canonical demo part. Milestone 1 therefore normalizes those identifiers and makes every RL-001 inventory, BOM, production-order, and customer-order input explicit before committing a known-answer result.

## Approaches considered

### 1. Merge the unrelated histories

Rejected. `git merge --allow-unrelated-histories` would turn independently authored trees into a large conflict-resolution exercise, obscure which contracts were intentionally selected, and import known build and dependency problems.

### 2. Replace local code with the GitHub donor

Rejected. This would discard the smaller verified architecture, regress exact currency handling to floating point, and make the broken frontend and unfinished agent integrations the new baseline.

### 3. Selectively port donor capabilities onto local contracts

Selected. Each capability is introduced behind a focused interface, begins with a failing test or known-answer fixture, and produces a working commit. Donor code is treated as reference material rather than an authoritative patch.

## Global constraints

- Python remains compatible with 3.12 and uses bounded dependency ranges.
- Authoritative currency and financial calculations use `Decimal`, never binary floating point.
- All fictional identifiers and communications retain the `RL-` prefix.
- No LLM performs authoritative arithmetic.
- The browser communicates only with the backend API and receives no Fabric, Foundry, or Work IQ credentials.
- Supplier Beta remains non-executable until a positive qualification record exists.
- Approval writes evidence and calculation lineage but never creates a real purchase order or financial commitment.
- Each milestone must leave Python tests, frontend tests, and the frontend production build passing.
- Dependency lockfiles are committed before deployable application code is considered reproducible.

## Repository and history strategy

Implementation occurs on `codex/integrate-github-core`, created from local `main`. Local `main`, GitHub `main`, and the GitHub donor branch remain unchanged. The GitHub branches are read through namespaced `github/*` refs.

The donor's large implementation commit will not be cherry-picked. Files and behavior are ported through ordinary reviewed commits so each change has local ancestry and a clear test boundary.

## Milestone decomposition

### Milestone 1: Brief, evaluation contracts, and domain alignment

This is the first implementation plan and the only milestone authorized by initial execution.

Deliverables:

- Preserve the GitHub project brief as project documentation.
- Add executable evaluation-case metadata and a local 2026 known-answer result.
- Guarantee unique synthetic part and purchase-order identifiers.
- Isolate the canonical RL-001 calculation from randomly generated BOM and customer-order relationships.
- Add `plant_id` to the disruption contract so analysis no longer hardcodes Chicago.
- Add richer qualification evidence and scenario approval metadata only where required by the evaluation cases.
- Preserve existing model names where possible and add compatibility through explicit fields rather than parallel model hierarchies.
- Update generator fixtures and API analysis to use the disruption's plant.
- Add tests proving plant-aware analysis, exact currency serialization, qualification blocking, and evaluation-file integrity.

Milestone 1 does not add SQLite, new UI screens, Fabric integrations, or LLM agents.

### Milestone 2: Exposure and policy enrichment

Deliverables:

- Separate confirmed receipts from unconfirmed recovery information.
- Add approved transfer inputs and transfer-availability checks.
- Represent policy decisions with stable codes, evidence references, human-readable messages, and approver roles.
- Calculate response cost, remaining exposure, revenue protected, and deterministic scenario scores.
- Cover all ten evaluation cases with executable tests.

Calculation services remain independent of FastAPI and persistence.

### Milestone 3: Persistence and API boundaries

Deliverables:

- Introduce repository protocols for cases, evaluated scenarios, and action-ledger entries.
- Retain an in-memory repository for unit tests.
- Add a SQLite repository as the local runtime implementation.
- Split API routing from application services without duplicating domain contracts.
- Add case listing, CORS configuration, idempotent analysis persistence, and guarded state transitions.

SQLAlchemy models are persistence details and do not replace Pydantic domain models.

### Milestone 4: Decision console frontend

Deliverables:

- Add case header, exposure, evidence, scenario comparison, and approval components.
- Expand the typed API client to cover analysis, scenarios, decisions, narratives, and dashboard summary.
- Use the Vite proxy for local `/api` calls.
- Resolve the donor's TypeScript configuration errors without importing vulnerable dependency versions.
- Add component tests for blocked scenarios, recommendation selection, loading, and API errors.

### Milestone 5: Fabric design artifacts

Deliverables:

- Align SQL schemas with finalized domain field names and exact numeric types.
- Validate calculation SQL against Python known-answer results.
- Align semantic-model and ontology entity identifiers with the same contracts.
- Retain Power BI page definitions as deployable design documentation until a Fabric workspace is explicitly authorized.

No live Fabric deployment occurs as part of repository integration.

### Milestone 6: Agent orchestration

Deliverables:

- Keep deterministic signal, context, and narrative fallbacks for local operation.
- Define agent inputs and outputs as structured domain contracts.
- Implement hosted-agent integration with Microsoft Agent Framework and Foundry rather than direct ad hoc OpenAI calls.
- Make Work IQ and Foundry optional adapters with explicit unavailable/error states.
- Preserve source citations, facts, assumptions, unknowns, and approval boundaries.

Agent failure must never alter deterministic calculation results or silently present an LLM result as authoritative.

### Milestone 7: Reproducibility and release hardening

Deliverables:

- Commit Python and npm lockfiles.
- Add CI for Python tests, frontend tests, TypeScript build, dependency auditing, and generated-artifact drift.
- Run the complete three-minute demo from a clean checkout.
- Record accepted differences between Python, SQL, and dashboard calculations.

## Milestone 1 component design

### Documentation sources

`Supply-Response-Project-Brief.md` is imported from GitHub `main` without treating donor implementation details as requirements. The existing `README.md` remains the local setup authority. Architecture documentation links the brief, local contracts, and milestone roadmap.

### Domain contracts

`Disruption` gains a required `plant_id`. Existing synthetic fixture construction is updated in the same commit so no invalid transitional state exists. Quality qualification keeps its current exact status enum and gains optional evidence fields only when needed to express the brief's audit and first-article constraints.

Scenario approval metadata is represented as immutable values on `ResponseScenario`: stable constraint codes, evidence references, and required approver roles. Existing `constraint_violations` remains the human-readable summary for API compatibility.

### Evaluation contracts

`evaluations/datasets/evaluation_cases.json` lists the ten brief cases with stable IDs, input descriptions, expected behavior, and the test node that enforces each behavior. A JSON integrity test verifies unique IDs, required keys, referenced test existence, and the `RL-` naming rule.

The first known-answer file records the normalized 2026 RL-001 baseline. It serializes decimal values as strings to preserve exactness. The baseline uses explicit demo rows and cannot depend on random rows sharing a demo business key. Later milestones expand this file with scenario rankings rather than changing existing baseline meanings silently.

### Data flow

The API receives or locates a disruption containing `part_id` and `plant_id`. Analysis passes both identifiers into the exposure service. The exposure service filters inventory and production demand by those identifiers, returns immutable exposure metadata, and the API stores the result on the mutable case aggregate.

Qualification evidence flows from synthetic data into scenario evaluation. A missing or non-approved Supplier Beta qualification produces a stable blocking code, human-readable violation, and evidence reference. Approval checks the executable flag before writing any action.

### Error handling

- Invalid JSON evaluation fixtures fail tests with the file and case ID identified.
- A disruption without a plant fails Pydantic validation rather than falling back to a hardcoded plant.
- Unknown cases continue to return HTTP 404.
- Approval of an unknown scenario continues to return HTTP 400.
- Approval of a blocked scenario continues to return HTTP 409 without writing an action-ledger entry.

### Testing strategy

Milestone 1 uses test-driven changes:

1. Add failing generator tests for unique IDs and isolated demo relationships.
2. Add failing schema and API tests for plant-aware disruptions.
3. Add failing scenario tests for stable qualification evidence metadata.
4. Add failing JSON integrity tests and the 2026 known-answer fixture.
5. Implement the smallest contract and generator changes that satisfy them.
6. Run all Python tests.
7. Run frontend tests and production build to detect contract drift.
8. Verify `git diff --check` and review the milestone diff before commit.

## Explicit exclusions

- No merge or rebase of unrelated histories.
- No wholesale copying of the donor's domain models, calculator, API service module, or synthetic generator.
- No use of `float` for currency.
- No live Azure, Fabric, Foundry, Work IQ, email, Teams, supplier, ERP, or customer connection.
- No direct OpenAI SDK integration as the final agent architecture.
- No real procurement or financial action.

## Success criteria

The integration succeeds when local ancestry remains intact, each donor capability has an explicit local contract and test, all verification gates pass after every milestone, and the resulting application satisfies the project brief without inheriting the donor branch's known build, dependency, precision, or integration weaknesses.
