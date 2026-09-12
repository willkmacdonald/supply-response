# Expired-session recovery implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development and test-driven-development; review the complete correction before release.

**Goal:** Renew an old browser session correctly and offer a safe, understandable sign-in recovery when renewal fails.

**Architecture:** Keep the registered `/auth/callback` URL. Route that path to the installed MSAL v5 redirect bridge before importing/rendering the application. Keep session-recovery state in AuthProvider, block authenticated operations while recovery is required, and preserve mounted planning state until navigation.

**Tech Stack:** React, TypeScript, MSAL Browser 5.20.0, Vitest, Playwright, existing Azure Container App.

## Global constraints

- No new case, analysis, decision, action, simulation, or source-data writes.
- No changes to tenant, scopes, permissions, app registration, licensing, or reporting.
- Never expose authentication responses, tokens, raw identity errors, or callback URL contents.
- Preserve the current case URL through sign-in; never automatically replay a failed POST.
- Use ordinary language and an explicit **Sign in again** control.
- Keep fallback mode working, and preserve current initialization retry behavior.

## Evidence

The stale browser attempted authorization, loaded `/auth/callback`, then booted the whole SPA and requested `/api/runtime`, but never requested `/api/cases`. A fresh private sign-in works. The installed MSAL 5.20.0 redirect bridge broadcasts silent responses and restores the originating URL for redirect responses. Current `main.tsx` always mounts AuthProvider/App instead. Current AuthProvider only handles InteractionRequiredAuthError; other renewal errors become generic workspace failures.

Microsoft reference: https://learn.microsoft.com/en-us/entra/msal/javascript/browser/redirect-bridge . Check installed implementation in `node_modules/@azure/msal-browser/dist/redirect_bridge/index.mjs`; do not use a v4 blank-page workaround with v5.

### Task 1: Correct callback and add recoverable session state

**Files:** `apps/web/src/main.tsx`, new bootstrap/callback module if needed, `apps/web/src/auth/AuthProvider.tsx`, `apps/web/src/api.ts`, corresponding tests. Keep changes cohesive and small.

- [ ] Reproduce callback boot behavior and renewal failure with failing tests before changing production code. MSAL/network boundaries may be mocked; tests must exercise real bootstrap/provider/API behavior.
- [ ] On the exact configured callback path, call `broadcastResponseToMainFrame` without constructing AuthProvider/App. Normal paths still start the application. A callback failure displays only safe guidance, never raw details. Keep existing registered path and full-page sign-in handling functional.
- [ ] On silent renewal failure, show **We couldn't renew your sign-in. Sign in again to continue.** (not an unproven claim that every failure means expiration). Show **Sign in again**; keep planning state mounted but inaccessible during recovery. Do not hide a failed request behind a misleading missing-data message.
- [ ] Reject token acquisition while recovery is required. Never return null in Entra mode after a failed renewal, and never send an unauthenticated request or automatically replay a POST.
- [ ] Clicking recovery starts one interactive sign-in for the existing account/API scope, preserving the current case URL. Deduplicate concurrent clicks; a failed redirect remains recoverable. Do not auto-redirect users without letting them read the recovery notice.
- [ ] Tests cover cached token success, InteractionRequiredAuthError, timeout/generic renewal failures, concurrent failures/clicks, redirect failure, missing active account, successful initialization, fallback, state/URL preservation, and GET/POST blocked on auth failure. No raw identity details visible.
- [ ] Run focused tests, full frontend tests, and production build. Record RED/GREEN evidence in `.superpowers/sdd/session-recovery-report.md`; commit only scoped files after self-review.
- [ ] Independent review of spec compliance and code quality; resolve Important findings before release.

## Verification and release

- [ ] Verify the built callback with a real browser and synthetic auth response: bridge runs, no dashboard/API calls, no credential logging. Verify interactive return preserves original case URL using isolated synthetic browser storage, not user credentials.
- [ ] Verify the recovery notice in a browser with a controlled failing authentication client and preserved planning state; retain visual proof.
- [ ] Follow existing Azure validation/deployment gates for the same app only; report code completion separately from deployment and real Microsoft sign-in acceptance.

## Progress

Plan created from the observed failure and user's approval on September 12. Reporting gap work is separate and unchanged.

Task 1 complete: implementation `5bbb75b`, independent session_recovery_review
approved with no findings. Fresh parent 305 tests/build passed. Chromium checked
real MSAL bridge in development and production bundles and the full recovery UI
at 1280px/390px; screenshots inspected. Initial UI browser test exposed the token
provider registration ordering issue; corrected and retested successfully.
Azure validation workflow complete for the same existing app. Deployment and
real Microsoft sign-in return acceptance are still pending.
