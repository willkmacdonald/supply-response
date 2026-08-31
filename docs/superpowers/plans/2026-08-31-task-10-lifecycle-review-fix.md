# Task 10 Lifecycle Review Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Task 10 workspace progress through real Task 9 pending action planning and playback states when only Uvicorn and Vite are running.

**Architecture:** A FastAPI lifespan-owned runtime loop advances canonical action-planning outbox work and explicitly-started playback through existing idempotent services, then shuts down cleanly. The browser only polls canonical Decision, playback, action, draft, and observation GET routes with bounded waits; it never executes worker logic or fabricates state.

**Tech Stack:** Python 3.12+, FastAPI lifespan, asyncio/thread offloading, SQLAlchemy/SQLite, React 19, TypeScript, Vitest/Testing Library.

## Global Constraints

- Preserve Task 7 targeted/global outbox semantics, Task 8 playback/event idempotency, and Task 9 auth/contracts.
- Production playback uses the existing `RealClock` exact schedule; tests inject `ImmediateClock` and incur no real delay.
- Keep `useCaseWorkspace` as the sole browser orchestrator and `App.tsx` as a composition root.
- Do not add Task 11 Playwright files, Teams, live adapters, Power BI, deployment, or Task 12+ integrations.
- Pin jsdom to a release supporting Node 20+ and commit the npm lockfile; do not modify `uv.lock`.

---

### Task 1: Lifespan-owned action-planning progression

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/dependencies.py`
- Test: `tests/api/test_runtime_progression.py`

**Interfaces:**
- Consumes: `ApplicationServices.planning_worker.process_next_outbox()` and the existing claimed-outbox transaction semantics.
- Produces: an app-local runtime progression loop started/stopped by FastAPI lifespan.

- [x] Write an API test that enters `TestClient(create_app(...))`, records an approved Decision, and condition-waits until canonical GET Decision reports `complete`, then asserts five actions and one unsent draft.
- [x] Run `.venv/bin/pytest -q tests/api/test_runtime_progression.py -k planning` and confirm it fails because no lifespan worker advances the pending outbox.
- [x] Add a runtime coordinator owned by `ApplicationServices`/`main.py` lifespan that processes global outbox work off the event loop, wakes promptly, and stops cleanly.
- [x] Re-run the focused test and existing action-planning/outbox tests; confirm targeted retry behavior remains unchanged.

### Task 2: Nonblocking, idempotent playback progression

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/dependencies.py`
- Modify: `apps/api/app/routes/execution.py`
- Test: `tests/api/test_runtime_progression.py`

**Interfaces:**
- Consumes: explicit authenticated `POST /api/decisions/{id}/playback` and `PlaybackService.run_to_completion(playback_id)`.
- Produces: one background completion run per persisted in-progress playback, including recovery after app restart.

- [x] Write an API test that measures the playback POST returning before completion, repeats POST safely, and condition-waits on canonical playback GET until `completed`, then asserts ten `Simulated` observations with no duplicate events.
- [x] Run the focused playback test and confirm it fails because POST only persists an in-progress playback.
- [x] Queue persisted in-progress playback IDs for the lifespan coordinator after explicit POST; on startup recover any persisted in-progress playback. Track active runs to avoid duplicate concurrent execution and use the service's idempotent persistence methods.
- [x] Re-run the focused test plus `tests/execution/test_playback.py` and observation/action-attempt tests.

### Task 3: Canonical browser polling

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/hooks/useCaseWorkspace.ts`
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/api.test.ts`

**Interfaces:**
- Consumes: canonical GET Decision and GET playback routes plus existing action/draft/observation endpoints.
- Produces: bounded pending-to-complete/failed transitions owned by `useCaseWorkspace`.

- [x] Change the UI fixture so approval returns `pending`, GET Decision returns pending then complete, playback POST returns `in_progress`, and GET playback returns in-progress then completed.
- [x] Run the focused happy-path test and confirm actions/outcomes never appear with the current hook.
- [x] Add typed `decision()` and `playback()` GET methods. Implement a bounded condition poll helper that reads only canonical server state, stops on complete/failed/timeout, and leaves readable pending/error UI state.
- [x] Re-run happy path, planning-failure, progressive-visibility, simulated-label, and API request-shape tests.

### Task 4: Accessible initialization and Node 20 dependency

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`

**Interfaces:**
- Consumes: `workspace.operation` values `initializing` and `creating`.
- Produces: a live status throughout initial create; jsdom package metadata compatible with Node 20.

- [x] Add a deferred-create UI test asserting a `role=status` announcement remains visible while `operation` is `creating`; run it and confirm the current announcement disappears.
- [x] Render the same accessible live initialization status for both initialization states and re-run the focused test.
- [x] Pin jsdom to a Node-20-compatible major, regenerate only the npm lockfile, and verify the installed package `engines.node` admits Node 20.

### Task 5: Verification, report, and commit

**Files:**
- Modify: `.superpowers/sdd/task-10-report.md` (ignored evidence artifact)

- [x] Run focused runtime/API/execution tests, `npm --prefix apps/web test`, and `npm --prefix apps/web run build`.
- [x] Run `.venv/bin/pytest -q`, scoped Ruff/Pyright commands if configured, `git diff --check`, and confirm `uv.lock` is unchanged.
- [x] Self-review lifespan ownership, shutdown, restart/idempotency, bounded polling, labels, accessibility, and scope.
- [x] Append `## Review Fix` evidence to the Task 10 report.
- [ ] Commit with a focused Task 10 lifecycle-fix message and do not push.
