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
