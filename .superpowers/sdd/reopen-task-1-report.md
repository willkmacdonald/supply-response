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
