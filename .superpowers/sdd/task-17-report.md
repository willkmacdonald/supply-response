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

---

## Second independent-review correction

Status: **DONE_WITH_CONCERNS**

### Corrections completed

- Live evidence now validates the complete collection at each retrieval boundary before any classification. Operational items must all be exact `FABRIC`/`LIVE`, non-synthetic, healthy/current, tenant-safe, and restricted to operational quantity/date/qualification authority. Supplier and Quality collections must all be exact `WORK_IQ`/`LIVE`, non-synthetic, healthy/current, tenant-safe, restricted to their respective authority scopes, and bound to their configured source ID. Extra server, synthetic, stale, untrusted, wrong-scope, wrong-source, or cross-runtime items fail closed; arbitrary items are never relabeled.
- The authoritative Fabric operational DDL now publishes exact schema version 12, matching `FABRIC_SCHEMA_VERSION` and `check_fabric_health`. The analytics script's version-12 publication remains idempotent.
- Analysis claim completion now checks the exact owner and unexpired lease, inserts the immutable Analysis and nested records, updates the Case projection, and deletes the successful claim in one database transaction and connection. The claim/projection reads use row locking where supported. A stale owner after expiry/takeover cannot commit and resolves to the canonical winner. Insert/projection failure rolls back every Analysis/evidence/projection row, and the public boundary safely releases the claim.
- Analysis losers now poll for the canonical winner using an injected monotonic clock/sleep and configurable bounded budget, validated at no more than 90 seconds, rather than a fixed one-second loop.
- Browser citation trust no longer consumes `citation_trusted_host` from Evidence. The independently configured exact tenant SharePoint host is returned in the live runtime deployment contract and supplied to the browser trust policy. Cross-tenant payload self-authorization is rejected.
- Removed the permanent process-local playback blacklist. Runtime progression retries transient playback failures a bounded three times, removes transient counters after completion, and durably records terminal `failed` state with only `PLAYBACK_EXECUTION_FAILED`. Domain, SQLite/Alembic migration `0006`, Fabric DDL/store, API, and frontend types carry the bounded terminal state. Persisted `in_progress` playback still recovers on restart; terminal playback is no longer rediscovered.
- The React workspace coalesces concurrent playback starts into one shared in-flight start/poll promise. The full browser test now proves two synchronous clicks produce one POST/poll loop and no duplicate outcomes.

### TDD and systematic diagnosis evidence

- RED evidence extras: arbitrary operational items relabeled as Work IQ and wrong-scope extras were accepted. GREEN: 23 live hardening tests pass, including invalid extras, takeover, bounded waiting, and transactional rollback.
- RED claim takeover: the winning Analysis was returned but the successful claim remained. GREEN: stale owner is excluded and the claim table is empty after canonical completion.
- RED browser trust: a forged item naming `other.sharepoint.com` as its own trusted host rendered a live link. GREEN: the same payload is blocked under the independently configured tenant host.
- Playback root cause was reproduced as the permanent runtime blacklist plus two uncoalesced browser poll loops. RED tests showed transient failures never retried, terminal failures remained `in_progress`, and two synchronous clicks emitted two POSTs. GREEN tests prove transient recovery on attempt three, durable bounded terminal failure, and one browser operation.
- Initial helper attempts did not launch a browser: systematic diagnosis found the guarded E2E database-path contract and then the sandboxed localhost bind. The valid helper runs used approved localhost access, a distinct guarded `.tmp/e2e-<UUID>.db`, and fresh API/Vite servers.

### Verification

- Safe Python suite excluding the Task 13 NuGet-dependent Power BI validator file: passed in full, with only expected live skips.
- Remaining safe Power BI project tests: **58 passed**; the four locked TOM/TMDL restore tests remain environment-blocked because public NuGet is unavailable.
- Focused runtime/playback/persistence/Fabric suite: **62 passed**.
- Live hardening suite: **23 passed**.
- Frontend Vitest: **49 passed**; production build passed.
- Fallback Playwright helper run 1: **6/6 passed** in 1.8 minutes; duplicate-click recovery test 51.3 seconds.
- Fallback Playwright helper run 2: **6/6 passed** in 1.8 minutes; duplicate-click recovery test 51.8 seconds.
- Ruff focused import/undefined checks passed; pinned Pyright: **0 errors, 0 warnings**.
- npm offline production audit: **0 vulnerabilities**; Python `pip check`: no broken requirements; `git diff --check`: passed.

No live browser, tenant authentication, external network, Azure, Graph, Entra, Microsoft 365, Work IQ, Fabric, Foundry, or Power BI operation was performed. The approval-gated Task 18 live acceptance remains deferred.
