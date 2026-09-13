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

## Outstanding acceptance

- Live additive loading of the accepted dataset.
- Traditional semantic model, native tables/charts/slicers and exact saved pages.
- Existing-item publication, native rendering/filter checks as the demo account.
- Card-to-record parity, negative identity checks and justified link activation.
- Presenter walkthrough and final screenshots of the actual published report.
