# Portable core architecture

The initial scaffold implements only local, portable concerns:

- Pydantic schemas for the proposed synthetic data model.
- Seeded fictional `RL-` dataset generation.
- Deterministic inventory projection and exposure calculation.
- Deterministic scenario constraint evaluation.
- FastAPI request/response contracts matching the proposed endpoints.
- React/TypeScript frontend shell and typed API client.
- Automated Python and frontend tests.

Agent, Fabric, Foundry, Work IQ, and Fabric IQ directories are preserved as integration seams but contain no live integration code.

## Milestone 1 domain alignment

- Disruptions carry the affected plant explicitly; analysis has no hardcoded plant fallback.
- Scenario results carry stable constraint codes, evidence references, and required approver roles.
- The ten evaluation cases are cataloged in `evaluations/datasets/evaluation_cases.json` and linked to executable pytest nodes.
- The timestamp-independent 2026 RL-001 result is guarded by `evaluations/expected-results/rl-001.json`.
- Financial values remain `Decimal` in Python and exact strings in committed JSON results.
- The baseline freezes the normalized seed-42 behavior; any later fixture change must update the known-answer contract explicitly.

The complete product requirements are preserved in `Supply-Response-Project-Brief.md`.
