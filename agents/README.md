# Agents

Four Foundry agents wrap the deterministic services. None of them performs
arithmetic: every number comes from `services/` and is quoted verbatim.

| Agent | Type | Prompt |
|---|---|---|
| Orchestrator | Foundry hosted agent (Microsoft Agent Framework) | [`orchestrator/prompt.md`](orchestrator/prompt.md) |
| Signal | Foundry prompt agent | [`signal/prompt.md`](signal/prompt.md) |
| Context | Foundry prompt agent | [`context/prompt.md`](context/prompt.md) |
| Decision | Foundry prompt agent | [`decision/prompt.md`](decision/prompt.md) |

`orchestrator/orchestrator.py` is the local, model-free implementation of the
orchestration sequence. It is what the demo runs when Foundry is unavailable.

## Tools exposed to the agents

| Tool | Implementation |
|---|---|
| `calculate_exposure` | `services.exposure.calculator.calculate_exposure` |
| `evaluate_scenarios` | `services.scenarios.evaluator.evaluate_scenarios` |
| `check_supplier_qualification` | `services.policy.checker.check_supplier_qualification` |
| `check_spend_approval` | `services.policy.checker.check_spend_approval` |
