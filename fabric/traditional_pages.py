"""Native PBIR pages for broad traditional operational investigation."""

from __future__ import annotations

TABLE = "OperationalRecords"
ORDER = (
    "operations-overview",
    "operations-inventory",
    "operations-deliveries",
    "operations-transfers",
    "operations-qualification",
    "operations-orders",
    "operations-demand",
)
DATASET_ID = "TRADITIONAL-OPS-2026-09-V1"
DATE_FIELDS = {
    "operations-overview": "due_date",
    "operations-inventory": "effective_at",
    "operations-deliveries": "due_date",
    "operations-transfers": "arrival_date",
    "operations-qualification": "expected_decision_date",
    "operations-orders": "due_date",
    "operations-demand": "due_date",
}

PAGES = {
    "operations-overview": (
        "Supply overview",
        None,
        (
            "record_family",
            "status",
            "part_id",
            "part_name",
            "plant_name",
            "supplier_name",
            "quantity",
            "due_date",
            "data_origin",
        ),
        "due_date",
        "Open Customer Revenue",
    ),
    "operations-inventory": (
        "Inventory",
        "inventory",
        (
            "part_id",
            "part_name",
            "plant_name",
            "on_hand",
            "quality_hold",
            "protected_allocation",
            "usable_inventory",
            "status",
            "data_origin",
        ),
        "part_id",
        "Inventory Usable Units",
    ),
    "operations-deliveries": (
        "Supplier deliveries",
        "supply",
        (
            "record_family",
            "record_id",
            "supplier_name",
            "part_id",
            "plant_name",
            "quantity",
            "original_due_date",
            "due_date",
            "dispatch_date",
            "arrival_date",
            "incremental_cost_per_unit",
            "status",
            "data_origin",
        ),
        "supplier_name",
        "Supply Line Count",
    ),
    "operations-transfers": (
        "Plant transfers",
        "transfer",
        (
            "record_id",
            "part_id",
            "source_plant_name",
            "destination_plant_name",
            "quantity",
            "dispatch_date",
            "arrival_date",
            "incremental_cost_per_unit",
            "status",
            "data_origin",
        ),
        "source_plant_name",
        "Transfer Line Count",
    ),
    "operations-qualification": (
        "Supplier qualification",
        "qualification",
        (
            "record_id",
            "supplier_name",
            "part_id",
            "status",
            "audit_complete",
            "first_article_complete",
            "expected_decision_date",
            "data_origin",
        ),
        "supplier_name",
        "Qualification Record Count",
    ),
    "operations-orders": (
        "Customer orders",
        "customer_order",
        (
            "customer_order_id",
            "customer_id",
            "product_id",
            "part_id",
            "plant_name",
            "quantity",
            "due_date",
            "line_revenue",
            "line_margin",
            "status",
            "data_origin",
        ),
        "customer_id",
        "Open Customer Revenue",
    ),
    "operations-demand": (
        "Production demand",
        "production_order",
        (
            "production_order_id",
            "product_id",
            "part_id",
            "plant_name",
            "quantity",
            "component_demand",
            "due_date",
            "status",
            "data_origin",
        ),
        "part_id",
        "Production Component Demand",
    ),
}


def _slicer(rp, name, label, field_name, rect, *, single=False):
    visual = rp.base_visual(name, "slicer", rect)
    projection = rp.column(TABLE, field_name)
    projection["active"] = True
    visual["visual"]["query"] = {
        "queryState": {"Values": {"projections": [projection]}}
    }
    visual["visual"]["objects"] = {
        "data": rp.obj({"mode": rp.literal("Dropdown")}),
        "selection": rp.obj(
            {
                "singleSelect": rp.literal(single),
                "strictSingleSelect": rp.literal(single),
                "selectAllCheckboxEnabled": rp.literal(not single),
            }
        ),
        "header": rp.obj(
            {
                "show": rp.literal(True),
                "text": rp.literal(label),
                "textSize": rp.literal(11),
                "fontColor": rp.color(rp.GREEN),
            }
        ),
        "items": rp.obj({"textSize": rp.literal(10), "fontColor": rp.color(rp.GREEN)}),
    }
    return visual


def _chart(rp, category, measure_name, title, scope):
    visual = rp.base_visual(
        "operational-chart", "clusteredColumnChart", (824, 166, 432, 456), title
    )
    category_projection = rp.column(TABLE, category)
    category_projection["active"] = True
    visual["visual"]["query"] = {
        "queryState": {
            "Category": {"projections": [category_projection]},
            "Y": {"projections": [rp.measure(measure_name, table=TABLE)]},
        }
    }
    visual["visual"]["objects"] = {
        "labels": rp.obj({"show": rp.literal(True), "fontSize": rp.literal(10)}),
        "dataPoint": rp.obj({"defaultColor": rp.color(rp.TEAL)}),
        "categoryAxis": rp.obj({"fontSize": rp.literal(10)}),
        "valueAxis": rp.obj({"show": rp.literal(True), "fontSize": rp.literal(10)}),
    }
    visual["filterConfig"] = {"filters": [rp.gate(scope, TABLE)]}
    return visual


def dataset_filter(rp):
    return rp.categorical_filter(
        TABLE, "dataset_id", DATASET_ID, "LockedOperationalDataset"
    )


def page(page_id, rp):
    title, family, fields, category, measure_name = PAGES[page_id]
    scope = {
        None: "Operational Row Visible",
        "inventory": "Inventory Row Visible",
        "shipment": "Delivery Row Visible",
        "transfer": "Transfer Row Visible",
        "qualification": "Qualification Row Visible",
        "customer_order": "Customer Order Row Visible",
        "production_order": "Production Demand Row Visible",
        "supply": "Supply Line Row Visible",
    }[family]
    route_slicers = (
        (
            _slicer(
                rp,
                "source-plant-filter",
                "Source plant",
                "source_plant_name",
                (272, 62, 232, 86),
            ),
            _slicer(
                rp,
                "destination-plant-filter",
                "Destination plant",
                "destination_plant_name",
                (520, 62, 232, 86),
            ),
        )
        if page_id == "operations-transfers"
        else (
            _slicer(rp, "plant-filter", "Plant", "plant_name", (272, 62, 232, 86)),
            _slicer(
                rp, "supplier-filter", "Supplier", "supplier_name", (768, 62, 232, 86)
            ),
        )
    )
    items = [
        rp.text("page-title", title, (24, 12, 1232, 49), 25),
        _slicer(
            rp,
            "dataset-filter",
            "Snapshot",
            "dataset_id",
            (24, 62, 232, 86),
            single=True,
        ),
        *route_slicers,
        _slicer(
            rp,
            "component-filter",
            "Component",
            "part_id",
            (520 if page_id != "operations-transfers" else 768, 62, 232, 86),
        ),
        _slicer(
            rp,
            "date-filter",
            "Operational date",
            DATE_FIELDS[page_id],
            (1016, 62, 240, 86),
        ),
        rp.table(
            "operational-rows",
            title + " — operational rows",
            TABLE,
            fields,
            scope,
            (24, 166, 784, 456),
            scope_table=TABLE,
        ),
        _chart(rp, category, measure_name, title + " — filtered view", scope),
        rp.card(
            "snapshot-context",
            "Selected fictional snapshot",
            "Operational Snapshot Context",
            (24, 622, 760, 90),
            size=14,
            table=TABLE,
        ),
    ]
    index = ORDER.index(page_id)
    if index:
        items.append(
            rp.navigation_button(
                "operations-previous", "Previous", (824, 668, 200, 44), ORDER[index - 1]
            )
        )
    if index + 1 < len(ORDER):
        items.append(
            rp.navigation_button(
                "operations-next", "Next", (1056, 668, 200, 44), ORDER[index + 1]
            )
        )
    return title, items, None if family == "supply" else family
