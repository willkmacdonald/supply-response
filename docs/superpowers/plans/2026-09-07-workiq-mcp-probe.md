# Work IQ MCP Probe Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for implementation and review. The controller owns cloud execution and cleanup verification.

**Goal:** Verify one Work IQ MCP fetch with the deployed API's existing Alex OBO identity, then retire all diagnostic code.

**Architecture:** A temporary FastAPI router uses `get_actor` and the configured `AuthService`, constructs the existing OBO exchange, and calls only a fixed Work IQ MCP fetch. A separate React diagnostic view invokes this endpoint using `useAuth().getAccessToken()` without creating Cases.

**Tech Stack:** Existing FastAPI, MSAL, httpx, React, pytest and Vitest. No new dependencies.

## Global Constraints

The approved spec is `docs/superpowers/specs/2026-09-07-workiq-mcp-probe-design.md` and governs all tasks. No arbitrary source inputs, no Graph fallback, no permission/billing changes, no raw message/token logging or persistence, and no changes to ordinary analysis. A fixed UTC window lasts at most 30 minutes; one attempt per process with one deployed replica/worker. Stop after a restart or scale event. Cleanup is mandatory even on failure. No Git push.

### Task 1: Implement and test the isolated probe

**Files:** Create `integrations/workiq/mcp_probe.py`, `apps/api/app/routes/workiq_probe.py`, `apps/web/src/components/WorkIQProbe.tsx` and their tests. Modify only `apps/api/app/main.py` and `apps/web/src/App.tsx` for wiring. Create a temporary `integrations/workiq/probe_binding.py` containing the deployment binding and disabled-by-default UTC window; controller fills the window just before deployment.

**Interfaces:** Router prefix `/api/diagnostics/workiq-fetch`, POST with no body or query. `WorkIQProbe` renders at `/diagnostics/workiq-fetch` after the existing sign-in gate; it must not render `CaseWorkspace`. Return only a safe result object with stage, HTTP status and validation booleans. No public raw-result endpoint.

- [ ] Write failing tests using existing signed JWT fixtures and actual `get_actor`/`AuthService`; reject absent auth, wrong object/roles, expired token, fallback mode, payload/query overrides, expired window, repeat/concurrent attempts. Start with an assertion that the intended POST route is absent (404) before wiring it.
- [ ] Run `uv run pytest -q tests/integration/test_workiq_mcp_probe.py` and confirm feature assertions fail, then implement.
- [ ] Use the configured services' AuthService and `build_obo_exchange` with settings `api_client_id`, `entra_client_secret`, and `allowed_tenant_id`; never manufacture an actor. Claim a lock-protected one-attempt latch before OBO. Validate actor ownership before consuming the latch.
- [ ] Use a dedicated nonredirecting httpx client with no retries, bounded connect/read/total time and a maximum 1 MiB upstream response. Suppress instrumentation for the diagnostic outbound operation. Do not emit upstream exceptions or arbitrary strings.
- [ ] MCP: send JSON-RPC `initialize` with protocol `2025-03-26`, empty capabilities and fixed client info. Require matching ID and valid result, then `notifications/initialized`, then `tools/call` with name `fetch` and fixed `entityUrls`. Support bounded JSON or SSE JSON-RPC responses and validated server session/protocol headers. Do not send tokens to a redirected host. Validate the tool result before inspecting the fixed entity.
- [ ] Validate exact message ID, author object ID, channel identity, navigable expected Teams link, nonempty body and timezone-aware source timestamp. Report each check as a boolean; body content is not an API response field. Handle JSON/text `structuredContent` wrappers according to the documented MCP response shapes, never infer success from HTTP alone.
- [ ] Frontend: button invokes one authenticated POST; disable while pending/after result, do not autorun on mount/refresh, and display only explicitly selected safe fields. Catch errors with fixed UI copy. Do not use storage or log the token/result.
- [ ] Run scoped backend tests, frontend tests/build, Ruff/Pyright and full Python suite/build. Commit task files and record test evidence in `/tmp/workiq-probe-task-report.md`.

### Task 2: Review, deploy, run once, and remove

**Files:** `.azure/deployment-plan.md`, local ignored environment record, task ledger; remove Task 1 files and wiring after use. Retain a small cleanup regression and sanitized outcome document.

- [ ] Review Task 1 diff independently for both spec compliance and correctness; resolve findings and rerun affected tests before deployment.
- [ ] Follow azure-validate workflow and existing deployment preflight/preview/package checks. Verify current identities, roles, replica count and single Uvicorn worker. Use the already-approved existing tenant/subscription/app.
- [ ] Set the binding's fixed start/expiry immediately before the final commit/build (expiry minus start exactly 30 minutes). Require readiness before spending the window. Follow azure-deploy checklist and `scripts/deploy_personal_tenant.sh --apply`; no new resource scope.
- [ ] Open the diagnostic view, verify Alex sign-in, click once, record safe outcome. If sign-in is required ask the user; if the window cannot be used remove the probe rather than extend it silently.
- [ ] Write a failing cleanup regression asserting temporary module/router/view absence, remove implementation and wiring, run regression and full tests/build, review cleanup, commit locally.
- [ ] Repeat azure validation/deployment for cleanup. Verify former revision inactive with zero traffic, probe absent from OpenAPI, retired route GET 404 and POST 405 under baseline SPA routing, health good, roles unchanged. Update sanitized result/cleanup record and report success or precise retrieval blocker.

## Progress

- Spec approved by user; implementation authorized.
- Task 1 implemented, independently reviewed and verified; temporary code now removed after successful single deployed fetch.
- Task 2 complete: one-shot fetch passed all checks; cleanup bc3f11a deployed as revision13, revision12 inactive/stopped, route absent and health/smoke verified. No push. See docs/deployment/workiq-mcp-probe-result.md for final evidence.
- Cleanup review reproduced baseline SPA behavior: removed API paths return GET 404 and POST 405. Acceptance checks now exercise the packaged static configuration; normal routing remains unchanged.
