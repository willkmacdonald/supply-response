# Native saved-analysis report generators implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement deterministic native Power BI pages and typed saved-analysis model generation with exact-selection and tamper-detection contracts.

**Architecture:** Two focused Python modules own native PBIR presentation and TMDL semantic generation. They consume the five reviewed SQL projections and expose a typed manifest/binding interface for the paired artifact/preflight integration task. This task tests generation in temporary directories; it does not replace existing checked-in report artifacts or activate app links.

**Tech Stack:** Python 3.12, native PBIR/TMDL, pinned offline Microsoft JSON schemas, pytest. No custom visuals, HTML report substitute, new dependencies or live calls.

## Global Constraints

- The first card at the top left is always the supplier delay, not a platform record.
- Preserve the three-row layout approved in conversation, including the labels on the left.
- Derive every quantity, date, status, and attribution from validated evidence and persisted analysis.
- Project the exact saved snapshot behind the card into the reporting model, not an unlabeled current database value.
- Never silently substitute the latest analysis, a similarly named record, or aggregate records across cases.
- Query filters are navigation context, not access control; Microsoft authorization remains required.
- Preserve original message text, source identifiers, citations, and immutable analysis records.
- Missing values must never be replaced with fabricated zeros.
- A recommendation is never labeled an approval.
- Keep predicted and observed results distinct and retain the permanent Simulated label for simulated observations.
- No live deployment, permission or license changes, analysis runs, approvals or playback in this implementation stage.
- Preserve report logical ID 8ff233ca-a127-5ff7-a559-cfbbb6fc8046 and model logical ID 1808b468-5fe3-542e-9004-ae82d8cbd452. This task does not edit either metadata file.

## File map and interfaces

- `fabric/report_pages.py`: deterministic eight-page native layout and complete document verification; `ORDER`, `artifacts() -> dict[str, dict]`, `required_fields() -> tuple[tuple[str,str,str],...]`, `encoded(value) -> str`, `verify(definition: Path) -> None`, CLI main.
- `fabric/report_model.py`: five disconnected DirectQuery table sources and explicit scoped DAX measures; `TABLES`, `COLUMNS`, `TYPES`, `Measure`, `measures()`, `manifest()`, `column_format(table,name)`, `check_required_fields(required)`, `artifacts(query_directory:Path) -> dict[str,str]`, `verify(definition,query_directory)`, CLI main.
- `tests/fabric/test_report_generators.py`: real generation/schema/drift/scope-expression/binding/prewrite tests. These do not execute DAX.
- Prerequisite: SavedAnalyses completeness extension reviewed and actual SQL green. The model requires its inventory_complete, production_orders_complete and customer_orders_complete boolean columns.
- The next paired artifact/preflight task consumes these exact interfaces, generates checked-in report files, updates strict validation and runs Microsoft's TOM parser. API artifact-bound receipt, app links and traditional walkthrough follow; this generator task does not claim those outcomes.

### Task 1: Implement and test the native generators

**Files:** Create only the two modules and one test file above. Do not modify `fabric/power-bi/`, `fabric/deploy.py`, existing test files, dependency files or source SQL in this task.

- [x] **Step 1: Write the full failing generator tests.**

```python
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from fabric import report_model, report_pages
from fabric.deploy import _validate_offline_json_schemas

ROOT = Path(__file__).resolve().parents[2]
QUERIES = ROOT / "fabric/reporting/queries"


def write_pages(root: Path) -> None:
    for name, value in report_pages.artifacts().items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report_pages.encoded(value), encoding="utf-8")


def write_model(root: Path) -> None:
    for name, value in report_model.artifacts(QUERIES).items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")


def test_deterministic_native_pages_match_pinned_schemas(tmp_path):
    assert report_pages.artifacts() == report_pages.artifacts()
    write_pages(tmp_path)
    report_pages.verify(tmp_path)
    _validate_offline_json_schemas(tmp_path)
    assert report_pages.ORDER == (
        "command-center", "actions-outcomes", "supplier-shipment", "plant-transfer",
        "supplier-qualification", "available-stock", "customer-orders", "response-options",
    )
    for path, value in report_pages.artifacts().items():
        if not path.endswith("visual.json"):
            continue
        position = value["position"]
        assert 0 <= position["x"] < position["x"] + position["width"] <= 1280
        assert 0 <= position["y"] < position["y"] + position["height"] <= 720
        visual = value["visual"]
        if visual["visualType"] == "cardVisual":
            assert set(visual["query"]["queryState"]) == {"Data"}
        if visual["visualType"] in {"tableEx", "clusteredColumnChart"}:
            gate, = value["filterConfig"]["filters"]
            assert gate["isHiddenInViewMode"] and gate["isLockedInViewMode"]
            condition = gate["filter"]["Where"][0]["Condition"]["Comparison"]
            assert condition["ComparisonKind"] == 0
            assert condition["Right"] == {"Literal": {"Value": "1L"}}


def test_preserves_existing_visual_identities_and_three_rows():
    artifacts = report_pages.artifacts()
    old_ids = {
        "command-center": ("active-cases", "current-decision", "otif-loss", "revenue-at-risk", "scenario-effective-time", "showcase-cases"),
        "actions-outcomes": ("action-status", "decision-id", "observation-kind", "predicted-observed-variance", "projection-refresh", "scenario-effective-time"),
    }
    for page, identities in old_ids.items():
        for identity in identities:
            assert f"pages/{page}/visuals/{identity}/visual.json" in artifacts
    first = artifacts["pages/command-center/visuals/active-cases/visual.json"]
    assert first["visual"]["query"]["queryState"]["Data"]["projections"][0]["queryRef"] == "CaseCommandCenter.Disruption Answer"
    for row in (1, 2, 3):
        assert f"pages/command-center/visuals/row-label-{row}/visual.json" in artifacts


def test_clearable_case_selector_is_shared_without_a_default():
    for page in report_pages.ORDER:
        value = report_pages.artifacts()[f"pages/{page}/visuals/case-selector/visual.json"]["visual"]
        assert value["syncGroup"] == {"groupName": "SupplyResponseCase", "fieldChanges": True, "filterChanges": True}
        selection = value["objects"]["selection"][0]["properties"]
        assert selection["singleSelect"] == {"expr": {"Literal": {"Value": "true"}}}
        assert selection["strictSingleSelect"] == {"expr": {"Literal": {"Value": "false"}}}
        assert "general" not in value["objects"]
        assert value["query"]["queryState"]["Values"]["projections"][0]["queryRef"] == "CaseCommandCenter.case_id"


def test_business_tables_preserve_stock_totals_and_order_line_grain():
    artifacts = report_pages.artifacts()
    def projections(page):
        return artifacts[f"pages/{page}/visuals/supporting-records/visual.json"]["visual"]["query"]["queryState"]["Values"]["projections"]
    stock = projections("available-stock")
    assert [item["queryRef"] for item in stock] == [
        "SavedRecords.part_id", "SavedRecords.plant_id", "CaseCommandCenter.Stock On Hand Row",
        "CaseCommandCenter.Stock Held Row", "CaseCommandCenter.Stock Protected Row", "CaseCommandCenter.Stock Usable Row",
    ]
    orders = projections("customer-orders")
    assert any(item["queryRef"] == "SavedRecords.source_record_id" and item["displayName"] == "Order line" for item in orders)


@pytest.mark.parametrize("change", ["unlock", "remove-gate", "role", "field", "type", "title", "aggregation", "extra"])
def test_schema_shaped_report_mutations_fail(tmp_path, change):
    write_pages(tmp_path)
    path = tmp_path / "pages/supplier-shipment/visuals/supporting-records/visual.json"
    value = json.loads(path.read_text())
    visual = value["visual"]
    if change == "unlock":
        value["filterConfig"]["filters"][0]["isLockedInViewMode"] = False
    elif change == "remove-gate":
        del value["filterConfig"]
    elif change == "role":
        visual["query"]["queryState"]["Data"] = visual["query"]["queryState"].pop("Values")
    elif change == "field":
        visual["query"]["queryState"]["Values"]["projections"][0]["field"]["Column"]["Property"] = "other"
    elif change == "type":
        visual["visualType"] = "card"
    elif change == "title":
        visual["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"] = "'Wrong'"
    elif change == "aggregation":
        projection = visual["query"]["queryState"]["Values"]["projections"][0]
        projection["field"] = {"Aggregation": {"Expression": deepcopy(projection["field"]), "Function": 0}}
    else:
        (tmp_path / "pages/extra.json").write_text("{}")
    path.write_text(report_pages.encoded(value), encoding="utf-8")
    with pytest.raises(ValueError):
        report_pages.verify(tmp_path)


def test_model_manifest_binds_every_report_field_without_json_payloads(tmp_path):
    report_model.check_required_fields(report_pages.required_fields())
    manifest = report_model.manifest()
    assert set(manifest["tables"]) == {"CaseCommandCenter", "ActionOutcomes", "SavedAnalyses", "SavedRecords", "SavedOptions"}
    assert manifest["relationships"] == []
    for flag in ("inventory_complete", "production_orders_complete", "customer_orders_complete"):
        assert manifest["tables"]["SavedAnalyses"]["columns"][flag] == "boolean"
    for table, details in manifest["tables"].items():
        assert details["mode"] == "directQuery"
        assert details["partition"] == table
        assert all(not name.endswith("_json") for name in details["columns"])
    with pytest.raises(ValueError, match="Unknown report binding"):
        report_model.check_required_fields([("Measure", "CaseCommandCenter", "Not an approved measure")])
    write_model(tmp_path)
    report_model.verify(tmp_path, QUERIES)
    assert report_model.artifacts(QUERIES) == report_model.artifacts(QUERIES)


def test_all_dax_bindings_resolve_and_selection_gates_are_explicit():
    manifest = report_model.manifest()["tables"]
    measures = report_model.measures()
    names = {name for definitions in measures.values() for name in definitions}
    for definitions in measures.values():
        for measure in definitions.values():
            for table, field in re.findall(r"(\w+)\[([^\]]+)\]", measure.expression):
                assert table in manifest, (table, field)
                assert field in manifest[table]["columns"] or field in manifest[table]["measures"], (table, field)
            for name in re.findall(r"(?<![\w'])\[([^\]]+)\]", measure.expression):
                assert name in names, name
            assert "NOW()" not in measure.expression.upper()
    cc = measures["CaseCommandCenter"]
    assert "[Selected inventory_complete] == TRUE()" in cc["Stock Rows Valid"].expression
    assert "[Overview inventory_complete] == TRUE()" in cc["Overview Stock Rows Valid"].expression
    assert "[Selected production_orders_complete] == TRUE()" in cc["Orders Rows Valid"].expression
    assert "[Selected customer_orders_complete] == TRUE()" in cc["Orders Rows Valid"].expression
    assert "ALLSELECTED(CaseCommandCenter)" in cc["Selected Case Key"].expression
    assert "HASONEFILTER(CaseCommandCenter[case_key])" in cc["External Selected Case Key"].expression
    assert "[Analysis Requested] == 1" in cc["Overview Analysis Key"].expression
    for gate in ("Record Row Visible", "Stock Row Visible", "Order Row Visible", "Option Row Visible"):
        expression = cc[gate].expression
        assert "[Selected Case Key]" in expression and "[Selected Analysis Key]" in expression
        assert "KEEPFILTERS" in expression and "TREATAS" in expression
        assert "REMOVEFILTERS" not in expression
    for gate in ("Action Row Visible", "Observation Row Visible"):
        expression = cc[gate].expression
        assert "[Selected Case Key]" in expression and "[Current Decision Key]" in expression
        assert "ActionOutcomes[decision_key]" in expression
    variance = measures["ActionOutcomes"]["Observed Variance"].expression
    assert "[Observation Row Visible] == 1" in variance
    assert "IFERROR(VALUE(PredictedText), BLANK())" in variance
    assert "IFERROR(VALUE(ObservedText), BLANK())" in variance
    assert "Predicted == 0" in variance and "ABS(Predicted)" in variance
    assert "AVERAGEX" not in variance and "REMOVEFILTERS" not in variance


def test_formats_preserve_dates_utc_zero_and_literal_m_escapes():
    assert report_model.column_format("SavedRecords", "due_date") == "MMM d, yyyy"
    assert report_model.column_format("SavedRecords", "retrieved_at") == 'MMM d, yyyy HH:mm "UTC"'
    assert report_model.column_format("SavedOptions", "response_cost") == "#,0.00"
    assert report_model.column_format("SavedOptions", "otif_loss_percentage") == '0"%"'
    assert report_model.m_string('#(lf)\n"quoted"') == '"#(#)(lf)#(lf)""quoted"""'
    cc = report_model.measures()["CaseCommandCenter"]
    for name in ("Record Quantity Display", "Record Unit Cost Display", "Stock Usable Display"):
        assert "ISBLANK(V)" in cc[name].expression
    for name in ("Record Audit Display", "Record First Article Display"):
        assert 'IF(ISBLANK(V),"Unavailable",IF(V,"Complete","Outstanding"))' in cc[name].expression


@pytest.mark.parametrize("change", ["measure", "partition", "relationship", "extra-table"])
def test_model_drift_fails(tmp_path, change):
    write_model(tmp_path)
    path = tmp_path / "tables/CaseCommandCenter.tmdl"
    if change == "measure":
        path.write_text(path.read_text().replace("HASONEFILTER", "HASONEVALUE", 1))
    elif change == "partition":
        path.write_text(path.read_text().replace("mode: directQuery", "mode: import", 1))
    elif change == "relationship":
        (tmp_path / "relationships.tmdl").write_text("relationship NotApproved\n")
    else:
        (tmp_path / "tables/Extra.tmdl").write_text("table Extra\n")
    with pytest.raises(ValueError):
        report_model.verify(tmp_path, QUERIES)


@pytest.mark.parametrize("kind", ["pages-root", "definition-root", "tables-root", "query-root"])
def test_symlink_roots_are_rejected(tmp_path, kind):
    actual = tmp_path / "actual"
    alias = tmp_path / "alias"
    actual.mkdir()
    alias.mkdir()
    if kind in {"pages-root", "definition-root"}:
        write_pages(actual)
        if kind == "pages-root":
            (alias / "pages").symlink_to(actual / "pages", target_is_directory=True)
            candidate = alias
        else:
            candidate = tmp_path / "definition-link"
            candidate.symlink_to(actual, target_is_directory=True)
        with pytest.raises(ValueError):
            report_pages.verify(candidate)
    else:
        write_model(actual)
        if kind == "tables-root":
            (alias / "tables").symlink_to(actual / "tables", target_is_directory=True)
            with pytest.raises(ValueError):
                report_model.verify(alias, QUERIES)
        else:
            query_link = tmp_path / "queries"
            query_link.symlink_to(QUERIES, target_is_directory=True)
            with pytest.raises(ValueError):
                report_model.artifacts(query_link)


def test_model_cli_rejects_late_symlink_before_any_write(tmp_path, monkeypatch):
    import sys

    write_model(tmp_path)
    first = tmp_path / "tables/CaseCommandCenter.tmdl"
    first.write_text("preserve sentinel", encoding="utf-8")
    last = tmp_path / "tables/SavedOptions.tmdl"
    last.unlink()
    outside = tmp_path / "unchanged.txt"
    outside.write_text("outside sentinel", encoding="utf-8")
    last.symlink_to(outside)
    monkeypatch.setattr(sys, "argv", ["report_model", str(tmp_path), str(QUERIES)])
    with pytest.raises(ValueError):
        report_model.main()
    assert first.read_text() == "preserve sentinel"
    assert outside.read_text() == "outside sentinel"


def test_page_cli_rejects_late_symlink_before_any_write(tmp_path, monkeypatch):
    import sys

    write_pages(tmp_path)
    first = tmp_path / "pages/pages.json"
    first.write_text("preserve sentinel", encoding="utf-8")
    final_relative = list(report_pages.artifacts())[-1]
    last = tmp_path / final_relative
    last.unlink()
    outside = tmp_path / "unchanged.txt"
    outside.write_text("outside sentinel", encoding="utf-8")
    last.symlink_to(outside)
    monkeypatch.setattr(sys, "argv", ["report_pages", str(tmp_path)])
    with pytest.raises(ValueError):
        report_pages.main()
    assert first.read_text() == "preserve sentinel"
    assert outside.read_text() == "outside sentinel"

def test_exposure_page_repeats_saved_baseline_with_strict_analysis_scope():
    pages = report_pages.artifacts()
    def answer(index):
        return pages[f"pages/customer-orders/visuals/answer-{index}/visual.json"]["visual"]["query"]["queryState"]["Data"]["projections"][0]["queryRef"]
    assert answer(1) == "CaseCommandCenter.Orders Baseline Revenue Display"
    assert answer(2) == "CaseCommandCenter.Orders Baseline OTIF Display"
    assert answer(3) == "CaseCommandCenter.Affected Lines Display"
    definitions = report_model.manifest()["tables"]["CaseCommandCenter"]["measures"]
    for name, source in (("Orders Baseline Revenue", "Baseline revenue_at_risk"),
                         ("Orders Baseline OTIF", "Baseline otif_loss_percentage")):
        expression = definitions[name]["expression"]
        assert "NOT ISBLANK([Selected Analysis Key])" in expression
        assert "[" + source + "]" in expression
    assert '"0"' in definitions["Orders Baseline OTIF Display"]["expression"]
    assert '"%"' in definitions["Orders Baseline OTIF Display"]["expression"]
    assert "Without a response" in definitions["Orders Explanation"]["expression"]
    assert "do not identify individual missed service targets" in definitions["Orders Explanation"]["expression"]

def test_business_measures_are_implemented_and_use_saved_values():
    tables = report_model.manifest()["tables"]
    definitions = tables["CaseCommandCenter"]["measures"]
    assert not [
        name for table in tables.values() for name, spec in table["measures"].items()
        if spec["expression"].strip() == "BLANK()"
    ]
    for name in ("Baseline revenue_at_risk", "Recommended revenue_at_risk", "Approved revenue_at_risk"):
        text = definitions[name]["expression"]
        assert "SELECTEDVALUE(SavedOptions[revenue_at_risk])" in text
        assert "COUNTROWS(SavedOptions) == 1" in text
        assert "TREATAS" in text
    assert "SUM(SavedRecords[usable_inventory])" in definitions["Stock Usable"]["expression"]
    assert "[Overview disruption original_quantity]" in definitions["Disruption Answer"]["expression"]
    variance = tables["ActionOutcomes"]["measures"]["Observed Variance"]["expression"]
    assert "DIVIDE(Observed - Predicted, ABS(Predicted))" in variance
    assert "ISBLANK(Predicted) || ISBLANK(Observed) || Predicted == 0" in variance
    assert "[Observation Row Visible] == 1" in variance
```

- [x] **Step 2: Run RED before creating either module.**

```sh
.venv/bin/pytest tests/fabric/test_report_generators.py -o addopts='' -q
```

Expected missing report_model/report_pages imports: these feature modules do not exist. Record exact failure and distinguish it from a dependency or fixture failure.

- [x] **Step 3: Create the complete page generator.**

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
PAGE_SCHEMA = BASE + "page/2.0.0/schema.json"
VISUAL_SCHEMA = BASE + "visualContainer/2.9.0/schema.json"
PAGES_SCHEMA = BASE + "pagesMetadata/1.1.0/schema.json"
ORDER = ("command-center", "actions-outcomes", "supplier-shipment", "plant-transfer",
         "supplier-qualification", "available-stock", "customer-orders", "response-options")
GREEN, TEAL, AMBER, CREAM, WHITE = "#183E35", "#187D78", "#9A641C", "#F5F3EA", "#FFFFFF"
CC, SR, SO, AO = "CaseCommandCenter", "SavedRecords", "SavedOptions", "ActionOutcomes"


def literal(value):
    token = ("true" if value else "false") if isinstance(value, bool) else (
        str(value) + "D" if isinstance(value, (int, float)) else "'" + value.replace("'", "''") + "'")
    return {"expr": {"Literal": {"Value": token}}}


def color(value):
    return {"solid": {"color": literal(value)}}


def obj(properties, instance=False):
    item = {"properties": properties}
    if instance:
        item["selector"] = {"id": "default"}
    return [item]


def field(kind, table, name, source=False):
    return {kind: {"Expression": {"SourceRef": {"Source" if source else "Entity": table}},
                   "Property": name}}


def projection(kind, table, name, label=None):
    result = {"field": field(kind, table, name), "queryRef": table + "." + name}
    if label is not None:
        result["displayName"] = label
    return result


def measure(name, label=None, table=CC):
    return projection("Measure", table, name, label)


def column(table, name):
    return projection("Column", table, name, name.replace("_", " ").capitalize())


def gate(name):
    return {"name": "Locked" + name.replace(" ", ""), "field": field("Measure", CC, name),
            "type": "Advanced", "howCreated": "User", "isHiddenInViewMode": True,
            "isLockedInViewMode": True,
            "filter": {"Version": 2, "From": [{"Name": "c", "Entity": CC, "Type": 0}],
                       "Where": [{"Condition": {"Comparison": {"ComparisonKind": 0,
                           "Left": field("Measure", "c", name, True),
                           "Right": {"Literal": {"Value": "1L"}}}}}]}}


def family_filter(family):
    return {"name": "LockedRecordFamily", "field": field("Column", SR, "record_family"),
            "type": "Categorical", "howCreated": "User", "isHiddenInViewMode": True,
            "isLockedInViewMode": True,
            "filter": {"Version": 2, "From": [{"Name": "r", "Entity": SR, "Type": 0}],
                       "Where": [{"Condition": {"In": {
                           "Expressions": [field("Column", "r", "record_family", True)],
                           "Values": [[{"Literal": {"Value": "'" + family + "'"}}]]}}}]}}


def base_visual(name, kind, rect, title=None, fill=WHITE):
    x, y, width, height = rect
    vco = {"background": obj({"show": literal(True), "color": color(fill), "transparency": literal(0)}),
           "border": obj({"show": literal(False)}),
           "padding": obj({k: literal(4) for k in ("top", "bottom", "left", "right")}),
           "title": obj({"show": literal(title is not None), "text": literal(title or ""),
                         "fontColor": color(GREEN), "fontSize": literal(12), "fontFamily": literal("Segoe UI")})}
    return {"$schema": VISUAL_SCHEMA, "name": name,
            "position": {"x": x, "y": y, "width": width, "height": height, "z": 0, "tabOrder": 0},
            "visual": {"visualType": kind, "visualContainerObjects": vco}}


def text(name, value, rect, size=20, fill=CREAM, ink=GREEN):
    v = base_visual(name, "textbox", rect, fill=fill)
    v["visual"]["objects"] = {"general": obj({"paragraphs": [{"textRuns": [{"value": value,
        "textStyle": {"fontFamily": "Segoe UI", "fontSize": str(size) + "px", "color": ink}}],
        "horizontalTextAlignment": "left"}]})}
    return v


def card(name, title, value, rect, accent=TEAL, size=18):
    v = base_visual(name, "cardVisual", rect, title)
    v["visual"]["query"] = {"queryState": {"Data": {"projections": [measure(value, title)]}}}
    v["visual"]["objects"] = {
        "value": obj({"fontSize": literal(size), "fontColor": color(GREEN)}, True),
        "label": obj({"show": literal(True), "text": literal(""), "fontSize": literal(12)}, True),
        "outline": obj({"show": literal(False)}, True),
        "padding": obj({"paddingUniform": literal(4)}, True),
        "layout": obj({"paddingUniform": literal(0)}, True),
        "spacing": obj({"verticalSpacing": literal(0)}, True),
        "accentBar": obj({"show": literal(True), "position": literal("Left"),
                          "width": literal(3), "color": color(accent)}, True)}
    # Explicit padding/title/value/label heights; leave room for the always-rendered label.
    assert 8 + 18 + 8 + int(size * 1.5 + .999) + 18 <= rect[3]
    return v


def table(name, title, entity, names, scope, rect):
    v = base_visual(name, "tableEx", rect, title)
    v["visual"]["query"] = {"queryState": {"Values": {"projections": [column(entity, n) for n in names]}}}
    v["filterConfig"] = {"filters": [gate(scope)]}
    v["visual"]["objects"] = {
        "columnHeaders": obj({"fontColor": color(WHITE), "backColor": color(GREEN), "fontSize": literal(11)}),
        "values": obj({"fontColorPrimary": color(GREEN), "backColorPrimary": color(WHITE),
                       "backColorSecondary": color(CREAM), "fontSize": literal(11)}),
        "total": obj({"totals": literal(False)}),
        "grid": obj({"rowPadding": literal(5)})}
    return v


RECORD_IDS = ("case_key", "analysis_key", "record_key", "record_family")
OPTION_IDS = ("case_key", "analysis_key", "option_key")
DETAILS = {
    "supplier-shipment": ("What can the original supplier still supply?", "shipment", "Record State",
        (("Scheduled quantity", "Record Quantity Display"), ("Scheduled receipt", "Record Due Date Display"),
         ("Incremental cost per unit", "Record Unit Cost Display")), "Record Explanation", "Record Row Visible",
        ("supplier_id", "part_id", "plant_id", "quantity", "due_date", "incremental_cost_per_unit")),
    "plant-transfer": ("Can another plant help?", "transfer", "Record State",
        (("Transfer quantity", "Record Quantity Display"), ("Arrival date", "Record Arrival Date Display"),
         ("Incremental cost per unit", "Record Unit Cost Display")), "Record Explanation", "Record Row Visible",
        ("source_plant_id", "destination_plant_id", "part_id", "quantity", "dispatch_date", "arrival_date", "incremental_cost_per_unit")),
    "supplier-qualification": ("Can we use the alternate supplier?", "qualification", "Record State",
        (("Qualification status", "Record Status Display"), ("Audit requirement", "Record Audit Display"),
         ("First article requirement", "Record First Article Display")), "Record Explanation", "Record Row Visible",
        ("supplier_id", "part_id", "status", "audit_complete", "first_article_complete", "expected_decision_date")),
    "available-stock": ("What do we have available?", None, "Stock State",
        (("Usable component units", "Stock Usable Display"), ("Units on quality hold", "Stock Held Display"),
         ("Protected allocation", "Stock Protected Display")), "Stock Explanation", "Stock Row Visible",
        ("part_id", "plant_id", "on_hand", "quality_hold", "protected_allocation", "usable_inventory")),
    "customer-orders": ("What does that put at risk?", None, "Orders State",
        (("Revenue at risk — without a response", "Orders Baseline Revenue Display"),
         ("Order lines expected to miss on-time, in-full", "Orders Baseline OTIF Display"),
         ("Order lines in this saved plan", "Affected Lines Display")), "Orders Explanation", "Order Row Visible",
        ("customer_order_id", "product_id", "plant_id", "quantity", "due_date", "line_revenue")),
}


def case_selector():
    v = base_visual("case-selector", "slicer", (952, 62, 304, 90))
    v["visual"]["query"] = {"queryState": {"Values": {"projections": [column(CC, "case_id")]}}}
    v["visual"]["syncGroup"] = {"groupName": "SupplyResponseCase", "fieldChanges": True, "filterChanges": True}
    v["visual"]["visualContainerObjects"]["padding"] = obj({k: literal(8) for k in ("top", "bottom", "left", "right")})
    v["visual"]["objects"] = {
        "data": obj({"mode": literal("Dropdown")}),
        "selection": obj({"singleSelect": literal(True), "strictSingleSelect": literal(False),
                          "selectAllCheckboxEnabled": literal(False)}),
        "header": obj({"show": literal(True), "text": literal("Select a case"),
                       "textSize": literal(11), "fontColor": color(GREEN)}),
        "items": obj({"textSize": literal(11), "fontColor": color(GREEN)})}
    return v


def common(title, state):
    return [text("page-title", title, (24, 14, 1232, 40), 26),
            card("selection-state", "Selected case and analysis", state, (24, 62, 916, 90), size=14),
            case_selector(),
            text("fictional-footer", "Snapshot used for this analysis · Demo corpus — fictional · Use page tabs to explore this case",
                 (24, 682, 1232, 26), 13)]


def detail(page):
    title, family, state, metrics, explanation, scope, fields = DETAILS[page]
    items = common(title, state)
    for i, (label, value) in enumerate(metrics):
        items.append(card("answer-" + str(i + 1), label, value, (24 + 416 * i, 164, 400, 108),
                          (TEAL, GREEN, AMBER)[i]))
    items.append(card("explanation", "What this means for the response", explanation, (24, 284, 1232, 90), size=14))
    supporting = table("supporting-records", "Supporting saved records", SR, fields, scope, (24, 386, 1232, 166))
    if page == "available-stock":
        supporting["visual"]["query"]["queryState"]["Values"]["projections"] = [
            column(SR, "part_id"), column(SR, "plant_id"),
            measure("Stock On Hand Row", "On hand"), measure("Stock Held Row", "Quality hold"),
            measure("Stock Protected Row", "Protected allocation"), measure("Stock Usable Row", "Usable units")]
    elif page == "customer-orders":
        supporting["visual"]["query"]["queryState"]["Values"]["projections"].insert(
            0, projection("Column", SR, "source_record_id", "Order line"))
    items.append(supporting)
    items.append(table("source-details", "Source details — identifiers retain their original values", SR,
                       ("source_record_id", "case_id", "analysis_id", "analysis_created_at", "source_timestamp", "retrieved_at", "evidence_state") + RECORD_IDS,
                       scope, (24, 564, 1232, 106)))
    return title, items, family


def overview():
    items = common("Case dashboard", "Overview State")
    rows = (
        ("1. Understand\nthe disruption", (
            ("active-cases", "What changed?", "Disruption Answer"),
            ("revenue-at-risk", "What do we have available?", "Availability Answer"),
            ("otif-loss", "What does that put at risk?", "Exposure Answer"))),
        ("2. Investigate\nresponses", (
            ("scenario-effective-time", "What can the original supplier still supply?", "Shipment Answer"),
            ("showcase-cases", "Can another plant help?", "Transfer Answer"),
            ("qualification-answer", "Can we use the alternate supplier?", "Qualification Answer"))),
        ("3. Make\nthe decision", (
            ("options-answer", "Compare the options", "Options Answer"),
            ("recommendation-answer", "Saved recommendation", "Recommendation Answer"),
            ("current-decision", "Recorded decision", "Decision Answer"))))
    for row, (label, cards) in enumerate(rows):
        y = 166 + row * 170
        items.append(text("row-label-" + str(row + 1), label, (24, y + 20, 190, 96), 20))
        for col, (name, question, value) in enumerate(cards):
            items.append(card(name, question, value, (226 + col * 348, y, 334, 156),
                              (TEAL, GREEN, AMBER)[row], size=14))
    return "Case dashboard", items, None


def options():
    items = common("Compare the response options", "Options State")
    for i, (title, value) in enumerate((("Selected option", "Selected Option Display"),
            ("Expected revenue at risk", "Option Revenue Display"), ("Response cost", "Option Cost Display"))):
        items.append(card("option-answer-" + str(i), title, value, (24 + 416 * i, 164, 400, 108)))
    items.append(card("option-explanation", "Expected if we take this option", "Options Explanation", (24, 284, 1232, 90), size=14))
    items.append(table("option-comparison", "Saved options — expected results, subject to planning requirements", SO,
        ("option_name", "is_baseline", "executable", "response_cost", "revenue_at_risk",
         "otif_loss_percentage", "uncovered_part_demand", "blockers_text", "required_roles_text"),
        "Option Row Visible", (24, 386, 1232, 176)))
    items.append(table("source-details", "Source details — saved option identities", SO,
        ("option_name", "option_id") + OPTION_IDS, "Option Row Visible", (24, 574, 1232, 96)))
    return "Response options", items, None


def actions():
    items = common("Current decision: actions and outcomes", "Actions State")
    for i, (name, title, value) in enumerate((
        ("decision-id", "Current governing decision", "Current Decision Display"),
        ("observation-kind", "Observation context", "Current Observation Display"),
        ("scenario-effective-time", "In this scenario, as of", "Scenario Context"),
        ("projection-refresh", "Projection updated", "Projection Updated Display"))):
        items.append(card(name, title, value, (24 + 312 * i, 164, 296, 108), size=14))
    items.append(card("action-explanation", "Current decision lineage", "Action Explanation", (24, 284, 1232, 90), size=14))
    items.append(table("action-status", "Current actions", AO,
        ("action_kind", "action_status"), "Action Row Visible", (24, 386, 604, 176)))
    items.append(table("source-details", "Source details — current action identities", AO,
        ("action_kind", "case_key", "decision_key", "action_key"),
        "Action Row Visible", (24, 574, 604, 96)))
    chart = base_visual("predicted-observed-variance", "clusteredColumnChart", (644, 386, 612, 284),
                        "Observed variance — recorded metrics only")
    chart["visual"]["query"] = {"queryState": {
        "Category": {"projections": [column(AO, "metric")]},
        "Series": {"projections": [column(AO, "observation_kind")]},
        "Y": {"projections": [measure("Observed Variance", "Variance", AO)]}}}
    chart["visual"]["objects"] = {
        "labels": obj({"show": literal(True), "fontSize": literal(11)}),
        "dataPoint": obj({"defaultColor": color(TEAL)}),
        "legend": obj({"show": literal(True), "fontSize": literal(11)}),
        "categoryAxis": obj({"fontSize": literal(11)}),
        "valueAxis": obj({"show": literal(True), "fontSize": literal(11)})}
    chart["filterConfig"] = {"filters": [gate("Observation Row Visible")]}
    items.append(chart)
    return "Actions and outcomes", items, None


def artifacts():
    result = {"pages/pages.json": {"$schema": PAGES_SCHEMA, "pageOrder": list(ORDER), "activePageName": ORDER[0]}}
    for page in ORDER:
        title, items, family = (overview() if page == ORDER[0] else actions() if page == ORDER[1]
                                else options() if page == "response-options" else detail(page))
        definition = {"$schema": PAGE_SCHEMA, "name": page, "displayName": title, "displayOption": "FitToPage",
            "width": 1280, "height": 720, "objects": {
                "background": obj({"color": color(CREAM), "transparency": literal(0)}),
                "pageRefresh": [{"properties": {"show": True, "refreshType": "FixedInterval", "duration": 30}}]}}
        if family:
            definition["filterConfig"] = {"filters": [family_filter(family)]}
        result[f"pages/{page}/page.json"] = definition
        for order, visual in enumerate(sorted(items, key=lambda v: (v["position"]["y"], v["position"]["x"]))):
            visual["position"].update(z=order, tabOrder=order)
            result[f"pages/{page}/visuals/{visual['name']}/visual.json"] = visual
    return result


def required_fields():
    found = set()
    def visit(value):
        if isinstance(value, dict):
            for kind in ("Column", "Measure"):
                binding = value.get(kind)
                if isinstance(binding, dict):
                    entity = binding.get("Expression", {}).get("SourceRef", {}).get("Entity")
                    if entity:
                        found.add((kind, entity, binding["Property"]))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(artifacts())
    return tuple(sorted(found))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def verify(definition):
    expected = artifacts()
    if definition.is_symlink() or (definition / "pages").is_symlink():
        raise ValueError("Report definition and pages roots must not be symbolic links")
    paths = list((definition / "pages").rglob("*"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("Report artifacts must not contain symbolic links")
    actual = {p.relative_to(definition).as_posix() for p in paths if p.is_file()}
    if actual != set(expected):
        raise ValueError("Report page file inventory differs from the approved generator")
    expected_dirs = {parent.as_posix() for name in expected for parent in Path(name).parents
                     if parent.as_posix() not in {".", "pages"}}
    actual_dirs = {p.relative_to(definition).as_posix() for p in paths if p.is_dir()}
    if actual_dirs != expected_dirs:
        raise ValueError("Report page directory inventory differs from the approved generator")
    for path, value in expected.items():
        if (definition / path).read_text(encoding="utf-8") != encoded(value):
            raise ValueError("Report artifact differs from approved generation: " + path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("definition", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verify(args.definition)
        return
    expected = artifacts()
    # Validate all destinations before writing; never traverse a linked output directory.
    for relative in expected:
        target = args.definition / relative
        for candidate in (target, *target.parents):
            if candidate.is_symlink():
                raise ValueError("Refusing symbolic-link output path")
            if candidate == args.definition:
                break
    # No deletion: unexpected pre-existing files require explicit reviewed migration.
    for relative, value in expected.items():
        path = args.definition / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded(value), encoding="utf-8")
    verify(args.definition)


if __name__ == "__main__":
    main()
```

- [x] **Step 4: Create the complete semantic generator.**

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
from pathlib import Path

CC, SA, SR, SO, AO = ('CaseCommandCenter', 'SavedAnalyses', 'SavedRecords', 'SavedOptions', 'ActionOutcomes')
TABLES = (CC, AO, SA, SR, SO)
COLUMNS = {
 CC: '''case_id purpose status runtime_mode scenario_effective_time current_analysis_id current_decision_id analysis_created_at snapshot_state recommended_option_id baseline_option_id decision_kind decision_analysis_id decided_at approved_option_id baseline_revenue_at_risk baseline_otif_loss_percentage baseline_uncovered_part_demand baseline_response_cost recommended_revenue_at_risk recommended_otif_loss_percentage recommended_uncovered_part_demand recommended_response_cost approved_revenue_at_risk approved_otif_loss_percentage approved_uncovered_part_demand approved_response_cost case_key current_analysis_key current_decision_key decision_analysis_key approved_option_key'''.split(),
 SA: '''case_id analysis_id runtime_mode analysis_started_at retrieval_window_ends_at analysis_created_at scenario_effective_time calculation_version recommended_option_id payload_state snapshot_state inventory_complete production_orders_complete customer_orders_complete case_key analysis_key recommended_option_key'''.split(),
 SO: '''case_id analysis_id option_id option_kind option_name is_baseline is_recommended executable active_mitigation uncovered_part_demand otif_loss_percentage revenue_at_risk margin_at_risk response_cost blockers_text required_roles_text assumptions_text protected_customer_order_count case_key analysis_key option_key'''.split(),
 AO: '''case_id decision_id selected_option_id record_type action_id action_kind action_status metric predicted_value observed_value unit observation_kind scenario_effective_time projection_updated_at case_key decision_key action_key'''.split(),
 SR: '''case_id analysis_id record_family source_record_id runtime_mode analysis_created_at scenario_effective_time record_state supplier_id part_id plant_id source_plant_id destination_plant_id product_id customer_id production_order_id customer_order_id po_line_id quantity due_date dispatch_date arrival_date incremental_cost_per_unit status evidence_ref audit_complete first_article_complete effective_date expected_decision_date on_hand quality_hold protected_allocation usable_inventory component_demand customer_priority customer_revenue customer_margin unit_revenue unit_margin line_revenue original_quantity partial_quantity original_due_date partial_due_date recovery_date source_ref evidence_state provenance evidence_id source_id source_system synthetic source_timestamp retrieved_at case_key analysis_key record_key part_key plant_key product_key source_plant_key destination_plant_key production_order_key in_disruption_scope'''.split(),
}
EXCEPTIONS = {
 CC: {'dateTime': 'scenario_effective_time analysis_created_at decided_at',
      'int64': 'baseline_otif_loss_percentage baseline_uncovered_part_demand recommended_otif_loss_percentage recommended_uncovered_part_demand approved_otif_loss_percentage approved_uncovered_part_demand',
      'decimal': 'baseline_revenue_at_risk baseline_response_cost recommended_revenue_at_risk recommended_response_cost approved_revenue_at_risk approved_response_cost'},
 SA: {'dateTime': 'analysis_started_at retrieval_window_ends_at analysis_created_at scenario_effective_time',
      'boolean': 'inventory_complete production_orders_complete customer_orders_complete'},
 SO: {'boolean': 'is_baseline is_recommended executable active_mitigation',
      'int64': 'uncovered_part_demand otif_loss_percentage protected_customer_order_count',
      'decimal': 'revenue_at_risk margin_at_risk response_cost'},
 AO: {'dateTime': 'scenario_effective_time projection_updated_at'},
 SR: {'dateTime': 'analysis_created_at scenario_effective_time due_date dispatch_date arrival_date effective_date expected_decision_date original_due_date partial_due_date recovery_date source_timestamp retrieved_at',
      'boolean': 'audit_complete first_article_complete synthetic in_disruption_scope',
      'int64': 'quantity on_hand quality_hold protected_allocation usable_inventory component_demand customer_priority original_quantity partial_quantity',
      'decimal': 'incremental_cost_per_unit customer_revenue customer_margin unit_revenue unit_margin line_revenue'},
}
TYPES = {t: {c: 'string' for c in COLUMNS[t]} for t in TABLES}
for _table, _groups in EXCEPTIONS.items():
    for _type, _names in _groups.items():
        for _column in _names.split():
            assert _column in TYPES[_table]
            TYPES[_table][_column] = _type
DATE_ONLY = {'due_date','dispatch_date','arrival_date','effective_date','expected_decision_date',
             'original_due_date','partial_due_date','recovery_date'}


def column_format(table, name):
    kind = TYPES[table][name]
    if kind == 'dateTime':
        return 'MMM d, yyyy' if name in DATE_ONLY else 'MMM d, yyyy HH:mm "UTC"'
    if kind == 'decimal':
        return '#,0.00'
    if kind == 'int64':
        return '0"%"' if name.endswith('otif_loss_percentage') else '#,0'
    return None


def col(table, name):
    return table + '[' + name + ']'


def lit(value):
    return '"' + value.replace('"', '""') + '"'


def calc(expression, filters):
    return 'CALCULATE(' + expression + ', ' + ', '.join(filters) + ')'


def key_filter(table, field, variable):
    return 'KEEPFILTERS(TREATAS({' + variable + '}, ' + col(table, field) + '))'


def eq(table, field, value):
    return 'KEEPFILTERS(' + col(table, field) + ' == ' + value + ')'


def scoped(table, expression, *, analysis='[Selected Analysis Key]', family=None,
           extra=(), clear=False, decision=False):
    variables = 'VAR C = [Selected Case Key]\n'
    variables += 'VAR A = ' + ('[Current Decision Key]' if decision else analysis) + '\n'
    filters = (['REMOVEFILTERS(' + table + ')'] if clear else [])
    filters += [key_filter(table, 'case_key', 'C'),
                key_filter(table, 'decision_key' if decision else 'analysis_key', 'A')]
    if family:
        filters += [eq(table, 'record_family', lit(family))]
    filters += list(extra)
    return variables + 'RETURN IF(NOT ISBLANK(C) && NOT ISBLANK(A), ' + calc(expression, filters) + ')'


@dataclass(frozen=True)
class Measure:
    expression: str
    result_type: str = 'string'
    format_string: str | None = None
    hidden: bool = False


def measures():
    result = {t: {} for t in TABLES}
    def add(name, expression, kind='string', fmt=None, hidden=False, table=CC):
        assert name not in result[table], name
        # Avoid R1C1-reserved single-letter C as a DAX variable name.
        expression = re.sub(r'\bC\b', 'ScopeCase', expression)
        expression = re.sub(r'\bA\b', 'ScopeAnalysis', expression)
        result[table][name] = Measure(expression, kind, fmt, hidden)
    def external(name, expression, table, kind='string'):
        helper = 'External ' + name
        add(helper, expression, kind, hidden=True)
        add(name, calc('[' + helper + ']', ['ALLSELECTED(' + table + ')']), kind, hidden=True)
    def display(name, source, suffix='', fmt='#,0.##'):
        add(name, 'VAR V = [' + source + '] RETURN IF(ISBLANK(V), "Unavailable", FORMAT(V, '
            + lit(fmt) + ') & ' + lit(suffix) + ')')
    def textvalue(name, source):
        add(name, 'VAR V = [' + source + '] RETURN IF(ISBLANK(V), "Unavailable", V)')
    def entity(name, source, kind):
        pairs = ({'RL-SUP-ALPHA':'RL-Supplier Alpha — Current supplier',
                  'RL-SUP-BETA':'RL-Supplier Beta — Alternate supplier'} if kind == 'Supplier'
                 else {'RL-PLANT-DAL':'Dallas plant','RL-PLANT-CHI':'Chicago plant'})
        mapping = ','.join('EXACT(V,'+lit(k)+'),'+lit(v) for k,v in pairs.items())
        add(name,'VAR V = ['+source+'] RETURN IF(ISBLANK(V),'+lit(kind+' unavailable')
            +',SWITCH(TRUE(),'+mapping+','+lit(kind+' ')+' & V))',hidden=True)
    def qualification(name, source):
        add(name,'VAR V = ['+source+'] RETURN SWITCH(TRUE(),ISBLANK(V),"Qualification unavailable",'
            'EXACT(V,"approved"),"Qualification approved",EXACT(V,"pending"),"Not yet qualified — review pending",'
            'EXACT(V,"not_approved"),"Qualification not approved",EXACT(V,"conditional"),'
            '"Conditional qualification — requirements remain","Qualification status unresolved (" & V & ")")',hidden=True)

    external('Case Requested','INT(ISFILTERED(CaseCommandCenter[case_key]) || ISFILTERED(CaseCommandCenter[case_id]))',CC,'int64')

    external('Selected Case Key', '''IF(
        (ISFILTERED(CaseCommandCenter[case_key]) || ISFILTERED(CaseCommandCenter[case_id]))
        && (NOT ISFILTERED(CaseCommandCenter[case_key]) || HASONEFILTER(CaseCommandCenter[case_key]))
        && (NOT ISFILTERED(CaseCommandCenter[case_id]) || HASONEFILTER(CaseCommandCenter[case_id]))
        && COUNTROWS(CaseCommandCenter) == 1,
        SELECTEDVALUE(CaseCommandCenter[case_key]))''', CC)
    external('Analysis Requested', 'INT(ISFILTERED(SavedAnalyses[analysis_key]))', SA, 'int64')
    external('Selected Analysis Key', '''VAR C = [Selected Case Key]
        VAR N = CALCULATE(COUNTROWS(SavedAnalyses), KEEPFILTERS(TREATAS({C},SavedAnalyses[case_key])),
            KEEPFILTERS(SavedAnalyses[payload_state] == "available"),
            KEEPFILTERS(SavedAnalyses[snapshot_state] == "available"))
        RETURN IF(NOT ISBLANK(C) && ISFILTERED(SavedAnalyses[analysis_key])
        && HASONEFILTER(SavedAnalyses[analysis_key]) && N == 1,
        SELECTEDVALUE(SavedAnalyses[analysis_key]))''', SA)
    for name, field in (('Case Current Analysis Key','current_analysis_key'),
                        ('Current Decision Key','current_decision_key'),
                        ('Decision Analysis Key','decision_analysis_key'),
                        ('Approved Option Key','approved_option_key'),
                        ('Current Decision ID','current_decision_id'),
                        ('Case Status','status'),('Decision Kind','decision_kind'),
                        ('Case Runtime','runtime_mode'),
                        ('Case Display ID','case_id')):
        add(name, 'IF(NOT ISBLANK([Selected Case Key]), ' + calc('SELECTEDVALUE(' + col(CC,field) + ')',
            ['ALLSELECTED(' + CC + ')']) + ')', hidden=True)
    add('Overview Analysis Key', '''VAR C = [Selected Case Key]
        VAR A = [Case Current Analysis Key]
        VAR N = CALCULATE(COUNTROWS(SavedAnalyses), REMOVEFILTERS(SavedAnalyses),
            TREATAS({C},SavedAnalyses[case_key]),TREATAS({A},SavedAnalyses[analysis_key]),
            SavedAnalyses[payload_state] == "available",SavedAnalyses[snapshot_state] == "available")
        RETURN IF([Analysis Requested] == 1, [Selected Analysis Key],
            IF(NOT ISBLANK(C) && NOT ISBLANK(A) && N == 1,A))''', hidden=True)
    for prefix, basis in (('Selected','[Selected Analysis Key]'),('Overview','[Overview Analysis Key]')):
        for field in ('analysis_id','analysis_created_at','scenario_effective_time','snapshot_state','payload_state','runtime_mode',
                      'inventory_complete','production_orders_complete','customer_orders_complete'):
            add(prefix + ' ' + field, scoped(SA,'SELECTEDVALUE(' + col(SA,field) + ')',
                analysis=basis,clear=True), TYPES[SA][field], hidden=True)
    add('Case Selection State','IF([Case Requested] == 0,"Select a case",IF(ISBLANK([Selected Case Key]),"Case selection unavailable — unknown, multiple or conflicting selections","Case " & [Case Display ID]))')
    add('Overview State', '''SWITCH(TRUE(),ISBLANK([Selected Case Key]),[Case Selection State],
        [Analysis Requested] == 1 && ISBLANK([Selected Analysis Key]),"This analysis is unavailable in the report",
        ISBLANK([Case Current Analysis Key]) && [Analysis Requested] == 0,"Not analyzed yet",
        ISBLANK([Overview Analysis Key]),"Saved analysis or operational snapshot unavailable",
        [Overview payload_state] <> "available","Saved analysis unavailable",
        "Case " & [Case Display ID] & " · Analysis " & [Overview analysis_id] & " · " & [Overview Provenance])''')
    for prefix in ('Selected','Overview'):
        add(prefix+' Provenance','VAR V = ['+prefix+' runtime_mode] RETURN IF(ISBLANK(['+prefix+' analysis_id]),BLANK(),'
            'SWITCH(V,"fallback","Saved demo fixture · fictional",'
            '"live","Saved analysis from live-service mode · fictional scenario · no new retrieval",'
            '"Saved analysis · source mode unavailable"))',hidden=True)
    add('Scenario Context', '''VAR V = [Overview scenario_effective_time]
        RETURN IF(NOT ISBLANK([Selected Case Key]),IF(ISBLANK(V),"Scenario time unavailable",
        "In this scenario, as of " & FORMAT(V,"MMM d, yyyy HH:mm") & " UTC"))''')
    add('Snapshot Context', '''VAR V = [Selected analysis_created_at]
        RETURN IF(NOT ISBLANK([Selected Analysis Key]),
        "Snapshot used for this analysis · " & IF(ISBLANK(V),"Analysis time unavailable",
        FORMAT(V,"MMM d, yyyy HH:mm") & " UTC") & " · " & [Selected Provenance])''')

    external('Selected Record Key', '''VAR C = [Selected Case Key] VAR A = [Selected Analysis Key]
        VAR N = CALCULATE(COUNTROWS(SavedRecords),
            KEEPFILTERS(TREATAS({C},SavedRecords[case_key])),
            KEEPFILTERS(TREATAS({A},SavedRecords[analysis_key])),
            KEEPFILTERS(SavedRecords[record_state] == "available"),
            KEEPFILTERS(SavedRecords[evidence_state] == "available"))
        RETURN IF(NOT ISBLANK(C) && NOT ISBLANK(A)
            && ISFILTERED(SavedRecords[record_key]) && HASONEFILTER(SavedRecords[record_key])
            && ISFILTERED(SavedRecords[record_family]) && HASONEFILTER(SavedRecords[record_family])
            && SELECTEDVALUE(SavedRecords[record_family]) IN {"shipment","transfer","qualification"}
            && N == 1,SELECTEDVALUE(SavedRecords[record_key]))''', SR)
    external('Selected Record Family', 'IF(NOT ISBLANK([Selected Record Key]), SELECTEDVALUE(SavedRecords[record_family]))', SR)
    record_filters = [key_filter(SR,'record_key','[Selected Record Key]'),
                      key_filter(SR,'record_family','[Selected Record Family]'),
                      eq(SR,'record_state','"available"'),eq(SR,'evidence_state','"available"')]
    for field in ('quantity','due_date','arrival_date','incremental_cost_per_unit','status','audit_complete',
                  'first_article_complete','expected_decision_date','supplier_id','source_plant_id',
                  'destination_plant_id','part_id','retrieved_at','provenance','runtime_mode','source_system','source_timestamp'):
        add('Record ' + field, 'IF(NOT ISBLANK([Selected Record Key]), (' + scoped(SR,
            'SELECTEDVALUE(' + col(SR,field) + ')',extra=record_filters,clear=True) + '))',
            TYPES[SR][field],hidden=True)
    add('Record Row Visible', 'IF(NOT ISBLANK([Selected Record Key]), INT((' + scoped(SR,
        'COUNTROWS(SavedRecords)',extra=record_filters) + ') > 0),0)', 'int64', hidden=True)
    entity('Record Supplier','Record supplier_id','Supplier')
    entity('Record Source Plant','Record source_plant_id','Plant')
    entity('Record Destination Plant','Record destination_plant_id','Plant')
    qualification('Record Qualification','Record status')
    add('Record Provenance','''IF(NOT ISBLANK([Selected Record Key]),SWITCH([Record provenance],
        "saved_fabric","Saved Microsoft Fabric record · fictional scenario",
        "demo_fixture","Saved demo fixture · fictional",
        "Saved record · provenance unavailable") & " · Retrieved for this analysis: "
        & IF(ISBLANK([Record retrieved_at]),"Unavailable",FORMAT([Record retrieved_at],"MMM d, yyyy HH:mm") & " UTC"))''',hidden=True)
    add('Record State', '''IF(ISBLANK([Selected Record Key]),"Supporting record unavailable — select the exact case, analysis and record",
        SWITCH([Selected Record Family],"shipment",[Record Supplier] & " · Partial shipment",
        "qualification",[Record Supplier] & " · Qualification",
        "transfer",[Record Source Plant] & " to " & [Record Destination Plant])
        & " · " & [Record Provenance])''')
    for name, source, suffix, fmt in (
        ('Record Quantity Display','Record quantity',' component units','#,0'),
        ('Record Due Date Display','Record due_date','','MMM d, yyyy'),
        ('Record Arrival Date Display','Record arrival_date','','MMM d, yyyy'),
        ('Record Unit Cost Display','Record incremental_cost_per_unit',' per unit; currency not specified','#,0.00')):
        display(name,source,suffix,fmt)
    textvalue('Record Status Display','Record Qualification')
    for name, field in (('Record Audit Display','audit_complete'),('Record First Article Display','first_article_complete')):
        add(name,'VAR V = [Record '+field+'] RETURN IF(ISBLANK(V),"Unavailable",IF(V,"Complete","Outstanding"))')
    add('Record Explanation', '''IF(NOT ISBLANK([Selected Record Key]),SWITCH([Selected Record Family],
        "shipment","Scheduled receipt from the saved shipment record. Supplier statements remain in the original supplier email. This is not approval or execution.",
        "transfer","Saved dispatch and arrival dates describe the planned plant transfer. Approval and execution are separate.",
        "qualification","Audit: " & [Record Audit Display] & "; first article: " & [Record First Article Display]
            & ". Review date: " & IF(ISBLANK([Record expected_decision_date]),"Unavailable",FORMAT([Record expected_decision_date],"MMM d, yyyy"))
            & ". A review date is not an approval or delivery date."))''')

    for prefix, family, gate in (('Stock','inventory','Stock Row Visible'),('Orders','customer_order_line','Order Row Visible')):
        filters = [eq(SR,'in_disruption_scope','TRUE()'),eq(SR,'record_state','"available"')]
        complete = ('[Selected inventory_complete] == TRUE()' if prefix=='Stock' else
                    '[Selected production_orders_complete] == TRUE() && [Selected customer_orders_complete] == TRUE()')
        add(prefix+' Rows Valid','IF('+complete+',('+scoped(SR,
            'IF(COUNTROWS(SavedRecords)>0 && COUNTROWS(FILTER(SavedRecords,SavedRecords[record_state] <> "available")) == 0,1,0)',
            family=family,clear=True)+'),0)','int64',hidden=True)
        add(gate,'IF(['+prefix+' Rows Valid] == 1,INT((' + scoped(SR,'COUNTROWS(SavedRecords)',family=family,extra=filters) + ') > 0),0)', 'int64',hidden=True)
        add(prefix + ' Count','IF(['+prefix+' Rows Valid] == 1,('+scoped(SR,'COUNTROWS(SavedRecords)',family=family,extra=filters,clear=True)+'))','int64',hidden=True)
        add(prefix + ' State','IF(ISBLANK([Selected Case Key]),[Case Selection State],'
            'IF(ISBLANK([Selected Analysis Key]),"Select an available saved analysis",'
            'IF(ISBLANK(['+prefix+' Count]) || ['+prefix+' Count] == 0,"Supporting records unavailable",[Snapshot Context])))')
    for prefix, family, field, measure in (
        ('Stock','inventory','usable_inventory','Stock Usable'),
        ('Stock','inventory','quality_hold','Stock Held'),
        ('Stock','inventory','protected_allocation','Stock Protected'),
        ('Orders','customer_order_line','line_revenue','Affected Revenue')):
        # A missing cell never becomes a fabricated zero subtotal.
        expression = 'IF(COUNTROWS(SavedRecords) > 0 && COUNTBLANK('+col(SR,field)+') == 0, SUM('+col(SR,field)+'))'
        add(measure,'IF(['+prefix+' Rows Valid] == 1,('+scoped(SR,expression,family=family,extra=[eq(SR,'in_disruption_scope','TRUE()'),
            eq(SR,'record_state','"available"')],clear=True)+'))',TYPES[SR][field],hidden=True)
        display(measure+' Display',measure,'; currency not specified' if field=='line_revenue' else ' component units')
    display('Affected Lines Display','Orders Count',' saved customer order lines','#,0')
    for name, field in (('Stock On Hand Row','on_hand'),('Stock Held Row','quality_hold'),
                        ('Stock Protected Row','protected_allocation'),('Stock Usable Row','usable_inventory')):
        add(name,'IF([Stock Rows Valid] == 1,('+scoped(SR,'IF(COUNTROWS(SavedRecords)>0 && COUNTBLANK('+col(SR,field)+') == 0,SUM('+col(SR,field)+'))',
            family='inventory',extra=[eq(SR,'in_disruption_scope','TRUE()'),eq(SR,'record_state','"available"')])+'))',
            'int64','#,0')
    add('Stock Explanation','IF(NOT ISBLANK([Selected Analysis Key]),"Usable component stock = on hand − quality holds − protected allocations, for the disruption’s exact part and plant.")')
    add('Orders Basis Display','IF(NOT ISBLANK([Selected Analysis Key]),"Customer lines participating in this saved plan")')
    add('Orders Baseline Revenue','IF(NOT ISBLANK([Selected Analysis Key]),[Baseline revenue_at_risk])','decimal',hidden=True)
    add('Orders Baseline OTIF','IF(NOT ISBLANK([Selected Analysis Key]),[Baseline otif_loss_percentage])','int64',hidden=True)
    display('Orders Baseline Revenue Display','Orders Baseline Revenue','; currency not specified')
    display('Orders Baseline OTIF Display','Orders Baseline OTIF','%','0')
    add('Orders Explanation','IF(NOT ISBLANK([Selected Analysis Key]),"Without a response: saved baseline predictions from the same calculation as the card. The supporting rows are customer lines included in this plan; their line values are not predicted revenue at risk, and these rows do not identify individual missed service targets.")')

    external('Option Requested','INT(ISFILTERED(SavedOptions[option_key]))',SO,'int64')
    external('Selected Option Key', '''VAR C = [Selected Case Key] VAR A = [Selected Analysis Key]
        VAR N = CALCULATE(COUNTROWS(SavedOptions),KEEPFILTERS(TREATAS({C},SavedOptions[case_key])),
            KEEPFILTERS(TREATAS({A},SavedOptions[analysis_key])))
        RETURN IF(NOT ISBLANK(C) && NOT ISBLANK(A) && ISFILTERED(SavedOptions[option_key])
            && HASONEFILTER(SavedOptions[option_key]) && N == 1,SELECTEDVALUE(SavedOptions[option_key]))''',SO)
    add('Option Row Visible','IF([Option Requested] == 0 || NOT ISBLANK([Selected Option Key]),INT(('
        +scoped(SO,'COUNTROWS(SavedOptions)')+') > 0),0)','int64',hidden=True)
    for name,field in (('Option Revenue','revenue_at_risk'),('Option Response Cost','response_cost')):
        add(name,'IF([Option Row Visible] == 1,('+scoped(SO,
            'IF(COUNTROWS(SavedOptions) == 1,SELECTEDVALUE('+col(SO,field)+'))')+'))','decimal','#,0.00')
    for field in ('option_name','revenue_at_risk','response_cost','blockers_text','required_roles_text','assumptions_text'):
        add('Selected Option '+field,'IF(NOT ISBLANK([Selected Option Key]),('+scoped(SO,
            'SELECTEDVALUE('+col(SO,field)+')',extra=[key_filter(SO,'option_key','[Selected Option Key]')],clear=True)+'))',
            TYPES[SO][field],hidden=True)
    add('Options State','IF(ISBLANK([Selected Case Key]),[Case Selection State],IF(ISBLANK([Selected Analysis Key]),"Saved analysis or operational snapshot unavailable",IF([Option Requested] == 1 && ISBLANK([Selected Option Key]),"Selected option unavailable",[Snapshot Context])))')
    add('Selected Option Display','IF([Option Requested] == 0,"Compare the saved options",IF(ISBLANK([Selected Option Key]),"Selected option unavailable",[Selected Option option_name]))')
    display('Option Revenue Display','Selected Option revenue_at_risk','; currency not specified')
    display('Option Cost Display','Selected Option response_cost','; currency not specified')
    add('Options Explanation','IF(NOT ISBLANK([Selected Analysis Key]),IF([Option Requested] == 0,"Expected results from the shared saved calculation engine. Meeting planning requirements is separate from approval.",IF(NOT ISBLANK([Selected Option Key]),COALESCE([Selected Option blockers_text],"Planning blockers unavailable") & ". " & COALESCE([Selected Option required_roles_text],"Required roles unavailable"))))')

    # Overview basis measures ignore detail/option selection only after exact overview scope is captured.
    for basis, flag in (('Baseline','is_baseline'),('Recommended','is_recommended')):
        for field in ('option_name','revenue_at_risk','response_cost','otif_loss_percentage','uncovered_part_demand','blockers_text'):
            add(basis+' '+field,scoped(SO,'IF(COUNTROWS(SavedOptions) == 1,SELECTEDVALUE('+col(SO,field)+'))',
                analysis='[Overview Analysis Key]',extra=[eq(SO,flag,'TRUE()')],clear=True),TYPES[SO][field],hidden=True)
    for field in ('option_name','revenue_at_risk','response_cost','otif_loss_percentage','uncovered_part_demand'):
        add('Approved '+field,'IF([Decision Kind] == "approved" && NOT ISBLANK([Approved Option Key]),('
            +scoped(SO,'IF(COUNTROWS(SavedOptions) == 1,SELECTEDVALUE('+col(SO,field)+'))',analysis='[Decision Analysis Key]',
                extra=[key_filter(SO,'option_key','[Approved Option Key]')],clear=True)+'))',TYPES[SO][field],hidden=True)
    for family in ('disruption','shipment','transfer','qualification'):
        fields = {'disruption':('original_quantity','partial_quantity','original_due_date','partial_due_date','supplier_id','part_id','plant_id'),
                  'shipment':('quantity','due_date','supplier_id'),
                  'transfer':('quantity','arrival_date','source_plant_id','destination_plant_id'),
                  'qualification':('status','supplier_id')}[family]
        for field in fields:
            guards=[eq(SR,'record_state','"available"')]
            if family!='disruption':
                guards += [eq(SR,'evidence_state','"available"')]
            add('Overview '+family+' '+field,scoped(SR,'IF(COUNTROWS(SavedRecords) == 1,SELECTEDVALUE('+col(SR,field)+'))',
                analysis='[Overview Analysis Key]',family=family,extra=guards,clear=True),TYPES[SR][field],hidden=True)
    add('Overview Stock Rows Valid','IF([Overview inventory_complete] == TRUE(),('+scoped(SR,
        'IF(COUNTROWS(SavedRecords)>0 && COUNTROWS(FILTER(SavedRecords,SavedRecords[record_state] <> "available")) == 0,1,0)',
        analysis='[Overview Analysis Key]',family='inventory',clear=True)+'),0)','int64',hidden=True)
    add('Overview Stock','IF([Overview Stock Rows Valid] == 1,('+scoped(SR,'IF(COUNTROWS(SavedRecords)>0 && COUNTBLANK(SavedRecords[usable_inventory]) == 0,SUM(SavedRecords[usable_inventory]))',
        analysis='[Overview Analysis Key]',family='inventory',extra=[eq(SR,'in_disruption_scope','TRUE()'),eq(SR,'record_state','"available"')],clear=True)+'))','int64',hidden=True)
    for family in ('disruption','shipment','qualification'):
        entity('Overview '+family+' Supplier','Overview '+family+' supplier_id','Supplier')
    entity('Overview Transfer Source','Overview transfer source_plant_id','Plant')
    entity('Overview Transfer Destination','Overview transfer destination_plant_id','Plant')
    entity('Overview Disruption Plant','Overview disruption plant_id','Plant')
    qualification('Overview Qualification Status','Overview qualification status')
    add('Disruption Answer','''VAR Q = [Overview disruption original_quantity] VAR P = [Overview disruption partial_quantity]
        RETURN IF(NOT ISBLANK([Overview Analysis Key]),IF(ISBLANK(Q)||ISBLANK(P),"Disruption details unavailable",
        [Overview disruption Supplier] & "; part " & COALESCE([Overview disruption part_id],"unavailable")
        & " at " & [Overview Disruption Plant] & ": " & FORMAT(Q,"#,0") & " component units originally due "
        & IF(ISBLANK([Overview disruption original_due_date]),"date unavailable",FORMAT([Overview disruption original_due_date],"MMM d"))
        & "; " & FORMAT(P,"#,0") & " in the partial response."))''')
    add('Availability Answer','IF(NOT ISBLANK([Overview Analysis Key]),IF(ISBLANK([Overview Stock]),"Available stock unavailable",FORMAT([Overview Stock],"#,0") & " usable component units after holds and protected allocations"))')
    add('Exposure Answer','''VAR V = [Baseline revenue_at_risk] VAR P = [Baseline otif_loss_percentage]
        RETURN IF(NOT ISBLANK([Overview Analysis Key]),"Without a response: "
        & IF(ISBLANK(V),"revenue exposure unavailable",FORMAT(V,"#,0.00") & " revenue at risk; currency not specified")
        & ". Service-target exposure: " & IF(ISBLANK(P),"Unavailable",FORMAT(P,"0") & "%"))''')
    for label,family,datefield,entity_expression in (
            ('Shipment','shipment','due_date','[Overview shipment Supplier]'),
            ('Transfer','transfer','arrival_date','[Overview Transfer Source] & " to " & [Overview Transfer Destination]')):
        add(label+' Answer','VAR Q = [Overview '+family+' quantity] VAR D = [Overview '+family+' '+datefield+'] '
            'RETURN IF(NOT ISBLANK([Overview Analysis Key]),IF(ISBLANK(Q),"Supporting record unavailable",'
            +'('+entity_expression+') & ": " & FORMAT(Q,"#,0") & " component units; " & IF(ISBLANK(D),"date unavailable",FORMAT(D,"MMM d, yyyy"))))')
    add('Qualification Answer','IF(NOT ISBLANK([Overview Analysis Key]),[Overview qualification Supplier] & ": " & [Overview Qualification Status])')
    add('Options Answer','IF(NOT ISBLANK([Overview Analysis Key]),"Compare saved baseline and response options by cost, service exposure, and parts still needed. Predictions are not observed results.")')
    add('Recommendation Answer','''IF(NOT ISBLANK([Overview Analysis Key]),IF(ISBLANK([Recommended option_name]),"Recommendation unavailable",
        [Recommended option_name] & "; " & IF(ISBLANK([Recommended uncovered_part_demand]),"parts still needed unavailable",
        FORMAT([Recommended uncovered_part_demand],"#,0") & " component units still needed")
        & "; revenue at risk " & IF(ISBLANK([Recommended revenue_at_risk]),"unavailable",FORMAT([Recommended revenue_at_risk],"#,0.00"))
        & "; response cost " & IF(ISBLANK([Recommended response_cost]),"unavailable",FORMAT([Recommended response_cost],"#,0.00"))
        & " (currency not specified)"
        & ". Saved recommendation. Current decision is shown separately."))''')
    add('Decision Answer','''IF(NOT ISBLANK([Selected Case Key]),IF(ISBLANK([Current Decision Key]),
        IF([Case Status] == "awaiting_decision","Awaiting approval","No current decision recorded · " & [Case Status]),
        IF([Decision Kind] == "approved","Approved option: " & COALESCE([Approved option_name],"Unavailable"),
        "Recorded decision: " & COALESCE([Decision Kind],"Unavailable"))) & ". Approval remains an explicit action in the demo.")''')

    action_filters = [eq(AO,'record_type','"action"')]
    observation_filters = [eq(AO,'record_type','"observation"')]
    add('Action Row Visible','INT(('+scoped(AO,'COUNTROWS(ActionOutcomes)',extra=action_filters,decision=True)+') > 0)','int64',hidden=True)
    unit_pairs = {'alpha_expedited_quantity':'units','dallas_transfer_quantity':'units','total_response_arranged_supply':'units',
                  'uncovered_part_demand':'units','response_cost':'USD','protected_customer_orders':'orders',
                  'revenue_protected':'USD','margin_protected':'USD','otif_loss_percentage':'percent'}
    expected = 'SWITCH(M,' + ','.join(lit(k)+','+lit(v) for k,v in unit_pairs.items()) + ',BLANK())'
    obs_gate = '''VAR M = SELECTEDVALUE(ActionOutcomes[metric]) VAR U = SELECTEDVALUE(ActionOutcomes[unit])
        VAR K = SELECTEDVALUE(ActionOutcomes[observation_kind])
        VAR E = '''+expected+'''
        RETURN IF(COUNTROWS(ActionOutcomes)>0 && NOT ISBLANK(M) && NOT ISBLANK(U)
        && NOT ISBLANK(K) && NOT ISBLANK(E) && U == E,1,0)'''
    add('Observation Row Visible',scoped(AO,obs_gate,extra=observation_filters,decision=True),'int64',hidden=True)
    variance = '''VAR PredictedText = SELECTEDVALUE(ActionOutcomes[predicted_value])
        VAR ObservedText = SELECTEDVALUE(ActionOutcomes[observed_value])
        VAR Predicted = IFERROR(VALUE(PredictedText), BLANK())
        VAR Observed = IFERROR(VALUE(ObservedText), BLANK())
        RETURN IF(ISBLANK(Predicted) || ISBLANK(Observed) || Predicted == 0,BLANK(),
            DIVIDE(Observed - Predicted, ABS(Predicted)))'''
    add('Observed Variance','IF([Observation Row Visible] == 1,('+scoped(AO,variance,extra=observation_filters,decision=True)+'))',
        'double','0.00%;-0.00%;0.00%',table=AO)
    for name, expr, filters, kind in (
        ('Current Actions Count','COUNTROWS(ActionOutcomes)',action_filters,'int64'),
        ('Current Observations Count','COUNTROWS(ActionOutcomes)',observation_filters,'int64'),
        ('Current Action Status','SELECTEDVALUE(ActionOutcomes[action_status])',action_filters,'string'),
        ('Current Observation Kind','SELECTEDVALUE(ActionOutcomes[observation_kind])',observation_filters,'string'),
        ('Projection Refresh Time','MAX(ActionOutcomes[projection_updated_at])',[],'dateTime')):
        add(name,scoped(AO,expr,extra=filters,decision=True,clear=True),kind,hidden=True)
    add('Current Decision Display','IF(ISBLANK([Selected Case Key]),[Case Selection State],IF(ISBLANK([Current Decision Key]),"No current decision recorded",COALESCE([Decision Kind],"Decision kind unavailable")))')
    add('Current Action Status Display','IF(ISBLANK([Current Actions Count]) || [Current Actions Count] == 0,"No actions recorded",COALESCE([Current Action Status],"Multiple action states — see current actions"))')
    add('Current Observation Display','IF(ISBLANK([Current Observations Count]) || [Current Observations Count] == 0,"No outcomes recorded",IF([Current Observation Kind] == "simulated","Simulated",COALESCE([Current Observation Kind],"Mixed observation kinds — see each series")))')
    display('Projection Updated Display','Projection Refresh Time',' UTC','MMM d, yyyy HH:mm')
    add('Actions State','IF(ISBLANK([Selected Case Key]),[Case Selection State],IF(ISBLANK([Current Decision Key]),"No current decision recorded","Current governing decision" & IF([Analysis Requested] == 1 && ISBLANK([Selected Analysis Key])," · Requested analysis unavailable; these are current-decision records",IF(NOT ISBLANK([Selected Analysis Key]) && [Selected Analysis Key] <> [Decision Analysis Key]," · Decision belongs to a different saved analysis from the one being viewed",""))))')
    add('Action Explanation','IF(NOT ISBLANK([Selected Case Key]),[Current Action Status Display] & ". " & [Current Observation Display] & ". Predictions and observations remain separate. Simulated observations are not real-world outcomes.")')
    return result


def manifest():
    definitions = measures()
    return {'tables': {t: {'columns': dict(TYPES[t]),
        'column_formats': {c:column_format(t,c) for c in COLUMNS[t]}, 'partition': t, 'mode': 'directQuery',
        'query_file': 'fabric/reporting/queries/' + t + '.sql',
        'measures': {n: {'expression': m.expression, 'result_type': m.result_type,
            'format_string': m.format_string, 'hidden': m.hidden} for n,m in definitions[t].items()}}
        for t in TABLES}, 'relationships': []}


def check_required_fields(required):
    current = manifest()['tables']
    for kind, table, name in required:
        group = 'columns' if kind == 'Column' else 'measures' if kind == 'Measure' else None
        if group is None or table not in current or name not in current[table][group]:
            raise ValueError('Unknown report binding: ' + repr((kind,table,name)))


def m_string(value):
    return '"' + value.replace('#','#(#)').replace('"','""').replace('\r','').replace('\n','#(lf)') + '"'


def artifacts(query_directory):
    reject_symlink_chain(query_directory)
    output = {}
    definitions = measures()
    for table in TABLES:
        query_path = query_directory / (table + '.sql')
        if query_path.is_symlink():
            raise ValueError('SQL source must not be a symlink')
        query = query_path.read_text(encoding='utf-8')
        if not query.strip():
            raise ValueError('Empty partition query')
        lines = ['table '+table]
        for name in COLUMNS[table]:
            lines += ['  column '+name, '    dataType: '+TYPES[table][name],
                      '    sourceColumn: '+name, '    summarizeBy: none']
            if column_format(table,name):
                lines += ['    formatString: '+column_format(table,name)]
            lines += ['']
        for name, measure in definitions[table].items():
            lines += ["  measure '"+name.replace("'","''")+"' ="]
            lines += ['      '+line for line in measure.expression.splitlines()]
            if measure.format_string:
                lines += ['    formatString: '+measure.format_string]
            if measure.hidden:
                lines += ['    isHidden']
            lines += ['']
        lines += ['  partition '+table+' = m','    mode: directQuery','    source =',
            '        Sql.Database(FABRIC_SQL_SERVER, FABRIC_SQL_DATABASE, [Query='+m_string(query)+'])','']
        output['tables/'+table+'.tmdl'] = '\n'.join(lines)
    output['model.tmdl'] = ('model Model\n  culture: en-US\n  defaultPowerBIDataSourceVersion: powerBI_V3\n'
        '  sourceQueryCulture: en-US\n\n  dataAccessOptions\n    legacyRedirects\n    returnErrorValuesAsNull\n\n'
        'ref expression FABRIC_SQL_SERVER\nref expression FABRIC_SQL_DATABASE\n'
        + ''.join('ref table '+table+'\n' for table in TABLES))
    output['relationships.tmdl'] = ''
    return output


def reject_symlink_chain(path):
    for candidate in (path,*path.parents):
        if candidate.is_symlink():
            raise ValueError('Symlink in semantic/query path: '+str(candidate))


def check_output_paths(definition, expected):
    reject_symlink_chain(definition)
    reject_symlink_chain(definition/'tables')
    for name in expected:
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid generated relative path')
        target=definition/relative
        reject_symlink_chain(target)
        if target.exists() and not target.is_file():
            raise ValueError('Generated file target is not a file: '+str(target))
        for directory in target.parents:
            if directory.exists() and not directory.is_dir():
                raise ValueError('Generated parent is not a directory: '+str(directory))
    table_directory=definition/'tables'
    if table_directory.exists():
        allowed={t+'.tmdl' for t in TABLES}
        if any(p.name not in allowed or not p.is_file() or p.is_symlink() for p in table_directory.iterdir()):
            raise ValueError('Unexpected existing semantic table path')


def verify(definition, query_directory):
    reject_symlink_chain(query_directory)
    expected = artifacts(query_directory)
    check_output_paths(definition,expected)
    actual_tables = {p.name for p in (definition/'tables').iterdir()}
    if actual_tables != {t+'.tmdl' for t in TABLES}:
        raise ValueError('Unexpected semantic table inventory')
    for name, value in expected.items():
        target = definition/name
        if target.is_symlink() or target.read_text(encoding='utf-8') != value:
            raise ValueError('Semantic artifact drift: '+name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('definition',type=Path)
    parser.add_argument('queries',type=Path)
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    reject_symlink_chain(args.queries)
    from fabric.report_pages import required_fields
    check_required_fields(required_fields())
    if args.check:
        verify(args.definition,args.queries)
        return
    planned=artifacts(args.queries)
    check_output_paths(args.definition,planned)
    # All targets/ancestors checked before the first mkdir or write.
    for name,value in planned.items():
        target=args.definition/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.is_symlink():
            raise ValueError('Refusing symlink target')
        target.write_text(value,encoding='utf-8')
    verify(args.definition,args.queries)


if __name__ == '__main__':
    main()
```

- [x] **Step 5: Verify generated artifacts and compatibility, then self-review.**

```sh
.venv/bin/pytest tests/fabric/test_report_generators.py -o addopts='' -q
.venv/bin/ruff check fabric/report_pages.py fabric/report_model.py tests/fabric/test_report_generators.py
.venv/bin/pytest tests/fabric/test_power_bi_project.py tests/fabric/test_schema_updater.py -o addopts='' -q
git diff --check
```

The new tests generate temporary PBIR, verify every file against the pinned offline schema catalog, resolve every model binding, and reject schema-shaped tampering and symlink writes. They do not establish DAX execution or rendered appearance. Existing 76 compatibility tests must remain green; if NuGet sandbox restore is blocked, ask the controller for its scoped restore run, without changing test gates or dependencies.

Apply mechanical Ruff formatting/import cleanup if required; do not change the designed identity or gate contracts just to pass a test. No generation into tracked report folders at this step. Report any code defect discovered by tests with the correction and evidence.

- [x] **Step 6: Commit the three task files and report for independent review.**

```sh
git add fabric/report_pages.py fabric/report_model.py tests/fabric/test_report_generators.py
git commit -m "feat: generate focused saved-analysis report pages and model"
```

Write complete evidence to .superpowers/sdd/report-generators-task-1-report.md. Include generated page count, schema results, exact commands, RED/GREEN, and explicit TOM/DAX/rendering limitations.

## Controller self-review

Execution: completed through `fa4312f`; independent review approved both the
implementation and subsequent fixes. Review corrections supersede the original
code snippets below: output inventory and path types are checked before any page
write, and DAX variable substitution preserves quoted strings. Regressions cover
all four invalid-output cases and doubled-quote literals. Parent verification:
32 generator tests and Ruff passed; preceding combined compatibility run passed
103 checks. That compatibility TOM run parsed the old checked-in model; the next
paired-artifact task must parse the new model with the real Microsoft parser.

The eight pages preserve both original page IDs and all twelve original visual IDs while adding focused destinations. The model does not infer scope from raw table grouping: external selection helpers validate case/analysis and row gates intersect exact keys. UTF-16LE hex query keys match the reviewed URL builder and SQL projections. Actual quantities, dates, source provenance, pending qualification and observed zero remain distinct; completeness flags suppress unsubstantiated collection totals. Main supporting stock tables aggregate validated records by part/plant; customer rows retain the source order-line identity. Original identifiers remain in Source details. The report emits no approval action or fabricated fresh retrieval.

Remaining approved-spec work has explicit subsequent tasks: paired generated artifact/preflight/TOM integration, runtime receipt and mounted exact links, contextual traditional navigation/presenter guide, and actual DAX/native visual review during coordinated release. No step in this task claims that saved recommendation text is a persisted ranking rationale, or that included customer lines have persisted per-line late/on-time predictions.
