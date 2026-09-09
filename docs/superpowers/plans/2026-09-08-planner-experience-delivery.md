# Planner Experience Delivery Sequence

Approved spec: [Evidence records and case dashboard](../specs/2026-09-08-evidence-records-and-case-dashboard-design.md).

This is the coverage and sequencing map; the checkpoint below distinguishes
local implementation from live acceptance. Detailed executable plans are scoped
to independently testable stages. Keep the current working deployment intact
until coordinated release.

## Current checkpoint

Stages 1–2 are implemented and reviewed in the isolated planner-experience branch;
169 frontend tests and the production build pass. Stage 3 is implemented through
`255646d`, with independent review between its six tasks. Its dedicated SQL gate
passed 58 reporting tests plus 12 deployment-contract tests, with a separate
full saved-demo-payload acceptance test also passing. See the
[reporting execution record](2026-09-08-saved-analysis-reporting.md#execution-evidence-and-remaining-release-gate).

These changes have not been deployed. Stage 4 is implemented locally: the exact-context
URL builder and five saved-report SELECT projections are implemented and
independently reviewed through `ab25ae9`. The expanded actual SQL gate passes
126 tests, including collection completeness and all five SELECT result-type
contracts. Native page/model artifacts and preflight are implemented and
independently reviewed through `f0a0ff7`: 134 report/model/schema checks pass with
the real Microsoft TOM parser, and the official offline visual validator reports
zero errors and zero warnings. These do not execute DAX or prove native rendering.
Report activation and mounted card links are implemented and independently
reviewed through `cecc1ef`: 204 frontend tests/build and twelve desktop/mobile
browser variants pass. No reporting receipt is installed. The
[traditional walkthrough plan](2026-09-09-traditional-walkthrough.md) is implemented
and independently reviewed through `f32969e`, including neutral native navigation,
the two app routes, presenter guide and coordinated artifact marker. The web suite
now passes 226 tests/build; twelve walkthrough browser variants and twelve
card-link variants pass at desktop/mobile widths. The updated SQL gate passed
126 tests on the private disposable database. Stages 4–5 will co-release only
after stage 6's live acceptance checks. Local end-to-end and whole-branch final
verification are tracked separately; these checkpoints do not activate any link.

### Final local regression checkpoint (2026-09-09)

Final review found missing report comparison fields and an absent explicit
no-feasible-response state. Corrections at `605015e` passed independent source
re-review. The user then approved the **Customer orders protected** column
(`5a57e36`), resolving the specification versus later fixed-column-list conflict,
and the exact four-file upload to the existing private SQL test VM. Both approved
actions are complete. Independent whole-branch re-review through `1ef0aaf`
approved local readiness and closed the previous conditions, with no critical,
important or newly identified minor findings. The reviewer independently
confirmed the four local source hashes match the recorded real-SQL tested files.
This is approval for the local implementation boundary, not live acceptance or
authorization to publish, activate a receipt, merge or push.

- Non-live Python suite after the column change: **1,182 passed** in 133.64
  seconds, 125 skipped for locally unconfigured SQL connections, and 14 live
  tests deliberately deselected.
- Actual SQL: **137 passed** in 14.58 seconds on the existing private VM.
  The new tests first failed against the previous SQL because the
  `no_feasible_mitigation` column was absent; the updated SQL passed, including
  legacy saved-analysis compatibility. All four approved files had matching
  local/remote SHA256 hashes. The runner removed its disposable synthetic
  database. No live Fabric database, credentials or VM settings were changed.
- Focused report/model/schema/activation suite: **185 passed**, including the
  real Microsoft TOM parser.
- Web suite: **226 passed**, with the production build passing.
- Browser layout/navigation checks: **24 desktop/mobile variants passed**.
- Local end-to-end suite: **6 passed** in 1.8 minutes, covering simulated outcomes,
  evidence-preserving rejection/reanalysis, stale-analysis protection, planning
  and child-action retry, and duplicate-playback coalescing. These use disposable
  local data, not the live demo.
- Model/page generation, packaged reporting digest, changed-Python lint, and
  official offline visual validation pass (zero visual errors or warnings).
- One inherited Starlette/httpx deprecation warning remains a dependency
  maintenance item; no dependency change was made as part of this redesign.

These results do not verify native DAX values, published report rendering,
preserved filters, Alex's access, or live card-to-record navigation. Those checks
remain mandatory before activating the coordinated release. In particular,
inspect the longer overview copy inside the existing 334×156 cards and the wider
option comparison in native Power BI; geometry checks do not prove text fit.

## Stages and acceptance boundaries

1. **Visible, truthful evidence status.** Implement the companion
   `2026-09-08-evidence-status-footer.md` plan. Bottom-of-card platform badges,
   recorded retrieval timestamps, conservative validation summaries, prominent
   failures, and honest analysis-in-progress text. No change to source retrieval,
   approval policy, or report targets.
2. **Typed supporting records and the investigation flow.** Parse and validate
   `AnalysisVersion.material.operational_snapshot_json`; resolve shipment,
   transfer, and qualification by exact record identity. Recompose `App.tsx`,
   `EvidencePanel.tsx`, `ExposurePanel.tsx`, `OptionComparison.tsx`, and
   `DecisionPanel.tsx` into the approved three labeled rows with plain-language
   supplier/person/plant names. Preserve original source excerpts, controls,
   validation gates, and post-decision panels. Test missing/invalid material,
   zero/false values, mobile reading order, typed details, and unchanged email/
   Teams links. This stage does not activate new Power BI links.
3. **Saved-analysis reporting projections.** Extend
   `fabric/sql/002_analytics_views.sql` with explicit analysis identity and typed
   source-record/option projections from immutable persisted analysis. Verify
   joins at case/analysis/record or option grain, baseline versus option metrics,
   recommended versus approved option, historical links, and missing versus zero.
   Preserve the existing schema/version deployment contract. Local tests only;
   a production SQL migration belongs to the coordinated release.
4. **Focused Power BI pages and safe navigation.** Update the existing semantic
   model and report under `fabric/power-bi/`. Remove filter-ignoring latest-case
   behavior; add exact-analysis record views, available-stock and affected-order
   views, response comparison, clear selection and missing-data states, and the
   case overview. Add allowlisted page/filter URL construction under
   `apps/web/src/security/`; wire card actions only to matching views. Verify
   schema/TMDL, query results, identity preservation, link escaping, readable
   populated/empty layouts, and Alex's existing Read access. Return-to-app links
   require exact case/analysis restoration; omit them until verified.
5. **Traditional versus assisted walkthrough.** Reuse the focused report pages
   with previous/next navigation preserving selection; traditional comparison
   does not highlight the recommendation. Provide a presenter guide with source
   inspection, common calculation basis, replay disclosure, and human review.
   Validate both routes against the same existing case and analysis; do not
   manufacture timings, create cases, approve decisions, or run playback.
6. **Coordinated release and handoff.** Run frontend, projection/model, and
   artifact checks; review representative layouts; prepare migration order and
   rollback; preserve report/model IDs and permissions. Follow project deployment
   gates. Publish external links only with their verified report targets. Recheck
   each card-to-record journey read-only after release; update operator-facing
   documentation and roadmap with verified results, not planned successes.

## Inspection findings shaping the plans

- `useCaseWorkspace.analyze` awaits one API response. There is no frontend stream
  of per-stage discovery/retrieval events. Use an honest pending message and
  completed results; introducing a telemetry subsystem is unnecessary for this
  approved first implementation.
- `EvidencePanel` currently exposes raw health/uncertainty fields and generic
  Fabric citations. Its safe URL policy and warning must remain effective.
- `AnalysisVersion` already carries per-item policy validation results and
  retrieval identity/timestamps. These support a conservative footer, but do not
  prove individual message-identity checks or whether a result was cached.
- Record families and entity names are available in `data/synthetic/rl001.py`
  and `data/domain/operations.py`; names must not be globally replaced inside
  quoted source evidence or immutable history.
- `tests/fabric/test_power_bi_live.py` mutates the environment. Do not use it for
  the read-only acceptance checks.

Stages 1–5 have concrete implementation plans and reviewed local artifacts.
Stage 6 remains required scope; passing local checks is not completion of the
published demo redesign.
