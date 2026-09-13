from pathlib import Path

from fabric import report_model, report_pages

ROOT = Path(__file__).resolve().parents[2]
QUERIES = ROOT / "fabric/reporting/queries"


def test_operational_records_is_a_sixth_direct_query_table_with_raw_fields():
    model = report_model.manifest()
    assert tuple(model["tables"]) == report_model.TABLES
    assert len(model["tables"]) == 6
    operational = model["tables"]["OperationalRecords"]
    assert operational["mode"] == "directQuery"
    assert operational["query_file"].endswith("OperationalRecords.sql")
    assert operational["columns"]["dataset_id"] == "string"
    assert operational["columns"]["effective_at"] == "dateTime"
    assert operational["columns"]["incremental_cost_per_unit"] == "decimal"
    assert operational["columns"]["data_origin"] == "string"
    assert model["relationships"] == []


def test_operational_measures_require_exactly_one_allselected_dataset():
    measures = report_model.measures()["OperationalRecords"]
    selected = measures["Selected Operational Dataset"].expression
    assert "ALLSELECTED(OperationalRecords)" in selected
    external = measures["External Selected Operational Dataset"].expression
    assert "HASONEFILTER(OperationalRecords[dataset_id])" in external
    assert "DISTINCTCOUNT(OperationalRecords[dataset_id])" in external
    assert "SelectedDatasetCount == 1" in external
    for name in (
        "Operational Row Visible",
        "Inventory Row Visible",
        "Delivery Row Visible",
        "Transfer Row Visible",
        "Qualification Row Visible",
        "Customer Order Row Visible",
        "Production Demand Row Visible",
        "Supply Line Row Visible",
    ):
        assert "[Selected Operational Dataset]" in measures[name].expression


def test_operational_totals_are_family_specific_and_formats_are_honest():
    measures = report_model.measures()["OperationalRecords"]
    assert (
        'OperationalRecords[record_family] == "inventory"'
        in measures["Inventory Usable Units"].expression
    )
    assert (
        'OperationalRecords[record_family] == "customer_order"'
        in measures["Open Customer Revenue"].expression
    )
    assert (
        'OperationalRecords[record_family] == "production_order"'
        in measures["Production Component Demand"].expression
    )
    assert measures["Open Customer Revenue"].format_string == "$#,0"
    assert measures["Delivery Extended Cost"].format_string == "$#,0"
    assert (
        report_model.column_format("OperationalRecords", "incremental_cost_per_unit")
        == "$#,0.00"
    )
    assert "quantity" not in measures["Operational Record Count"].expression.lower()


def test_operational_unit_totals_require_one_nonblank_component():
    measures = report_model.measures()["OperationalRecords"]
    for name in (
        "Inventory On Hand Units",
        "Inventory Hold Units",
        "Inventory Protected Units",
        "Inventory Usable Units",
        "Delivery Units",
        "Transfer Units",
        "Production Component Demand",
    ):
        expression = measures[name].expression
        assert "CALCULATE(SELECTEDVALUE(OperationalRecords[part_id])" in expression
        assert "NOT ISBLANK(PartKey)" in expression
        assert expression.count("OperationalRecords[record_family] ==") == 2
    context = measures["Operational Quantity Context"].expression
    assert "Select one component" in context


def test_delivery_cost_is_blank_if_any_contributing_line_lacks_cost_inputs():
    expression = report_model.measures()["OperationalRecords"][
        "Delivery Extended Cost"
    ].expression
    assert "MissingCostInputs" in expression
    assert "ISBLANK(OperationalRecords[quantity])" in expression
    assert "ISBLANK(OperationalRecords[incremental_cost_per_unit])" in expression
    assert "MissingCostInputs == 0" in expression
    assert "COALESCE(CALCULATE(COUNTROWS(OperationalRecords)" in expression
    assert "COALESCE(OperationalRecords[quantity]" not in expression
    assert "COALESCE(OperationalRecords[incremental_cost_per_unit]" not in expression


def test_operational_partition_uses_the_accepted_explicit_query():
    artifacts = report_model.artifacts(QUERIES)
    tmdl = artifacts["tables/OperationalRecords.tmdl"]
    query = (QUERIES / "OperationalRecords.sql").read_text()
    assert "Sql.Database" in tmdl
    assert "record_id" in query and "data_origin" in query
    assert "SELECT *" not in query.upper()


def test_broad_operational_pages_are_new_default_and_keep_saved_ids():
    artifacts = report_pages.artifacts()
    pages = artifacts["pages/pages.json"]
    broad = (
        "operations-overview",
        "operations-inventory",
        "operations-deliveries",
        "operations-transfers",
        "operations-qualification",
        "operations-orders",
        "operations-demand",
    )
    assert pages["activePageName"] == "operations-overview"
    assert tuple(pages["pageOrder"][:7]) == broad
    for page in broad:
        assert f"pages/{page}/page.json" in artifacts
    for saved in (
        "command-center",
        "available-stock",
        "supplier-shipment",
        "plant-transfer",
        "supplier-qualification",
        "customer-orders",
        "response-options",
        "actions-outcomes",
    ):
        assert f"pages/{saved}/page.json" in artifacts


def test_broad_pages_use_visible_slicers_dense_tables_and_native_charts():
    artifacts = report_pages.artifacts()
    for page in report_pages.OPERATIONAL_ORDER:
        prefix = f"pages/{page}/visuals/"
        visuals = {
            path.removeprefix(prefix).removesuffix("/visual.json"): value
            for path, value in artifacts.items()
            if path.startswith(prefix) and path.endswith("/visual.json")
        }
        assert {
            "dataset-filter",
            "plant-filter",
            "component-filter",
            "supplier-filter",
        } <= set(visuals)
        assert all(
            visuals[name]["visual"]["visualType"] == "slicer"
            for name in (
                "dataset-filter",
                "plant-filter",
                "component-filter",
                "supplier-filter",
            )
        )
        table = visuals["operational-rows"]
        assert table["visual"]["visualType"] == "tableEx"
        assert table["position"]["height"] >= 300
        assert len(table["visual"]["query"]["queryState"]["Values"]["projections"]) >= 6
        chart = visuals["operational-chart"]
        assert chart["visual"]["visualType"] == "clusteredColumnChart"
        assert set(chart["visual"]["query"]["queryState"]) == {"Category", "Y"}


def test_active_projection_metadata_is_only_on_categories_and_slicers():
    for path, artifact in report_pages.artifacts().items():
        visual = artifact.get("visual", {})
        kind = visual.get("visualType")
        for role, state in visual.get("query", {}).get("queryState", {}).items():
            for projection in state["projections"]:
                assert "nativeQueryRef" in projection, path
                if projection.get("active"):
                    assert role == "Category" or kind == "slicer", (path, role)
                if kind == "tableEx":
                    assert "active" not in projection, path


def test_saved_detail_pages_remain_exact_and_are_not_ai_prose_layouts():
    artifacts = report_pages.artifacts()
    for page in (
        "available-stock",
        "supplier-shipment",
        "plant-transfer",
        "supplier-qualification",
        "customer-orders",
    ):
        prefix = f"pages/{page}/visuals/"
        names = {path.split("/")[-2] for path in artifacts if path.startswith(prefix)}
        assert "supporting-records" in names
        assert not any(name.startswith("answer-") for name in names)
        assert "explanation" not in names
        table = artifacts[prefix + "supporting-records/visual.json"]
        assert table["position"]["height"] >= 300


def test_native_tom_validator_requires_the_explicit_six_table_contract():
    source = (ROOT / "tests/fabric/tmdl-validator/Program.cs").read_text()
    assert "manifest must contain the six approved tables" in source
    assert '"OperationalRecords"' in source


def test_delivery_investigation_keeps_purchase_and_shipment_lines_distinct():
    measures = report_model.measures()["OperationalRecords"]
    gate = measures["Supply Line Row Visible"].expression
    assert '{"purchase","shipment"}' in gate
    count = measures["Supply Line Count"].expression
    assert '{"purchase","shipment"}' in count
    artifacts = report_pages.artifacts()
    table = artifacts[
        "pages/operations-deliveries/visuals/operational-rows/visual.json"
    ]["visual"]
    refs = [
        item["queryRef"]
        for item in table["query"]["queryState"]["Values"]["projections"]
    ]
    assert "OperationalRecords.record_family" in refs
    assert "OperationalRecords.original_due_date" in refs
    page_filters = artifacts["pages/operations-deliveries/page.json"]["filterConfig"][
        "filters"
    ]
    assert not any(item["name"].endswith("OperationalFamily") for item in page_filters)


def test_saved_snapshot_known_usd_columns_use_total_and_unit_formats():
    for name in ("line_revenue", "customer_revenue", "customer_margin"):
        assert report_model.column_format("SavedRecords", name) == "$#,0"
    for name in ("incremental_cost_per_unit", "unit_revenue", "unit_margin"):
        assert report_model.column_format("SavedRecords", name) == "$#,0.00"
