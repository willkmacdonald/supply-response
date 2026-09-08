# Planner Experience Delivery Sequence

Approved spec: [Evidence records and case dashboard](../specs/2026-09-08-evidence-records-and-case-dashboard-design.md).

This is the coverage and sequencing map, not a claim that the redesign is
implemented. Detailed executable plans are scoped to independently testable
stages. Keep the current working deployment intact until coordinated release.

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

The remaining stages require their own concrete implementation plans after the
preceding interfaces are verified. They are still required scope; completing the
footer stage is not completion of the redesign.
