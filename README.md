# Supply Response

Multi-agent prototype that helps manufacturing supply-chain teams respond to
supplier disruptions faster. This repository contains the **portable core**:
deterministic calculations, synthetic data, the FastAPI backend, and the
React/TypeScript decision console.

All data is fictional and prefixed with `RL-`. The local stack calls **no**
external services: no Azure, no Fabric, no Foundry, no Work IQ. Reference data
comes from a deterministic synthetic generator and application state is stored
in SQLite.

See [`Supply-Response-Project-Brief.md`](Supply-Response-Project-Brief.md) for
the full project brief.

## Quick start

Requires Python 3.12 and Node.js 18+.

```bash
# 1. Backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r apps/api/requirements.txt
cp .env.example .env

# 2. Run the tests (fast, no external services)
python -m pytest -q

# 3. Start the API on http://localhost:8000
uvicorn apps.api.main:app --reload --port 8000

# 4. Frontend (in a second terminal)
cd apps/web
cp .env.example .env
npm install
npm run dev                        # http://localhost:5173
```

API documentation is served at <http://localhost:8000/docs>.

### Walk through the RL-001 demo from the terminal

```bash
CASE=$(curl -s -X POST localhost:8000/api/cases \
  -H 'content-type: application/json' \
  -d '{"disruption_id":"RL-001"}' | python -c 'import json,sys;print(json.load(sys.stdin)["case_id"])')

curl -s -X POST localhost:8000/api/cases/$CASE/analyze | python -m json.tool | head -40
curl -s localhost:8000/api/cases/$CASE/scenarios | python -m json.tool
curl -s -X POST localhost:8000/api/cases/$CASE/approve \
  -H 'content-type: application/json' \
  -d '{"scenario_id":"RL-SCN-006","decided_by":"Alex Morgan","rationale":"Best net benefit."}' | python -m json.tool
curl -s localhost:8000/api/dashboard/summary | python -m json.tool
```

### Generate a dataset file

```bash
python -m data.synthetic.generator --seed 42 --out data/synthetic/dataset.json
export SUPPLY_RESPONSE_DATASET=data/synthetic/dataset.json   # optional
```

## Repository structure

```text
supply-response/
  apps/
    web/                 React + TypeScript decision console (Vite)
    api/                 FastAPI backend, SQLAlchemy, SQLite
  agents/
    orchestrator/        Hosted agent prompt + local deterministic orchestrator
    signal/              Supplier-signal extraction prompt
    context/             Work IQ context retrieval prompt
    decision/            Scenario explanation prompt
  services/
    exposure/            Deterministic inventory and exposure calculations
    scenarios/           Scenario construction, evaluation, and ranking
    policy/              Quality qualification and approval-threshold checks
  data/
    schemas/             Pydantic v2 models for all 15 tables
    synthetic/           Deterministic dataset generator
    fixtures/            RL-001 demo fixtures
  fabric/
    notebooks/           Lakehouse load notebook
    sql/                 Portable DDL and calculation views
    semantic-model/      Semantic model definition
    ontology/            Fabric IQ entities and relationships
    power-bi/            Report page definitions
  evaluations/
    datasets/            The ten evaluation cases
    expected-results/    Golden results for RL-001
  tests/                 pytest suite
  docs/
    architecture/        Architecture and data-model documentation
    demo-script/         Three-minute demo script
```

## The RL-001 demo scenario

| Item | Value |
|---|---|
| Signal | Email `RL-001`: Supplier Alpha cannot deliver 8,000 units of MAT-10247 on 2025-09-03 |
| Partial offer | 3,000 units on 2025-09-06 by air freight |
| Recovery date | Unconfirmed |
| Constraint | Teams message `RL-QUALITY-001`: Supplier Beta is not approved for MAT-10247 (earliest decision 2025-09-15) |

Because of `RL-QUALITY-001`, scenario `RL-SCN-005` (source from Supplier Beta) is
returned as **not executable** and is retained only as a conditional future
option.

| Scenario | Type | Executable |
|---|---|---|
| `RL-SCN-001` | Accept the delay and allow backlog | yes |
| `RL-SCN-002` | Expedite Supplier Alpha's 3,000-unit partial shipment | yes |
| `RL-SCN-003` | Transfer inventory from RL-PLANT-02 | yes |
| `RL-SCN-004` | Resequence production toward priority customers | yes |
| `RL-SCN-005` | Source from Supplier Beta | **no — RL-QUALITY-001** |
| `RL-SCN-006` | Combine expedite, transfer, and resequencing | yes (recommended) |

## Core calculations

Implemented in `services/exposure/calculator.py`. No LLM performs arithmetic.

```text
usable_inventory = on_hand - quality_hold - protected_allocation

projected_balance[date] = prior_balance
                        + confirmed_receipts
                        + approved_transfers
                        - component_demand
```

Derived values: first projected stockout date, maximum shortage quantity,
affected production orders, affected customer-order lines, revenue and margin at
risk, OTIF lines at risk, response cost, revenue protected, and remaining
uncertainty.

Every result carries a scenario id, calculation version, timestamp, assumptions,
and source-data lineage.

Rules worth knowing:

- A delayed purchase order with **no** revised date contributes no receipt: the
  system never invents a supplier commitment.
- `project_balance` carries deficits forward; order allocation does not lend
  inventory it does not have, so a shortage is never double counted.
- Shortfall is absorbed by the least protected demand first (lowest customer
  priority tier, then latest promised date).

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/cases` | Create a disruption case |
| `GET` | `/api/cases` | List cases |
| `GET` | `/api/cases/{caseId}` | Case detail: facts, uncertainties, evidence, exposure, scenarios, actions |
| `POST` | `/api/cases/{caseId}/analyze` | Run the deterministic exposure and scenario analysis |
| `GET` | `/api/cases/{caseId}/scenarios` | Ranked scenarios (409 before analysis) |
| `POST` | `/api/cases/{caseId}/approve` | Approve a scenario and write the action ledger |
| `POST` | `/api/cases/{caseId}/reject` | Reject a scenario |
| `GET` | `/api/dashboard/summary` | Command-center metrics |
| `GET` | `/api/health` | Version and status |

Approving a non-executable scenario returns `409` with the blocking constraint.
Approval writes an action-ledger record, drafts a supplier recovery request, and
creates Procurement and Quality follow-up tasks. The prototype never creates a
real purchase order or financial commitment.

## Synthetic data

`data/synthetic/generator.py` produces a deterministic dataset (default seed 42):
50 suppliers, 500 parts, and all fifteen tables, with the RL-001 fixtures always
merged in. The brief's full demonstration scale (250 suppliers, 10,000 parts,
100,000 BOM rows) is generated in Fabric; the local dataset is scaled down so the
test suite runs in about a second.

Tables: `suppliers`, `parts`, `supplier_parts`, `purchase_orders`,
`inventory_positions`, `bom_components`, `production_orders`, `customers`,
`customer_orders`, `transport_options`, `quality_qualifications`, `disruptions`,
`response_scenarios`, `action_ledger`, `outcome_history`.

## Testing

```bash
python -m pytest -q                      # everything
python -m pytest tests/test_calculations.py -q
cd apps/web && npm test                  # frontend component tests
```

| File | Covers |
|---|---|
| `tests/test_calculations.py` | Core formulas, policy checks, scenario ranking |
| `tests/test_api.py` | Every API endpoint, including approval guardrails |
| `tests/test_generator.py` | Determinism, RL- prefixes, referential integrity |
| `tests/test_evaluations.py` | Golden results for RL-001 and the ten evaluation cases |

## Configuration

All configuration is environment based; see [`.env.example`](.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `SUPPLY_RESPONSE_DB_URL` | `sqlite:///./supply_response.db` | Application-state database |
| `SUPPLY_RESPONSE_SEED` | `42` | Synthetic dataset seed |
| `SUPPLY_RESPONSE_DATASET` | unset | Load a pre-generated dataset JSON instead |
| `SUPPLY_RESPONSE_CORS_ORIGINS` | `http://localhost:5173` | Allowed browser origins |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend URL used by the frontend |

## Hosted services (optional, not required locally)

Fabric, Foundry, Work IQ, and Fabric IQ are additive. The contracts live in
`fabric/` and `agents/`; the portable core in this repository runs without them.
Fabric IQ stays optional until the September 11 go/no-go.

## Security and development rules

- Fictional data only; every business key uses the `RL-` prefix.
- Never commit secrets or tenant credentials. Use environment variables and
  managed identity where available.
- The browser calls the backend only; credentials never reach frontend code.
- Calculation logic is versioned (`CALCULATION_VERSION`) and tested.
- Consequential actions require explicit human approval.
- Source citations and calculation lineage are preserved on every result.
