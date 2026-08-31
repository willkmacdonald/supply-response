# Task 17 implementation report

Status: **DONE_WITH_CONCERNS**

## Delivered

- Added one mutually exclusive application dependency graph. Fallback remains SQLite/synthetic/local; live constructs Fabric SQL, exact Task 14 `AuthService`, lazy delegated Work IQ OBO, exact-version Foundry agents, shared Decision/planning/playback services, and one validated Power BI URL.
- Added a composed live analysis service that re-checks immutable Case runtime on every load, uses the stored live Operational Snapshot, accepts only non-synthetic Fabric/Work IQ evidence with trusted citations, passes only typed evidence and token-free typed retrieval lineage into the Agent Framework/deterministic boundary, serializes concurrent analysis to one immutable Analysis Version, and never substitutes fallback after a live failure.
- Added bounded authentication/source failure mapping. Missing/invalid bearer state and unauthorized personas produce fixed public errors; live-source failures produce `503 LIVE_SOURCE_UNAVAILABLE` with `new_fallback_case_allowed=true` and no source/token/endpoint detail.
- Bound live analysis, Decision, retry, and playback mutations to the authenticated Alex identity snapshot. The exact `AuthService` instance owns the OBO assertion; raw inbound/downstream tokens and A2A envelopes do not enter Foundry, persistence, responses, logs, Power BI, or identity snapshots.
- Made Work IQ confidential-client construction lazy so startup/health performs no authority discovery, OBO, Work IQ, Foundry, or user-context call. Lifespan shutdown closes owned async clients and disposes the store engine.
- Extended `/api/runtime` with live/fallback capability health and a server-validated Power BI URL without secrets or internal error detail.
- Added UI trust enforcement for Microsoft 365/tenant SharePoint/Power BI URLs, safe new-tab links, live Power BI visibility, and visible `Required live citation missing` approval blocking while preserving the unauthenticated fallback journey.
- Added a separate fail-closed `live` Playwright project. It requires an exact HTTPS base URL, owner-only Alex storage state, pinned corpus/three agent versions, and an explicit live switch before browser/network activity. Trace, screenshots, and video are disabled for that project.
- Updated the personal-tenant deployment runbook with the full composition configuration and approval-gated live browser checklist.

## TDD evidence

- Initial RED: `tests/integration/test_live_case_contract.py` failed collection because `apps.api.app.live` did not exist.
- Subsequent RED: UI safety tests failed because Power BI was absent and unsafe/missing required live citations were rendered without blocking.
- GREEN composed contract: live service provenance and bounded-failure tests passed, followed by real FastAPI route composition from Case creation through analysis, Alex Decision, five actions, playback, and simulated observations.
- Additional regression coverage proves concurrent live analysis returns one immutable Analysis ID, live browser artifact collection is disabled, and the existing fallback route/UI behavior remains intact.

## Verification

- Composed Task 17 integration suite: 6 passed.
- Full safe Python suite excluding the previously documented NuGet-gated Power BI/TMDL project file: green (552 collected; 14 expected live/infrastructure skips).
- Frontend Vitest: 38 passed.
- Frontend production build: passed.
- Fallback Playwright API/UI journey: passed through the `webapp-testing` server-lifecycle helper after invoking its `--help`; no live project was executed.
- Live Playwright project discovery: one gated test listed; no browser/network execution.
- Ruff changed scope (imports, errors, upgrades): passed.
- Pyright changed scope with repository virtualenv: 0 errors, 0 warnings.
- Offline npm production audit: 0 vulnerabilities. Python `pip check`: no broken requirements.
- `git diff --check`: passed.
- `uv lock --check --offline` could not read the user-level uv cache under the sandbox; no dependency or lockfile changed in this task.
- The four Task 13 TMDL/NuGet checks remain excluded because the sandbox cannot restore `Microsoft.AnalysisServices`; this is unchanged and unrelated to Task 17.

## Deferred external prerequisites

No Azure, Graph, Entra, Microsoft 365, Work IQ, Fabric, Foundry, Power BI, credential, tenant-authentication, live browser, or other network call was made.

Task 18/reviewer approval is still required to provision/deploy resources, create/verify persona bindings and corpus artifacts, supply the confidential credential, confirm Fabric schema/data, publish and pin Foundry versions, publish Power BI, create fresh owner-only Alex browser state, run authenticated citation verification, execute the live Playwright journey, and inspect matching Decision/outbox/action/observation/Power BI records.
