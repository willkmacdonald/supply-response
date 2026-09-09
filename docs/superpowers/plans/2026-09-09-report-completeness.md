# Saved collection completeness implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent partial totals when malformed or duplicate saved records are suppressed by typed reporting views.

**Architecture:** The SavedAnalyses partition compares each original saved array's member count and shape to its exact typed projection. Three boolean completeness flags let the report suppress totals that cannot be substantiated. This is a query extension over existing synthetic-data storage, not a new database.

**Tech Stack:** T-SQL, existing localhost-only SQL Server integration harness, pytest.

## Global Constraints

- Project the exact saved snapshot behind the card into the reporting model, not an unlabeled current database value.
- Missing values must never be replaced with fabricated zeros.
- Do not mutate immutable analysis material, source bundles, hashes, or stored citations.
- Preserve original message text, source identifiers, citations, and immutable analysis records.
- No live deployment, permission or license changes, analysis runs, approvals or playback in this implementation stage.
- Actual SQL tests use only the existing private supply-response-test.exe.xyz VM and its guarded fresh disposable database runner.
- Leave schema version 12, SQL views/functions, source records, and all other partition queries unchanged.

### Task 1: Certify saved collection completeness

**Files:**
- Modify: `fabric/reporting/queries/SavedAnalyses.sql`.
- Test: append to `tests/integrations/test_saved_analysis_reporting_sql.py`.
- Add `import copy` alongside the existing imports, rather than mid-module.

**Interfaces:**
- Consumes: analytics.saved_analyses.snapshot_json, payload_state, snapshot_state; analytics.saved_records at exact case/analysis/family/source-record grain.
- Produces: SQL bit columns inventory_complete, production_orders_complete, customer_orders_complete, without changing existing output columns or row grain.
- Model stock totals must require inventory_complete. Customer collection display must require production_orders_complete AND customer_orders_complete. The model implementation follows separately.
- Valid empty arrays are complete. Empty scoped collections remain unavailable in the report until their business zero interpretation is established. Explicit numeric zeros in valid records remain valid.
- Tests reuse seed(engine, snapshot=...) returning (case_id, analysis_id, payload), partition_rows(engine, table_name, case_id), and rewrite_fixture_payload on disposable fixtures only.

- [x] **Step 1: Append the actual regression tests below.**

```python
import copy


COMPLETENESS_FIXTURES = {
    'inventory_positions': ('inventory_complete', {
        'inventory_id':'scope-record', 'part_id':'part', 'plant_id':'plant',
        'on_hand':0, 'quality_hold':0, 'protected_allocation':0,
    }, 'inventory_id', 'on_hand'),
    'production_orders': ('production_orders_complete', {
        'production_order_id':'scope-record', 'product_id':'product', 'plant_id':'plant',
        'quantity':1, 'due_date':'2026-09-05', 'component_demand':1,
    }, 'production_order_id', 'quantity'),
    'customer_orders': ('customer_orders_complete', {
        'customer_order_line_id':'scope-record', 'customer_id':'customer',
        'production_order_id':'production', 'product_id':'product', 'plant_id':'plant',
        'quantity':1, 'due_date':'2026-09-05', 'unit_revenue':'0.00', 'unit_margin':'0.00',
    }, 'customer_order_line_id', 'quantity'),
}


def completeness_flags(engine, case_id):
    records=partition_rows(engine,'SavedAnalyses',case_id)
    assert len(records)==1
    return {name:records[0][name] for name in (
        'inventory_complete','production_orders_complete','customer_orders_complete')}


@pytest.mark.parametrize('member',tuple(COMPLETENESS_FIXTURES))
@pytest.mark.parametrize('mutation',('valid','empty','primitive','missing-id','duplicate-id-survivor',
                                     'invalid-numeric-survivor','duplicate-property'))
def test_partition_completeness_detects_missing_projected_members(engine,member,mutation):
    flag,valid,id_field,numeric_field=COMPLETENESS_FIXTURES[member]
    item=copy.deepcopy(valid)
    survivor={**valid,id_field:'survivor'}
    expected=mutation in {'valid','empty'}
    source=[item]
    if mutation=='empty': source=[]
    elif mutation=='primitive': source=[item,42]
    elif mutation=='missing-id':
        item.pop(id_field)
        source=[item,survivor]
    elif mutation=='duplicate-id-survivor': source=[item,copy.deepcopy(item),survivor]
    elif mutation=='invalid-numeric-survivor':
        item[numeric_field]='invalid-number'
        source=[item,survivor]
    case_id,analysis_id,_=seed(engine,snapshot={member:source})
    if mutation=='duplicate-property':
        payload=json.loads(rows(engine,'SELECT payload_json FROM app.analysis_versions WHERE analysis_id=:a',a=analysis_id)[0]['payload_json'])
        snapshot=payload['material']['operational_snapshot_json']
        # Add a second exact property name without round-tripping through a dict.
        payload['material']['operational_snapshot_json']=snapshot[:-1]+','+json.dumps(member)+':[]}'
        rewrite_fixture_payload(engine,analysis_id,payload)
    flags=completeness_flags(engine,case_id)
    assert flags[flag] is expected
    # Well-formed empty sibling collections remain complete.
    assert all(value for name,value in flags.items() if name!=flag)


@pytest.mark.parametrize('member',tuple(COMPLETENESS_FIXTURES))
@pytest.mark.parametrize('bad_property',('missing','null','object','string'))
def test_partition_completeness_requires_present_array_property(engine,member,bad_property):
    flag,valid,_,_=COMPLETENESS_FIXTURES[member]
    case_id,analysis_id,_=seed(engine,snapshot={member:[valid]})
    payload=json.loads(rows(engine,'SELECT payload_json FROM app.analysis_versions WHERE analysis_id=:a',a=analysis_id)[0]['payload_json'])
    snapshot=json.loads(payload['material']['operational_snapshot_json'])
    if bad_property=='missing': snapshot.pop(member)
    else: snapshot[member]={'null':None,'object':{},'string':'[]'}[bad_property]
    payload['material']['operational_snapshot_json']=json.dumps(snapshot)
    rewrite_fixture_payload(engine,analysis_id,payload)
    # Existing saved_analyses may invalidate the whole snapshot, which is conservative.
    assert completeness_flags(engine,case_id)[flag] is False


@pytest.mark.parametrize('member',tuple(COMPLETENESS_FIXTURES))
def test_partition_completeness_isolated_for_reused_ids(engine,member):
    flag,valid,id_field,_=COMPLETENESS_FIXTURES[member]
    good,_,_=seed(engine,snapshot={member:[valid]})
    bad,_,_=seed(engine,snapshot={member:[valid,copy.deepcopy(valid),{**valid,id_field:'survivor'}]})
    assert completeness_flags(engine,good)[flag] is True
    assert completeness_flags(engine,bad)[flag] is False
    assert completeness_flags(engine,good)[flag] is True
```

- [x] **Step 2: Ask the controller to execute actual SQL RED before changing the query.**

Controller uploads only the changed test module to the private test VM and runs:

```sh
../.venv/bin/python run-reporting-tests.py -q tests/integrations/test_saved_analysis_reporting_sql.py -k completeness -x --tb=short
```

Expected: missing inventory_complete output key. The controller supplies exact RED evidence; do not substitute a local skip for actual SQL execution.

- [x] **Step 3: Replace SavedAnalyses.sql with this complete query.**

```sql
SELECT a.case_id,a.analysis_id,a.runtime_mode,
 CONVERT(datetime2(6),SWITCHOFFSET(a.analysis_started_at,'+00:00')) AS analysis_started_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.retrieval_window_ends_at,'+00:00')) AS retrieval_window_ends_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.analysis_created_at,'+00:00')) AS analysis_created_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.scenario_effective_time,'+00:00')) AS scenario_effective_time,
 a.calculation_version,a.recommended_option_id,a.payload_state,a.snapshot_state,
 completeness.inventory_complete,completeness.production_orders_complete,completeness.customer_orders_complete,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.analysis_id)),2) AS analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.recommended_option_id)),2) AS recommended_option_key
FROM analytics.saved_analyses a
OUTER APPLY (
 SELECT CAST(MAX(CASE WHEN f.family=N'inventory' THEN verdict.complete END) AS bit) AS inventory_complete,
        CAST(MAX(CASE WHEN f.family=N'production_order' THEN verdict.complete END) AS bit) AS production_orders_complete,
        CAST(MAX(CASE WHEN f.family=N'customer_order_line' THEN verdict.complete END) AS bit) AS customer_orders_complete
 FROM (VALUES (N'inventory_positions',N'inventory'),
              (N'production_orders',N'production_order'),
              (N'customer_orders',N'customer_order_line')) f(property_name,family)
 CROSS APPLY (
   SELECT COUNT(*) AS property_count,MAX(j.[type]) AS property_type,MAX(j.[value]) AS array_json
   FROM OPENJSON(CASE WHEN ISJSON(a.snapshot_json)=1 AND LEFT(LTRIM(a.snapshot_json),1)=N'{'
                     THEN a.snapshot_json ELSE N'{}' END) j
   WHERE j.[key] COLLATE Latin1_General_100_BIN2=f.property_name COLLATE Latin1_General_100_BIN2
 ) property
 CROSS APPLY (
   SELECT COUNT(*) AS raw_count,COALESCE(SUM(CASE WHEN j.[type]=5 THEN 0 ELSE 1 END),0) AS nonobject_count
   FROM OPENJSON(CASE WHEN property.property_count=1 AND property.property_type=4
                     THEN property.array_json ELSE N'[]' END) j
 ) raw_members
 CROSS APPLY (
   SELECT COUNT(*) AS projected_count,
          COALESCE(SUM(CASE WHEN r.record_state=N'available' THEN 0 ELSE 1 END),0) AS unavailable_count
   FROM analytics.saved_records r
   WHERE r.case_id COLLATE Latin1_General_100_BIN2=a.case_id COLLATE Latin1_General_100_BIN2
     AND r.analysis_id COLLATE Latin1_General_100_BIN2=a.analysis_id COLLATE Latin1_General_100_BIN2
     AND r.record_family COLLATE Latin1_General_100_BIN2=f.family COLLATE Latin1_General_100_BIN2
 ) projected
 CROSS APPLY (SELECT CASE WHEN a.snapshot_state=N'available' AND a.payload_state=N'available'
    AND property.property_count=1 AND property.property_type=4
    AND raw_members.nonobject_count=0 AND raw_members.raw_count=projected.projected_count
    AND projected.unavailable_count=0 THEN 1 ELSE 0 END AS complete) verdict
) completeness
```

- [x] **Step 4: Ask controller to sync this one query and run the complete actual SQL gate.**

```sh
../.venv/bin/python run-reporting-tests.py -q tests/integrations/test_saved_analysis_reporting_sql.py tests/integrations/test_fabric_sql_scripts.py -x --tb=short
```

Expected: all prior 85 checks and all completeness parametrizations pass. Runner removes only its own generated test database. Locally run:

```sh
.venv/bin/ruff check tests/integrations/test_saved_analysis_reporting_sql.py
git diff --check
```

No query text or test expectation may be weakened to make a failed engine check pass.

- [x] **Step 5: Self-review, record evidence, and commit only the two task files.**

```sh
git add fabric/reporting/queries/SavedAnalyses.sql tests/integrations/test_saved_analysis_reporting_sql.py
git commit -m "fix: reject incomplete saved report collections"
```

Record full RED/GREEN commands and results in .superpowers/sdd/report-completeness-task-1-report.md; independent review follows before model generation.

## Controller preflight

Supplied test seed arity corrected to the existing three-value return; SQL bit values are asserted without bool() coercion. Each family is checked independently; unavailable envelope conservatively invalidates all flags. Count equality is sound because the typed view emits at most one row per source member and suppresses ambiguous identities. SQL execution, not query-text similarity, is the acceptance gate.
