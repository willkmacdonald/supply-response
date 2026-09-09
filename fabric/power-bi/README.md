# Supply Response Power BI reports

The native report follows the same saved case and analysis as the planner workspace. It presents the supplier delay first, then available stock and customer orders, response choices, and the recorded decision. Focused pages expose the exact saved shipment, transfer or qualification record behind a card.

All scenario data is fictional. A saved analysis is historical evidence, not a fresh source retrieval. Missing or incomplete records display as unavailable; recommendations and approved decisions remain separate. Simulated observations stay labeled as simulated.

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

Before activating the new card links, the coordinated release must verify the saved views in Fabric, publish the matching model/report, execute read-only multi-case and historical-analysis checks, and inspect each page in native Power BI. The API must expose the matching reporting contract only after those gates pass. The traditional dashboard walkthrough is a separate delivery stage.

This folder does not authorize deployment or new live scenario runs. Use the repository's approval-gated deployment workflow when release is explicitly authorized.
