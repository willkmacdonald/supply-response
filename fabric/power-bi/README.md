# Supply Response Power BI reports

The native report follows the same saved case and analysis as the planner workspace. It presents the supplier delay first, then available stock and customer orders, response choices, and the recorded decision. Focused pages expose the exact saved shipment, transfer or qualification record behind a card.

All scenario data is fictional. A saved analysis is historical evidence, not a fresh source retrieval. Missing or incomplete records display as unavailable; recommendations and approved decisions remain separate. Simulated observations stay labeled as simulated.

## From a card to its supporting data

Each destination keeps the originating case and saved analysis, including a
historical analysis when a newer one exists. A record-specific link adds that
record's identity; it does not open an unrelated case count.

| Starting point | Report destination | Supporting information |
| --- | --- | --- |
| Case header | Case dashboard | Selected case, disruption and saved-analysis context |
| Available stock | Available stock | Component stock by plant, holds, protected allocations and usable units |
| Customer exposure | Affected customer orders | Saved order lines, due dates and separately labeled baseline predictions |
| Partial supplier shipment | Supplier shipment | Exact shipment quantity, scheduled date and cost |
| Another plant's supply | Plant transfer | Exact transfer record, origin/destination, quantity, date and cost |
| Alternate supplier | Supplier qualification | Exact qualification status, outstanding checks and review date |
| Option comparison or recommendation | Response options | The selected option from that card, alongside the saved comparison |
| Decision review in the report | Actions and outcomes | Recorded decision lineage, actions and explicitly labeled observations |

Original email and Teams links stay in the demo. The report presents saved
records and predictions; it is not independent corroboration of those sources.

The separate **Explore in Power BI** walkthrough starts without a record or
option preselected. Its Previous/Next controls guide the same analysis through
the eight pages. In contrast, navigation from a specific record card retains
that record filter: another record family can correctly show unavailable.
Do not clear identity filters or select a similar record to fill the screen.

Use the [traditional and assisted presenter guide](../../docs/demo/traditional-and-assisted-walkthrough.md)
to compare both routes without creating another case or executing a decision.

## Build and verify locally

From the repository root:

```sh
.venv/bin/python -m fabric.report_pages fabric/power-bi/SupplyResponse.Report/definition
.venv/bin/python -m fabric.report_model fabric/power-bi/SupplyResponse.SemanticModel/definition fabric/reporting/queries
.venv/bin/pytest tests/fabric/test_report_generators.py tests/fabric/test_power_bi_project.py tests/fabric/test_schema_updater.py -o addopts='' -q
```

The generators own the checked-in PBIR pages and TMDL tables. Edit the generator and its tests, then regenerate; do not hand-edit generated artifacts. Deployment preflight checks exact generated content, the pinned Microsoft schema catalog, stable item identities and Microsoft's locked TOM parser before publication can begin.

The five DirectQuery projections read saved reporting views in the existing Fabric SQL database. They do not create another production database. Case, analysis and record selection use explicit scoped measures; page URL filters are navigation context, not an authorization boundary.

## Acceptance and release

Passing local checks establishes artifact structure and source/query contracts. It does **not** prove DAX engine results, native visual rendering, report access or link navigation.

Before activating the new card links, the coordinated release must verify the saved views in Fabric, publish the matching model/report, execute read-only multi-case and historical-analysis checks, and inspect each page in native Power BI. The API must expose the matching reporting contract only after those gates pass. The focused report and traditional walkthrough must release together.

Release SQL first, then the matching model/report, then the application and
activation setting after acceptance. Preserve existing report/model IDs and
permissions. On rollback, deactivate the new links and restore the matching
previous application/report/model; additive reporting views can remain. Never
downgrade the operational schema version or rewrite saved analysis payloads.
See the [artifact-bound release gates](../../docs/superpowers/plans/2026-09-09-report-activation.md#separate-coordinated-release-issuance-gate-not-implemented-or-executed-here)
and [native walkthrough acceptance matrix](../../docs/superpowers/plans/2026-09-09-traditional-walkthrough.md).

The activation receipt binds reviewed artifacts and connection settings; it does
not poll Power BI or prove continued availability. Remove it if the report,
model, SQL bindings or acceptance evidence change. Publication at the same URL
alone does not validate a replacement report.

This checkout has no `.github/workflows` deployment definition. Stage 6 must
identify and verify the actual approved deployment mechanism before release.
`scripts/deploy_personal_tenant.sh` and the `.azure` plan are inspection leads;
their presence is neither permission to execute them nor evidence that they are
currently release-ready. This folder does not authorize deployment or new live
scenario runs.
