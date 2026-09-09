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
        "command-center",
        "actions-outcomes",
        "supplier-shipment",
        "plant-transfer",
        "supplier-qualification",
        "available-stock",
        "customer-orders",
        "response-options",
    )
    for path, value in report_pages.artifacts().items():
        if not path.endswith("visual.json"):
            continue
        position = value["position"]
        page_name = path.split("/")[1]
        page_definition = report_pages.artifacts()[f"pages/{page_name}/page.json"]
        assert (
            0
            <= position["x"]
            < position["x"] + position["width"]
            <= page_definition["width"]
        )
        assert (
            0
            <= position["y"]
            < position["y"] + position["height"]
            <= page_definition["height"]
        )
        visual = value["visual"]
        if visual["visualType"] == "cardVisual":
            assert set(visual["query"]["queryState"]) == {"Data"}
        if visual["visualType"] in {
            "tableEx",
            "pivotTable",
            "clusteredColumnChart",
        }:
            (gate,) = value["filterConfig"]["filters"]
            assert gate["isHiddenInViewMode"] and gate["isLockedInViewMode"]
            condition = gate["filter"]["Where"][0]["Condition"]["Comparison"]
            assert condition["ComparisonKind"] == 0
            assert condition["Right"] == {"Literal": {"Value": "1L"}}


def test_preserves_existing_visual_identities_and_three_rows():
    artifacts = report_pages.artifacts()
    old_ids = {
        "command-center": (
            "active-cases",
            "current-decision",
            "otif-loss",
            "revenue-at-risk",
            "scenario-effective-time",
            "showcase-cases",
        ),
        "actions-outcomes": (
            "action-status",
            "decision-id",
            "observation-kind",
            "predicted-observed-variance",
            "projection-refresh",
            "scenario-effective-time",
        ),
    }
    for page, identities in old_ids.items():
        for identity in identities:
            assert f"pages/{page}/visuals/{identity}/visual.json" in artifacts
    first = artifacts["pages/command-center/visuals/active-cases/visual.json"]
    assert (
        first["visual"]["query"]["queryState"]["Data"]["projections"][0]["queryRef"]
        == "CaseCommandCenter.Disruption Answer"
    )
    for row in (1, 2, 3):
        assert f"pages/command-center/visuals/row-label-{row}/visual.json" in artifacts


def test_walkthrough_sequence_uses_all_existing_pages_once():
    sequence = tuple(page for page, title in report_pages.WALKTHROUGH)
    assert len(sequence) == len(set(sequence)) == 8
    assert set(sequence) == set(report_pages.ORDER)
    assert sequence[0] == "command-center"
    assert sequence[-1] == "actions-outcomes"


def test_walkthrough_footer_replaces_old_page_tab_instruction():
    artifacts = report_pages.artifacts()
    expected = (
        "Snapshot used for this analysis · Demo corpus — fictional · "
        "Return to the existing demo tab for original messages and AI assistance."
    )
    for page in report_pages.ORDER:
        footer = artifacts[f"pages/{page}/visuals/fictional-footer/visual.json"]
        paragraphs = footer["visual"]["objects"]["general"][0]["properties"][
            "paragraphs"
        ]
        assert paragraphs[0]["textRuns"][0]["value"] == expected


def test_native_previous_next_match_official_action_shape():
    artifacts = report_pages.artifacts()
    sequence = tuple(page for page, _ in report_pages.WALKTHROUGH)
    controls = []
    for index, page in enumerate(sequence):
        prefix = f"pages/{page}/visuals/"
        expected = {}
        if index:
            expected["walkthrough-previous"] = sequence[index - 1]
        if index + 1 < len(sequence):
            expected["walkthrough-next"] = sequence[index + 1]
        for name in ("walkthrough-previous", "walkthrough-next"):
            key = prefix + name + "/visual.json"
            if name not in expected:
                assert key not in artifacts
                continue
            control = artifacts[key]
            controls.append(control)
            assert control["visual"]["visualType"] == "actionButton"
            assert "filterConfig" not in control
            assert control["visual"]["visualContainerObjects"]["visualLink"] == [
                {
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "type": {"expr": {"Literal": {"Value": "'PageNavigation'"}}},
                        "navigationSection": {
                            "expr": {"Literal": {"Value": "'" + expected[name] + "'"}}
                        },
                    },
                }
            ]
            assert control["position"]["height"] >= 44
            assert control["visual"]["visualContainerObjects"]["general"][0][
                "properties"
            ]["altText"]
    assert len(controls) == 14


def test_native_navigation_rejects_unrecognized_destinations():
    with pytest.raises(ValueError, match="Unknown walkthrough page"):
        report_pages.navigation_button(
            "next", "Next", (0, 0, 220, 44), "https://evil.example"
        )


def test_traditional_pages_are_neutral_and_options_sort_by_name():
    artifacts = report_pages.artifacts()
    review = artifacts[
        "pages/command-center/visuals/recommendation-answer/visual.json"
    ]["visual"]
    assert review["query"]["queryState"]["Data"]["projections"][0]["queryRef"] == (
        "CaseCommandCenter.Review Approach"
    )
    assert review["visualContainerObjects"]["title"][0]["properties"]["text"] == (
        report_pages.literal("Review approach")
    )
    comparison = artifacts[
        "pages/response-options/visuals/option-comparison/visual.json"
    ]["visual"]
    assert comparison["query"]["sortDefinition"] == {
        "sort": [
            {
                "field": report_pages.field("Column", report_pages.SO, "option_name"),
                "direction": "Ascending",
            }
        ],
        "isDefaultSort": False,
    }


def test_option_comparison_includes_protected_customer_orders_column():
    visual = report_pages.artifacts()[
        "pages/response-options/visuals/option-comparison/visual.json"
    ]["visual"]
    projections = visual["query"]["queryState"]["Values"]["projections"]
    assert [projection["queryRef"] for projection in projections] == [
        "SavedOptions.option_name",
        "SavedOptions.is_baseline",
        "SavedOptions.executable",
        "SavedOptions.response_cost",
        "SavedOptions.revenue_at_risk",
        "SavedOptions.otif_loss_percentage",
        "SavedOptions.uncovered_part_demand",
        "SavedOptions.protected_customer_order_count",
        "SavedOptions.blockers_text",
        "SavedOptions.required_roles_text",
    ]
    protected = projections[7]
    assert protected["displayName"] == "Customer orders protected"
    assert (
        sum(
            projection["nativeQueryRef"] == "protected_customer_order_count"
            for projection in projections
        )
        == 1
    )
    assert "recommend" not in protected
    assert visual["visualType"] == "tableEx"


def test_clearable_case_selector_is_shared_without_a_default():
    for page in report_pages.ORDER:
        value = report_pages.artifacts()[
            f"pages/{page}/visuals/case-selector/visual.json"
        ]["visual"]
        assert value["syncGroup"] == {
            "groupName": "SupplyResponseCase",
            "fieldChanges": True,
            "filterChanges": True,
        }
        selection = value["objects"]["selection"][0]["properties"]
        assert selection["singleSelect"] == {"expr": {"Literal": {"Value": "true"}}}
        assert selection["strictSingleSelect"] == {
            "expr": {"Literal": {"Value": "false"}}
        }
        assert "general" not in value["objects"]
        assert (
            value["query"]["queryState"]["Values"]["projections"][0]["queryRef"]
            == "CaseCommandCenter.case_id"
        )


def test_business_tables_preserve_stock_totals_and_order_line_grain():
    artifacts = report_pages.artifacts()

    def projections(page):
        state = artifacts[f"pages/{page}/visuals/supporting-records/visual.json"][
            "visual"
        ]["query"]["queryState"]
        return [
            projection
            for role in ("Rows", "Values")
            for projection in state.get(role, {}).get("projections", [])
        ]

    stock = projections("available-stock")
    assert [item["queryRef"] for item in stock] == [
        "SavedRecords.part_id",
        "SavedRecords.plant_id",
        "CaseCommandCenter.Stock On Hand Row",
        "CaseCommandCenter.Stock Held Row",
        "CaseCommandCenter.Stock Protected Row",
        "CaseCommandCenter.Stock Usable Row",
    ]
    orders = projections("customer-orders")
    assert any(
        item["queryRef"] == "SavedRecords.source_record_id"
        and item["displayName"] == "Order line"
        for item in orders
    )


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
        size = max(
            float(run["textStyle"]["fontSize"].removesuffix("px"))
            for paragraph in paragraphs
            for run in paragraph["textRuns"]
        )
        padding = visual["visualContainerObjects"]["padding"][0]["properties"]
        vertical = sum(
            float(padding[key]["expr"]["Literal"]["Value"].removesuffix("D"))
            for key in ("top", "bottom")
        )
        position = artifact["position"]
        assert position["height"] >= max(18, ceil(size * 25 / 16)) + vertical, path
        page_name = path.split("/")[1]
        page = artifacts[f"pages/{page_name}/page.json"]
        assert position["y"] + position["height"] <= page["height"], path


def test_stock_matrix_retains_part_plant_grain_and_guarded_measures():
    artifact = report_pages.artifacts()[
        "pages/available-stock/visuals/supporting-records/visual.json"
    ]
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
        "Measure", report_pages.CC, "Stock Row Visible"
    )
    assert visual["expansionStates"] == [
        {
            "roles": ["Rows"],
            "levels": [
                {
                    "queryRefs": [item["queryRef"]],
                    "identityKeys": [item["field"]],
                    "isCollapsed": False,
                    "isPinned": True,
                }
                for item in roles["Rows"]["projections"]
            ],
        }
    ]
    assert "total" not in visual["objects"]
    for instance in visual["objects"]["subTotals"]:
        assert instance["properties"] == {
            "rowSubtotals": report_pages.literal(False),
            "columnSubtotals": report_pages.literal(False),
        }
    for path, value in report_pages.artifacts().items():
        item = value.get("visual", {})
        if item.get("visualType") == "tableEx":
            assert all(
                "Column" in p["field"]
                for p in item["query"]["queryState"]["Values"]["projections"]
            ), path


@pytest.mark.parametrize(
    "change",
    ["unlock", "remove-gate", "role", "field", "type", "title", "aggregation", "extra"],
)
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
        visual["query"]["queryState"]["Data"] = visual["query"]["queryState"].pop(
            "Values"
        )
    elif change == "field":
        visual["query"]["queryState"]["Values"]["projections"][0]["field"]["Column"][
            "Property"
        ] = "other"
    elif change == "type":
        visual["visualType"] = "card"
    elif change == "title":
        visual["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"][
            "Literal"
        ]["Value"] = "'Wrong'"
    elif change == "aggregation":
        projection = visual["query"]["queryState"]["Values"]["projections"][0]
        projection["field"] = {
            "Aggregation": {"Expression": deepcopy(projection["field"]), "Function": 0}
        }
    else:
        (tmp_path / "pages/extra.json").write_text("{}")
    path.write_text(report_pages.encoded(value), encoding="utf-8")
    with pytest.raises(ValueError):
        report_pages.verify(tmp_path)


def test_model_manifest_binds_every_report_field_without_json_payloads(tmp_path):
    report_model.check_required_fields(report_pages.required_fields())
    manifest = report_model.manifest()
    assert set(manifest["tables"]) == {
        "CaseCommandCenter",
        "ActionOutcomes",
        "SavedAnalyses",
        "SavedRecords",
        "SavedOptions",
    }
    assert manifest["relationships"] == []
    for flag in (
        "no_feasible_mitigation",
        "inventory_complete",
        "production_orders_complete",
        "customer_orders_complete",
    ):
        assert manifest["tables"]["SavedAnalyses"]["columns"][flag] == "boolean"
    for table, details in manifest["tables"].items():
        assert details["mode"] == "directQuery"
        assert details["partition"] == table
        assert all(not name.endswith("_json") for name in details["columns"])
    with pytest.raises(ValueError, match="Unknown report binding"):
        report_model.check_required_fields(
            [("Measure", "CaseCommandCenter", "Not an approved measure")]
        )
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
                assert (
                    field in manifest[table]["columns"]
                    or field in manifest[table]["measures"]
                ), (table, field)
            for name in re.findall(r"(?<![\w'])\[([^\]]+)\]", measure.expression):
                assert name in names, name
            assert "NOW()" not in measure.expression.upper()
    cc = measures["CaseCommandCenter"]
    assert (
        "[Selected inventory_complete] == TRUE()" in cc["Stock Rows Valid"].expression
    )
    assert (
        "[Overview inventory_complete] == TRUE()"
        in cc["Overview Stock Rows Valid"].expression
    )
    assert (
        "[Selected production_orders_complete] == TRUE()"
        in cc["Orders Rows Valid"].expression
    )
    assert (
        "[Selected customer_orders_complete] == TRUE()"
        in cc["Orders Rows Valid"].expression
    )
    assert "ALLSELECTED(CaseCommandCenter)" in cc["Selected Case Key"].expression
    assert (
        "HASONEFILTER(CaseCommandCenter[case_key])"
        in cc["External Selected Case Key"].expression
    )
    assert "[Analysis Requested] == 1" in cc["Overview Analysis Key"].expression
    for gate in (
        "Record Row Visible",
        "Stock Row Visible",
        "Order Row Visible",
        "Option Row Visible",
    ):
        expression = cc[gate].expression
        assert (
            "[Selected Case Key]" in expression
            and "[Selected Analysis Key]" in expression
        )
        assert "KEEPFILTERS" in expression and "TREATAS" in expression
        assert "REMOVEFILTERS" not in expression
    for gate in ("Action Row Visible", "Observation Row Visible"):
        expression = cc[gate].expression
        assert (
            "[Selected Case Key]" in expression
            and "[Current Decision Key]" in expression
        )
        assert "ActionOutcomes[decision_key]" in expression
    variance = measures["ActionOutcomes"]["Observed Variance"].expression
    assert "[Observation Row Visible] == 1" in variance
    assert "IFERROR(VALUE(PredictedText), BLANK())" in variance
    assert "IFERROR(VALUE(ObservedText), BLANK())" in variance
    assert "Predicted == 0" in variance and "ABS(Predicted)" in variance
    assert "AVERAGEX" not in variance and "REMOVEFILTERS" not in variance


def test_traditional_marker_is_a_presentation_column_not_a_new_table():
    model = report_model.manifest()
    assert set(model["tables"]) == set(report_model.TABLES)
    assert len(model["tables"]) == 5
    assert (
        model["tables"]["CaseCommandCenter"]["columns"]["walkthrough_route"] == "string"
    )
    sql = (QUERIES / "CaseCommandCenter.sql").read_text()
    assert "CAST(N'traditional' AS nvarchar(16)) AS walkthrough_route" in sql
    assert model["relationships"] == []


def test_traditional_entry_never_falls_back_to_current_analysis():
    measures = report_model.measures()[report_model.CC]
    expression = measures["Overview Analysis Key"].expression
    assert "[Walkthrough Requested] == 1 || [Analysis Requested] == 1" in expression
    assert "[Selected Analysis Key]" in expression
    approach = measures["Review Approach"].expression
    assert "[Walkthrough Requested] == 1" in approach
    assert "Walkthrough selection unavailable" in approach


def test_walkthrough_does_not_replace_explicit_record_identity_validation():
    measures = report_model.measures()[report_model.CC]
    explicit = measures["External Explicit Selected Record Key"].expression
    assert "HASONEFILTER(SavedRecords[record_key])" in explicit
    assert '"shipment","transfer","qualification"' in explicit
    selected = measures["Selected Record Key"].expression
    assert "[Record Identity Requested] == 1" in selected
    assert "[Explicit Selected Record Key]" in selected
    singleton = measures["External Walkthrough Record Key"].expression
    assert "COUNTROWS(Candidates) == 1 && COUNTROWS(ValidCandidates) == 1" in singleton
    assert "REMOVEFILTERS(SavedRecords)" in singleton
    assert "[Record Identity Requested] == 0" in singleton
    assert 'SavedRecords[provenance] == "saved_fabric"' in singleton


def test_measure_names_are_globally_casefold_unique_and_displays_use_raw_values():
    definitions = report_model.measures()
    names = [name for table in definitions.values() for name in table]
    assert len({name.casefold() for name in names}) == len(names)

    case_measures = definitions["CaseCommandCenter"]
    expected_helpers = {
        "Record Provenance Display": "Record provenance",
        "Overview Qualification Status Display": "Overview qualification status",
    }
    for display_name, raw_name in expected_helpers.items():
        expression = case_measures[display_name].expression
        assert f"[{raw_name}]" in expression
        assert f"[{display_name}]" not in expression


@pytest.mark.parametrize(
    "invalid", ["target-directory", "parent-file", "extra-file", "extra-directory"]
)
def test_page_cli_rejects_invalid_inventory_before_writes(
    tmp_path, monkeypatch, invalid
):
    import sys

    expected = report_pages.artifacts()
    first = tmp_path / "pages/pages.json"
    first.parent.mkdir(parents=True)
    first.write_text("sentinel", encoding="utf-8")
    late = tmp_path / list(expected)[-1]
    if invalid == "target-directory":
        late.mkdir(parents=True)
    elif invalid == "parent-file":
        late.parent.parent.mkdir(parents=True)
        late.parent.write_text("keep parent", encoding="utf-8")
    elif invalid == "extra-file":
        (tmp_path / "pages/unexpected.json").write_text("keep extra", encoding="utf-8")
    else:
        (tmp_path / "pages/unexpected").mkdir()
    monkeypatch.setattr(sys, "argv", ["report_pages", str(tmp_path)])
    with pytest.raises(ValueError):
        report_pages.main()
    assert first.read_text(encoding="utf-8") == "sentinel"


def test_formats_preserve_dates_utc_zero_and_literal_m_escapes():
    assert report_model.column_format("SavedRecords", "due_date") == "MMM d, yyyy"
    assert (
        report_model.column_format("SavedRecords", "retrieved_at")
        == 'MMM d, yyyy HH:mm "UTC"'
    )
    assert report_model.column_format("SavedOptions", "response_cost") == "#,0.00"
    assert report_model.column_format("SavedOptions", "otif_loss_percentage") == '0"%"'
    assert report_model.m_string('#(lf)\n"quoted"') == '"#(#)(lf)#(lf)""quoted"""'
    cc = report_model.measures()["CaseCommandCenter"]
    for name in (
        "Record Quantity Display",
        "Record Unit Cost Display",
        "Stock Usable Display",
    ):
        assert "ISBLANK(V)" in cc[name].expression
    for name in ("Record Audit Display", "Record First Article Display"):
        assert (
            'IF(ISBLANK(V),"Unavailable",IF(V,"Complete","Outstanding"))'
            in cc[name].expression
        )


@pytest.mark.parametrize(
    "change", ["measure", "partition", "relationship", "extra-table"]
)
def test_model_drift_fails(tmp_path, change):
    write_model(tmp_path)
    path = tmp_path / "tables/CaseCommandCenter.tmdl"
    if change == "measure":
        path.write_text(path.read_text().replace("HASONEFILTER", "HASONEVALUE", 1))
    elif change == "partition":
        path.write_text(
            path.read_text().replace("mode: directQuery", "mode: import", 1)
        )
    elif change == "relationship":
        (tmp_path / "relationships.tmdl").write_text("relationship NotApproved\n")
    else:
        (tmp_path / "tables/Extra.tmdl").write_text("table Extra\n")
    with pytest.raises(ValueError):
        report_model.verify(tmp_path, QUERIES)


@pytest.mark.parametrize(
    "kind", ["pages-root", "definition-root", "tables-root", "query-root"]
)
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
        return pages[f"pages/customer-orders/visuals/answer-{index}/visual.json"][
            "visual"
        ]["query"]["queryState"]["Data"]["projections"][0]["queryRef"]

    assert answer(1) == "CaseCommandCenter.Orders Baseline Revenue Display"
    assert answer(2) == "CaseCommandCenter.Orders Baseline OTIF Display"
    assert answer(3) == "CaseCommandCenter.Affected Lines Display"
    definitions = report_model.manifest()["tables"]["CaseCommandCenter"]["measures"]
    for name, source in (
        ("Orders Baseline Revenue", "Baseline revenue_at_risk"),
        ("Orders Baseline OTIF", "Baseline otif_loss_percentage"),
    ):
        expression = definitions[name]["expression"]
        assert "NOT ISBLANK([Selected Analysis Key])" in expression
        assert "[" + source + "]" in expression
    assert '"0"' in definitions["Orders Baseline OTIF Display"]["expression"]
    assert '"%"' in definitions["Orders Baseline OTIF Display"]["expression"]
    assert "Without a response" in definitions["Orders Explanation"]["expression"]
    assert (
        "do not identify individual missed service targets"
        in definitions["Orders Explanation"]["expression"]
    )


def test_business_measures_are_implemented_and_use_saved_values():
    tables = report_model.manifest()["tables"]
    definitions = tables["CaseCommandCenter"]["measures"]
    assert not [
        name
        for table in tables.values()
        for name, spec in table["measures"].items()
        if spec["expression"].strip() == "BLANK()"
    ]
    for name in (
        "Baseline revenue_at_risk",
        "Recommended revenue_at_risk",
        "Approved revenue_at_risk",
    ):
        text = definitions[name]["expression"]
        assert "SELECTEDVALUE(SavedOptions[revenue_at_risk])" in text
        assert "COUNTROWS(SavedOptions) == 1" in text
        assert "TREATAS" in text
    assert (
        "SUM(SavedRecords[usable_inventory])"
        in definitions["Stock Usable"]["expression"]
    )
    assert (
        "[Overview disruption original_quantity]"
        in definitions["Disruption Answer"]["expression"]
    )
    variance = tables["ActionOutcomes"]["measures"]["Observed Variance"]["expression"]
    assert "DIVIDE(Observed - Predicted, ABS(Predicted))" in variance
    assert "ISBLANK(Predicted) || ISBLANK(Observed) || Predicted == 0" in variance
    assert "[Observation Row Visible] == 1" in variance


def test_overview_answers_bind_explicit_saved_prediction_bases():
    definitions = report_model.manifest()["tables"]["CaseCommandCenter"]["measures"]
    exposure = definitions["Exposure Answer"]["expression"]
    assert "[Baseline uncovered_part_demand]" in exposure
    assert "component units still needed" in exposure
    assert "[Baseline response_cost]" in exposure
    assert "currency not specified" in exposure
    assert "Service-target exposure" in exposure

    recommendation = definitions["Recommendation Answer"]["expression"]
    assert "[Overview no_feasible_mitigation] == TRUE()" in recommendation
    assert "No option meets the planning requirements" in recommendation
    assert "[Recommended otif_loss_percentage]" in recommendation
    assert "order-line service-target exposure" in recommendation
    assert "ISBLANK([Recommended option_name])" in recommendation


def test_no_feasible_state_is_selected_from_exact_saved_analysis():
    expression = report_model.manifest()["tables"]["CaseCommandCenter"]["measures"][
        "Overview no_feasible_mitigation"
    ]["expression"]
    assert "SELECTEDVALUE(SavedAnalyses[no_feasible_mitigation])" in expression
    assert "[Overview Analysis Key]" in expression
    assert "REMOVEFILTERS(SavedAnalyses)" in expression


def test_dax_variable_renaming_preserves_quoted_business_copy():
    expression = report_model.manifest()["tables"]["CaseCommandCenter"]["measures"][
        "Record Explanation"
    ]["expression"]
    assert "A review date is not an approval or delivery date." in expression
    assert "ScopeAnalysis review date" not in expression
    source = 'VAR C = 1 VAR A = 2 RETURN "A ""quoted C"" message" & C & A'
    assert report_model.rename_scope_variables(source) == (
        'VAR ScopeCase = 1 VAR ScopeAnalysis = 2 RETURN "A ""quoted C"" message" & ScopeCase & ScopeAnalysis'
    )
