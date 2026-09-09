# Saved-analysis report partition queries implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each Power BI table an exact, tested read-only projection of the already saved synthetic scenario data.

**Architecture:** Five explicit SELECT files read the existing analytics views. These are Power BI source queries, not another database or new SQL views. The paired semantic-model/report migration consumes these files after their actual SQL Server tests pass.

**Tech Stack:** T-SQL SELECT, SQL Server 2022 test VM, pytest/SQLAlchemy; later TMDL DirectQuery consumers.

## Global Constraints

- Preserve the existing report and semantic-model item identities.
- A record link must include the exact case, immutable analysis, record family and source record identity.
- Invalid or unavailable selection must not silently select another record or the newest case.
- A fallback fixture must not be presented as a live Fabric record.
- Preserve original supplier email and Quality Teams citations.
- No live deployment, permission or license changes, analysis runs, approvals or playback in this implementation stage.
- The new report links must remain inactive until the matching report contract is verified by the API.
- Query filters are navigation context, not access control; Microsoft authorization remains required.
- Preserve existing schema version 12 and existing saved views; no new database, view, function, source-data update or migration is part of this task.
- Preserve zero versus null and true versus false; no invented currency, customer-line risk classification or OTIF denominator.
- Timestamp output is normalized to UTC; calendar dates are not shifted.

## File map

- `fabric/reporting/queries/{CaseCommandCenter,SavedAnalyses,SavedRecords,SavedOptions,ActionOutcomes}.sql`: exact explicitly projected SELECT source for each table.
- `tests/integrations/test_saved_analysis_reporting_sql.py`: append runtime tests using its existing isolated test-database fixture, fixture seed helpers and schema safeguards.

### Task 1: Typed saved-data partition sources

**Files:** create `fabric/reporting/queries/CaseCommandCenter.sql`, `fabric/reporting/queries/SavedAnalyses.sql`, `fabric/reporting/queries/SavedRecords.sql`, `fabric/reporting/queries/SavedOptions.sql`, `fabric/reporting/queries/ActionOutcomes.sql`; append tests to `tests/integrations/test_saved_analysis_reporting_sql.py`. Do not edit TMDL, native report, source views, schema version or deployment validators in this task.

**Interfaces:**
- Consumes existing `analytics.case_reporting`, `analytics.saved_analyses`, `analytics.saved_records`, `analytics.saved_record_evidence`, `analytics.saved_options`, `analytics.action_outcomes`.
- Produces five standalone SELECT files, without terminating semicolon, so tests can query them as derived tables and TMDL can use them as native queries.
- Identity keys use uppercase UTF-16LE hex, matching `reportIdentityKey` in the reviewed frontend utility.
- Source column/type inventory in the implementation section is the exact contract for the subsequent five-table model.
- Customer membership means participation in the saved planning scope, not a computed line-level late/at-risk label.

- [x] **Step 1: Append these failing runtime tests**

```python
def partition_rows(engine, table_name, case_id):
    from pathlib import Path

    assert table_name in {
        "CaseCommandCenter", "SavedAnalyses", "SavedRecords", "SavedOptions", "ActionOutcomes"
    }
    query = (Path(__file__).resolve().parents[2] / "fabric" / "reporting" / "queries"
             / f"{table_name}.sql").read_text()
    return rows(engine, f"SELECT * FROM ({query}) AS partition_data WHERE case_id=:c", c=case_id)


def test_partition_queries_preserve_identity_and_utc_without_exposing_payload(engine):
    from datetime import datetime

    c, a, _ = seed(engine, options=[option("A'😀"), option("a'😀")])
    analysis = partition_rows(engine, "SavedAnalyses", c)
    assert len(analysis) == 1
    assert analysis[0]["case_key"] == c.encode("utf-16le").hex().upper()
    assert analysis[0]["analysis_key"] == a.encode("utf-16le").hex().upper()
    assert analysis[0]["scenario_effective_time"] == datetime(2026, 9, 1, 14)
    assert not any(key.endswith("_json") for key in analysis[0])
    options = partition_rows(engine, "SavedOptions", c)
    assert {r["option_key"] for r in options} == {
        identity.encode("utf-16le").hex().upper() for identity in ("A'😀", "a'😀")
    }
    assert all(r["response_cost"] == Decimal("0") for r in options)
    assert all(r["executable"] is False for r in options)
    for table in ("CaseCommandCenter", "SavedRecords", "ActionOutcomes"):
        result = partition_rows(engine, table, c)
        assert all(r["case_id"] == c for r in result)
        assert all(not any(key.endswith("_json") for key in r) for r in result)


def test_partition_stock_and_customer_membership_follow_saved_planning_scope(engine):
    from datetime import date

    disruption = {
        "disruption_id": "signal", "supplier_id": "supplier", "part_id": "Part",
        "plant_id": "Plant", "po_line_id": "po", "source_ref": "source",
        "original_quantity": 100, "partial_quantity": 0, "original_due_date": "2026-09-02",
        "partial_due_date": None, "recovery_date": None,
    }
    inventory = lambda identity, part: {
        "inventory_id": identity, "part_id": part, "plant_id": "Plant",
        "on_hand": 10, "quality_hold": 2, "protected_allocation": 3,
    }
    production = {
        "production_order_id": "production", "product_id": "product", "plant_id": "OtherPlant",
        "quantity": 10, "due_date": "2026-09-03", "component_demand": 10,
        "customer_priority": 1, "customer_revenue": "200.00", "customer_margin": "20.00",
    }
    customer = lambda identity, production_id: {
        "customer_order_line_id": identity, "customer_order_id": identity,
        "production_order_id": production_id, "customer_id": "customer",
        "product_id": "product", "plant_id": "OtherPlant", "quantity": 10,
        "due_date": "2026-09-03", "unit_revenue": "5.00", "unit_margin": "1.00",
    }
    c, a, _ = seed(engine, snapshot={
        "disruption": disruption,
        "inventory_positions": [inventory("stock", "Part"), inventory("wrong-case", "part")],
        "production_orders": [production],
        "customer_orders": [customer("linked", "production"), customer("unlinked", "Production")],
    })
    records = partition_rows(engine, "SavedRecords", c)
    by_id = {r["source_record_id"]: r for r in records}
    assert by_id["stock"]["in_disruption_scope"] is True
    assert by_id["stock"]["usable_inventory"] == 5
    assert by_id["wrong-case"]["in_disruption_scope"] is False
    assert by_id["production"]["in_disruption_scope"] is True
    assert by_id["linked"]["in_disruption_scope"] is True
    assert by_id["unlinked"]["in_disruption_scope"] is False
    assert by_id["linked"]["due_date"] == date(2026, 9, 3)
    assert by_id["linked"]["line_revenue"] == Decimal("50")
    assert len(records) == len({(r["case_key"], r["analysis_key"], r["record_family"], r["record_key"]) for r in records})
    assert all(r["analysis_key"] == a.encode("utf-16le").hex().upper() for r in records)


def test_partition_reused_source_ids_do_not_cross_case_or_analysis(engine):
    one, a, _ = seed(engine, options=[option("same", value="1")])
    two, b, _ = seed(engine, options=[option("same", value="2")])
    first = partition_rows(engine, "SavedOptions", one)
    second = partition_rows(engine, "SavedOptions", two)
    assert first[0]["option_key"] == second[0]["option_key"]
    assert first[0]["analysis_key"] != second[0]["analysis_key"]
    assert first[0]["analysis_id"] == a and second[0]["analysis_id"] == b
    assert first[0]["response_cost"] == Decimal("1")
    assert second[0]["response_cost"] == Decimal("2")


@pytest.mark.parametrize("field,value,output,expected", [
    ("blocking_codes", ["QUALITY_QUALIFICATION_PENDING"], "blockers_text",
     "Cannot use Supplier Beta yet: supplier qualification is incomplete"),
    ("blocking_codes", [], "blockers_text", "No planning blockers recorded"),
    ("blocking_codes", None, "blockers_text", None),
    ("blocking_codes", {"code": "x"}, "blockers_text", None),
    ("blocking_codes", ["x", 1], "blockers_text", None),
    ("blocking_codes", [" "], "blockers_text", None),
    ("prerequisite_roles", ["finance_approver", "quality_approver"], "required_roles_text",
     "Finance approver\nQuality approver"),
    ("assumptions", ["Saved assumption", "<literal text>"], "assumptions_text",
     "Saved assumption\n<literal text>"),
    ("protected_customer_order_ids", [], "protected_customer_order_count", 0),
    ("protected_customer_order_ids", ["A", "a"], "protected_customer_order_count", 2),
    ("protected_customer_order_ids", ["A", "A"], "protected_customer_order_count", None),
    ("protected_customer_order_ids", ["A", None], "protected_customer_order_count", None),
])
def test_partition_lists_are_ordered_validated_and_do_not_multiply_options(engine, field, value, output, expected):
    item = option("one")
    target = item["predicted"] if field == "protected_customer_order_ids" else item
    target[field] = value
    c, _, _ = seed(engine, options=[item])
    result = partition_rows(engine, "SavedOptions", c)
    assert len(result) == 1
    assert result[0][output] == expected
    assert result[0]["response_cost"] == Decimal("0")
```

- [x] **Step 2: Execute RED on the dedicated SQL test VM**

Controller uploads only this test file to the existing `supply-response-test.exe.xyz` test checkout. The worker may run local pytest for collection but a local skip is not acceptance.

```sh
../.venv/bin/python run-reporting-tests.py -q tests/integrations/test_saved_analysis_reporting_sql.py -k partition -x --tb=short
```

Expected: missing query file failure after the dedicated test database is created. The existing runner removes only its own fresh UUID test database.

- [x] **Step 3: Add the five SELECT files from the implementation section**

Use each complete SQL block as its corresponding file contents, with a final newline and no terminating semicolon. Parent-reviewed strict list projections and UTC conversions are part of the supplied SQL, not optional transformations.

- [x] **Step 4: Run actual SQL and compatibility verification**

```sh
../.venv/bin/python run-reporting-tests.py -q tests/integrations/test_saved_analysis_reporting_sql.py tests/integrations/test_fabric_sql_scripts.py -x --tb=short
```

Expected: all prior SQL tests plus these partition tests pass. Controller runs on the existing dedicated VM; no live Fabric connection.

Local compatibility and formatting:

```sh
.venv/bin/pytest tests/fabric/test_power_bi_project.py tests/fabric/test_schema_updater.py -o addopts='' -q
.venv/bin/ruff check tests/integrations/test_saved_analysis_reporting_sql.py
git diff --check
```

Expected: existing report validations continue to pass because neither current TMDL nor report artifacts changed yet. Run focused tests while iterating and the full compatibility command once before commit.

- [x] **Step 5: Commit and independent review**

```sh
git add fabric/reporting/queries tests/integrations/test_saved_analysis_reporting_sql.py
git commit -m "feat: project saved analysis data for focused reports"
```

## Implementation: complete SQL and model type contract

## CaseCommandCenter.sql

```sql
SELECT c.case_id,c.purpose,c.status,c.runtime_mode,
 CONVERT(datetime2(6),SWITCHOFFSET(c.scenario_effective_time,'+00:00')) AS scenario_effective_time,
 c.current_analysis_id,c.current_decision_id,
 CONVERT(datetime2(6),SWITCHOFFSET(c.analysis_created_at,'+00:00')) AS analysis_created_at,c.snapshot_state,
 c.recommended_option_id,c.baseline_option_id,c.decision_kind,c.decision_analysis_id,
 CONVERT(datetime2(6),SWITCHOFFSET(c.decided_at,'+00:00')) AS decided_at,c.approved_option_id,
 c.baseline_revenue_at_risk,c.baseline_otif_loss_percentage,
 c.baseline_uncovered_part_demand,c.baseline_response_cost,
 c.recommended_revenue_at_risk,c.recommended_otif_loss_percentage,
 c.recommended_uncovered_part_demand,c.recommended_response_cost,
 c.approved_revenue_at_risk,c.approved_otif_loss_percentage,
 c.approved_uncovered_part_demand,c.approved_response_cost,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),c.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),c.current_analysis_id)),2) AS current_analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),c.current_decision_id)),2) AS current_decision_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),c.decision_analysis_id)),2) AS decision_analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),c.approved_option_id)),2) AS approved_option_key
FROM analytics.case_reporting c
```

## SavedAnalyses.sql

```sql
SELECT a.case_id,a.analysis_id,a.runtime_mode,
 CONVERT(datetime2(6),SWITCHOFFSET(a.analysis_started_at,'+00:00')) AS analysis_started_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.retrieval_window_ends_at,'+00:00')) AS retrieval_window_ends_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.analysis_created_at,'+00:00')) AS analysis_created_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.scenario_effective_time,'+00:00')) AS scenario_effective_time,
 a.calculation_version,a.recommended_option_id,a.payload_state,a.snapshot_state,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.analysis_id)),2) AS analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.recommended_option_id)),2) AS recommended_option_key
FROM analytics.saved_analyses a
```

## SavedOptions.sql

```sql
SELECT o.case_id,o.analysis_id,o.option_id,o.option_kind,o.option_name,
 o.is_baseline,o.is_recommended,o.executable,o.active_mitigation,
 o.uncovered_part_demand,o.otif_loss_percentage,o.revenue_at_risk,
 o.margin_at_risk,o.response_cost,
 lists.blockers_text,lists.required_roles_text,lists.assumptions_text,
 lists.protected_customer_order_count,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),o.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),o.analysis_id)),2) AS analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),o.option_id)),2) AS option_key
FROM analytics.saved_options o
OUTER APPLY (
 SELECT
   MAX(CASE WHEN v.list_kind=N'blockers' THEN validated.display_text END) AS blockers_text,
   MAX(CASE WHEN v.list_kind=N'roles' THEN validated.display_text END) AS required_roles_text,
   MAX(CASE WHEN v.list_kind=N'assumptions' THEN validated.display_text END) AS assumptions_text,
   MAX(CASE WHEN v.list_kind=N'protected' THEN validated.item_count END) AS protected_customer_order_count
 FROM (VALUES
   (N'blockers',o.blocking_codes_json),
   (N'roles',o.prerequisite_roles_json),
   (N'assumptions',o.assumptions_json),
   (N'protected',o.protected_customer_order_ids_json)
 ) v(list_kind,json_text)
 CROSS APPLY (SELECT CASE WHEN ISJSON(v.json_text)=1
   AND LEFT(LTRIM(v.json_text),1)=N'[' THEN 1 ELSE 0 END AS is_array) shape
 CROSS APPLY (
   SELECT COUNT(*) AS item_count,
     COUNT(DISTINCT CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),j.[value])),2)) AS distinct_count,
     COALESCE(SUM(CASE WHEN j.[type]=1 AND LEN(LTRIM(RTRIM(j.[value])))>0
       THEN 0 ELSE 1 END),0) AS invalid_count,
     STRING_AGG(mapped.display_value,NCHAR(10))
       WITHIN GROUP (ORDER BY CONVERT(int,j.[key])) AS joined_text
   FROM OPENJSON(CASE WHEN shape.is_array=1 THEN v.json_text ELSE N'[]' END) j
   CROSS APPLY (SELECT CONVERT(nvarchar(max),CASE
       WHEN v.list_kind=N'blockers' THEN CASE j.[value] COLLATE Latin1_General_100_BIN2
         WHEN N'QUALITY_QUALIFICATION_PENDING' THEN N'Cannot use Supplier Beta yet: supplier qualification is incomplete'
         WHEN N'ALPHA_PARTIAL_SHIPMENT_UNAVAILABLE' THEN N'No partial shipment from Supplier Alpha is available'
         WHEN N'TRANSFER_INVENTORY_UNAVAILABLE' THEN N'The source plant does not have enough available inventory for this transfer'
         WHEN N'RESEQUENCE_NOT_APPLICABLE' THEN N'Changing the production sequence does not provide a response for this plan'
         ELSE N'Planning requirement unresolved ('+j.[value]+N')' END
       WHEN v.list_kind=N'roles' THEN CASE j.[value] COLLATE Latin1_General_100_BIN2
         WHEN N'material_planner' THEN N'Material planner'
         WHEN N'finance_approver' THEN N'Finance approver'
         WHEN N'quality_approver' THEN N'Quality approver'
         WHEN N'response_approver' THEN N'Response approver'
         ELSE N'Required role unresolved ('+j.[value]+N')' END
       ELSE j.[value]
     END) AS display_value) mapped
 ) parsed
 CROSS APPLY (SELECT
   CASE WHEN shape.is_array=1 AND parsed.invalid_count=0
     AND (v.list_kind<>N'protected' OR parsed.item_count=parsed.distinct_count)
     THEN CASE WHEN parsed.item_count=0 THEN
       CASE v.list_kind
         WHEN N'blockers' THEN N'No planning blockers recorded'
         WHEN N'roles' THEN N'No required roles recorded'
         WHEN N'assumptions' THEN N'No assumptions recorded'
         ELSE N'No protected customer orders recorded' END
       ELSE parsed.joined_text END END AS display_text,
   CASE WHEN shape.is_array=1 AND parsed.invalid_count=0
     AND (v.list_kind<>N'protected' OR parsed.item_count=parsed.distinct_count)
     THEN parsed.item_count END AS item_count
 ) validated
) lists
```

## ActionOutcomes.sql

```sql
SELECT a.case_id,a.decision_id,a.selected_option_id,a.record_type,a.action_id,
 a.action_kind,a.action_status,a.metric,a.predicted_value,a.observed_value,
 a.unit,a.observation_kind,
 CONVERT(datetime2(6),SWITCHOFFSET(a.scenario_effective_time,'+00:00')) AS scenario_effective_time,
 CONVERT(datetime2(6),SWITCHOFFSET(a.projection_updated_at,'+00:00')) AS projection_updated_at,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.decision_id)),2) AS decision_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.action_id)),2) AS action_key
FROM analytics.action_outcomes a
```

## SavedRecords.sql

The scalar subquery's disruption count is deliberately over all disruption rows, including unavailable ones; only exactly one available disruption establishes context. Inventory scope exactly follows `OperationalSnapshot.usable_inventory` in data/synthetic/rl001.py. Current prediction engine services/analysis/options.py `_calculate_intervention_outcome` passes **all saved production orders** into allocation, without plant/product/date/BOM filtering. Customer membership joins each line's production_order_id to one saved production-order source_record_id in that same analysis. It is participation in the saved planning scope, **not a newly computed affected/missed-OTIF flag**. All equality on dynamic identity fields uses BIN2.

```sql
SELECT r.case_id,r.analysis_id,r.record_family,r.source_record_id,r.runtime_mode,
 CONVERT(datetime2(6),SWITCHOFFSET(r.analysis_created_at,'+00:00')) AS analysis_created_at,
 CONVERT(datetime2(6),SWITCHOFFSET(r.scenario_effective_time,'+00:00')) AS scenario_effective_time,r.record_state,
 r.supplier_id,r.part_id,r.plant_id,r.source_plant_id,r.destination_plant_id,
 r.product_id,r.customer_id,r.production_order_id,r.customer_order_id,r.po_line_id,
 r.quantity,r.due_date,r.dispatch_date,r.arrival_date,r.incremental_cost_per_unit,
 r.status,r.evidence_ref,r.audit_complete,r.first_article_complete,
 r.effective_date,r.expected_decision_date,r.on_hand,r.quality_hold,
 r.protected_allocation,r.usable_inventory,r.component_demand,r.customer_priority,
 r.customer_revenue,r.customer_margin,r.unit_revenue,r.unit_margin,r.line_revenue,
 r.original_quantity,r.partial_quantity,r.original_due_date,r.partial_due_date,
 r.recovery_date,r.source_ref,
 e.evidence_state,e.provenance,e.evidence_id,e.source_id,e.source_system,
 e.synthetic,
 CONVERT(datetime2(6),SWITCHOFFSET(e.source_timestamp,'+00:00')) AS source_timestamp,
 CONVERT(datetime2(6),SWITCHOFFSET(e.retrieved_at,'+00:00')) AS retrieved_at,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.analysis_id)),2) AS analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.source_record_id)),2) AS record_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.part_id)),2) AS part_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.plant_id)),2) AS plant_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.product_id)),2) AS product_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.source_plant_id)),2) AS source_plant_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.destination_plant_id)),2) AS destination_plant_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.production_order_id)),2) AS production_order_key,
 CAST(CASE WHEN r.record_state=N'available' AND d.disruption_count=1
   AND d.disruption_state=N'available' THEN
   CASE
     WHEN r.record_family=N'inventory'
       AND r.part_id COLLATE Latin1_General_100_BIN2=d.part_id COLLATE Latin1_General_100_BIN2
       AND r.plant_id COLLATE Latin1_General_100_BIN2=d.plant_id COLLATE Latin1_General_100_BIN2 THEN 1
     WHEN r.record_family=N'production_order' THEN 1
     WHEN r.record_family=N'customer_order_line' AND EXISTS (
       SELECT 1 FROM analytics.saved_records p
       WHERE p.case_id COLLATE Latin1_General_100_BIN2=r.case_id COLLATE Latin1_General_100_BIN2
         AND p.analysis_id COLLATE Latin1_General_100_BIN2=r.analysis_id COLLATE Latin1_General_100_BIN2
         AND p.record_family=N'production_order' AND p.record_state=N'available'
         AND p.source_record_id COLLATE Latin1_General_100_BIN2=r.production_order_id COLLATE Latin1_General_100_BIN2
     ) THEN 1
     ELSE 0
   END ELSE 0 END AS bit) AS in_disruption_scope
FROM analytics.saved_records r
LEFT JOIN analytics.saved_record_evidence e
 ON e.case_id COLLATE Latin1_General_100_BIN2=r.case_id COLLATE Latin1_General_100_BIN2
 AND e.analysis_id COLLATE Latin1_General_100_BIN2=r.analysis_id COLLATE Latin1_General_100_BIN2
 AND e.record_family COLLATE Latin1_General_100_BIN2=r.record_family COLLATE Latin1_General_100_BIN2
 AND e.source_record_id COLLATE Latin1_General_100_BIN2=r.source_record_id COLLATE Latin1_General_100_BIN2
OUTER APPLY (
 SELECT COUNT(*) AS disruption_count,MAX(x.record_state) AS disruption_state,
   MAX(x.part_id) AS part_id,MAX(x.plant_id) AS plant_id
 FROM analytics.saved_records x
 WHERE x.case_id COLLATE Latin1_General_100_BIN2=r.case_id COLLATE Latin1_General_100_BIN2
   AND x.analysis_id COLLATE Latin1_General_100_BIN2=r.analysis_id COLLATE Latin1_General_100_BIN2
   AND x.record_family=N'disruption'
) d
```

The saved_records projection suppresses duplicate source identities, so multiple same-ID disruptions may yield zero rows; zero disruption_count keeps scope closed. MAX only selects values after requiring disruption_count = 1; it never resolves ambiguity. Full four-field evidence join prevents repeated IDs across cases, analyses, or families from multiplying/cross-binding records. Assert uniqueness of saved_record_evidence's four-column grain in SQL contract tests.

`in_disruption_scope` is false for shipment/transfer/qualification (these use exact detail identity), and true only for the inventory/production/customer collections described above. Customer rows with null or absent production links cannot establish membership. Do not silently substitute a matching product or plant.

## Exact model type inventory

The SELECT column order above is the exact source-column inventory. For each table, assign listed exceptions below; **every remaining selected output column is string**. This rule yields no unspecified types and lets a compact generator maintain explicit SQL and manifests. `*_key` are varchar(max) hex strings from nvarchar UTF-16LE bytes; no truncating casts. Set summarizeBy none for every source column. Model measures perform intentional numeric aggregation.

| Table | TMDL type | Exact columns |
|---|---|---|
| CaseCommandCenter | dateTime | scenario_effective_time, analysis_created_at, decided_at |
| CaseCommandCenter | decimal | baseline_revenue_at_risk, baseline_response_cost, recommended_revenue_at_risk, recommended_response_cost, approved_revenue_at_risk, approved_response_cost |
| CaseCommandCenter | int64 | baseline_otif_loss_percentage, baseline_uncovered_part_demand, recommended_otif_loss_percentage, recommended_uncovered_part_demand, approved_otif_loss_percentage, approved_uncovered_part_demand |
| SavedAnalyses | dateTime | analysis_started_at, retrieval_window_ends_at, analysis_created_at, scenario_effective_time |
| SavedOptions | boolean | is_baseline, is_recommended, executable, active_mitigation |
| SavedOptions | int64 | uncovered_part_demand, otif_loss_percentage, protected_customer_order_count |
| SavedOptions | decimal | revenue_at_risk, margin_at_risk, response_cost |
| ActionOutcomes | dateTime | scenario_effective_time, projection_updated_at |
| SavedRecords | dateTime | analysis_created_at, scenario_effective_time, due_date, dispatch_date, arrival_date, effective_date, expected_decision_date, original_due_date, partial_due_date, recovery_date, source_timestamp, retrieved_at |
| SavedRecords | boolean | audit_complete, first_article_complete, synthetic, in_disruption_scope |
| SavedRecords | int64 | quantity, on_hand, quality_hold, protected_allocation, usable_inventory, component_demand, customer_priority, original_quantity, partial_quantity |
| SavedRecords | decimal | incremental_cost_per_unit, customer_revenue, customer_margin, unit_revenue, unit_margin, line_revenue |

SQL source numeric types: int64 entries originate as int except usable_inventory (bigint); decimal entries originate decimal(19,4), except line_revenue is SQL multiplication's promoted decimal type. Boolean is bit. Date-only values originate date and are untouched. Every event timestamp is mandatorily normalized from datetimeoffset(6) to UTC datetime2(6) in the SELECT above; display with explicit UTC labels. `blockers_text`, `required_roles_text`, and `assumptions_text` are nvarchar(max), mapped to string; protected_customer_order_count is nullable int, mapped int64.

## Unavailable requirements and faithful presentation

The options query projects validated JSON arrays into scalar strings/counts; no opaque JSON enters the model. Each list must be a JSON array of nonempty strings, with saved order preserved by numeric OPENJSON key and newline-separated text. Unknown blocker/role codes remain visible as unresolved; four known labels per family match plannerFormatting.ts exactly. Assumptions are original decoded strings, displayed as data, never interpreted as HTML or instructions. Missing, JSON null, non-array, mixed-type, and empty/whitespace-string lists yield NULL (not partially rendered text). Valid empty arrays produce explicit no-items text; protected count is 0. Protected IDs additionally require binary identity uniqueness using UTF-16LE hex distinctness; duplicate IDs yield NULL rather than silently deduplicating. A single aggregate APPLY over four list kinds always yields one row per option, so list expansion cannot multiply metrics. Empty/malformed arrays in one field do not hide valid sibling fields. Evidence ID lists remain excluded.

Saved options still do not contain a line-level affected/OTIF result. Protected customer count is a customer-ID count, not an inferred OTIF order-line denominator. Likewise never use summed customer-order line revenue as a replacement for persisted option revenue_at_risk: active engine uses production-order customer_revenue. A customer-list revenue subtotal can be labeled `Value of these customer order lines` only.

The older generic services/exposure/calculator.py filters BOM/product/plant and allocates differently; it does not define membership for the active saved option engine. Recomputing its shortages would violate the requirement to use saved predictions. A precise per-option customer exposure page remains unavailable from scalar fields alone. Safe initial customer page shows saved customer lines participating in planning, alongside separately labeled persisted baseline/option exposure totals.

Implementation preflight must intentionally replace the old `SELECT *`/one-source-count checks with exact checked-in query identity, approved underlying view sets per table, and known immutable projection manifest. SavedRecords intentionally references saved_records three times plus saved_record_evidence; no blanket assertion that each view occurs once. Preserve strict allowed tables/columns/types/partitions and mutation tests. No change to `.platform`, item IDs, credentials, environments, publication order, or source schema.
