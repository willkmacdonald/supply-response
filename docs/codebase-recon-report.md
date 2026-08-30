# Supply Response Codebase Recon Report

Generated: 2026-08-30

> **Historical snapshot:** This report describes base commit `83bf7f6` before the
> local-first GitHub integration work. Statements below are retained as the original
> reconnaissance record and must not be read as the current branch state.

## Current branch status

The integration branch now includes the project brief and evaluation catalog,
normalized RL-001 synthetic fixtures, plant-aware analysis, stable scenario evidence
and approval metadata, and an executable RL-001 known-answer fixture. The README and
current test results are authoritative for the branch; the remainder of this report
is historical context only.

## Project summary

Supply Response is an early portable prototype for evaluating supply disruptions and response scenarios without external Microsoft, Azure, Fabric, Foundry, Work IQ, or Fabric IQ integrations.

The main workflow is:

```text
Disruption -> Case -> Exposure analysis -> Response scenarios -> Approval or rejection -> Action ledger
```

The central design decision is to keep authoritative inventory, financial, and constraint calculations in deterministic application services. Future agents can orchestrate or explain those results without owning the underlying arithmetic.

## Architecture map

- `data/schemas/models.py`: Pydantic domain contracts for suppliers, parts, inventory, orders, disruptions, response scenarios, exposure results, cases, decisions, and outcomes.
- `data/synthetic/generator.py`: Deterministic fictional `RL-` data, including the canonical Supplier Alpha disruption and unapproved Supplier Beta alternative.
- `services/exposure/calculator.py`: Usable inventory, time-phased projection, stockout, shortage, affected-order, revenue, margin, and OTIF exposure calculations.
- `services/scenarios/evaluator.py`: Six fixed mitigation scenarios plus qualification and feasibility checks.
- `services/policy/thresholds.py`: Finance approval, collaboration-evidence staleness, and date-conflict policies.
- `apps/api/app/main.py`: FastAPI case lifecycle and dashboard endpoints backed by in-memory process state.
- `apps/api/app/contracts.py`: API-specific request and response contracts.
- `apps/web/src/api.ts`: Typed frontend client for creating and retrieving cases.
- `apps/web/src/App.tsx`: Minimal React shell; it does not yet expose the case-analysis workflow.
- `agents/`, `fabric/`, and `evaluations/`: Reserved extension points that are mostly placeholders in this increment.

## Runtime flow

1. `POST /api/cases` accepts a disruption and creates an open in-memory case.
2. `POST /api/cases/{caseId}/analyze` converts the confirmed partial shipment into a timed receipt.
3. The exposure service calculates usable inventory and component demand from BOM and production-order data.
4. Inventory is projected chronologically to determine stockout date and maximum shortage.
5. Affected production orders are linked to customer orders to calculate revenue, margin, and OTIF risk.
6. The scenario evaluator creates six response scenarios and blocks Supplier Beta when qualification evidence says it is not approved.
7. Approval or rejection updates the case and appends an in-memory action-ledger record.
8. The dashboard endpoint aggregates case counts and exposure totals from the same in-memory state.

## Current maturity

The repository is a functional scaffold rather than a production application:

- The backend contains meaningful portable-core behavior.
- The frontend is only a shell and a partial API client.
- State is held in process-global dictionaries and lists and disappears on restart.
- Agent, Fabric, Foundry, ontology, Power BI, and evaluation-data directories contain placeholders.
- Authentication, durable persistence, deployment, CI, and external integrations are intentionally deferred.

## Notable constraints and risks

1. **Browser integration:** The API has no CORS middleware and the frontend has no Vite proxy configuration. Calls from the default Vite development origin to `localhost:8000` will be cross-origin once the UI uses the API client.
2. **Hardcoded plant:** Case analysis always evaluates `RL-PLANT-CHI`; the disruption contract does not identify the affected plant.
3. **Volatile and process-local state:** Cases and action-ledger records are lost on restart and are unsuitable for multiple API workers.
4. **Dependency reproducibility:** There are no Python or npm lockfiles. Frontend dependencies use `latest` versions.
5. **Fixed demo scenarios:** Scenario IDs, costs, and rules are largely hardcoded around the canonical demonstration.
6. **Loose lifecycle controls:** Repeated decisions and replacement decisions are not guarded by an explicit case-state transition policy.
7. **Limited UI contract:** The TypeScript case interface omits the optional exposure field returned by the backend, and the client only implements create/get operations.

## Test coverage and verification

The repository contains 18 Python test functions and one frontend Vitest test. The Python tests cover API contracts, exposure arithmetic, deterministic data generation, qualification rules, policy thresholds, and remaining evaluation cases. The frontend test covers the case retrieval client.

Fresh verification was attempted on 2026-08-30:

```text
python3.12 -m pytest
Result: exit 1 - No module named pytest

npm test
Result: exit 127 - vitest: command not found
```

These outcomes indicate that development dependencies were not installed in the review environment. They do not establish whether the test suites pass or fail after installation.

## Git-history reconnaissance

### Repo vitals

- Age: 2026-08-25 to 2026-08-25
- Commits: 1
- Branches: 3, including remote references
- Analysis window: all history

### Code hotspots

All tracked files were introduced in the same scaffold commit and therefore have the same change count. No meaningful hotspot ranking can be inferred yet.

### Bug magnets and high-risk intersections

No commits matched `fix`, `bug`, or `broken`, so there are no history-derived bug magnets or files appearing in both the hotspot and bug-magnet sets.

### Bus factor

- Contributors: 1 (`OpenAI`)
- Active in the previous three months: 1 of 1

The repository has concentrated authorship, but one scaffold commit is insufficient for a meaningful ownership or bus-factor assessment.

### Team momentum

The repository contains one commit in August 2026. There is not enough history to classify momentum as rising, stable, declining, or erratic.

### Firefighting frequency

No revert, hotfix, emergency, or rollback commits were found: 0 of 1 commits.

### Recently added files

Every tracked file was added in the only commit, so this signal does not distinguish recent areas of development.

## Recommended reading order

1. `data/schemas/models.py`
2. `services/exposure/calculator.py`
3. `apps/api/app/main.py`
4. `data/synthetic/generator.py`
5. `services/scenarios/evaluator.py`
6. `tests/test_api.py` and `tests/test_exposure.py`

## Recommended near-term priorities

1. Add a reproducible dependency lock/install workflow and CI verification.
2. Add local CORS or Vite proxy configuration before connecting the UI.
3. Put `plant_id` into the disruption/case analysis contract instead of hardcoding Chicago.
4. Replace process-global storage with a repository abstraction before adding multiple workers or persistence.
5. Expand the frontend around the existing case, analysis, scenario, and decision endpoints.
6. Convert placeholder evaluation datasets into executable known-answer fixtures as the scenario logic grows.
