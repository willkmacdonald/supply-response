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
        required = {
            "dataset-filter",
            "component-filter",
            "date-filter",
            "snapshot-context",
        }
        required |= (
            {"source-plant-filter", "destination-plant-filter"}
            if page == "operations-transfers"
            else {"plant-filter", "supplier-filter"}
        )
        assert required <= set(visuals)
        assert all(
            visuals[name]["visual"]["visualType"] == "slicer"
            for name in required - {"snapshot-context"}
        )
        context = visuals["snapshot-context"]
        assert context["visual"]["objects"]["values"][0]["properties"]["expr"][
            "expr"
        ] == report_pages.field(
            "Measure", "OperationalRecords", "Operational Snapshot Context"
        )
        table = visuals["operational-rows"]
        assert table["visual"]["visualType"] == "tableEx"
        assert table["position"]["height"] >= 300
        assert len(table["visual"]["query"]["queryState"]["Values"]["projections"]) >= 6
        chart = visuals["operational-chart"]
        assert chart["visual"]["visualType"] == "clusteredColumnChart"
        assert set(chart["visual"]["query"]["queryState"]) == {"Category", "Y"}

    expected_dates = {
        "operations-overview": ("due_date", "Due date"),
        "operations-inventory": ("effective_at", "Stock snapshot date"),
        "operations-deliveries": ("due_date", "Due date"),
        "operations-transfers": ("arrival_date", "Expected arrival"),
        "operations-qualification": ("expected_decision_date", "Review date"),
        "operations-orders": ("due_date", "Due date"),
        "operations-demand": ("due_date", "Due date"),
    }
    for page, (field_name, label) in expected_dates.items():
        slicer = artifacts[f"pages/{page}/visuals/date-filter/visual.json"]
        projection = slicer["visual"]["query"]["queryState"]["Values"]["projections"][0]
        assert projection["queryRef"] == f"OperationalRecords.{field_name}"
        assert slicer["visual"]["objects"]["header"][0]["properties"][
            "text"
        ] == report_pages.literal(label)

    for page, expected_title in {
        "operations-overview": "Open customer order value by due date (USD)",
        "operations-inventory": "Usable inventory by component (units)",
        "operations-deliveries": "Purchase and shipment lines by supplier (count)",
        "operations-transfers": "Transfer lines by source plant (count)",
        "operations-qualification": "Qualification records by supplier (count)",
        "operations-orders": "Open customer order value by customer (USD)",
        "operations-demand": "Production demand by component (units)",
    }.items():
        chart = artifacts[f"pages/{page}/visuals/operational-chart/visual.json"]
        title = chart["visual"]["visualContainerObjects"]["title"][0]["properties"][
            "text"
        ]
        assert title == report_pages.literal(expected_title)
        table = artifacts[f"pages/{page}/visuals/operational-rows/visual.json"]
        table_title = table["visual"]["visualContainerObjects"]["title"][0][
            "properties"
        ]["text"]
        assert "operational rows" not in table_title["expr"]["Literal"]["Value"].lower()


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
        assert "saved-detail-chart" in names
        table = artifacts[prefix + "supporting-records/visual.json"]
        assert table["position"]["height"] >= 300
        assert artifacts[f"pages/{page}/page.json"]["visibility"] == "HiddenInViewMode"


def test_exact_record_headers_use_fast_saved_snapshot_context():
    artifacts = report_pages.artifacts()
    for page in ("supplier-shipment", "plant-transfer", "supplier-qualification"):
        header = artifacts[f"pages/{page}/visuals/selection-state/visual.json"]
        expression = header["visual"]["objects"]["values"][0]["properties"]["expr"][
            "expr"
        ]
        assert expression == report_pages.field(
            "Measure", report_pages.CC, "Snapshot Context"
        )


def test_option_money_displays_are_usd_whole_dollars():
    measures = report_model.measures()["CaseCommandCenter"]
    for name in ("Option Revenue Display", "Option Cost Display"):
        expression = measures[name].expression
        assert 'FORMAT(V, "$#,0")' in expression
        assert "currency not specified" not in expression
    assert report_model.column_format("SavedOptions", "revenue_at_risk") == "$#,0"
    assert report_model.column_format("SavedOptions", "response_cost") == "$#,0"
    assert measures["Option Revenue"].format_string == "$#,0"
    assert measures["Option Response Cost"].format_string == "$#,0"
    table = report_pages.artifacts()[
        "pages/response-options/visuals/option-comparison/visual.json"
    ]
    refs = {
        item["queryRef"]
        for item in table["visual"]["query"]["queryState"]["Values"]["projections"]
    }
    assert {"SavedOptions.revenue_at_risk", "SavedOptions.response_cost"} <= refs


def test_native_tom_validator_requires_the_explicit_six_table_contract():
    source = (ROOT / "tests/fabric/tmdl-validator/Program.cs").read_text()
    assert "manifest must contain the six approved tables" in source
    assert '"OperationalRecords"' in source


def test_delivery_investigation_keeps_purchase_and_shipment_lines_distinct():
    measures = report_model.measures()["OperationalRecords"]
    gate = measures["Supply Line Row Visible"].expression
    assert '{"purchase","shipment"}' in gate
    assert "COUNTROWS(OperationalRecords)" in gate
    assert "SELECTEDVALUE(OperationalRecords[record_family])" not in gate
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


def test_transfer_page_filters_both_route_endpoints():
    artifacts = report_pages.artifacts()
    prefix = "pages/operations-transfers/visuals/"
    refs = {
        artifact["visual"]["query"]["queryState"]["Values"]["projections"][0][
            "queryRef"
        ]
        for path, artifact in artifacts.items()
        if path.startswith(prefix) and path.endswith("filter/visual.json")
    }
    assert "OperationalRecords.source_plant_name" in refs
    assert "OperationalRecords.destination_plant_name" in refs


def test_saved_snapshot_known_usd_columns_use_total_and_unit_formats():
    for name in ("line_revenue", "customer_revenue", "customer_margin"):
        assert report_model.column_format("SavedRecords", name) == "$#,0"
    for name in ("incremental_cost_per_unit", "unit_revenue", "unit_margin"):
        assert report_model.column_format("SavedRecords", name) == "$#,0.00"


def test_saved_order_chart_uses_row_scoped_revenue():
    expression = report_model.measures()["CaseCommandCenter"][
        "Affected Revenue Row"
    ].expression
    assert "ALL(SavedRecords)" not in expression
    chart = report_pages.artifacts()[
        "pages/customer-orders/visuals/saved-detail-chart/visual.json"
    ]
    projection = chart["visual"]["query"]["queryState"]["Y"]["projections"][0]
    assert projection["queryRef"] == "CaseCommandCenter.Affected Revenue Row"
    category = chart["visual"]["query"]["queryState"]["Category"]["projections"][0]
    assert category["queryRef"] == "SavedRecords.source_record_id"


def test_saved_overview_leads_orders_with_canonical_line_identity():
    table = report_pages.artifacts()[
        "pages/command-center/visuals/saved-order-rows/visual.json"
    ]
    projections = table["visual"]["query"]["queryState"]["Values"]["projections"]
    assert projections[0]["queryRef"] == "SavedRecords.source_record_id"
    assert projections[0]["displayName"] == "Order line"
    assert projections[1]["queryRef"] == "SavedRecords.customer_order_id"


def test_saved_numeric_guards_normalize_empty_countblank_only():
    measures = report_model.measures()["CaseCommandCenter"]
    guarded = (
        "Stock Usable",
        "Stock Held",
        "Stock Protected",
        "Affected Revenue",
        "Stock On Hand Row",
        "Stock Held Row",
        "Stock Protected Row",
        "Stock Usable Row",
        "Affected Revenue Row",
        "Overview Stock",
    )
    for name in guarded:
        expression = measures[name].expression
        assert "COALESCE(COUNTBLANK(" in expression, name
        assert "COALESCE(SUM(" not in expression, name
