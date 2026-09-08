# Evidence records and a case-focused Power BI dashboard

Date: 2026-09-08
Status: Written specification approved by the user; implementation planning in progress.

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

Use an in-app, read-only supporting-record view, card-specific Power BI detail
views, and a separate case overview. The user has explicitly expanded the design
to include meaningful, visually polished Power BI destinations that are strongly
correlated with the originating card. Evidence-detail pages are no longer deferred.

Inline details alone are useful for quick inspection but do not satisfy this
cross-application experience. A case-filtered overview alone also falls short:
it still makes the user search for the shipment or qualification they clicked.
Use focused detail pages within the existing report, reusing page layouts for
records of the same type rather than creating a separate report per card.

Simply relabeling the generic report link is insufficient: it would explain the
destination but still would not substantiate the evidence claim.

## Part 1: supporting records in the demo

### Investigation flow and visible row labels

Preserve the three-row layout approved in conversation, including the labels on
the left. Read each row left to right, then move down. On narrow screens, place
the row label above its cards and stack those cards in the same order.

| Visible left-hand label | First card | Second card | Third card |
| --- | --- | --- | --- |
| **1. Understand the disruption** | **What changed?** Supplier delay, missed quantity, original delivery date. | **What do we have available?** Stock at the affected plant after holds and protected allocations. | **What does that put at risk?** Affected production and customer orders, due dates, and revenue. |
| **2. Investigate responses** | **What can Supplier Alpha still supply?** Partial offer, arrival date, cost, and what remains unconfirmed. | **Can another plant help?** Dallas plant transfer quantity, arrival date, and cost. | **Can we use the alternate supplier?** Supplier Beta qualification status and the requirements still outstanding. |
| **3. Make the decision** | **Compare the options.** Alternatives alongside doing nothing. | **Recommended response—and why.** Benefits, cost, and parts still needed. | **Review and approve.** Current decision state and outstanding requirements; approval remains an explicit user action. |

This is an organization of existing case information, not nine new evidence
items. The supplier delay and partial-offer cards can cite the same supplier
email. Place the corresponding shipment record with the partial-offer card, the
transfer record with the plant-transfer card, and the qualification record and
Quality Teams post with the alternate-supplier card. Keep each source's role
clear rather than merging statements into an unsupported claim of agreement.

The first card at the top left is always the supplier delay, not a platform
record. Missing information leaves a clearly explained gap in its logical
position; it does not silently reorder the investigation or invent a fact.

### Planner-friendly language

Lead with a business question, a short answer, and the specific quantities,
dates, costs, or requirements that explain it. Avoid repeating the same claim
as both heading and body. Use normal supply-chain language throughout cards,
status labels, source actions, empty states, and the case dashboard.

### Unambiguous names and roles

Never require a planner to infer whether a name is a supplier, person, or plant.
Use **RL-Supplier Beta — Alternate supplier** on first reference in each
standalone card or report detail view, then **Supplier Beta** in its supporting
copy. Beta is the fictional alternate supplier whose qualification is pending,
not the person posting the update. Label **Jordan Lee — Quality Manager** when
attributing the Quality Teams post.

Apply the same convention to **RL-Supplier Alpha — Current supplier** (then
**Supplier Alpha**) and **Dallas plant** / **Chicago plant**. A useful card
heading is **Can we use the alternate supplier?**, followed by **Supplier Beta
is not yet qualified** and the outstanding requirements. Avoid bare **Beta**,
**Alpha**, or **Dallas** in user-facing headings and status summaries when the
entity's role is not otherwise explicit.

These are display clarifications, not source-data renames. Preserve original
message text, source identifiers, citations, and immutable analysis records.
Derive names and roles from the supported scenario/entity mapping; never invent
a realistic company name that no longer matches the cited email or record.
Use the same naming consistently in the demo, Power BI views, and walkthrough.

### Status and terminology wording

| Current wording or pattern | User-facing treatment |
| --- | --- |
| `fabric`, `work_iq` as prominent badges | Lead with the business question and answer. Keep human-readable platform badges in a compact footer at the bottom of the card, not above the heading. Name the source **Shipment record**, **Inventory record**, **Supplier email**, or **Quality Teams post**; put identifiers and implementation details in **Source details**. |
| `healthy` | Keep visible retrieval transparency, labeled **Retrieved for this analysis** with the actual retrieval time when available. Do not present retrieval health as supply status or continuous connection health. |
| `certain` | Show the specific checks actually completed, such as **Message identity and source link validated**, separately from business uncertainty such as **Delivery date for the remaining 5,000 units is not confirmed**. Do not invent checks or use a blanket **Confirmed** badge. |
| `operational_quantity`, `operational_date`, `collaboration_statement` | Show the business fields and attribute statements to their source. Keep technical authority scopes in Source details. |
| `Evidence ID` as a headline field | Put the identifier under **Source details**, labeled **Source record ID**. |
| `Open citation` | Use **Open supplier email**, **Open Quality Teams post**, **View shipment record**, **View transfer record**, or **View qualification record**, matching the destination. |
| Uncovered constrained-part demand | **Parts still needed**, with the component name and units; do not imply these are finished-product units. |
| Projected OTIF loss | **Customer order lines expected to miss the on-time, in-full target**, with the percentage and count/denominator where available. Do not silently change an order-line metric into an order count or a late-only metric. |
| Feasible / infeasible | Explain **Meets the planning requirements** or the specific blocker, such as **Cannot use Supplier Beta yet: supplier qualification is incomplete**. Meeting planning requirements does not mean approved or executed. |

Use **In this scenario, as of** for the fictional scenario timestamp and label
the actual analysis/retrieval timestamps separately. Explain **Revenue at risk**
as the value of customer order lines expected to miss the service target, only
where that matches the persisted metric definition. Label predictions as
**Expected if we take this option**, not achieved results.

Example partial-offer wording for the canonical fixture:

> **What can Supplier Alpha still supply?**
> **RL-Supplier Alpha — Current supplier**
> Supplier Alpha offers 3,000 units by air for September 6 at $7.50 per unit.
> Delivery for the remaining 5,000 units is not confirmed.
> **Open supplier email** · **View shipment record**

Examples are copy guidance, not hardcoded runtime facts. Derive every quantity,
date, status, and attribution from validated evidence and persisted analysis.
Preserve distinctions between an offer, a scheduled receipt, a qualification
review date, and an approved action. Display the fictional-demo notice clearly;
moving technical details out of the headline must not hide synthetic provenance,
source failures, missing evidence, or approval blockers.

### Visible proof of live activity

Plain language must not remove the transparency that makes this demonstrably a
working application rather than a static HTML mockup. Keep a compact, visible
evidence-status line on cards and an activity trail for the analysis. Users should
be able to see which real services were used, what the application is doing, what
finished successfully, and what failed, without expanding technical details.

Place platform badges (for example, **Work IQ** and **Microsoft Fabric**, only
where those integrations were actually used) and the compact retrieval/validation
summary in a visually subordinate footer at the bottom of each card. The reading
order is business question, answer and supporting facts, clearly named source
actions, then the platform/activity footer. Do not put platform branding above
the card heading or use it as the card's primary identity. Keep the footer visible
and readable on desktop and mobile; the separate analysis activity trail can
still show run-wide progress. Use actual product names, not an inferred **Fabric
IQ** label for a Microsoft Fabric integration. Business blockers and critical
source failures remain near the affected claim rather than buried in the footer.

Separate **business status** from **evidence-processing status**. For example,
**Supplier Beta is not yet qualified** can appear alongside **Teams post retrieved for
this analysis at [actual time] · Message identity and source link validated**.
The latter is proof of the checks performed, not a guarantee of the statement's
truth, supplier performance, qualification approval, or a numerical confidence
score. Do not derive specific validation claims solely from the existing
`certain` enum or source retrieval claims solely from a configured live-mode flag.

Show discovery, message/record retrieval, and validation stages only as supported
by actual run events/results. Identify the component responsible for each stage
accurately; a Graph retrieval must not be described as Work IQ discovery. If a
stage is not observable while running, show **Analysis in progress** and report
its verified completed steps afterward. Never use timed animations or fabricated
progress events to imply work that is not being observed. Any added status
plumbing is scoped to these stages and must not expose tokens, sensitive raw
payloads, or internal exception details.

Completed cards say **Retrieved for this analysis**, not **Checking now** or an
unqualified **Live** indicator suggesting ongoing monitoring. Preserve the actual
retrieval timestamp, with a clear timezone; do not reset it on page refresh. Show
timestamps as unavailable when absent. Distinguish a saved analysis or replay
from a new retrieval and a cached result from a fresh service call when known.
Missing evidence, failures, and uncertainty remain visible even when other
sources succeeded.

Keep **live service access** and **fictional scenario content** distinct. This
demo can genuinely discover and retrieve deliberately synthetic messages and
records stored in Microsoft 365/Fabric. State both facts visibly where supported;
do not imply the underlying supplier disruption is real. Fallback fixtures must
remain labeled as such and must never display an invented live-retrieval trail.
The traditional-versus-AI walkthrough should explain this distinction and show
the same honest provenance in report snapshots and the application.

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
- Keep inline **View shipment record** / **View transfer record** / **View
  qualification record** actions distinct from external **Explore shipment in
  Power BI** / **Explore transfer in Power BI** / **Explore qualification in
  Power BI** actions. External actions land on the matching detail view below.

### Card-to-report destination contract

Every Fabric/Power BI action must answer the originating card's question on the
first screen, without searching, selecting another case, or interpreting an
unrelated case count. Do not link to Fabric home, a workspace listing, or the
general case overview as a substitute for a supporting record.

| Originating card | Focused Power BI destination | Useful additional detail |
| --- | --- | --- |
| What can Supplier Alpha still supply? | **Supplier Alpha partial shipment**, repeating the card's question and matching quantity, date, and cost. | Scheduled receipt details, original requirement versus partial supply, and explicitly unconfirmed remainder; distinguish supplier statements from shipment-record fields. |
| Can another plant help? | **Dallas plant to Chicago plant transfer**, showing the same quantity, arrival date, and cost. | Dispatch/arrival timeline and available stock after holds and protected allocations, where supported by the snapshot. |
| Can we use the alternate supplier? | **Supplier Beta qualification**, showing the same pending status. | Audit and first-article requirements, outstanding blockers, and the review date clearly distinguished from an approval or delivery date. |
| What do we have available? | **Available stock**, scoped to the selected plant and part. | On-hand stock minus holds and protected allocations, with the resulting usable quantity. |
| What does that put at risk? | **Affected customer orders**, scoped to the same analysis and explicitly labeled baseline or response option. | Order-line quantities, due dates, service exposure, and supporting revenue totals. |
| Compare the options / Recommended response—and why | **Response options**, preserving the selected analysis and option when applicable. | Side-by-side cost, service impact, parts still needed, and planning blockers; identify recommendation separately from approval. |

Not every card needs a Power BI link. The supplier-delay card's primary source
remains the original supplier email; the Quality Teams post remains directly
accessible. The case-header **Open case dashboard** is the deliberate entry to
the broader overview, not an evidence citation.

Detail links identify an allowlisted page and carry the case, immutable analysis
version, and relevant source-record or option identity. The report must enforce
those selections in its measures and show a clear missing/ambiguous-record state
if the exact combination cannot be resolved. Never silently substitute the latest
analysis, a similarly named record, or aggregate records across cases. Properly
encode and validate navigation values; these filters are not access controls.

Project the exact saved snapshot behind the card into the reporting model, not
an unlabeled current database value. Label **Snapshot used for this analysis**
and show analysis time and fictional provenance. If report data has not caught
up, say **This analysis is not available in the report yet** when that condition
can be established, and retain the working inline record view. Do not show stale
numbers as if they matched the card. A Power BI view of a saved Fabric record is
a presentation of that evidence, not independent corroboration.

### Detail-view visual standard

The first screen repeats the card's business question, names the supplier/plant/
part, and makes its key quantity, date, status, and cost immediately recognizable.
Use the demo's green/teal/amber palette, readable labels, consistent number/date
formats, generous spacing, and a clear hierarchy. Use a small timeline for dates,
a stock breakdown for availability, or a requirements checklist for qualification
only when it clarifies the facts. Avoid decorative charts and giant ID tables.

Below the answer, show supporting records and what they mean for the response.
Keep unknowns and blockers visible, and technical identifiers in Source details.
Provide clearly named navigation to the case overview and, only when exact-case
restoration is supported, back to the demo. Obtain visual review of representative
populated and empty-state pages before treating the report redesign as complete.

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
- The overview and Actions and Outcomes pages share the case selection. Detail
  pages additionally preserve the explicit analysis and record/option selection.
  Decision/action measures use the
  current decision belonging to that case, not another case or a historical
  decision selected accidentally through a relationship.
- URL filters are navigation, not security; existing access controls remain.

Microsoft reference: https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-url-filters

### Report content

The command center becomes a one-case business summary following the same three
labeled investigation rows above. Its final card shows decision status and a
return-to-demo action, not an approval control. Within that flow, retain:

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
5. **Evidence/navigation:** link to focused supporting-record views and return
   to the application for original messages and the approval workflow.
   If a return link cannot restore the exact case safely, omit it rather
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
Project supporting records at case/analysis/source-record grain, keeping their
typed fields and provenance tied to the immutable saved analysis. Include only
the record families needed by the card-to-report mappings above.

Expose current analysis ID/time and current decision lineage explicitly. Keep
current recommendations separate from metrics for the option actually approved,
including when a later analysis exists or the approved option differs from the
recommendation. Use authoritative persisted predictions; do not reimplement the
ranking or prediction engine in DAX.

Present the existing scenario-effective date as **In this scenario, as of**. Do not calculate elapsed time
from wall-clock `NOW()` against the fixed fictional scenario date. Show analysis
time separately where useful.

### Empty and error states

- No analysis: **Not analyzed yet**.
- Analysis with no recommendation: **No option meets the planning requirements** when that is
  supported by the analysis; missing/corrupt metrics instead say **Unavailable**.
- No decision: **Awaiting approval** only for the corresponding case state;
  otherwise describe its actual recorded state.
- No observations: **No outcomes recorded**.
- Zero is a valid numeric result, not missing data. Missing values must never be
  replaced with fabricated zeros.

## Part 3: traditional planning walkthrough versus AI-assisted planning

Provide two clearly named routes through the same scenario: **Explore in Power
BI** and **Review with AI assistance**. The traditional route is a credible,
well-designed planning experience, not an intentionally awkward baseline. Reuse
the focused report pages and saved data above, with guided navigation and a short
presenter walkthrough. Do not build a second analytical engine or duplicate the
report into independently maintained versions.

The recommended approach is a guided sequence of existing report pages plus a
concise presenter guide. A guide alone would leave the live navigation unclear;
a separate reporting application would add unnecessary maintenance. This expands
presentation/navigation and documentation scope, not data creation or execution.

### Walkthrough sequence

| Step | Traditional planning route | AI-assisted route to demonstrate |
| --- | --- | --- |
| 1. Investigate the delay | Start with the supplier email, identify the affected part/plant and original delivery requirement, then open the relevant supply view. | Show the supplier-delay card, source attribution, and original email link. |
| 2. Check available stock | Inspect inventory, subtract holds and protected allocations, and inspect the affected customer order lines. | Show available stock and customer exposure together, with supporting records accessible. |
| 3. Investigate responses | Review Alpha's partial shipment, Dallas transfer, and Beta qualification pages; inspect the supplier email and Quality Teams post for the related statements. | Show those response cards together, including dates, cost, unknowns, and qualification blockers. |
| 4. Weigh the trade-offs | Compare the same persisted option predictions, using clearly labeled quantities, cost, service exposure, and planning requirements. The planner interprets the trade-offs. | Show the application's recommendation and explanation alongside the same comparison and source evidence. |
| 5. Review the decision | State the planner's proposed response and remaining questions. Return to the demo if an actual approval is separately requested. | Show the review/approval boundary and remaining requirements. Do not approve as part of this walkthrough. |

Provide visible step titles and previous/next navigation that retain case and
analysis context. Users may also explore the report pages freely. The traditional
route does not open on the AI recommendation or reveal a preselected answer;
its comparison can show all options without the recommendation highlight. The
AI-assisted route makes the recommendation explicit. Navigation between routes
must restore the same case/analysis; do not silently create a fresh case.

### Fair comparison and presenter guidance

Use the same fictional case, immutable analysis snapshot, units, assumptions,
option predictions, and permissions in both routes. The intended comparison is
how the planner finds, connects, checks, and interprets information. It is not a
claim that Power BI cannot analyze data or integrate collaboration sources.
Explain that this particular traditional route uses report pages plus original
email/Teams sources, while this application's assisted route brings them together.

If Power BI displays option predictions generated by the application's shared
analysis engine, disclose that shared calculation basis. Do not call those
independently calculated Power BI results or attribute deterministic ranking and
arithmetic to Work IQ or an LLM. Describe discovery, retrieval, validation,
calculation, recommendation, and human approval according to the implemented
responsibilities. Demonstrating previously saved evidence is a replay, not proof
of a new live discovery run.

The presenter guide covers the starting case, each page/action, what the planner
should notice, a corresponding AI-assisted step, and a closing discussion of
what work is reduced versus what still needs human judgment. Keep source links
and unresolved uncertainty visible in both experiences. Do not manufacture
elapsed-time savings, accuracy improvements, clicks, or measured outcomes.
Any future timed comparison must distinguish cached/replayed from fresh runs.

## Verification and release boundaries

1. Frontend tests cover all three records, exact ID matching, malformed/missing
   material, zero/false values, date formatting, accessible expansion, fallback
   provenance, unchanged Work IQ links, and safe case-filter construction.
   Also verify the approved row labels and reading order on desktop/mobile,
   business-first headings, specific source actions, visible source/retrieval/
   validation summaries with technical identifiers confined to details, and
   explicit unknowns and approval blockers. Copy must preserve
   metric units, denominators, source attribution, and prediction versus outcome.
   Verify that standalone cards and report views identify suppliers, plants, and
   people by role, without altering original quoted evidence or source identities.
   Verify that platform badges and compact retrieval/validation summaries appear
   in the bottom card footer, after the business content and source actions, on
   both desktop and mobile, while critical warnings remain prominent.
   Verify activity states against actual events/results, partial failures,
   unavailable timestamps, saved/replayed analyses, fallback fixtures, and page
   refresh without timestamp resets. Neither `healthy`, `certain`, nor a live-mode
   configuration alone may produce unsupported validation or live-activity claims.
2. Projection/model tests cover an unanalyzed case beside analyzed cases, explicit
   case selection, no/multiple selections, no recommendation, legitimate zero
   metrics, different recommended/approved options, and newer analysis versus
   governing-decision lineage.
   Verify exact card-to-detail identity and values, repeated source IDs across
   case instances, historical analysis links after a newer analysis, report
   refresh lag, and absent/ambiguous record selections. No cross-case totals or
   latest-analysis substitution may appear in a record detail view.
3. Power BI artifact/schema/TMDL checks and frontend type/build checks pass.
4. Read-only live checks compare a selected existing analyzed case against its
   persisted analysis and the report query. Recheck the same case in Alex's UI,
   including navigation from its app header and source-record inspection.
   For each external card action, compare the visible destination title, record,
   quantities, dates, and status against the originating card and saved analysis.
   Review page layout and readable empty states, not just query correctness.
5. No tests that create cases, approve decisions, or invoke playback are run
   against this environment without separate specific authorization.
6. Deployment planning must include SQL migration order, preservation of existing
   report/model IDs and Alex's Read permissions, rollback, and the project's
   release gates. No permissions, licensing, source-message, or source-bundle
   changes are part of this redesign.
7. Rehearse both walkthrough routes read-only against the same existing case and
   analysis. Check previous/next and cross-route navigation, parity of displayed
   facts and option predictions, accessible original sources, no recommendation
   highlight in the traditional comparison, and no implicit case creation,
   analysis, approval, or execution. Verify the presenter guide against the actual
   delivered UI, including empty states and explicit replay labeling.

## Delivery sequence

First implement and verify the evidence-record view and safe link construction.
Next update analytics/evidence projections, case-aware measures, focused detail
pages, and overview presentation. Release external card links and report changes
together only after exact case/analysis/record filtering and visual review are
verified; a new URL filter against old filter-ignoring measures is not a working
intermediate release.
Then verify the guided traditional route and matching AI-assisted presenter
walkthrough using those same pages and source records. The comparison is a
required demo deliverable, not a separate data-processing workflow.

## Design review

Self-review completed for scope, source provenance, immutable-history protection,
missing-versus-zero behavior, case/decision lineage, navigation security, and
test/release boundaries. Implementation planning follows user review of this spec.
