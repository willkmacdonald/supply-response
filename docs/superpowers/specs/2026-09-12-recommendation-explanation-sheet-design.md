# Recommendation explanation sheet

## Approved direction

Move the recommendation explanation beside the option it explains. The user
approved a pill-shaped “ⓘ Click here to understand why” button next to
“Recommended for review”, opening a desktop side sheet and a full-screen sheet
on phones. Remove the separate “Recommended response—and why” card below.

This focused amendment supersedes the earlier requirement for three cards in
the Make the decision tab: that tab now contains Compare the options and Review
and approve. The other two tabs and their card order remain unchanged.

## Interaction and content

- Show the explanation action only for the uniquely identified, consistent
  recommendation in the displayed analysis, not automatically for Combined
  response and not for whichever option the planner selects.
- Use a real button, visually distinct from the noninteractive recommendation
  badge. Allow the two pills to wrap on narrow screens without clipping.
- Open a modal sheet titled “Why this response is recommended”, naming the
  recommended response. On desktop it enters from the right with the comparison
  still partly visible behind a dimmed backdrop; below 640px it fills the screen.
- Present proposed actions, predicted impact compared with doing nothing,
  response cost, a plain-language explanation of the recorded ranking, required
  roles, and assumptions or unresolved questions. Keep detailed recorded
  comparison stages and source lineage available in disclosures.
- Explain the recommendation as the application's planning-policy result, not
  a new language-model judgment or live recalculation. Describe only ranking
  stages actually recorded; do not claim cost decided a shortage-based result.
- Retain existing validated Power BI navigation, prediction warnings, unavailable
  data messages, and subordinate source/provenance footer. Never substitute
  invented reasons when ranking details are missing.
- Opening or closing the sheet does not select, approve, reject, execute, fetch
  new evidence, or change the current analysis. The sheet follows the saved
  recommendation even when another response is selected.
- Provide a visible Close button, Escape dismissal, and backdrop dismissal.
  Clicking inside must not dismiss it. Focus starts inside, stays within the
  modal while open, and returns to the trigger on close. Background interaction
  and scrolling are blocked; long sheet content scrolls independently.
- Close/reset the sheet if the case or analysis changes so an explanation cannot
  remain associated with a different analysis.

## Missing or inconsistent recommendation

Do not display a recommendation badge/action for conflicting, duplicate, or
unresolvable recommendation identifiers. Keep a visible “Recommendation
unavailable for this analysis” message in the comparison section; preserve the
specific “No option meets the planning requirements” state when applicable.
Moving the old card must not remove these existing safeguards.

## Implementation boundary

Reuse the existing ExposurePanel content and PredictionComparison rather than
duplicating calculations or maintaining two explanation bodies. The modal
wrapper owns only presentation, focus, and dismissal. OptionComparison owns the
trigger alongside its recommended option; InvestigationFlow no longer renders
the standalone explanation card. Use existing analysis, snapshot, runtime, and
report context data without changing backend contracts.

Preserve the latest USD formatting: whole-dollar financial totals, two-decimal
per-unit prices, exact monetary policy thresholds. Do not change selection or
approval behavior, permissions, source URLs, ranking rules, or the local
preview's disabled approvals. More prominent selection feedback is a separate
follow-up, not silently included here. No Azure deployment in this change.

## Verification and review

1. Tests establish correct trigger placement and one explanation body, including
   when the recommended option is not Combined response.
2. Tests cover absent, inconsistent, duplicate, and infeasible recommendations;
   preserve baseline comparison and missing-data safety messages.
3. Opening/dismissing via button, Escape, and backdrop preserves selection and
   decision inputs and invokes no API or decision action. Test focus return,
   background exclusion, and case/analysis changes.
4. Compare sheet values and reasons with the displayed analysis; retain exact
   validated report destinations and the corrected monetary formatting.
5. Browser checks at 1440px and 390px verify placement, desktop/phone layouts,
   keyboard behavior, long-content scrolling, and no clipping or page overflow.
   Inspect screenshots of the built local preview; do not treat fixture evidence
   as live-service verification.
6. Run all frontend tests and the production build, with independent review
   between delegated implementation tasks before handoff.

## Design self-review

The approved two-card decision layout explicitly supersedes the earlier
three-card count. Recommendation, selection, and approval remain separate.
Source attribution, USD formatting, fallback truthfulness, and safety messages
are retained. No unresolved design choices or unrelated implementation scope.
