# Current Baseline and Acceptance-Criteria Traceability

Generated from `main` at commit `302a9ea` on 2026-08-30.

## Purpose

This document inventories the repository after the local-first GitHub integration and compares the current implementation with the acceptance criteria in `Supply-Response-Project-Brief.md`. It is an implementation baseline, not a claim that the complete product brief has been delivered.

## Source Provenance

- The implementation retains the local Codex base and its Git ancestry.
- The GitHub project brief and evaluation catalog were imported as requirements artifacts.
- Neither GitHub donor commit is an ancestor of current `main`.
- Core models, generator, calculation service, scenario service, API, and tests existed in the Codex base and were extended through reviewed local commits.
- No donor agent architecture, persistence layer, frontend application, Fabric runtime, Foundry runtime, or Work IQ integration was copied wholesale.

## Current Architecture Inventory

### Data and domain contracts

- `data/schemas/models.py` defines immutable Pydantic contracts for suppliers, parts, supplier-part relationships, purchase orders, inventory, BOMs, production orders, customers, customer orders, transport options, quality qualifications, disruptions, scenarios, ledger records, outcomes, calculation metadata, exposure results, and cases.
- Monetary values use `Decimal` in Python.
- `data/synthetic/generator.py` produces deterministic fictional `RL-` data and reserves explicit records for the RL-001 scenario.
- A demonstration-scale generator entry point exists for the target entity counts, but scale and performance are not tested.

### Deterministic services

- `services/exposure/calculator.py` implements usable inventory, time-phased projection, stockout, shortage, affected production/customer orders, revenue, margin, OTIF exposure, assumptions, calculation version, and source lineage.
- `services/scenarios/evaluator.py` emits six fixed response scenarios and applies partial-shipment, Supplier Beta qualification, response-cost, and approval-role rules.
- `services/policy/thresholds.py` implements finance-approval thresholds, date-conflict detection, and collaboration-evidence staleness checks.
- No LLM performs authoritative arithmetic.

### API and state

- `apps/api/app/main.py` implements case creation/retrieval, analysis, scenario retrieval, approval, rejection, and dashboard-summary routes.
- Cases and action-ledger records are stored in process-global memory and disappear on restart.
- Supplier Beta cannot be approved while its scenario is non-executable.
- Ledger records preserve server-owned scenario evidence, calculation version, source lineage, and caller-supplied approval evidence as separate fields.
- There is no authentication, authorization, durable persistence, lifecycle concurrency control, or external-system integration.

### Frontend

- `apps/web` is a React/TypeScript/Vite shell with a typed API client.
- The UI does not yet display the decision console, exposure, scenarios, approvals, dashboard, actions, or outcomes.
- The client implements only create-case and get-case calls.

### Agent and Microsoft integration seams

- `agents/` and `fabric/` contain placeholders only.
- Work IQ, Foundry agents, Microsoft Agent Framework, Fabric data services, Fabric IQ, Power BI, Teams, email, SharePoint, and ERP integrations are not implemented.

### Evaluation assets

- `evaluations/datasets/evaluation_cases.json` catalogs RL-EVAL-001 through RL-EVAL-010 and links each case to a pytest function.
- `evaluations/expected-results/rl-001.json` freezes the timestamp-independent deterministic RL-001 exposure result.
- The known-answer result covers inventory/exposure arithmetic and lineage; it does not cover scenario ranking, recommendations, approval workflow, dashboard behavior, UI behavior, or external retrieval.

## Verification Baseline

Fresh verification on current `main`:

- Python: 32 test cases passed.
- Frontend: 2 Vitest tests passed.
- TypeScript/Vite production build passed.
- One existing non-failing Starlette/httpx deprecation warning remains.

Test coverage is primarily unit and API-contract coverage. There are no browser end-to-end, external-integration, durable-persistence, load, demonstration-scale, or three-minute-demo reliability tests.

## Product Acceptance-Criteria Traceability

| ID | Acceptance criterion | Status | Current evidence | Gap or limitation |
|---|---|---|---|---|
| AC-01 | Supplier email is extracted accurately without inference. | Missing | Date-conflict and uncertainty helper functions exist. | No email ingestion, Work IQ retrieval, Signal Agent, structured extraction, source citation, or extraction test. |
| AC-02 | System identifies affected operational entities. | Satisfied and tested | Exposure service identifies affected production orders and customer-order lines; plant-aware API regression and exact RL-001 baseline exist. | Current entity traversal is limited to synthetic in-memory data. |
| AC-03 | Calculations are reproducible and tested. | Satisfied and tested | Seeded generator, `Decimal` arithmetic, calculation version, 32 Python cases, and exact RL-001 known-answer contract. | Demonstration-scale performance is not tested. |
| AC-04 | Work IQ retrieves the Supplier Beta Quality constraint. | Missing | Synthetic qualification fixture contains the constraint and evidence reference. | No Work IQ or collaboration-source retrieval; the constraint is seeded directly. |
| AC-05 | Supplier Beta is excluded from executable scenarios. | Satisfied and tested | Scenario 5 is blocked unless qualification status is approved; API rejects approval and writes no ledger record. | Qualification is fixture-backed rather than retrieved. |
| AC-06 | At least three feasible scenarios are compared. | Partially satisfied | Six scenarios are returned; multiple scenarios are executable in RL-001. | No ranking, scoring, comparative outcome calculation, or recommendation. Transfer and resequencing feasibility are not integrated into scenario construction. |
| AC-07 | Every recommendation shows evidence and assumptions. | Partially satisfied | Exposure results carry assumptions/lineage; Supplier Beta carries evidence and constraints. | No recommendation object exists, and most scenarios have no evidence or assumptions attached. |
| AC-08 | Alex can approve or reject the response. | Partially satisfied | Backend approve/reject routes are tested. | No user identity, UI interaction, authorization, or named Alex persona flow. |
| AC-09 | Approval writes a complete action-ledger record. | Satisfied and tested for the portable core | API tests verify decision, server scenario evidence, caller evidence, calculation version, and source lineage. | Records are volatile and “complete” is not formally defined against owners, due dates, drafted communications, or outcome tracking. |
| AC-10 | Dashboard reflects the disruption and selected action. | Partially satisfied | Dashboard summary API reports case counts, revenue risk, and OTIF risk. | It does not return the selected action; no dashboard UI or Power BI report exists. |
| AC-11 | Demo works without personal or customer data. | Implemented but insufficiently tested | Generator uses fictional `RL-` identifiers and no external data sources are connected. | Tests do not comprehensively scan every generated name, free-text field, fixture, or future communication artifact for non-fictional data. |
| AC-12 | End-to-end scenario completes reliably within three minutes. | Missing | Backend, frontend unit tests, and production build pass independently. | No runnable end-to-end demo test, browser workflow, timing assertion, or video rehearsal evidence. |

## Evaluation-Case Traceability

| Evaluation case | Status | Evidence and limitation |
|---|---|---|
| RL-EVAL-001 Confirmed recovery date | Satisfied and tested | Scenario builder removes the recovery uncertainty. |
| RL-EVAL-002 Unconfirmed recovery date | Satisfied and tested | Scenario builder preserves the uncertainty. |
| RL-EVAL-003 Partial shipment | Satisfied and tested | Partial quantity controls expedite feasibility. |
| RL-EVAL-004 Conflicting collaboration/operational dates | Implemented but insufficiently integrated | A pure policy helper is tested; no email/ERP ingestion path invokes it. |
| RL-EVAL-005 Alternate supplier approved | Satisfied and tested | Approved qualification makes Supplier Beta executable. |
| RL-EVAL-006 Alternate supplier not approved | Satisfied and tested | Supplier Beta is blocked with stable constraint/evidence metadata. |
| RL-EVAL-007 Inventory at another plant | Implemented but insufficiently integrated | Availability helper is tested; Scenario 3 is currently always executable and does not call it. |
| RL-EVAL-008 No feasible mitigation | Implemented but insufficiently integrated | Feasibility helper is tested using constructed scenarios; case analysis does not derive this state from operational inputs. |
| RL-EVAL-009 Premium freight threshold | Satisfied and tested | Expedite and combined scenarios carry cost and finance approval above the threshold. |
| RL-EVAL-010 Missing/stale collaboration evidence | Implemented but insufficiently integrated | Staleness helper is tested; there is no collaboration retrieval flow or scenario integration. |

## Contradictory or Ambiguous Requirements

1. **Product scope versus milestone scope:** The brief describes a Foundry/Work IQ/Fabric application, while the implemented milestone explicitly excludes all live Microsoft integrations. A revised specification must state which acceptance criteria belong to the portable core and which belong to later milestones.
2. **Scenario comparison:** “Compared” and “ranked” lack a defined scoring model, required output fields, tie-breaking behavior, and minimum evidence standard.
3. **Recommendation evidence:** The brief does not define whether evidence and assumptions belong to each scenario, only the recommended scenario, or the overall case analysis.
4. **Complete action ledger:** Required fields, durability, immutability, idempotency, actor identity, owners, due dates, and outcome linkage are not fully specified.
5. **Dashboard acceptance:** It is unclear whether the FastAPI summary, the web console, Power BI, or all three must reflect the selected action.
6. **SQLite versus in-memory state:** The brief recommends SQLite fixtures, while the integration milestone explicitly deferred SQLite. The required local persistence baseline needs a decision.
7. **Three-minute reliability:** Start/end points, environment, dataset scale, warm-up, success rate, and acceptable fallback behavior are undefined.
8. **Live integration priority:** Work IQ and Fabric are written as core architecture, while Fabric IQ is explicitly conditional. The minimum viable live-integration boundary still needs to be frozen.

## Baseline Conclusion

The repository is a tested portable decision-calculation core, not the complete Supply Response product described by the brief. Its strongest completed capabilities are deterministic exposure calculation, RL-001 fixture reproducibility, Supplier Beta safety enforcement, API decision recording, and executable unit-level evaluation contracts.

The next design phase should address only the eight unresolved requirement groups above. No implementation plan should be written until those decisions are incorporated into an approved revised specification.
