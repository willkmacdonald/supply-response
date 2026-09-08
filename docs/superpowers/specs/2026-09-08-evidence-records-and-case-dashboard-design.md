# Evidence records and a case-focused Power BI dashboard

Date: 2026-09-08
Status: Design direction approved in conversation; written specification awaiting review.

## User outcome

Clicking an evidence card must explain and substantiate that card's claim. Opening
the dashboard must show the same case the user is reviewing, rather than a count
of unrelated demo case instances. No approval or simulated execution is performed
to populate a presentation.

## Confirmed problems

Read-only inspection of the deployed report, data model, and repository found:

- All three Fabric evidence cards use the same generic Power BI report URL. The
  link contains neither a case identifier nor an evidence identifier.
- The deployed model contains nine showcase case instances: four have analysis
  metrics and five have null metrics. The four analyzed cases show a combined
  recommendation, $375,000 projected revenue at risk, and 50% projected OTIF loss.
  These numbers describe a recommended option, not an unmitigated baseline or an
  observed result.
- All nine have no recorded decision. `Latest Showcase Case` sorts by decision
  time and then case ID, selecting an unanalyzed case when decision times are null.
- Current headline measures remove case filters and reapply that selection.
  Adding a case filter to the URL alone will therefore not fix the dashboard.
- A date-valued `Scenario Effective Time` measure is displayed as `Time Since
  Signal`, an incorrect label.
- Alex's report and semantic-model Read permissions are now verified, and the
  report renders in his account. Licensing/access is not the remaining blank-data
  issue.

## Chosen approach and alternatives

Use an in-app, read-only supporting-record view and a separate case-specific
Power BI dashboard. This gives the claim a direct, stable explanation without
requiring the reader to navigate a reporting tool to inspect one shipment.

An alternative is an evidence-detail page inside Power BI. That introduces an
additional evidence projection, navigation, and independent permission dependency
for a record already present in the analysis response. Defer it.

Simply relabeling the generic report link is insufficient: it would explain the
destination but still would not substantiate the evidence claim.

## Part 1: supporting records in the demo

### What the user sees

- Alpha card: a concise, data-derived quantity/date summary and **View shipment
  record**. For the canonical data this is 3,000 units due September 6, 2026.
- Dallas card: quantity, source/destination, arrival date, and **View transfer
  record**.
- Beta card: qualification status and **View qualification record**.
- Each action expands an accessible detail section inside its card. It does not
  navigate away, create another case, refresh evidence, or alter the analysis.
- Details explicitly say **Snapshot used for this analysis** and **Demo corpus —
  fictional**. Show case ID, analysis ID, source record ID, source/retrieval time
  when available, scenario effective time, and the relevant record fields.
- Missing timestamps are labeled unavailable. No assertion of current database
  freshness is inferred from a stored healthy-retrieval badge.
- Existing supplier-email and Quality Teams-post actions remain unchanged.
- Fabric cards no longer present the generic report as `Open citation`.

### Data and validation

Use `analysis.material.operational_snapshot_json` already returned by the API.
Derive summaries and detail rows from this snapshot, not hardcoded display facts
or a fresh live-source query. Never render arbitrary HTML or unvalidated URLs.

Resolve only known typed record families:

| Source family | Snapshot member | Identity match |
| --- | --- | --- |
| `fabric.supply_receipt/` | `alpha_expedite` | receipt ID |
| `fabric.inventory_transfer/` | `transfer` | transfer ID |
| `fabric.qualification/` | `beta_qualification` | qualification ID and evidence reference |

Validate the snapshot shape and relevant field types, case/runtime agreement,
evidence membership in the displayed analysis, analysis retrieval identity, and
source-record identity. Preserve zero values and explicit false flags. Dates and
currency must be formatted without timezone-related day shifts or invented units.

Malformed snapshots, mismatched identifiers, missing records, and unsupported
source families show **Supporting record unavailable** rather than another
record or the generic report. Fallback data remains explicitly synthetic and is
not relabeled as a Fabric record.

This is an inspection view of existing evidence, not a new authority or approval
gate. Do not mutate immutable analysis material, source bundles, hashes, or stored
citations, and do not weaken existing trusted-URL validation or approval rules.
The legacy persisted report URL remains compatibility metadata; the new UI must
not imply that it proves the individual record.

## Part 2: case dashboard

### Navigation and selection

- Rename the case-header action **Open case dashboard** and include the current
  case in a safely constructed, encoded Power BI URL filter.
- Validate the configured Power BI HTTPS host/path before adding the filter;
  never concatenate an unescaped case value into a query expression.
- Hide the case-specific action before a case exists and in fallback mode.
- An explicit case filter always takes precedence. Measures must not silently
  remove it and jump to another case.
- Direct report entry without a case selection shows a clear **Select a case**
  state and a single-case selector, rather than picking by random identifier.
- A nonexistent case, conflicting selection, or multiple cases produces a clear
  selection/no-data state, not totals masquerading as one case.
- Both report pages share the case selection. Decision/action measures use the
  current decision belonging to that case, not another case or a historical
  decision selected accidentally through a relationship.
- URL filters are navigation, not security; existing access controls remain.

Microsoft reference: https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-url-filters

### Report content

The command center becomes a one-case business summary with this reading order:

1. **Disruption:** supplier, constrained part, affected plant, missed quantity and
   original delivery date, plus visible fictional/live-source provenance.
2. **Impact and response:** unmitigated baseline versus recommended-option
   projections, including revenue at risk, projected OTIF loss, uncovered part
   demand, and incremental response cost. Label each basis explicitly.
3. **Options:** baseline and response alternatives, showing feasibility, cost,
   protected customer orders, remaining exposure, and recommendation status.
   Qualification-blocked options must not look executable.
4. **Decision:** awaiting approval, rejected, or the current approved decision and
   its chosen option. A recommendation is never labeled an approval.
5. **Evidence/navigation:** return to the application for the source-backed
   evidence and approval workflow; keep the supporting records there for this
   phase. If a return link cannot restore the exact case safely, omit it rather
   than open an empty case-creation screen.

Use a restrained visual treatment consistent with the demo (dark green, teal,
amber, readable type, intentional spacing). Long identifiers belong in a compact
details area, not as the main story. Replace the nine-case headline with selected
case context; other case instances belong in the selector.

On Actions and Outcomes, keep predicted and observed results distinct and retain
the permanent **Simulated** label for simulated observations. If no decision or
execution exists, explain that rather than displaying empty result tables.

### Data plumbing

Extend the SQL analytics projections and semantic model only for the fields this
report requires. Source details from existing persisted case, operational
snapshot, analysis, decision, action, and observation records. Project response
options at case/analysis/option grain; do not duplicate totals through joins.

Expose current analysis ID/time and current decision lineage explicitly. Keep
current recommendations separate from metrics for the option actually approved,
including when a later analysis exists or the approved option differs from the
recommendation. Use authoritative persisted predictions; do not reimplement the
ranking or prediction engine in DAX.

Name the existing date **Scenario effective time**. Do not calculate elapsed time
from wall-clock `NOW()` against the fixed fictional scenario date. Show analysis
time separately where useful.

### Empty and error states

- No analysis: **Not analyzed yet**.
- Analysis with no recommendation: **No feasible recommendation** when that is
  supported by the analysis; missing/corrupt metrics instead say **Unavailable**.
- No decision: **Awaiting approval** only for the corresponding case state;
  otherwise describe its actual recorded state.
- No observations: **No outcomes recorded**.
- Zero is a valid numeric result, not missing data. Missing values must never be
  replaced with fabricated zeros.

## Verification and release boundaries

1. Frontend tests cover all three records, exact ID matching, malformed/missing
   material, zero/false values, date formatting, accessible expansion, fallback
   provenance, unchanged Work IQ links, and safe case-filter construction.
2. Projection/model tests cover an unanalyzed case beside analyzed cases, explicit
   case selection, no/multiple selections, no recommendation, legitimate zero
   metrics, different recommended/approved options, and newer analysis versus
   governing-decision lineage.
3. Power BI artifact/schema/TMDL checks and frontend type/build checks pass.
4. Read-only live checks compare a selected existing analyzed case against its
   persisted analysis and the report query. Recheck the same case in Alex's UI,
   including navigation from its app header and source-record inspection.
5. No tests that create cases, approve decisions, or invoke playback are run
   against this environment without separate specific authorization.
6. Deployment planning must include SQL migration order, preservation of existing
   report/model IDs and Alex's Read permissions, rollback, and the project's
   release gates. No permissions, licensing, source-message, or source-bundle
   changes are part of this redesign.

## Delivery sequence

First implement and verify the evidence-record view and safe link construction.
Next update analytics projections, case-aware measures, and report presentation.
Release the link and report changes together only after selected-case filtering
is verified; a new URL filter against the old filter-ignoring measures is not a
working intermediate release.

## Design review

Self-review completed for scope, source provenance, immutable-history protection,
missing-versus-zero behavior, case/decision lineage, navigation security, and
test/release boundaries. Implementation planning follows user review of this spec.
