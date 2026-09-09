# Native PBIR metadata correction plan

Scope: generator, regenerated pages, and generator regression tests only. Preserve all visual IDs, eight pages, 1280 × 720 canvases, semantic-model fields/measures, source identifiers, selection gates, and quantity/format semantics. No activation, publishing, or model changes. Native Desktop rendering remains the release gate.

## Execution checkpoint

Implemented in `f0a0ff7` and independently approved. The controller reran all
134 generator/project/schema checks with the real Microsoft TOM parser. The
official offline authoring CLI reported zero errors and zero warnings. All
previous native-query-reference, textbox-height, and filter-name findings were
resolved. This verifies artifact structure, not actual DAX or native rendering.

## Evidence and success criteria

Independently reproduced on the current worktree:

```sh
/private/tmp/supply-response-report-tools.Dadda4/node_modules/.bin/powerbi-report-author --out /private/tmp/supply-response-report-tools.Dadda4/recheck.json validate --no-schema fabric/power-bi/SupplyResponse.Report
```

Exit 1: 164 missing-nativeQueryRef errors, 16 textbox-floor warnings, 11 duplicate-filter-name warnings. Success: zero errors and zero warnings from this pinned 0.1.4 CLI, existing pinned-schema validation passes, and the regression tests below pass. `--no-schema` supplements, rather than replaces, repository pinned JSON Schema validation.

Ranked causes: (1) `projection()` omits `nativeQueryRef` for every visual binding; (2) `common()` rectangles violate CLI font-height floors; (3) `gate()` and `family_filter()` reuse names across report scopes. Independently, stock is the only mixed column/measure `tableEx`; migrate that visual to `pivotTable`.

Primary Microsoft evidence consulted:

- [Authoring skill](https://raw.githubusercontent.com/microsoft/skills-for-fabric/main/skills/powerbi-report-authoring/SKILL.md): mixed dimension/measure tableEx failure and mandatory nativeQueryRef.
- [Expression reference](https://raw.githubusercontent.com/microsoft/skills-for-fabric/main/skills/powerbi-report-authoring/references/expressions.md): nativeQueryRef normally uses the property name; expansion levels reference query expressions.
- [Table reference](https://raw.githubusercontent.com/microsoft/skills-for-fabric/main/skills/powerbi-report-authoring/references/table.md): matrix grouping roles and custom-color style preset behavior.
- Installed official CLI `catalog describe pivotTable`: Rows = Grouping, Values = Measure; Values required.
- CLI `formatting search pivotTable 'layout|stepped|subtotal|total|font|backColor|rowPadding'`, `formatting describe-object pivotTable subTotals`, `rowHeaders`, `columnHeaders`: verified properties below, including SubTotals selector IDs Row/Column.
- CLI source `validateTextboxScrollbar`: minimum height `max(18, ceil(font * 25 / 16)) + topPadding + bottomPadding`. At padding 4+4: title 49 and footer 29. Title y=12 avoids overlapping selection state at y=62; footer y=682 ends at 711.

## 1. Add failing tests before editing generator

Add these complete tests to `tests/fabric/test_report_generators.py` (imports already provide report_pages, deepcopy, pytest):

```python
def test_every_projection_has_native_property_reference():
    for path, artifact in report_pages.artifacts().items():
        visual = artifact.get("visual", {})
        refs = []
        for role in visual.get("query", {}).get("queryState", {}).values():
            for projection in role["projections"]:
                binding = next(iter(projection["field"].values()))
                assert projection.get("nativeQueryRef") == binding["Property"], path
                refs.append(projection["nativeQueryRef"])
        assert len(refs) == len(set(refs)), path


def test_filters_have_globally_unique_names_and_preserve_conditions():
    names = []
    for path, artifact in report_pages.artifacts().items():
        for item in artifact.get("filterConfig", {}).get("filters", []):
            names.append(item["name"])
            if "visual" in artifact:
                expected = report_pages.gate(item["field"]["Measure"]["Property"])
            else:
                family = report_pages.DETAILS[artifact["name"]][1]
                expected = report_pages.family_filter(family)
            actual = deepcopy(item)
            actual.pop("name")
            expected.pop("name")
            assert actual == expected, path
    assert names
    assert len(names) == len(set(names))


def test_common_text_fits_font_floors_and_does_not_overlap():
    from math import ceil

    artifacts = report_pages.artifacts()
    for page in report_pages.ORDER:
        prefix = f"pages/{page}/visuals/"
        title = artifacts[prefix + "page-title/visual.json"]["position"]
        state = artifacts[prefix + "selection-state/visual.json"]["position"]
        assert title["y"] + title["height"] <= state["y"]
    for path, artifact in artifacts.items():
        visual = artifact.get("visual", {})
        if visual.get("visualType") != "textbox":
            continue
        paragraphs = visual["objects"]["general"][0]["properties"]["paragraphs"]
        size = max(float(run["textStyle"]["fontSize"].removesuffix("px"))
                   for paragraph in paragraphs for run in paragraph["textRuns"])
        padding = visual["visualContainerObjects"]["padding"][0]["properties"]
        vertical = sum(float(padding[key]["expr"]["Literal"]["Value"].removesuffix("D"))
                       for key in ("top", "bottom"))
        position = artifact["position"]
        assert position["height"] >= max(18, ceil(size * 25 / 16)) + vertical, path
        assert position["y"] + position["height"] <= 720, path


def test_stock_matrix_retains_part_plant_grain_and_guarded_measures():
    artifact = report_pages.artifacts()[
        "pages/available-stock/visuals/supporting-records/visual.json"]
    visual = artifact["visual"]
    assert visual["visualType"] == "pivotTable"
    roles = visual["query"]["queryState"]
    assert set(roles) == {"Rows", "Values"}
    assert roles["Rows"]["projections"] == [
        report_pages.column(report_pages.SR, "part_id"),
        report_pages.column(report_pages.SR, "plant_id"),
    ]
    assert roles["Values"]["projections"] == [
        report_pages.measure("Stock On Hand Row", "On hand"),
        report_pages.measure("Stock Held Row", "Quality hold"),
        report_pages.measure("Stock Protected Row", "Protected allocation"),
        report_pages.measure("Stock Usable Row", "Usable units"),
    ]
    assert artifact["filterConfig"]["filters"][0]["field"] == report_pages.field(
        "Measure", report_pages.CC, "Stock Row Visible")
    assert visual["expansionStates"] == [{
        "roles": ["Rows"],
        "levels": [{"queryRefs": [item["queryRef"]], "identityKeys": [item["field"]],
                    "isCollapsed": False, "isPinned": True}
                   for item in roles["Rows"]["projections"]],
    }]
    assert "total" not in visual["objects"]
    for instance in visual["objects"]["subTotals"]:
        assert instance["properties"] == {
            "rowSubtotals": report_pages.literal(False),
            "columnSubtotals": report_pages.literal(False),
        }
    for path, value in report_pages.artifacts().items():
        item = value.get("visual", {})
        if item.get("visualType") == "tableEx":
            assert all("Column" in p["field"] for p in
                       item["query"]["queryState"]["Values"]["projections"]), path
```

Run `uv run pytest tests/fabric/test_report_generators.py -q`; new tests must fail on nativeQueryRef, names, title floor, and stock visual type. Existing tests should still pass at this point.

## 2. Exact generator changes

Replace `projection()` in `fabric/report_pages.py` with:

```python
def projection(kind, table, name, label=None):
    result = {
        "field": field(kind, table, name),
        "queryRef": table + "." + name,
        "nativeQueryRef": name,
    }
    if label is not None:
        result["displayName"] = label
    return result
```

In `common()`, change only the title rectangle to `(24, 12, 1232, 49)` and the footer rectangle to `(24, 682, 1232, 29)`. Preserve fonts and text. Do not simply increase title height at y=14, which would overlap the state card.

Replace the complete `if page == "available-stock":` body in `detail()` with:

```python
    if page == "available-stock":
        visual = supporting["visual"]
        visual["visualType"] = "pivotTable"
        rows = [column(SR, "part_id"), column(SR, "plant_id")]
        visual["query"]["queryState"] = {
            "Rows": {"projections": rows},
            "Values": {"projections": [
                measure("Stock On Hand Row", "On hand"),
                measure("Stock Held Row", "Quality hold"),
                measure("Stock Protected Row", "Protected allocation"),
                measure("Stock Usable Row", "Usable units"),
            ]},
        }
        visual["expansionStates"] = [{
            "roles": ["Rows"],
            "levels": [{
                "queryRefs": [item["queryRef"]],
                "identityKeys": [item["field"]],
                "isCollapsed": False,
                "isPinned": True,
            } for item in rows],
        }]
        objects = visual["objects"]
        del objects["total"]
        objects["rowHeaders"] = obj({
            "stepped": literal(False),
            "repeatRowHeaders": literal(True),
            "showExpandCollapseButtons": literal(False),
            "fontColor": color(GREEN),
            "backColor": color(WHITE),
            "fontSize": literal(11),
        })
        totals = {"rowSubtotals": literal(False), "columnSubtotals": literal(False)}
        objects["subTotals"] = [
            {"properties": totals},
            {"selector": {"id": "Row"}, "properties": totals},
            {"selector": {"id": "Column"}, "properties": totals},
        ]
        objects["columnHeaders"][0]["properties"].update({
            "autoSizeColumnWidth": literal(True),
            "columnAdjustment": literal("growToFit"),
        })
        objects["values"][0]["properties"]["fontColorSecondary"] = color(GREEN)
        visual["visualContainerObjects"]["stylePreset"] = obj({"name": literal("None")})
```

Keep the customer-orders `elif` unchanged. In particular its `source_record_id` Order line binding remains in Values. No new implicit aggregation, synthetic identity, zero replacement, source-column removal, or DAX change. Stock measures already sum at filtered part/plant context and enforce inventory validity; Rows preserves that context. Explicit expanded levels prevent a collapsed part-only initial view. The matrix reuses the table's geometry, title, locked row gate, banding and numeric measure formats.

In `artifacts()`, immediately before `result[f"pages/{page}/page.json"] = definition`, insert:

```python
        for filter_item in definition.get("filterConfig", {}).get("filters", []):
            filter_item["name"] = page + "-" + filter_item["name"]
```

Immediately after `visual["position"].update(z=order, tabOrder=order)`, insert:

```python
            for filter_item in visual.get("filterConfig", {}).get("filters", []):
                filter_item["name"] = page + "-" + visual["name"] + "-" + filter_item["name"]
```

Names are deterministic, stable and globally scoped; expressions and locks remain byte-for-byte equivalent. These fresh dictionaries are generated per call, so no prefix accumulation.

## 3. Adapt existing tests to the intentional role migration

In `test_deterministic_native_pages_match_pinned_schemas`, add `"pivotTable"` to the set of gate-bearing visual types.

In `test_business_tables_preserve_stock_totals_and_order_line_grain`, replace its local `projections` helper with this complete function. Existing expected flattened queryRef order remains unchanged:

```python
    def projections(page):
        state = artifacts[f"pages/{page}/visuals/supporting-records/visual.json"][
            "visual"]["query"]["queryState"]
        return [projection for role in ("Rows", "Values")
                for projection in state.get(role, {}).get("projections", [])]
```

The mutation tests use shipment, which stays tableEx, so their existing Values references remain valid.

## 4. Regenerate and validate

```sh
uv run pytest tests/fabric/test_report_generators.py -q
uv run python -m fabric.report_pages fabric/power-bi/SupplyResponse.Report/definition
uv run python -m fabric.report_pages fabric/power-bi/SupplyResponse.Report/definition --check
/private/tmp/supply-response-report-tools.Dadda4/node_modules/.bin/powerbi-report-author --out /private/tmp/supply-response-report-tools.Dadda4/report-validation-fixed.json validate --no-schema fabric/power-bi/SupplyResponse.Report
```

Regenerate the 8 pages from code; do not hand-edit PBIR JSON. Run existing Fabric reporting/schema/model checks and `git diff --check`. Inspect report artifact diffs: all projections gain nativeQueryRef, all title/footer positions change as above, filter names gain scope prefixes, stock alone changes roles/type/formatting; IDs, measures and source data must not change.

## Offline proof of this exact proposed code

Ran `/private/tmp/report-metadata-plan-probe.py` with `PYTHONPATH=. .venv/bin/python`. This harness extracts the Python blocks above, runs the four new tests against the original generator (all four fail on their intended assertions), compiles the proposed generator changes in memory, then runs the same tests (all four pass). It generates a temporary report copy; production generator, tests and report files remain unchanged. The temporary copy also passes the repository's pinned-schema validator.

Ran official CLI 0.1.4 against `/var/folders/zf/rcq9c9jx42l97zd9fgs115400000gn/T/report-native-plan-r8xrubdx/SupplyResponse.Report`: result **succeeded, 0 errors, 0 warnings**. Raw evidence: `/private/tmp/supply-response-report-tools.Dadda4/report-plan-probe-validation.json`. This confirms the proposed pivot properties and expansion state satisfy the installed metadata and pinned PBIR schema.

This plan is diagnosis and implementation-ready code, not a claim of production implementation or successful native rendering. Before stage 4 activation, capture all eight native pages and verify stock shows both part and plant with the four quantities, no aggregate subtotal rows, source details remain accessible, empty/error gates remain honest, and order lines remain distinct.

## Implementation handoff

After the preceding artifact integration checkpoint is reviewed, implement this bounded correction with RED/GREEN tests. Use `.venv/bin/python` and `.venv/bin/pytest` to avoid implicit dependency updates. Do not change model, SQL, dependencies, catalog, auth/approval or publication settings. Retain all generator/preflight adversarial tests; update only stock role assumptions if required by the intentional matrix migration. Run the full generator/project/schema suite with real TOM; controller can supply NuGet network escalation. Commit only `fabric/report_pages.py`, `tests/fabric/test_report_generators.py`, regenerated report page artifacts, and necessary stock-role expectations in `tests/fabric/test_power_bi_project.py`. Write `.superpowers/sdd/report-native-metadata-fix-report.md`, with exact commands and any residual warnings. No deployment, push or merge.
