# Supply Response

Portable-core scaffold for the Supply Response prototype. This first repository increment intentionally implements **no Azure, Fabric, Foundry, Work IQ, Fabric IQ, or other external-service integrations**.

## Implemented now

- Python 3.12-compatible FastAPI backend.
- React + TypeScript/Vite frontend shell.
- Portable Pydantic schemas for the proposed synthetic tables.
- Deterministic, seeded, fictional `RL-` synthetic dataset generator.
- Deterministic usable-inventory, time-phased projection, stockout, shortage, affected-order, revenue, margin, and OTIF exposure calculations.
- Initial scenario contracts and deterministic Supplier Beta qualification constraint.
- Proposed case/scenario/approval/dashboard API routes.
- In-memory local case/action storage (deliberately replaceable by SQLite/Fabric later).
- Pytest and Vitest coverage.

## Repository layout

The structure follows the project brief. Integration folders are retained as placeholders so later work can be added without reorganizing the repository.

```text
supply-response/
  apps/
    web/
    api/
  agents/
    orchestrator/
    signal/
    context/
    decision/
  services/
    exposure/
    scenarios/
    policy/
  data/
    schemas/
    synthetic/
    fixtures/
  fabric/
    notebooks/
    sql/
    semantic-model/
    ontology/
    power-bi/
  evaluations/
    datasets/
    expected-results/
  tests/
  docs/
    architecture/
    demo-script/
  .env.example
  README.md
```

## Project references

- [Project brief](Supply-Response-Project-Brief.md)
- [Portable-core architecture](docs/architecture/portable-core.md)
- [Evaluation catalog](evaluations/datasets/evaluation_cases.json)
- [RL-001 known-answer result](evaluations/expected-results/rl-001.json)

## Local setup

### Prerequisites

- Python **3.12**
- Node.js 20+ and npm

### Backend

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
pytest
uvicorn apps.api.app.main:app --reload
```

The API is then available at `http://localhost:8000`; OpenAPI docs are at `/docs`.

### Frontend

In a second terminal:

```bash
cd apps/web
npm install
npm test
npm run dev
```

The frontend defaults to calling `http://localhost:8000`. Override with `VITE_API_BASE_URL` when needed.

## API contracts

Implemented routes:

```text
POST /api/cases
GET  /api/cases/{caseId}
POST /api/cases/{caseId}/analyze
GET  /api/cases/{caseId}/scenarios
POST /api/cases/{caseId}/approve
POST /api/cases/{caseId}/reject
GET  /api/dashboard/summary
```

Approval is bounded: a non-executable scenario (including the default Supplier Beta scenario) cannot be approved.

## Synthetic data

`data.synthetic.generator.generate_dataset()` is deterministic for a given seed. Small defaults keep local development fast; the function accepts counts so larger demonstration-scale datasets can be generated without changing schemas or calculation contracts.

All generated identifiers and names are fictional and prefixed with `RL-`.

## Calculation behavior

The portable calculation service implements:

```text
usable inventory = on hand - quality hold - protected allocation
projected balance = prior balance + confirmed receipts + approved transfers - component demand
```

Results include calculation version, timestamp, assumptions, and source-data lineage. Authoritative arithmetic stays outside any future LLM/agent implementation.

## What is intentionally deferred

- Azure hosting/deployment
- Microsoft Foundry agents / Agent Framework
- Work IQ
- Fabric tables, SQL endpoint, semantic model, and Power BI
- Fabric IQ ontology/MCP
- Managed identity and tenant configuration
- Real email, Teams, supplier, ERP, or customer data

The preserved directories are the extension points for those later phases.
