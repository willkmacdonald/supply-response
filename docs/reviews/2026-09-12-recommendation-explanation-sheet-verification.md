# Recommendation explanation sheet — local verification

## Scope

Approved design: `docs/superpowers/specs/2026-09-12-recommendation-explanation-sheet-design.md`.
The explanation belongs to the recommended option, independent of the planner's
selection. The Make the decision tab now contains two main cards. Other tabs
keep their three-card order. No backend, ranking policy, approval enablement,
source destination, or Azure deployment change is included.

## Automated verification

Implementation commit: `2a8027e` (base `7a12856`). Parent independently ran
`npm test` and `npm run build` on this commit: all 325 tests in 22 files passed;
TypeScript and Vite production build passed. `git diff --check` passed. Focused
implementation RED/GREEN evidence is recorded in
`.superpowers/sdd/recommendation-sheet-task-1-report.md`.

Independent task review approved both spec compliance and code quality with no
findings. Parent reviewed the shared recommendation guard, modal lifecycle, and
unchanged selection/decision handler wiring in addition to the runtime checks.
Final independent integration review also found no actionable issues in
`7a12856..2a8027e`. No review findings remain open for this feature.

## Browser evidence

Parent ran `.tmp/recommendation-sheet-browser.cjs` against the actual frontend
components in the isolated local layout fixture. Node Playwright was used
because the existing workspace provides it; Python Playwright is unavailable.

At both 1440px and 390px:

- The single explanation action appears beside the recommended option's badge.
- Opening it after selecting the expedited shipment still explains Combined
  response and preserves the selected expedited option and decision display.
- The desktop sheet is right-aligned; the phone sheet fills the viewport.
- Native modal background exclusion and explicit Tab/Shift+Tab boundary wrapping
  keep focus within the sheet; Close and Escape return focus to its trigger.
- Desktop backdrop clicks close the sheet; clicks inside do not.
- Expanded long content scrolls independently without moving the background.
- No new requests, external navigation, page errors, approval actions, or
  horizontal page overflow occur during sheet interaction.
- The baseline/response comparison retains `$955,000 → $375,000` revenue,
  `$328,000 → $125,000` margin, and `$0 → $24,750` response cost.
- Fallback preview also opens/closes the sheet and retains sample-data labeling.

The first browser pass caught focus leaving the native dialog at a tab boundary;
explicit boundary handling was added and the same check subsequently passed.
Parent visually inspected open desktop/phone screenshots and expanded/scrolled
phone content under `.artifacts/recommendation-sheet/`.

The complete sheet browser test was rerun successfully on committed `2a8027e`.
The existing presenter-layout and USD browser checks also passed after changing
the expected decision-stage card count to two; they verified unchanged first
and second tabs, source icons, footer placement, and per-part prices.

These captures use simulated fixture data and source links. They do not prove
live Work IQ retrieval, Power BI permissions, production availability, or a
deployed Azure change. Approval stays disabled in the local layout preview.
