# Traditional reporting verification — in progress

This is an implementation record, not a completion or publication claim.
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

## Outstanding acceptance

- Traditional semantic model, native tables/charts/slicers and exact saved pages.
- Existing-item publication, native rendering/filter checks as the demo account.
- Card-to-record parity, negative identity checks and justified link activation.
- Presenter walkthrough and final screenshots of the actual published report.
