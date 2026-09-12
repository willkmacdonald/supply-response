# Native readability and read-only case reopening

## Approved scope and success criteria

The user approved correcting the native Power BI truncation and adding a way to
reopen an existing case, with Codex review and actual visual proof. This is a
bounded correction to the approved evidence-records specification, not a new
dashboard design. Existing isolated branch: `codex/planner-experience`.

Success means complete business statements render legibly without duplicate
captions, and a fresh app window can load and refresh an existing case without
creating a case, running an analysis, approving anything, or starting execution.
Native screenshots and identity/timestamp checks are required in addition to tests.

## Global Constraints

- Preserve exact case, analysis, record, option, and decision identity. Never
  substitute the latest case or a different analysis for a bookmarked analysis.
- Reopening reads existing stored results; it does not retrieve fresh evidence or
  change retrieval timestamps. Clearly explain this in normal planner language.
- Reopening must issue GET requests only. No automatic creation, analysis,
  approval, retry, simulation, or other business mutation.
- Honor server-supplied controls. Do not expose actionable mismatched or partially
  restored state. Keep authentication, citation trust, approval, and receipt gates.
- Preserve business facts, units, caveats, calculations, fictional provenance,
  exact report filtering, bottom-of-card platform/status attribution, and the
  traditional versus AI-assisted distinction.
- Publish only to existing authorized demo resources after validation. No
  push/merge, new grants, new business records, or report activation receipt.

## Task 1: Reopen existing case safely

Files: `apps/web/src/api.ts`, `apps/web/src/hooks/useCaseWorkspace.ts`,
`apps/web/src/App.tsx`, a focused `components/ExistingCases.tsx` component if useful,
related tests/styles, and `docs/demo/traditional-and-assisted-walkthrough.md`.
Keep backend unchanged unless a concrete contract gap is raised for review.

1. Add RED tests for the visible Reopen existing case flow using existing
   authenticated GET `/api/cases`, GET `/api/cases/{id}`, and current-analysis GET.
   Inspect actual API contracts first. Test an analyzed case, a case without an
   analysis, and a case with an existing decision/execution state.
2. Provide a clearly labeled existing-case picker (human-readable state and
   recorded date plus exact case ID to distinguish repeats). Load the list on
   explicit request; do not introduce unneeded polling. Show loading, empty,
   failure, and retry states. Do not silently select a different case.
3. Restore matching analysis and, where applicable, existing decision, actions,
   drafts, playback, and observations through GET only. Treat an absent optional
   playback distinctly from an actual read failure. Verify returned case and
   analysis/decision relationships before presenting them. Select the recorded
   decision's option when applicable, not a different recommendation.
4. Put case ID and the loaded analysis ID in the URL using history replacement,
   preserving unrelated query parameters. Refresh restores that same context.
   A bookmark whose analysis is no longer current must fail visibly rather than
   silently load a newer analysis. Use the existing current-analysis endpoint and
   check identity, including a second case read if necessary to detect changes
   during restoration. A user can explicitly choose the case anew to load its
   current analysis. No new historical-analysis API is needed for this correction.
5. Keep restoration atomic and guard overlapping requests/unmounts. Block other
   workspace operations during reopening. On failure do not leave stale actionable
   state. URL initialization must not overwrite an in-flight user operation.
   Existing create/analyze actions should update the URL only after success.
6. Test no POSTs on reopen/refresh; invalid/unknown IDs; mismatched/superseded
   analysis; failed related-state GET; concurrent changes; duplicate clicks and
   late responses; controls retained; timestamps unchanged; URL preservation.
7. Run focused tests during iteration, then `npm test -- --run` and `npm run build`
   in `apps/web`. Update walkthrough with read-only reopening and its limitations.
   Commit only this task's files. Record RED/GREEN evidence in the task report.

## Task 2: Complete, readable native Power BI statements

Files: `fabric/report_pages.py`, generator/project tests, generated report assets,
and generated `apps/api/app/_reporting_artifact.py` digest as required.

1. Confirm native failure: the current cardVisual renders long DAX strings as one
   line with ellipses and repeats the measure label below the visual title.
2. Verify supported formatting with official Microsoft documentation or an
   authored visual definition. Do not invent object/property names. Prefer a
   documented multiline presentation for narrative values; preserve data binding.
3. Write failing generator tests that assert the chosen wrapping/label behavior
   and appropriate space for business paragraphs. Distinguish narratives from
   compact numeric values where necessary; no hidden full-text-only workaround.
4. Implement the smallest common formatting correction, regenerate artifacts and
   digest, run generator/project/author validation. Do not change business DAX or
   SQL merely to shorten text. Check all eight pages, including metadata/caveats.
5. Review code/spec alignment independently before publication.

## Task 3: Release and native acceptance

1. Record fresh rollback definitions and app revision. Follow existing Azure
   validation/deploy instructions and the guarded same-resource release path.
2. Publish corrected report, then corrected app after local validation. Keep
   receipt absent and gated navigation honest until its separate gate is met.
3. As Alex, reopen the already existing test case and refresh. Compare exact case
   ID, analysis ID, evidence values and retrieval timestamps before/after. Do not
   create another business record to test. Inspect desktop and narrow viewport.
4. Inspect actual Power BI screenshots for all eight pages, filtered supporting
   records, empty/mismatched context, selected analysis, and traditional/AI parity.
   Readable DOM strings alone are not visual proof. Fix visible issues and repeat.
5. Save proof and a concise acceptance record. Explain any missing historical
   fixture/activation gate honestly; never manufacture data or mint a receipt to
   make the checks appear complete.

## Progress

- Baseline: `a78d1f7`; native findings documented in
  `docs/reviews/2026-09-11-native-planner-acceptance.md`.
- Task 1 implemented through `ecbdf0f`; independent spec/quality review passed.
  292 frontend tests, production build and two isolated desktop/mobile visual
  tests passed. Deployed exact-case reopening, refresh, wrong-analysis rejection
  and explicit recovery passed. `f5191ad` removes the picker after successful
  restoration; independently reviewed and verified live.
- Task 2 implemented through `7b6e20e`. The first formatting-only attempt
  (`6304b8f`) failed native rendering and was replaced by documented dynamic
  textboxes. Independent review confirmed all 46 exact measure bindings and
  unchanged titles, positions and filters. 153 report tests plus schema/author
  validation and publication dry run passed.
- Task 3's bounded correction release and native checks are complete; the separate
  full reporting activation gate remains open. The existing report/model were
  republished and matching app revision 25 is ready. Actual native
  shipment rendering now shows the full cost caveat, explanatory paragraph and
  provenance; the nine-card overview wraps all populated answers. The remaining
  pages and negative selections were checked. Native testing found an outcome
  chart grouping failure; reviewed `4748a91` replaces that one chart with a table,
  preserving all measures and identity/visibility filters. Final 154 report tests
  passed; native no-outcome state renders correctly. The reporting receipt remains
  empty: missing historical fixtures and inventory/order report coverage prevent
  full activation acceptance. See the native acceptance record for exact limits.
