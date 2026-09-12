# Native planner acceptance — September 11, 2026

Status: **readability and read-only reopening corrected; full reporting activation
not accepted**. The original inspection below was read-only. The subsequently
authorized corrections and their verification are recorded in the release
follow-up. No business records, analyses, decisions, permissions or reporting
activation receipt were changed.

## Release follow-up — September 11–12, 2026

The initial failure notes below are retained as the baseline, not current status.
The first formatting publication (`6304b8f`) failed actual Power BI rendering;
the runtime ignored wrapping on its single-line card callout. Correction
`7b6e20e` replaced 46 string callouts with native bound paragraph textboxes.
Independent review verified exact measure, position, title and filter parity.
Native screenshots showed full statements and caveats without duplicated titles.

Read-only reopening was hardened through `ecbdf0f`; `f5191ad` additionally clears
the case picker only after successful restoration. Independent reviews passed.
The deployed app restored the exact case and analysis listed below. A refresh
preserved the URL, planning content and evidence timestamps (September 8,
15:17 UTC), with no fresh source retrieval. A complete, non-truncated network
capture contained only four GET requests: runtime, case, analysis, and a second
case identity check. A wrong-analysis bookmark failed visibly without substituting
another analysis. Explicitly choosing the original case recovered correctly and
removed the picker while keeping Find existing cases available.

The native app shows the original delivery first, then available stock and risk,
with the three left-hand planning-stage labels retained. Supplier names include
their current/alternate role. Work IQ and Microsoft Fabric provenance are below
card content, with retrieval time and Required checks passed; they do not imply
continuous monitoring. Source email and Teams links remain available. A fresh
window now supports reopening; the old pre-release tab is not proof of the new UI.

Verification evidence:

- 292 frontend tests and production build passed (existing bundle-size advisory).
- Two isolated desktop/mobile visual tests passed. Screenshots in
  `.artifacts/planner-presentation/` were inspected, including
  `desktop-original-delivery-card.png` and `mobile-recommendation-card.png`.
- Live narrow-screen DOM geometry at 390 px showed no document/card horizontal
  overflow. The native screenshot backend mis-scaled the emulated viewport, so
  those captures are **not** claimed as mobile visual proof. Emulation was reset.
- 154 final report generator/project tests passed, including locked Microsoft TOM,
  exact artifact/digest checks and publication dry run. Offline author/schema
  validation reported zero errors and warnings.
- Power BI was checked as Alex across all eight native pages. Shipment showed
  3,000 units, September 6 and the unspecified-currency caveat; transfer showed
  1,500 units, September 5 and 1.50 per unit; qualification showed incomplete
  audit/first article and September 15 explicitly not an approval/delivery date.
- The traditional overview and neutral options table rendered. Selecting Combined
  response showed 375,000 revenue at risk and 24,750 response cost. Long blockers,
  explanations and provenance wrapped. Selected source identities matched.
- A mismatched existing case/analysis reported analysis unavailable and did not
  substitute another analysis's business values.
- Resetting the report's view selection showed Select a case with blank business
  answers. Removing a URL filter alone was insufficient because Power BI retains
  the report-view slicer selection; that retained selection was explicitly reset
  before this negative check. No report definition or business data was changed.
- Native Actions and outcomes exposed overlapping chart grouping keys, even with
  no observations. Reviewed correction `4748a91` replaces that chart in the same
  slot with Result metric / Outcome type / Variance on one table axis. Calculations,
  visibility and identity filters, SQL, and Actual/Simulated distinctions are
  unchanged. The published page renders an empty table and No outcomes recorded,
  without the original grouping error. This is not populated-outcome proof.
- The republished report still binds to model
  `2100a769-d718-47b7-9715-7f4e804f1c8a` with one SQL datasource. Existing resource
  IDs, roles, scale 0–2 and the absent reporting activation receipt are preserved.
- Final app revision `ca-sr-demo--0000025` is ready and receives 100% of traffic.
  Image: `sha256:dfd3e0f566ec0d929a0cc5fbe77a8a92697850f7a91fd91df24c6f4d6b29b4dc`.
  Health reports live mode, Fabric SQL, schema version 12. The final refresh again
  preserved the complete planning content and September 8 analysis timestamp,
  kept Find existing cases, and did not restore the dismissed picker.

Native accessibility snapshots retained generic Visuals are loading markers even
while screenshots showed populated values and the corrected table. This record
therefore claims visible rendered-state verification, not completion of every
background report query or a performance benchmark.

### Remaining reporting acceptance gaps

The old analysis's app snapshot contains 4,000 available component units, but its
report has no supported inventory record detail. Customer-order source rows are
also unavailable in the report, although baseline risk metrics render. The report
shows unavailable rather than zero or unrelated records. This is an unresolved
projection/coverage gap, not successful app/report parity.

Existing within-case historical-analysis and populated-outcome fixtures are also
missing for the separate activation gate. No new analysis, decision, simulation,
source data or receipt was created to hide these limitations. New card-to-report
links remain inactive with an explanatory message. Do not describe the entire
reporting experience or its historical/outcome coverage as fully accepted.

## Original inspection (before corrections)

## Existing context

- Case: `RL-CASE-b525c3d4-47c9-429b-804d-3a893e85d778`.
- Analysis: `RL-ANALYSIS-de5f07b1-2cb0-496b-9a11-b29573f40bd4`.
- Report: `e7611c8c-c887-443f-858a-13b1044bb4b9`.
- Power BI profile visibly confirms Alex Morgan, `agent@willmacdonald.com`.
- The original demo tab remains intact. It still renders the legacy Evidence
  items screen with platform badges above the headings. This proves that tab is
  displaying the old experience, not why it remained on that experience.

## Passed observations

Alex can render the published report. Selecting the exact case in the case
selector populated its matching analysis and corrected narratives: 8,000 units
originally due at Chicago on September 3, a separate 3,000-unit September 6
shipment, a 1,500-unit Dallas transfer and pending alternate-supplier qualification.
The selected case shows available stock unavailable; this was not replaced with
another case's stock or treated as a proven new data defect.

A manually constructed shipment URL using the implemented identity encoding and
the exact case, analysis, record family and record ID opened successfully. It
rendered `RL-ALPHA-OPTIONAL-3000`, 3,000 component units, September 6, 2026 and
7.50 per unit with currency unspecified. The source-details table matched both
case and analysis IDs. This is a direct destination check, **not** proof of an
enabled click from the updated app; its new links remain inactive.

## Failed visual check

The populated overview truncates business answers with ellipses. The focused
shipment page also truncates incremental-cost wording and the explanation of
what the proposed shipment means. This persists with both report side panes
closed, at the resulting 75% fit-to-page scale. Native accessibility/DOM text
contains the full answers, so the loss occurs in visual presentation rather than
in the returned answer string. Titles also repeat as card category labels.

`fabric/report_pages.py:307` uses the shared `cardVisual` helper for these answers;
it sets font sizes and a visible label but no explicit wrapping property. This
identifies the shared presentation path to investigate, not a verified fix or
proof of the correct Microsoft formatting property. Do not shorten away important
qualifiers merely to make a single line fit.

## Fresh-app inspection blocker

A separate fresh tab loaded the current app. Existing Alex sign-in completed
without new consent or credentials. Its initial screen offers only **Create
showcase case**. The old tab was not refreshed because it would lose its current
in-memory context. No case was created.

Source inspection confirms `useCaseWorkspace` initializes case and analysis to
null and retrieves runtime status only; the frontend API has no read-existing-case
workflow. Backend read routes exist, but their presence is not an implemented or
accepted UI restoration path. A supported read-only reopen workflow is a proposed
follow-up, not a change made under this verification request.

Consequently the updated populated app, footer placement, all eight native pages,
traditional/assisted route parity, and end-to-end card clicks are not accepted.
The previously recorded lack of within-case historical analyses also remains a
separate acceptance limitation. No receipt was issued or installed. Keep the
new reporting links inactive until the outstanding checks pass.
