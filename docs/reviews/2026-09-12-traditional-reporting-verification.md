# Traditional reporting verification — released September 12

This is a chronological implementation and release record. Earlier pending gates
are resolved by the final acceptance and deployment sections below, unless explicitly
listed as a remaining limitation.
Approved scope: [traditional operational reporting design](../superpowers/specs/2026-09-12-traditional-operational-reporting-design.md).

## Existing supporting-data defect

Read-only checks of the selected live analysis
`RL-ANALYSIS-210078da-5902-4039-b41b-4caf9b65066d` established that the
saved snapshot and SQL projection contain the inventory records. Chicago inventory
is 4,500 on hand, 200 on quality hold, 300 protected and 4,000 usable. The
Power BI model contains the records and marks the saved inventory/order families
complete, but its row-validity measures return zero.

The defect was the strict DAX comparison `COUNTROWS(empty invalid rows) == 0`:
an empty table returns BLANK, which is not strictly equal to zero. The correction
normalizes that count with `COALESCE(..., 0)` while retaining nonempty-data,
completeness and exact-identity checks.

A query-local candidate measure executed against the deployed model returned
stock/orders valid = 1, while the deployed measures returned 0. The same query
confirmed the strict empty count comparison is false and its coalesced comparison
is true. No saved data was changed. A failing-then-passing regression and 69
focused tests accompany commit `bb7bbeb`; independent review found no issues.
Publication and rendered card-to-report validation remain outstanding.

**Correction to the earlier explanation:** the inspected analysis does not lack
historical inventory data. The observed failure is a report-measure defect. This
does not establish that every older analysis has complete data; missing records
must still remain unavailable rather than being filled from current data.

## Traditional dataset foundation

The new dataset is isolated from the canonical live source and saved analyses.
The initial build contains 178 distinct fictional records. Its typed SQL projection
was executed on SQL Server in a guarded, uniquely named disposable test database;
all rows round-tripped and the canonical inventory and unit-price assertions passed.
The runner confirmed cleanup of that disposable database.

Independent review found configuration-error redaction and qualification-status
consistency defects, corrected in `e1440d9`. Follow-up review approved both fixes,
including an actual Pydantic validation-error reproduction with a dummy secret.
The parent reran 19 focused dataset/schema tests, regenerated the corrected fixture,
then repeated the actual SQL round-trip: **1 passed in 0.33 seconds**, with
disposable database removal confirmed. Local SQL-engine verification is not live
Fabric publication.

Read-only prepublication snapshots of the existing report (124 definition parts)
and semantic model (10 parts) are preserved locally for recovery. No item was
published or modified by that export.

## Live additive data installation

After a read-only preflight confirmed the reporting schema had no existing objects,
only `003_reporting_dataset.sql` and the insert-only dataset loader were applied
to the existing Fabric SQL target. Committed readback verified dataset ID, timestamp,
payload bytes/hash and typed row count. Dataset `TRADITIONAL-OPS-2026-09-V1` contains
178 rows: 74 inventory, 25 purchase, 25 shipment, 13 transfer, 13 qualification,
14 production orders and 14 customer orders.

Before/after fingerprints matched for all 12 case payloads, 12 operational
snapshots, seven analysis versions and the canonical live operational snapshot.
The application's operational schema version remained 12. No report/model
publication, application deployment or link activation occurred in this step.

Dataset content SHA-256:
`9f825e6b6fc468f267b9cc5207aba3a4c55dd2c97719a9ad3e54d30a5d9d8ce8`.

## Published semantic model checks

The six-table model was published to the existing semantic-model ID. Native
execution exposed a defect not caught by the structural TOM parser: `Dataset`
is reserved as a DAX variable name. Commit `25733bb` replaces that variable with
`SelectedDatasetId`; independent review passed. The corrected committed model
was published separately, without changing the report or website.

Read-only queries against the persisted model (not query-local overrides) passed:
178 operational records; 74 inventory positions; 14 customer order lines;
Chicago canonical component 4,500/200/300/4,000; Alpha partial shipment 3,000
units and $22,500; 13 distinct component inventory groups. Mixed-component unit
totals and missing/unknown dataset selections remain unavailable. The selected
saved analysis now has one valid inventory row; a mismatched case/analysis
returns unavailable rather than another case's stock.

Native rendering is still a separate gate. Independent page review found a
supplier chart aggregation filter, transfer plant filter, missing date/snapshot
presentation, legacy page visibility and supporting-page chart gaps. These are
being corrected before the report definition is published.

The candidate customer-order chart exposed two further native defects: the saved
line's canonical identifier is `source_record_id`, while `customer_order_id` is
null on those rows; and the native engine returned BLANK for COUNTBLANK over two
nonblank revenue cells. Strict comparison to zero suppressed both financial and
stock measures. The correction normalizes only the blank-count result, retaining
positive row count, completeness, identity and source-null safeguards. No source
value is replaced with zero. The actual query returned two rows, a $955,000 sum,
BLANK blank-count, false strict comparison and true normalized comparison.

Query-local corrected native measures now return customer line RL-CO-DEMO-1 at
$375,000 and RL-CO-DEMO-2 at $580,000, plus the exact saved stock row
4,500/200/300/4,000. Supplier chart grouping returns seven suppliers and 50
purchase/shipment rows without summing the two quantities as new supply.
Read-only SQL-to-published-model parity separately matched ten rows and twelve
fields per row for both the selected analysis and existing older analysis
`RL-ANALYSIS-de5f07b1-2cb0-496b-9a11-b29573f40bd4`.

The September 12 controlling acceptance covers traditional reporting and exact
supporting-data navigation. It does not certify within-case multi-version history,
populated outcomes or execution. The older activation plan is explicitly marked
superseded in those respects; no saved fixture is created to satisfy it.

## Native report acceptance — September 12, in progress

Reviewed report/model artifacts were published to the existing item IDs at
21:15 America/Chicago; the reviewed plain-language chart/date labels (`ada7f41`)
were published at 21:23. No replacement workspace, model or report was created.
Eleven read-only checks against the persisted model passed, including seven
supplier chart groups, the two saved order lines ($375,000 and $580,000), the
saved Chicago stock row (4,500/200/300/4,000), and unavailable results for absent,
unknown or mismatched selections. These were not query-local candidate measures.

Native browser inspection under Alex's existing session showed all seven broad
pages rendering rows and charts. The inventory Plant and Component slicers were
used to select Chicago and RL-MAT-10247; the resulting single row and chart
showed 4,000 usable units. Customer and production tables showed both canonical
lines alongside the wider fictional business context. Transfer rows showed
distinct source/destination plants and $1.50 per-unit cost. Whole-dollar order
values and two-decimal per-unit prices rendered correctly.

Exact saved customer-order navigation rendered the two $375,000/$580,000 rows
and matching chart, with the selected case/analysis identifiers below. Shipment
and transfer source rows rendered 3,000 / September 6 / $7.50 and 1,500 /
September 5 / $1.50 respectively. The qualification record rendered pending,
both requirements false and September 15 review date. A qualification evidence
ID mistakenly used as a source-record ID correctly produced an unavailable
message and no unrelated rows; the verified RL-QUAL-BETA source-record ID then
rendered the expected row.

Native acceptance found additional issues despite correct query results: the
saved stock matrix was blank, and exact-record contextual measures were slow
enough to leave the header loading after the row tables appeared. Shipment,
transfer and qualification charts did eventually render. These observations
are not waived as successful acceptance; correction and retest are underway.
The website reporting receipt remains disabled pending that work.

## Final native acceptance — published fd53e99

The apparent blank inventory matrix eventually rendered after a long DirectQuery
wait; it was not missing data. Commit 61dbdfa replaces it with a direct row table
while retaining StockRowVisible, and uses the fast saved snapshot header on exact
shipment, transfer and qualification pages. Commit 4577602 formats the actual
SavedOptions numeric columns as whole-dollar USD, not just summary labels.
Commit fd53e99 leads the saved command-center order grid with source_record_id.

Final model/report publication completed September 12 at 21:40:19/21:40:22
America/Chicago, using the existing resource IDs. Independent read-only remote
review matched all 180 committed report parts, with only Fabric-managed .platform
and expected byPath-to-byConnection normalization. The report is bound to model
2100a769-d718-47b7-9715-7f4e804f1c8a. Artifact SHA-256:
198ea01a8fc25a999355b730c92e843f6dc565e645c8ef571e6ab403b9b177c0.

Actual native browser screenshots as Alex confirmed after final publication:

- Exact available-stock table: 4,500 on hand, 200 held, 300 protected, 4,000 usable;
  matching chart and September 9 saved snapshot context.
- Exact supplier-shipment: 3,000 units, September 6, $7.50 per unit, saved snapshot
  header and eventually rendered quantity chart.
- Exact response-options raw table: combined response $24,750 cost / $375,000
  revenue at risk; do nothing $0 / $955,000; expedite $22,500 / $955,000.

Earlier native acceptance in this same release covers all seven broad pages,
interactive Chicago/component filtering, current and older saved inventory/order
lineage, transfer and qualification source rows, and unavailable mismatched IDs.
Final persisted-model read-only results retain all expected values and the
mismatched-analysis result valid=0, count=null. No query-local measure overrides
or synthetic replacement of saved source data were used for acceptance.

Fresh regression checks: 187 Fabric tests passed with one optional live integration
skip; 326 frontend tests and production build passed; 98 deployment/activation
tests passed (one inherited Starlette warning); git diff --check and guarded
read-only Azure preflight passed. The separately executed actual SQL engine test
and live SQL-to-model parity remain recorded above.

Reporting activation is accepted for the controlling September 12 scope. Some
native DirectQuery charts still load noticeably later than the row grids; instant
rendering is not claimed. Populated execution outcomes, within-case multi-version
history, Teams app handoff and finance-person interactive approval are not certified.
The presenter walkthrough is committed. Website release verification follows.

## Website deployment and acceptance

Deployed source 78a6bf5 through the existing guarded Azure release; ACR run ch1j
succeeded and ca-sr-demo--0000028 is Healthy/Running with 100% traffic. Image:
sha256:dd20b4659bb37a6154d7137829c845de3748d503e29bbb4ee4add679ba842c08.
The artifact-bound receipt now enables saved-analysis-v1 in the live runtime.
Health is live/Fabric SQL/schema12; post-release readiness smoke passed. Existing
three Azure roles and scale 0–2 are unchanged. azd show and the actual app resource
were read to verify the endpoint.

Actual deployed UI, using Alex's existing session and the selected September 9
case/analysis, confirmed:

- Heading: Respond to supply disruptions with AI; three stage tabs retained.
- Baseline currency: $955,000 revenue, $328,000 margin, $0 response cost.
- Investigation unit prices: $7.50 and $1.50, with email and Teams source icons.
- Recommendation explanation opens as a dialog with $955,000 → $375,000,
  $328,000 → $125,000 and $0 → $24,750 comparisons; Close works.
- Live inventory link emits available-stock with exact case/analysis filters.
  Native destination visibly shows 4,500/200/300/4,000 and its saved source row.
- Live affected-orders link emits customer-orders with the same identities.
  Native destination shows RL-CO-DEMO-1 $375,000 and RL-CO-DEMO-2 $580,000 plus chart.
- Live shipment link emits supplier-shipment plus exact shipment family/key.
  Native destination shows 3,000 / September 6 / $7.50 and the original record ID.
- Live broad Explore in Power BI URL points to operations-overview with only
  OperationalRecords/dataset_id=TRADITIONAL-OPS-2026-09-V1, not saved case filters.
  All seven broad native pages were separately inspected earlier in this release.

Browser automation did not expose a newly opened tab after a target=_blank click;
verification therefore navigated the inspected live anchor href in the existing
native report tab. The browser connection later lost that tab during the final
broad-entry revisit. Neither event is counted as successful automatic app/browser
handoff, and neither invalidates the observed deployed href or native row parity.
The Power BI launch/auth experience is still dependent on the browser session.
No original communications were resent or altered; no case, analysis, decision,
approval, simulation or execution mutation was used for this acceptance.
