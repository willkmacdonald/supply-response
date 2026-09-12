# Task 1 report: read-only case reopening

## Outcome

Implemented an explicit existing-case picker and atomic, GET-only restoration of
the current saved case context. The UI presents planning state, recorded time,
and exact case ID; restores current analysis, governing decision, recorded option,
actions, drafts, optional playback, and observations; and preserves unrelated URL
parameters while recording exact case and analysis IDs.

Restoration validates case, analysis, decision, option, and related-record identity.
It performs a second case read to detect projection changes, rejects superseded
analysis bookmarks, coalesces duplicate reopen requests, guards unmount/late
commits, clears actionable state on failure, and distinguishes absent playback
(404) from a failed read. Creating and analyzing update URL context only after a
successful response. No backend files were changed.

## TDD evidence

RED command:

`cd apps/web && npm test -- --run src/App.test.tsx`

Observed: 3 new tests failed for the missing **Find existing cases** control and
missing superseded-bookmark alert; 246 existing tests passed. This was the expected
feature-missing failure.

GREEN focused command:

`cd apps/web && npm test -- --run src/App.test.tsx`

Observed after implementation: 18 test files passed, 249 tests passed. Added
decision/related-state and atomic-failure coverage, then re-ran during refinement:
18 test files passed, 251 tests passed.

Final verification commands:

`cd apps/web && npm test -- --run`

Observed: 18 test files passed, 251 tests passed, 0 failed.

`cd apps/web && npm run build`

Observed: TypeScript and Vite production build completed successfully; 193 modules
transformed. Vite retained the pre-existing informational chunk-size warning.

## Changed task files

- `apps/web/src/api.ts`
- `apps/web/src/hooks/useCaseWorkspace.ts`
- `apps/web/src/App.tsx`
- `apps/web/src/App.test.tsx`
- `apps/web/src/components/ExistingCases.tsx`
- `apps/web/src/components/InvestigationFlow.test.tsx`
- `apps/web/src/components/reportCardLinks.test.tsx`
- `apps/web/src/styles.css`
- `docs/demo/traditional-and-assisted-walkthrough.md`
- `.superpowers/sdd/reopen-task-1-report.md`

## Self-review and concerns

- All reopening network paths use the existing authenticated GET helper. No live
  calls, deployment, push, or business writes were performed.
- Server controls and stored timestamps are retained unchanged.
- The current backend intentionally offers only current-analysis retrieval, so a
  superseded bookmark fails and requires an explicit picker selection for current
  context; historical analysis reopening remains unsupported and is documented.
- Verification reports Vite's existing bundle-size advisory only; it is unrelated
  to reopening correctness.

## Review correction (2026-09-11)

The initial implementation above had review-confirmed lifecycle, overlap, and
server-control defects. This correction supersedes its broad claims about those
areas and about treating every playback 404 as optional.

### Implementation

- StrictMode effect setup now establishes a fresh startup and cleanup invalidates
  the previous operation. An abandoned runtime response cannot overwrite a newer
  startup, and both picker and bookmarked restoration complete under StrictMode.
- One synchronous token gate covers initialization, listing, restoration, create,
  analysis, decision, planning, child-action retry, and playback. Every asynchronous
  mutation commit and completion verifies its token. Polling stops after unmount.
- Duplicate reopening coalesces by case and requested analysis; a distinct busy
  request receives visible wait feedback. Existing playback coalescing remains.
- Picker, option selection, approval/rejection, planning retry, and playback UI
  respect workspace activity. Saved decide, retry_action_planning, and
  start_playback controls govern UI and handlers. Evidence/citation blocking is
  also checked by decision handlers. Restoration never updates saved controls.
- Only a 404 with PLAYBACK_NOT_FOUND is optional. DECISION_NOT_FOUND is fatal.
  Case-only bookmarks restore the case's current saved analysis. Case path
  segments are encoded so malformed IDs cannot become another endpoint.
- Atomic restoration also checks analysis material/evidence identity, decision
  material hash, draft-to-action links, and observation-to-playback/action links.
  A decision projection without analysis is refused instead of silently dropped.
- Supporting OptionComparison/InvestigationFlow and two existing fixture tests
  are in scope to propagate the activity barrier and provide explicit server
  permission in tests that exercise enabled decision controls.

### RED/GREEN evidence

All commands ran from apps/web using local mocked requests only.

1. `npm test -- --run src/App.test.tsx -t 'reopening lifecycle'`:
   initial RED reported 7 failures / 21 skipped in App.test.tsx. The StrictMode
   tests could not find the restored response and showed a stuck reopening state;
   initialization overlap timed out because listing was incorrectly admitted.
   Later failures in this first batch were affected by the unresolved act timeout.
   After the gate/lifecycle/control correction, six passed and one exposed a test
   fixture reusing a consumed Response; cloning its deferred response fixed that.
2. `npx vitest run src/App.test.tsx -t 'reopening lifecycle'` after identity/UI
   coverage: RED 8 failed, 17 passed, 21 skipped. Four failures showed accepted
   mismatched material, evidence, draft, or observation state; malformed ID path
   interpolation and enabled option selection supplied two further genuine REDs.
   Two assertions were adjusted to accept the existing safe superseded-analysis
   error for analysis mismatches. GREEN targeted App/DecisionPanel/InvestigationFlow:
   3 files passed, 58 tests passed.
3. `npx vitest run src/App.test.tsx -t 'shared gate|disabled saved|late mutation|stops planning'`:
   RED 1 failed, 10 passed, 46 skipped: unmounted planning made 6 requests instead
   of 5. Adding a lifecycle check before polling reads fixed it. Subsequent
   lifecycle target: 36 passed, 21 skipped.
4. `npx vitest run src/App.test.tsx -t 'decision projection with no analysis'`:
   RED 1 failed / 59 skipped because error was null; GREEN 1 passed / 59 skipped
   after rejecting the inconsistent projection.

Additional passing coverage verifies exact timestamps/controls across refresh,
GET-only bookmarks and picker, unknown/malformed IDs, missing case ID, second-read
projection changes, initialization and listing overlaps, all seven mutation
operation overlaps, duplicate/distinct fast requests, late list/restoration/
mutation responses, StrictMode abandoned startup, picker loading/failure/retry/
empty states, server-disabled planning/playback/decision handlers and UI, and
specific optional playback errors. Existing playback double-click tests pass.

### Final verification and self-review

Final `npm test -- --run`: 18 test files passed; 290 tests passed; exit 0.
Final `npm run build`: TypeScript and Vite passed; 193 modules transformed;
exit 0. Existing >500 kB chunk advisory remains (513.38 kB main JS).
`git diff --check`: exit 0, no whitespace errors.

Self-review checked every asynchronous mutation response and completion against
the operation token and confirmed the startup handoff cannot release restoration.
Restoration performs GET requests only and commits all state together; it does
not poll or automatically resume pending business operations. No backend change,
live call, deployment, push, or merge was performed. Native acceptance remains
the parent's separate release task. Historical-analysis endpoint limitations
remain unchanged.
