# Task 2 implementation report

## Status

DONE — ready for independent Task 2 spec and quality review.

## What changed

- Added a typed `ApiRequestError` boundary. Only `LIVE_SOURCE_UNAVAILABLE` maps to the approved safe message; every other HTTP response or arbitrary exception maps to `The request could not be completed.` Raw response bodies, HTML, exception fields, and mutable `Error.message` values do not reach the visible workspace error.
- Reworked decision receipts around the recorded decision: friendly approved/rejected state, response resolved only against the matching analysis, human-readable required roles, rejection reason, and IDs/runtime/selected option in expandable decision details.
- Preserved standing-authorization meaning with `Authorization recorded` and `Authorization still required`.
- Added closed, own-key-safe maps for known action, status, draft, and outcome metric kinds. Unknown open-string values render honest fallback labels; raw kinds and IDs remain in expandable details.
- Kept drafts explicitly unsent, used a specific supplier-recovery label only for proven artifact kinds, and removed invented draft completion claims.
- Changed supported playback presentation to `Simulated results`, `Simulation in progress`, and a terminal failure message that preserves the no-second-simulation restriction without advising creation of a new Case.
- Aligned post-investigation sequence labels to steps 4 and 5.
- Moved the prominent Case ID into expandable `Case details`, preserving the identifier and existing report navigation behavior.
- Preserved HTTP methods, request bodies, idempotency headers, retry controls, approval/action controls, runtime gates, decision blocking, polling, and all source contracts.

## TDD evidence

### RED

Initial command:

`npm --prefix apps/web test -- --run src/api.test.ts src/components/DecisionPanel.test.tsx src/components/ExecutionPanel.test.tsx src/components/LiveSafety.test.tsx`

Result: 10 expected failures and 227 passes across the 237 tests selected by the project script. Failures showed raw API diagnostics, raw decision/action/draft/playback copy, and missing recorded-decision receipt behavior.

Case identity RED:

`npm --prefix apps/web test -- --run src/components/LiveSafety.test.tsx`

Result: the new `Case details` assertion failed because `.case-id` was still prominent.

Review-correction RED:

`npm --prefix apps/web test -- --run src/api.test.ts src/components/DecisionPanel.test.tsx src/components/LiveSafety.test.tsx`

Result: 6 expected failures proved inherited error-map keys, mutable error messages, cross-analysis option resolution, omitted selected-option diagnostics, and old terminal playback copy.

Open-string map RED:

`npm --prefix apps/web test -- --run src/components/ExecutionPanel.test.tsx src/components/LiveSafety.test.tsx`

Result: 2 expected failures plus React warnings proved that `constructor`/`toString` could resolve inherited functions instead of honest fallback labels.

### GREEN

Focused correction command:

`npm --prefix apps/web test -- --run src/components/ExecutionPanel.test.tsx src/components/LiveSafety.test.tsx`

Result: 18 test files passed, 242 tests passed, no test warnings.

Fresh full suite:

`npm --prefix apps/web test`

Result: 18 test files passed, 242 tests passed.

Fresh build:

`npm --prefix apps/web run build`

Result: TypeScript and Vite build succeeded; 191 modules transformed. Vite retained its existing advisory that a generated chunk is larger than 500 kB.

The first post-change build correctly found a test-fixture-only `never` spread error in `LiveSafety.test.tsx`; the fixture was corrected at its source, then the complete build and test commands above passed freshly.

## Files changed

- `apps/web/src/App.test.tsx`
- `apps/web/src/api.test.ts`
- `apps/web/src/api.ts`
- `apps/web/src/components/CaseHeader.tsx`
- `apps/web/src/components/DecisionPanel.test.tsx`
- `apps/web/src/components/DecisionPanel.tsx`
- `apps/web/src/components/ExecutionPanel.test.tsx`
- `apps/web/src/components/ExecutionPanel.tsx`
- `apps/web/src/components/LiveSafety.test.tsx`
- `apps/web/src/components/OutcomePanel.tsx`
- `apps/web/src/hooks/useCaseWorkspace.ts`

Implementation checkpoint: `9354907 fix(web): clarify planner lifecycle states`.

## Self-review

- Confirmed the selected response comes from `decision.selected_option_id` only when `decision.analysis_id` matches the displayed analysis; mutable selection cannot rewrite the receipt story.
- Confirmed rejected decisions do not present the current mutable selection as approved.
- Confirmed inherited JavaScript object keys cannot bypass safe error or open-string display fallbacks.
- Confirmed arbitrary HTTP JSON/HTML and arbitrary client exceptions do not appear in the visible alert.
- Confirmed disabled decision controls remain disabled, trimmed rejection reasons still submit unchanged, and retry/playback gates are unchanged.
- Confirmed the parent-owned `docs/reviews/2026-09-09-planner-spec-conformance.md` remains untracked and untouched.

## Concerns

- The successful build emits the existing Vite bundle-size advisory; Task 2 did not alter bundling architecture.
- This is local headless/type/build verification, not live UI acceptance. No live case, decision, action, playback, external system, permission, deployment, push, or merge operation was performed.
