# Traditional operational reporting implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task with Codex review between tasks.

**Goal:** Replace the Power BI answer-card clone with traditional operational tables,
charts and filters; preserve exact immutable supporting-data links from the AI app.

**Architecture:** A separate, immutable fictional reporting dataset in the existing
Fabric SQL database supplies wider operational context. A new DirectQuery table
`OperationalRecords` serves broad manual investigation pages. Existing `SavedRecords`
continues serving exact case/analysis evidence pages; never substitute broad or current
data for historical analysis. Existing app calculations and live RL-001 loader remain
unchanged. Keep report/model resource IDs and publication guards.

**Tech stack:** Python/Pydantic, SQL Server/Fabric SQL, TMDL, native Power BI report JSON,
existing React navigation and artifact-bound reporting activation.

## Global constraints

Approved spec: ../specs/2026-09-12-traditional-operational-reporting-design.md.
Power BI must show operational rows/charts/slicers, not AI question/answer cards.
Canonical inventory 4,500 − 200 − 300 = 4,000. USD totals whole dollars; unit prices
two decimals. Synthetic context must be visibly distinguished from exact saved
analysis evidence. No edits to saved analyses, live canonical source, recommendation
math, approval records, licensing or permissions. No activation without native proof.

### Task 1: Coherent, isolated traditional reporting dataset

Files: create `data/synthetic/reporting.py`, `integrations/fabric/reporting_source.py`,
`scripts/load_fabric_reporting.py`, `fabric/sql/003_reporting_dataset.sql`,
`fabric/reporting/queries/OperationalRecords.sql`, `tests/integrations/test_reporting_dataset.py`.
Update `integrations/fabric/schema.py`, `pyproject.toml` only to register/package the
additive SQL file, and relevant schema inventory tests if required.

- [x] Test first: deterministic content, stable unique IDs, coherent referential
  links, exact canonical values, and varied background data; observe RED.
- [x] Expose `build_operational_reporting_dataset()` returning a frozen validated
  dataset, stable `dataset_id`, effective time and canonical JSON/hash. Include
  at least 150 distinct operational rows across inventory, purchase, shipment,
  transfer, qualification, production_order and customer_order families, with
  at least 12 components, 4 plants and 6 clearly fictional suppliers. Preserve
  RL-001 source values by deriving canonical rows from OperationalSnapshot.rl001().
  New background data must not add canonical part demand or competing stock to
  RL-MAT-10247/Chicago/Dallas; planned receipts and proposals must be distinct.
- [x] Use a single flat typed record contract for simple report bindings:
  `record_id`, `record_family`, `supplier_id`, `supplier_name`, `part_id`, `part_name`,
  `plant_id`, `plant_name`, `source_plant_id`, `source_plant_name`, `destination_plant_id`,
  `destination_plant_name`, `customer_id`, `product_id`, `production_order_id`,
  `customer_order_id`, `quantity`, `on_hand`, `quality_hold`, `protected_allocation`,
  `usable_inventory`, `component_demand`, `due_date`, `original_due_date`,
  `dispatch_date`, `arrival_date`, `incremental_cost_per_unit`, `line_revenue`,
  `line_margin`, `status`, `audit_complete`, `first_article_complete`,
  `expected_decision_date`, `data_origin`. Nullable where not applicable.
  `data_origin`: `canonical_scenario` or `fictional_reporting_context`.
- [x] Add isolated `reporting.datasets` table with dataset ID primary key,
  effective_at, content_sha256, synthetic flag constrained true, payload_json.
  Add typed `reporting.operational_records` view projecting the validated envelope's
  records. Query OperationalRecords.sql must SELECT explicit fields including
  `dataset_id` and effective time from this view. No current/latest substitution.
- [x] Loader defaults dry run; explicitly targeted Azure CLI configuration like
  existing loader; insert-only transaction, reject same-ID/different-content;
  independent committed hash/row-count readback. No schema auto-apply inside loader.
  Never alter app.live_operational_sources, saved payloads or app.schema_version.
- [x] GREEN unit/loader tests, schema registration/package tests and Ruff. Actual
  SQL engine validation is parent-owned integration gate, not a claimed unit pass.
- [x] Commit only scoped files, self-review and report RED/GREEN evidence to
  `.superpowers/sdd/traditional-dataset-report.md`. Independent review before Task 2.

### Task 2: Operational semantic model and native report pages

Files: new focused `fabric/traditional_model.py`, `fabric/traditional_pages.py`;
integrate with `fabric/report_model.py`, `fabric/report_pages.py` and generated
`fabric/power-bi/` artifacts; tests under `tests/fabric/`.

- [x] Extend the model with OperationalRecords columns and explicit grain-safe
  measures. Require exactly one dataset, preventing version double counting.
- [x] Traditional entry page `operations-overview`; additional native inventory,
  supplier-deliveries, transfers, qualification and demand/orders pages. Use
  readable dense tables, charts and dataset/plant/component/supplier/date filters.
  No recommendation narration, no counterfeit delivery history, and no sums of
  unlike component units presented as a single material quantity.
- [x] Keep existing exact saved page IDs, but redesign their dominant content as
  contributing row tables and relevant charts rather than repeated AI narratives.
- [x] Observe failing generator assertions, implement, regenerate through existing
  generators, validate pinned Microsoft schemas/TOM and artifact digest.
- [x] Review independently; no receipt or publication claim from local tests.

### Task 3: Exact saved-data coverage and website navigation

- [x] Read-only compare actual selected old analysis JSON, SQL projection, model
  output and filters to establish the missing inventory/order root cause.
- [x] Reproduce evidenced defect with regression test and fix the responsible
  projection/filter only; do not backfill historical data from current source.
- [x] Traditional website action opens operations-overview with explicit dataset;
  card actions keep exact saved case/analysis/record context and plain labels.
- [x] Preserve honest unavailable states and activation safeguard. Review all
  link mappings and whole change before publication.

### Task 4: Publish, verify and record presenter proof

- [x] Apply only approved additive reporting schema/data to existing Fabric target,
  preserving exact fingerprints of app records. Guarded SQL runtime verification
  and dry-run publication before actual existing-model/report update.
- [x] Verify native Power BI as Alex: broad rows/charts/filter interactions, exact
  card inventory arithmetic, shipment/qualification/order lineage, mismatched IDs.
- [x] Enable only reporting behavior actually accepted; do not falsify receipt
  coverage. Deploy website only if navigation/runtime code changed and validated.
- [x] Update `docs/demo/traditional-and-assisted-walkthrough.md` with actual report
  names, manual investigation steps and source references. Record native screenshots,
  row counts, filter results and remaining limitations in a review document.
