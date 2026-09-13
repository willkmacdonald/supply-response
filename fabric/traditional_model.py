"""Focused semantic contracts for traditional operational reporting."""

from __future__ import annotations

TABLE = "OperationalRecords"
COLUMNS = (
    "dataset_id",
    "effective_at",
    "record_id",
    "record_family",
    "supplier_id",
    "supplier_name",
    "part_id",
    "part_name",
    "plant_id",
    "plant_name",
    "source_plant_id",
    "source_plant_name",
    "destination_plant_id",
    "destination_plant_name",
    "customer_id",
    "product_id",
    "production_order_id",
    "customer_order_id",
    "quantity",
    "on_hand",
    "quality_hold",
    "protected_allocation",
    "usable_inventory",
    "component_demand",
    "due_date",
    "original_due_date",
    "dispatch_date",
    "arrival_date",
    "incremental_cost_per_unit",
    "line_revenue",
    "line_margin",
    "status",
    "audit_complete",
    "first_article_complete",
    "expected_decision_date",
    "data_origin",
)
TYPES = {name: "string" for name in COLUMNS}
for name in (
    "quantity",
    "on_hand",
    "quality_hold",
    "protected_allocation",
    "usable_inventory",
    "component_demand",
):
    TYPES[name] = "int64"
for name in ("incremental_cost_per_unit", "line_revenue", "line_margin"):
    TYPES[name] = "decimal"
for name in (
    "effective_at",
    "due_date",
    "original_due_date",
    "dispatch_date",
    "arrival_date",
    "expected_decision_date",
):
    TYPES[name] = "dateTime"
for name in ("audit_complete", "first_article_complete"):
    TYPES[name] = "boolean"


def install_measures(add, external) -> None:
    """Install grain-safe measures through report_model's guarded registry."""
    external(
        "Selected Operational Dataset",
        """VAR SelectedDatasetCount = CALCULATE(DISTINCTCOUNT(OperationalRecords[dataset_id]),
            ALLSELECTED(OperationalRecords))
        RETURN IF(ISFILTERED(OperationalRecords[dataset_id])
        && HASONEFILTER(OperationalRecords[dataset_id])
        && SelectedDatasetCount == 1,
        SELECTEDVALUE(OperationalRecords[dataset_id]))""",
        TABLE,
        destination=TABLE,
    )
    add(
        "Operational Snapshot Context",
        'IF(NOT ISBLANK([Selected Operational Dataset]), "Fictional planning dataset · " & [Selected Operational Dataset] & " · Snapshot " & FORMAT(MAX(OperationalRecords[effective_at]), "MMM d, yyyy HH:mm") & " UTC")',
        table=TABLE,
    )
    add(
        "Operational Quantity Context",
        'IF(ISBLANK([Selected Operational Dataset]), "Select one dataset", IF(ISBLANK(SELECTEDVALUE(OperationalRecords[part_id])), "Select one component to compare material quantities", "Quantities for " & SELECTEDVALUE(OperationalRecords[part_id])))',
        table=TABLE,
    )
    gates = {
        "Operational Row Visible": None,
        "Inventory Row Visible": "inventory",
        "Delivery Row Visible": "shipment",
        "Transfer Row Visible": "transfer",
        "Qualification Row Visible": "qualification",
        "Customer Order Row Visible": "customer_order",
        "Production Demand Row Visible": "production_order",
    }
    for name, family in gates.items():
        family_test = (
            ""
            if family is None
            else f' && SELECTEDVALUE(OperationalRecords[record_family]) == "{family}"'
        )
        add(
            name,
            "INT(NOT ISBLANK([Selected Operational Dataset])" + family_test + ")",
            "int64",
            hidden=True,
            table=TABLE,
        )
    add(
        "Supply Line Row Visible",
        'INT(NOT ISBLANK([Selected Operational Dataset]) && SELECTEDVALUE(OperationalRecords[record_family]) IN {"purchase","shipment"})',
        "int64",
        hidden=True,
        table=TABLE,
    )

    def scoped(name, aggregate, family=None, kind="int64", fmt="#,0"):
        family_filter = (
            ""
            if family is None
            else f', KEEPFILTERS(OperationalRecords[record_family] == "{family}")'
        )
        add(
            name,
            "VAR SelectedDatasetId = [Selected Operational Dataset] "
            "RETURN IF(NOT ISBLANK(SelectedDatasetId), CALCULATE("
            + aggregate
            + ", KEEPFILTERS(TREATAS({SelectedDatasetId}, OperationalRecords[dataset_id]))"
            + family_filter
            + "))",
            kind,
            fmt,
            table=TABLE,
        )

    def unit_scoped(name, aggregate, family):
        add(
            name,
            "VAR SelectedDatasetId = [Selected Operational Dataset] "
            "VAR PartKey = CALCULATE(SELECTEDVALUE(OperationalRecords[part_id]), "
            "KEEPFILTERS(TREATAS({SelectedDatasetId}, OperationalRecords[dataset_id])), "
            + f'KEEPFILTERS(OperationalRecords[record_family] == "{family}")) '
            "RETURN IF(NOT ISBLANK(SelectedDatasetId) && NOT ISBLANK(PartKey), CALCULATE("
            + aggregate
            + ", KEEPFILTERS(TREATAS({SelectedDatasetId}, OperationalRecords[dataset_id])), "
            + f'KEEPFILTERS(OperationalRecords[record_family] == "{family}")))',
            "int64",
            "#,0",
            table=TABLE,
        )

    scoped("Operational Record Count", "COUNTROWS(OperationalRecords)")
    add(
        "Supply Line Count",
        'VAR SelectedDatasetId = [Selected Operational Dataset] RETURN IF(NOT ISBLANK(SelectedDatasetId), CALCULATE(COUNTROWS(OperationalRecords), KEEPFILTERS(TREATAS({SelectedDatasetId}, OperationalRecords[dataset_id])), KEEPFILTERS(OperationalRecords[record_family] IN {"purchase","shipment"})))',
        "int64",
        "#,0",
        table=TABLE,
    )
    scoped("Inventory Position Count", "COUNTROWS(OperationalRecords)", "inventory")
    scoped("Delivery Line Count", "COUNTROWS(OperationalRecords)", "shipment")
    scoped("Transfer Line Count", "COUNTROWS(OperationalRecords)", "transfer")
    scoped(
        "Qualification Record Count", "COUNTROWS(OperationalRecords)", "qualification"
    )
    scoped(
        "Customer Order Line Count", "COUNTROWS(OperationalRecords)", "customer_order"
    )
    scoped(
        "Production Order Count", "COUNTROWS(OperationalRecords)", "production_order"
    )
    unit_scoped(
        "Inventory On Hand Units", "SUM(OperationalRecords[on_hand])", "inventory"
    )
    unit_scoped(
        "Inventory Hold Units", "SUM(OperationalRecords[quality_hold])", "inventory"
    )
    unit_scoped(
        "Inventory Protected Units",
        "SUM(OperationalRecords[protected_allocation])",
        "inventory",
    )
    unit_scoped(
        "Inventory Usable Units",
        "SUM(OperationalRecords[usable_inventory])",
        "inventory",
    )
    unit_scoped("Delivery Units", "SUM(OperationalRecords[quantity])", "shipment")
    add(
        "Delivery Extended Cost",
        """VAR SelectedDatasetId = [Selected Operational Dataset]
        VAR MissingCostInputs = COALESCE(CALCULATE(COUNTROWS(OperationalRecords),
            KEEPFILTERS(TREATAS({SelectedDatasetId}, OperationalRecords[dataset_id])),
            KEEPFILTERS(OperationalRecords[record_family] == "shipment"),
            FILTER(OperationalRecords, ISBLANK(OperationalRecords[quantity])
                || ISBLANK(OperationalRecords[incremental_cost_per_unit]))), 0)
        RETURN IF(NOT ISBLANK(SelectedDatasetId) && MissingCostInputs == 0,
            CALCULATE(SUMX(OperationalRecords,
                OperationalRecords[quantity] * OperationalRecords[incremental_cost_per_unit]),
                KEEPFILTERS(TREATAS({SelectedDatasetId}, OperationalRecords[dataset_id])),
                KEEPFILTERS(OperationalRecords[record_family] == "shipment")))""",
        "decimal",
        "$#,0",
        table=TABLE,
    )
    unit_scoped("Transfer Units", "SUM(OperationalRecords[quantity])", "transfer")
    scoped(
        "Open Customer Revenue",
        "SUM(OperationalRecords[line_revenue])",
        "customer_order",
        "decimal",
        "$#,0",
    )
    scoped(
        "Open Customer Margin",
        "SUM(OperationalRecords[line_margin])",
        "customer_order",
        "decimal",
        "$#,0",
    )
    unit_scoped(
        "Production Component Demand",
        "SUM(OperationalRecords[component_demand])",
        "production_order",
    )
