from pathlib import Path

from fabric import report_model

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
    assert "DatasetCount == 1" in external
    for name in (
        "Operational Row Visible",
        "Inventory Row Visible",
        "Delivery Row Visible",
        "Transfer Row Visible",
        "Qualification Row Visible",
        "Customer Order Row Visible",
        "Production Demand Row Visible",
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
        assert "SELECTEDVALUE(OperationalRecords[part_id])" in expression
        assert "NOT ISBLANK(PartKey)" in expression
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
    assert "COALESCE" not in expression


def test_operational_partition_uses_the_accepted_explicit_query():
    artifacts = report_model.artifacts(QUERIES)
    tmdl = artifacts["tables/OperationalRecords.tmdl"]
    query = (QUERIES / "OperationalRecords.sql").read_text()
    assert "Sql.Database" in tmdl
    assert "record_id" in query and "data_origin" in query
    assert "SELECT *" not in query.upper()
