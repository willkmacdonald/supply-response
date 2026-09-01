# Task 17 review-fix report

Status: **DONE_WITH_CONCERNS**

## Review findings closed

- Replaced live synthetic construction/relabeling with a typed `LiveOperationalDataPort`. The Fabric adapter reads only a verified current `app.live_operational_sources` record and preserves original source IDs, timestamps, citations, LIVE mode, and FABRIC provenance. Live Case creation and analysis both use it; synthetic RL-001 builders are absent from the live graph.
- Require the complete Fabric quantity/date/qualification authority set and one exact, nonempty supplier and Quality Work IQ result bound to configured source IDs. Missing, downgraded, unhealthy, stale, incomplete, synthetic, or untrusted material maps to bounded `LIVE_SOURCE_UNAVAILABLE`.
- `AgentExplanationUnavailable` now saves the deterministic partial with explicit unavailable status. Immutable Analysis payloads retain token-free supplier/Quality context, task, artifact, and source lineage plus bounded explanation content/status across reload. Decisions still reference that Analysis Version.
- Added typed readiness. Configuration reports `unverified`; Fabric requires the Task 12 connectivity/schema check, while Work IQ/Foundry/Power BI require exact SHA-256 deployment-binding receipts. Startup performs no user-context call.
- Removed all process-local analysis locks. Added database-authoritative leased material claims, expired takeover, failure release, and an atomic immutable Analysis + Case projection transaction. Two independent service/store instances return one canonical Analysis ID.
- Moved live Playwright gating into config load before webservers/browser. It pins exact origin, Scenario Effective Time, corpus/source IDs, three agent versions, and owner-only Alex state; live never launches fallback servers. The 270-second timeout exceeds the inner gates. The spec invokes Task 15's rendered-artifact verifier for exactly supplier/Quality Work IQ, validates Fabric citations separately, and checks one Decision ID through analysis lineage, actions, observations, and Power BI.
- Replaced browser wildcard SharePoint trust with server-classified URL, exact trusted host, and navigable URL. Tests reject other tenants, lookalikes, userinfo, ports, and plain/encoded credential parameters.
- Validated all scalar/URL/host/agent bindings before allocating the Fabric engine or HTTP client.

Scope intentionally expanded into the domain model, persistence store, Alembic migration, and Fabric DDL because durable lineage, cross-process idempotency, and truthful readiness are correctness requirements.

## TDD and verification

- RED: missing `LiveOperationalRetrieval`; GREEN: 5/5 provenance, completeness, partial-lineage reload, and cross-instance claim tests.
- RED: missing readiness module; GREEN: injected readiness distinguishes unverified/ready without accepting SQLite as Fabric proof.
- RED: nine missing browser trust behaviors; GREEN: all nine adversarial cases pass.
- RED: live config lacked preflight; GREEN: live listing fails closed during config load before servers/browser.
- Focused Python hardening/API/persistence/Fabric suite: **80 passed**.
- Full safe Python reached completion with only two expected updated response/static assertions; both were corrected and focused suites are green. Known Task 13 NuGet/TMDL exclusion is unchanged.
- Frontend Vitest: **47 passed**; production build passed.
- Ruff passed; Pyright: **0 errors, 0 warnings**.
- npm offline production audit: **0 vulnerabilities**; Python `pip check`: no broken requirements; `git diff --check`: passed.
- Live Playwright was not run. Missing prerequisites fail during config load; fallback discovery lists six tests.
- Real fallback Playwright via `with_server.py`: **5/6 passed** in two full runs; only the final duplicate-click observation poll timed out after the full sequence. The exact test passed **1/1** alone and failed-child then duplicate passed **2/2** on fresh servers. This is recorded as a sequencing/helper flake.

## Deferred external acceptance

No Azure, Graph, Entra, Microsoft 365, Work IQ, Fabric, Foundry, Power BI, tenant authentication, or live browser call was made. Task 18 must seed/verify the operational source bundle, issue deployment receipts, validate real persona/corpus/agent/report bindings, and run the approval-gated live journey.
