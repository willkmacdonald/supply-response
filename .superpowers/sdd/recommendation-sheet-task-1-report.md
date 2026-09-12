# Task 1 report — recommendation explanation sheet

## Outcome

Implemented the approved recommendation explanation as a native modal side sheet attached to the uniquely resolved recommended option. The standalone decision-tab card is removed, leaving the approved two-card layout. Recommendation, selection, approval, reporting, and monetary formatting remain independent and unchanged.

## TDD evidence

### RED

Command:

`cd apps/web && npx vitest run src/components/RecommendationSheet.test.tsx src/components/InvestigationFlow.test.tsx`

Result: exit 1. The new suite failed because `recommendationState` and the recommendation-sheet behavior did not exist; the existing investigation suite remained 9/9 green. After the first implementation pass, the focused run exposed the expected obsolete standalone-card assertions and missing interaction details.

### GREEN

Focused command:

`cd apps/web && npx vitest run src/components/RecommendationSheet.test.tsx src/components/InvestigationFlow.test.tsx`

Result: exit 0; 2 files, 14 tests passed.

Full command:

`cd apps/web && npm test`

First full result: exit 1; 323 passed and 2 obsolete expectations failed (the old standalone heading and a report link that now lives inside the sheet). Those affected tests were updated to assert the approved interaction without weakening destination checks.

Final full result: exit 0; 22 files, 325 tests passed.

Build command:

`cd apps/web && npm run build`

First build result: exit 1 on two test-fixture TypeScript inference errors. The fixture annotations were corrected.

Final build result: exit 0; TypeScript and Vite production build completed.

## Files

- Added `apps/web/src/components/RecommendationSheet.tsx`
- Added `apps/web/src/components/recommendationState.ts`
- Added `apps/web/src/components/RecommendationSheet.test.tsx`
- Modified `OptionComparison.tsx`, `ExposurePanel.tsx`, `InvestigationFlow.tsx`, `PredictionComparison.tsx`, and scoped styles
- Updated affected integration/regression tests in `InvestigationFlow.test.tsx`, `reportCardLinks.test.tsx`, and `App.test.tsx`

## Self-review

- Recommendation resolution fails closed for absent/conflicting/duplicate identities, infeasible or contradictory ranking state, blocked/non-executable/inactive options, and invalid predictions.
- The trigger follows the saved recommendation, not the selected option, and invokes no selection or decision handler.
- Open state is bound to case plus analysis identity and resets when either changes.
- The wrapper owns native modal lifecycle, Escape/Close/backdrop dismissal, initial focus, explicit focus-boundary wrapping, focus restoration, and body-scroll restoration.
- The reused explanation body preserves predicted comparison values, recorded assumptions/roles, exact report destination, source lineage, and unavailable-detail messages.
- Plain-language ranking copy comes from the existing recorded-stage formatter and explicitly describes a saved policy result rather than a new AI judgment or live recalculation; raw thresholds and identifiers stay in disclosure content.
- No backend, ranking policy, permission, approval-enablement, source URL, deployment, preview, plan, or spec changes were made.

## Concerns

None known. Parent browser acceptance separately passed desktop and phone layouts, native modal activation, focus wrap/return, Close/Escape/backdrop dismissal, inside-click persistence, independent scrolling, selection persistence, and zero network/action side effects.
