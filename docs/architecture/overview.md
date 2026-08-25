# Architecture overview

## Runtime

```text
Supplier email / Teams / SharePoint
                 |
                 v
             Work IQ                (optional; fixtures locally)
                 |
                 v
        Foundry Orchestrator        (agents/orchestrator)
          |-- Signal Agent          (agents/signal)
          |-- Context Agent         (agents/context)
          |-- Decision Agent        (agents/decision)
          |-- Calculation Tools     (services/exposure)
          `-- Scenario Tools        (services/scenarios, services/policy)
                 |
                 v
      Fabric Lakehouse / Warehouse  (optional; SQLite + generator locally)
          |-- Semantic model
          |-- Power BI dashboard
          |-- Fabric IQ ontology
          `-- Action ledger
                 |
                 v
        Supply Response web app     (apps/web -> apps/api)
```

## Portable core

Everything required for the demo runs locally:

| Layer | Local implementation | Hosted equivalent |
|---|---|---|
| Reference data | `data/synthetic/generator.py` | Fabric Lakehouse / SQL endpoint |
| Human context | `data/fixtures/demo.py` | Work IQ |
| Calculations | `services/exposure`, `services/scenarios`, `services/policy` | Same code, called as Foundry tools |
| Orchestration | `agents/orchestrator/orchestrator.py` | Foundry hosted agent |
| Application state | SQLite via SQLAlchemy | Fabric tables |
| UI | React + TypeScript (`apps/web`) | Same, plus embedded Power BI |

## Request flow

1. `POST /api/cases` creates a case from a disruption record and attaches
   evidence, confirmed facts, and unresolved uncertainties.
2. `POST /api/cases/{caseId}/analyze` runs the do-nothing baseline exposure,
   builds or loads candidate scenarios, evaluates each one against the exposure
   engine, applies policy checks, and ranks the results.
3. `GET /api/cases/{caseId}/scenarios` returns the ranked list. Non-executable
   scenarios are always ranked last and carry their blocking constraint.
4. `POST /api/cases/{caseId}/approve` writes an action-ledger record with
   evidence, calculation version, and bounded follow-up tasks.
5. `GET /api/dashboard/summary` aggregates cases, exposure, and decisions.

## Determinism

No language model performs arithmetic. Given the same dataset, disruption, and
timestamp, the analysis is byte-for-byte reproducible. `CALCULATION_VERSION`,
`EVALUATOR_VERSION`, and `POLICY_VERSION` are stamped on every result, and
`evaluations/expected-results/rl-001.json` is a committed golden file guarded by
`tests/test_evaluations.py`.

## Approval boundary

The prototype may draft messages and create follow-up tasks. It must not create
a real purchase order or any financial commitment. Approving a scenario blocked
by a quality qualification is rejected by the API with HTTP 409.
