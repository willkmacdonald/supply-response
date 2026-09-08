# Work IQ discovery substep diagnostics

The user approved narrowly scoped statuses and one further Alex Analyze on
2026-09-07. This is diagnosis, not a discovery-behavior change or a new endpoint.

## Plan and success criteria

- [x] Add offline RED tests in `tests/integration/test_workiq_mcp_evidence.py`
  exercising real OBO/MCP composition with fake HTTP: initialization rejection,
  ask rejection, zero parsed locators, wrong scope, wrong message binding,
  successful retrieval, timeout/cancellation, and secret-bearing unknown errors.
- [x] Add failure-only diagnostics in `integrations/workiq/mcp_evidence.py`.
  Record fixed substep/reason names, bounded HTTP status and bounded candidate
  counts only. Never output bodies, links, source/actor/conversation/request IDs,
  exception strings, headers, tokens or response objects. Keep existing public
  errors, prompts, fetches, policy and limits unchanged.
- [x] Pass focused/full regression, scoped static checks and package build;
  independently review the bounded diff and commit locally without pushing.
- [x] Follow Azure validation/deployment workflow for the existing app only.
  Confirm readiness, revision, identity and roles; invoke normal Analyze once
  as Alex on the existing case where available.
- [x] Read only allowlisted diagnostic records for that attempt, document the
  supported conclusion and stop. No automatic retry, Graph, new permissions,
  billing, resources, source changes, approval or execution.

The previous red-capable live signal is the normal Alex Analyze returning 503
with supplier/discovery, but its exact upstream cause cannot yet be replayed
offline because raw responses were deliberately discarded. These tests prove
the diagnostic distinction, not a fix for the unknown live failure. Existing
candidate filters and retrieval outputs must remain identical. Failed live
acceptance is not permission to implement a speculative fix.

Completed 2026-09-08: revision15 is healthy; one existing-Case Alex Analyze
returned supplier/discovery503. Both sources failed `ask` answer-shape validation
before locator parsing (`discovery_shape`; all counts-1). The allowed diagnostic
distinction is established, not a live discovery fix. See the deployment result.
