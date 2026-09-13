from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
PAGE_SCHEMA = BASE + "page/2.0.0/schema.json"
VISUAL_SCHEMA = BASE + "visualContainer/2.9.0/schema.json"
PAGES_SCHEMA = BASE + "pagesMetadata/1.1.0/schema.json"
LEGACY_ORDER = (
    "command-center",
    "actions-outcomes",
    "supplier-shipment",
    "plant-transfer",
    "supplier-qualification",
    "available-stock",
    "customer-orders",
    "response-options",
)
from fabric.traditional_pages import ORDER as OPERATIONAL_ORDER

ORDER = OPERATIONAL_ORDER + LEGACY_ORDER
WALKTHROUGH = (
    ("command-center", "1. Investigate the delay"),
    ("available-stock", "2. Check available stock"),
    ("customer-orders", "2. Inspect affected order lines"),
    ("supplier-shipment", "3. Check the partial shipment"),
    ("plant-transfer", "3. Check the plant transfer"),
    ("supplier-qualification", "3. Check qualification"),
    ("response-options", "4. Weigh the trade-offs"),
    ("actions-outcomes", "5. Review the decision"),
)
GREEN, TEAL, AMBER, CREAM, WHITE = "#183E35", "#187D78", "#9A641C", "#F5F3EA", "#FFFFFF"
CC, SR, SO, AO = "CaseCommandCenter", "SavedRecords", "SavedOptions", "ActionOutcomes"
OVERVIEW_EXTRA_HEIGHT = 0


def literal(value):
    token = (
        ("true" if value else "false")
        if isinstance(value, bool)
        else (
            str(value) + "D"
            if isinstance(value, (int, float))
            else "'" + value.replace("'", "''") + "'"
        )
    )
    return {"expr": {"Literal": {"Value": token}}}


def color(value):
    return {"solid": {"color": literal(value)}}


def obj(properties, instance=False):
    item = {"properties": properties}
    if instance:
        item["selector"] = {"id": "default"}
    return [item]


def field(kind, table, name, source=False):
    return {
        kind: {
            "Expression": {"SourceRef": {"Source" if source else "Entity": table}},
            "Property": name,
        }
    }


def projection(kind, table, name, label=None):
    result = {
        "field": field(kind, table, name),
        "queryRef": table + "." + name,
        "nativeQueryRef": name,
    }
    if label is not None:
        result["displayName"] = label
    return result


def measure(name, label=None, table=CC):
    return projection("Measure", table, name, label)


def column(table, name):
    labels = {
        "action_display_name": "Action",
        "action_kind": "Action",
        "action_status_display": "Status",
        "action_status": "Status",
        "arrival_date": "Arrival date",
        "audit_complete": "Audit requirement met",
        "blockers_text": "Planning blockers",
        "dispatch_date": "Dispatch date",
        "due_date": "Due date",
        "protected_customer_order_count": "Customer orders protected",
        "uncovered_part_demand": "Parts still needed",
        "executable": "Meets planning requirements",
        "expected_decision_date": "Qualification review date",
        "first_article_complete": "First article requirement met",
        "incremental_cost_per_unit": "Incremental cost per unit",
        "is_baseline": "Do-nothing comparison",
        "observation_kind": "Outcome type",
        "observation_kind_display": "Outcome type",
        "metric_display_name": "Result metric",
        "option_name": "Response option",
        "option_display_name": "Response option",
        "otif_loss_percentage": "Service-target exposure (%)",
        "required_roles_text": "Required review roles",
        "response_cost": "Response cost",
        "revenue_at_risk": "Revenue at risk",
    }
    label = labels.get(name, name.replace("_", " ").capitalize())
    return projection("Column", table, name, label)


def gate(name, table=CC):
    return {
        "name": "Locked" + name.replace(" ", ""),
        "field": field("Measure", table, name),
        "type": "Advanced",
        "howCreated": "User",
        "isHiddenInViewMode": True,
        "isLockedInViewMode": True,
        "filter": {
            "Version": 2,
            "From": [{"Name": "c", "Entity": table, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "Comparison": {
                            "ComparisonKind": 0,
                            "Left": field("Measure", "c", name, True),
                            "Right": {"Literal": {"Value": "1L"}},
                        }
                    }
                }
            ],
        },
    }


def family_filter(family):
    return {
        "name": "LockedRecordFamily",
        "field": field("Column", SR, "record_family"),
        "type": "Categorical",
        "howCreated": "User",
        "isHiddenInViewMode": True,
        "isLockedInViewMode": True,
        "filter": {
            "Version": 2,
            "From": [{"Name": "r", "Entity": SR, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [
                                field("Column", "r", "record_family", True)
                            ],
                            "Values": [[{"Literal": {"Value": "'" + family + "'"}}]],
                        }
                    }
                }
            ],
        },
    }


def categorical_filter(table, column_name, value, name):
    return {
        "name": name,
        "field": field("Column", table, column_name),
        "type": "Categorical",
        "howCreated": "User",
        "isHiddenInViewMode": True,
        "isLockedInViewMode": True,
        "filter": {
            "Version": 2,
            "From": [{"Name": "r", "Entity": table, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [field("Column", "r", column_name, True)],
                            "Values": [[{"Literal": {"Value": "'" + value + "'"}}]],
                        }
                    }
                }
            ],
        },
    }


def base_visual(name, kind, rect, title=None, fill=WHITE):
    x, y, width, height = rect
    vco = {
        "background": obj(
            {"show": literal(True), "color": color(fill), "transparency": literal(0)}
        ),
        "border": obj({"show": literal(False)}),
        "padding": obj({k: literal(4) for k in ("top", "bottom", "left", "right")}),
        "title": obj(
            {
                "show": literal(title is not None),
                "text": literal(title or ""),
                "fontColor": color(GREEN),
                "fontSize": literal(12),
                "fontFamily": literal("Segoe UI"),
                "titleWrap": literal(True),
            }
        ),
    }
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "z": 0,
            "tabOrder": 0,
        },
        "visual": {"visualType": kind, "visualContainerObjects": vco},
    }


def text(name, value, rect, size=20, fill=CREAM, ink=GREEN):
    v = base_visual(name, "textbox", rect, fill=fill)
    v["visual"]["objects"] = {
        "general": obj(
            {
                "paragraphs": [
                    {
                        "textRuns": [
                            {
                                "value": value,
                                "textStyle": {
                                    "fontFamily": "Segoe UI",
                                    "fontSize": str(size) + "px",
                                    "color": ink,
                                },
                            }
                        ],
                        "horizontalTextAlignment": "left",
                    }
                ]
            }
        )
    }
    return v


def navigation_button(name, label, rect, destination):
    if destination not in ORDER:
        raise ValueError("Unknown walkthrough page: " + destination)
    visual = base_visual(name, "actionButton", rect, fill=CREAM)
    visual["visual"]["objects"] = {
        "text": [
            {"properties": {"show": literal(True)}},
            {
                "selector": {"id": "default"},
                "properties": {
                    "text": literal(label),
                    "fontFamily": literal("Segoe UI"),
                    "fontSize": literal(14),
                    "fontColor": color(WHITE),
                },
            },
        ],
        "fill": [
            {"properties": {"show": literal(True)}},
            {
                "selector": {"id": "default"},
                "properties": {
                    "fillColor": color(GREEN),
                    "transparency": literal(0),
                },
            },
            {
                "selector": {"id": "hover"},
                "properties": {
                    "fillColor": color(TEAL),
                    "transparency": literal(0),
                },
            },
        ],
        "outline": [
            {"properties": {"show": literal(False)}},
            {
                "selector": {"id": "default"},
                "properties": {"show": literal(False)},
            },
        ],
    }
    visual["visual"]["visualContainerObjects"]["visualLink"] = obj(
        {
            "show": literal(True),
            "type": literal("PageNavigation"),
            "navigationSection": literal(destination),
        }
    )
    visual["visual"]["visualContainerObjects"]["general"] = obj(
        {"altText": literal(label)}
    )
    return visual


def walkthrough_controls(page):
    sequence = tuple(name for name, title in WALKTHROUGH)
    index = sequence.index(page)
    y = 714 + (OVERVIEW_EXTRA_HEIGHT if page == "command-center" else 0)
    items = [text("walkthrough-step", WALKTHROUGH[index][1], (24, y, 768, 44), 18)]
    if index > 0:
        items.append(
            navigation_button(
                "walkthrough-previous",
                "Previous",
                (800, y, 220, 44),
                sequence[index - 1],
            )
        )
    if index + 1 < len(sequence):
        items.append(
            navigation_button(
                "walkthrough-next",
                "Next",
                (1036, y, 220, 44),
                sequence[index + 1],
            )
        )
    return items


def card(name, title, value, rect, accent=TEAL, size=14, table=CC):
    # Native card callouts truncate string measures even with textWrap enabled.
    # Microsoft's textbox authoring contract pairs a paragraph run selector with
    # objects.values[].properties.expr; bind the existing measure unchanged.
    # https://github.com/microsoft/skills-for-fabric/blob/main/plugins/powerbi-authoring/skills/powerbi-report-authoring/references/textbox.md
    v = base_visual(name, "textbox", rect, title)
    selector = {"id": "Narrative"}
    v["visual"]["objects"] = {
        "general": obj(
            {
                "paragraphs": [
                    {
                        "textRuns": [
                            {
                                "value": {
                                    "propertyIdentifier": {
                                        "objectName": "values",
                                        "propertyName": "expr",
                                    },
                                    "selector": selector,
                                },
                                "textStyle": {
                                    "fontFamily": "Segoe UI",
                                    "fontSize": str(size) + "pt",
                                    "fontWeight": "normal",
                                    "color": GREEN,
                                },
                            }
                        ],
                        "horizontalTextAlignment": "left",
                    }
                ]
            }
        ),
        "values": [
            {
                "properties": {"expr": {"expr": field("Measure", table, value)}},
                "selector": selector,
            }
        ],
    }
    # Retain each row's accent in the visible heading using container formatting.
    v["visual"]["visualContainerObjects"]["title"][0]["properties"]["fontColor"] = (
        color(accent)
    )
    # Space for a title and two body lines is a floor, not native rendering proof.
    assert rect[3] >= 90
    return v


def table(name, title, entity, names, scope, rect, scope_table=CC):
    v = base_visual(name, "tableEx", rect, title)
    v["visual"]["query"] = {
        "queryState": {"Values": {"projections": [column(entity, n) for n in names]}}
    }
    v["filterConfig"] = {"filters": [gate(scope, scope_table)]}
    v["visual"]["objects"] = {
        "columnHeaders": obj(
            {
                "fontColor": color(WHITE),
                "backColor": color(GREEN),
                "fontSize": literal(11),
            }
        ),
        "values": obj(
            {
                "fontColorPrimary": color(GREEN),
                "backColorPrimary": color(WHITE),
                "backColorSecondary": color(CREAM),
                "fontSize": literal(11),
            }
        ),
        "total": obj({"totals": literal(False)}),
        "grid": obj({"rowPadding": literal(5)}),
    }
    return v


RECORD_IDS = ("case_key", "analysis_key", "record_key", "record_family")
OPTION_IDS = ("case_key", "analysis_key", "option_key")
DETAILS = {
    "supplier-shipment": (
        "What can Supplier Alpha still supply?",
        "shipment",
        "Record State",
        (
            ("Scheduled quantity", "Record Quantity Display"),
            ("Scheduled receipt", "Record Due Date Display"),
            ("Incremental cost per unit", "Record Unit Cost Display"),
        ),
        "Record Explanation",
        "Record Row Visible",
        (
            "supplier_id",
            "part_id",
            "plant_id",
            "quantity",
            "due_date",
            "incremental_cost_per_unit",
        ),
    ),
    "plant-transfer": (
        "Can another plant help?",
        "transfer",
        "Record State",
        (
            ("Transfer quantity", "Record Quantity Display"),
            ("Arrival date", "Record Arrival Date Display"),
            ("Incremental cost per unit", "Record Unit Cost Display"),
        ),
        "Record Explanation",
        "Record Row Visible",
        (
            "source_plant_id",
            "destination_plant_id",
            "part_id",
            "quantity",
            "dispatch_date",
            "arrival_date",
            "incremental_cost_per_unit",
        ),
    ),
    "supplier-qualification": (
        "Can we use the alternate supplier?",
        "qualification",
        "Record State",
        (
            ("Qualification status", "Record Status Display"),
            ("Audit requirement", "Record Audit Display"),
            ("First article requirement", "Record First Article Display"),
        ),
        "Record Explanation",
        "Record Row Visible",
        (
            "supplier_id",
            "part_id",
            "status",
            "audit_complete",
            "first_article_complete",
            "expected_decision_date",
        ),
    ),
    "available-stock": (
        "What do we have available?",
        None,
        "Stock State",
        (
            ("Usable component units", "Stock Usable Display"),
            ("Units on quality hold", "Stock Held Display"),
            ("Protected allocation", "Stock Protected Display"),
        ),
        "Stock Explanation",
        "Stock Row Visible",
        (
            "part_id",
            "plant_id",
            "on_hand",
            "quality_hold",
            "protected_allocation",
            "usable_inventory",
        ),
    ),
    "customer-orders": (
        "What does that put at risk?",
        None,
        "Orders State",
        (
            ("Revenue at risk — without a response", "Orders Baseline Revenue Display"),
            (
                "Production orders expected to miss on-time, in-full",
                "Orders Baseline OTIF Display",
            ),
            ("Order lines in this analysis", "Affected Lines Display"),
        ),
        "Orders Explanation",
        "Order Row Visible",
        (
            "customer_order_id",
            "product_id",
            "plant_id",
            "quantity",
            "due_date",
            "line_revenue",
        ),
    ),
}


def case_selector():
    v = base_visual("case-selector", "slicer", (952, 62, 304, 90))
    v["visual"]["query"] = {
        "queryState": {"Values": {"projections": [column(CC, "case_id")]}}
    }
    v["visual"]["syncGroup"] = {
        "groupName": "SupplyResponseCase",
        "fieldChanges": True,
        "filterChanges": True,
    }
    v["visual"]["visualContainerObjects"]["padding"] = obj(
        {k: literal(8) for k in ("top", "bottom", "left", "right")}
    )
    v["visual"]["objects"] = {
        "data": obj({"mode": literal("Dropdown")}),
        "selection": obj(
            {
                "singleSelect": literal(True),
                "strictSingleSelect": literal(False),
                "selectAllCheckboxEnabled": literal(False),
            }
        ),
        "header": obj(
            {
                "show": literal(True),
                "text": literal("Select a case"),
                "textSize": literal(11),
                "fontColor": color(GREEN),
            }
        ),
        "items": obj({"textSize": literal(11), "fontColor": color(GREEN)}),
    }
    return v


def common(title, state):
    if state == "Record State":
        # Record State expands several DirectQuery identity/provenance measures and
        # takes about a minute in the service. The exact row and source-detail
        # visuals below retain the record identity; this header binds the faster
        # saved-analysis snapshot context.
        state = "Snapshot Context"
    return [
        text("page-title", title, (24, 12, 1232, 49), 26),
        card(
            "selection-state",
            "Selected case and analysis",
            state,
            (24, 62, 916, 90),
            size=14,
        ),
        case_selector(),
        text(
            "fictional-footer",
            "Snapshot used for this analysis · Demo corpus — fictional · Return to the existing demo tab for original messages and AI assistance.",
            (24, 770, 1232, 30),
            13,
        ),
    ]


def detail(page):
    title, family, state, _metrics, _explanation, scope, fields = DETAILS[page]
    items = common(title, state)
    supporting = table(
        "supporting-records",
        "Contributing rows from the selected saved snapshot",
        SR,
        fields,
        scope,
        (24, 164, 800, 388),
    )
    if page == "customer-orders":
        supporting["visual"]["query"]["queryState"]["Values"]["projections"].insert(
            0, projection("Column", SR, "source_record_id", "Order line")
        )
    items.append(supporting)
    chart_spec = {
        "available-stock": ("plant_id", "Stock Usable Row", "Usable stock by plant"),
        "supplier-shipment": (
            "supplier_id",
            "Record quantity",
            "Shipment quantity by supplier",
        ),
        "plant-transfer": (
            "destination_plant_id",
            "Record quantity",
            "Transfer quantity by destination",
        ),
        "supplier-qualification": (
            "supplier_id",
            "Record Row Visible",
            "Qualification records by supplier",
        ),
        "customer-orders": (
            "source_record_id",
            "Affected Revenue Row",
            "Affected value by saved order line",
        ),
    }
    category, value, chart_title = chart_spec[page]
    chart = base_visual(
        "saved-detail-chart", "clusteredColumnChart", (840, 164, 416, 388), chart_title
    )
    category_projection = column(SR, category)
    category_projection["active"] = True
    chart["visual"]["query"] = {
        "queryState": {
            "Category": {"projections": [category_projection]},
            "Y": {"projections": [measure(value, table=CC)]},
        }
    }
    chart["visual"]["objects"] = {
        "labels": obj({"show": literal(True), "fontSize": literal(10)}),
        "dataPoint": obj({"defaultColor": color(TEAL)}),
        "categoryAxis": obj({"fontSize": literal(10)}),
        "valueAxis": obj({"show": literal(True), "fontSize": literal(10)}),
    }
    chart["filterConfig"] = {"filters": [gate(scope)]}
    items.append(chart)
    items.append(
        table(
            "source-details",
            "Source details — identifiers retain their original values",
            SR,
            (
                "source_record_id",
                "case_id",
                "analysis_id",
                "analysis_created_at",
                "source_timestamp",
                "retrieved_at",
                "evidence_state",
            )
            + RECORD_IDS,
            scope,
            (24, 564, 1232, 106),
        )
    )
    return title, items, family


def overview():
    items = common("Saved case snapshot", "Overview State")
    items.append(
        table(
            "saved-inventory-rows",
            "Saved inventory contributing rows",
            SR,
            (
                "part_id",
                "plant_id",
                "on_hand",
                "quality_hold",
                "protected_allocation",
                "usable_inventory",
            ),
            "Stock Row Visible",
            (24, 164, 608, 388),
        )
    )
    order_rows = table(
        "saved-order-rows",
        "Saved customer-order contributing rows",
        SR,
        (
            "customer_order_id",
            "product_id",
            "part_id",
            "plant_id",
            "quantity",
            "due_date",
            "line_revenue",
        ),
        "Order Row Visible",
        (648, 164, 608, 388),
    )
    order_rows["visual"]["query"]["queryState"]["Values"]["projections"].insert(
        0, projection("Column", SR, "source_record_id", "Order line")
    )
    items.append(order_rows)
    return "Saved case snapshot", items, None


def options():
    items = common("Compare the response options", "Options State")
    for i, (title, value) in enumerate(
        (
            ("Selected option", "Selected Option Display"),
            ("Expected revenue at risk", "Option Revenue Display"),
            ("Response cost", "Option Cost Display"),
        )
    ):
        items.append(
            card("option-answer-" + str(i), title, value, (24 + 416 * i, 164, 400, 108))
        )
    items.append(
        card(
            "option-explanation",
            "Expected if we take this option",
            "Options Explanation",
            (24, 284, 1232, 90),
            size=14,
        )
    )
    comparison = table(
        "option-comparison",
        "Response options — expected results, subject to planning requirements",
        SO,
        (
            "option_display_name",
            "is_baseline",
            "executable",
            "response_cost",
            "revenue_at_risk",
            "otif_loss_percentage",
            "uncovered_part_demand",
            "protected_customer_order_count",
            "blockers_text",
            "required_roles_text",
        ),
        "Option Row Visible",
        (24, 386, 1232, 176),
    )
    comparison["visual"]["query"]["sortDefinition"] = {
        "sort": [
            {
                "field": field("Column", SO, "option_display_name"),
                "direction": "Ascending",
            }
        ],
        "isDefaultSort": False,
    }
    items.append(comparison)
    items.append(
        table(
            "source-details",
            "Source details — saved option identities",
            SO,
            (
                "option_name",
                "option_kind",
                "blocking_codes_text",
                "prerequisite_roles_text",
                "option_id",
            )
            + OPTION_IDS,
            "Option Row Visible",
            (24, 574, 1232, 96),
        )
    )
    return "Response options", items, None


def actions():
    items = common("Current decision: actions and outcomes", "Actions State")
    for i, (name, title, value) in enumerate(
        (
            ("decision-id", "Current decision", "Current Decision Display"),
            ("observation-kind", "Observation context", "Current Observation Display"),
            ("scenario-effective-time", "In this scenario, as of", "Scenario Context"),
            ("projection-refresh", "Report data updated", "Projection Updated Display"),
        )
    ):
        items.append(card(name, title, value, (24 + 312 * i, 164, 296, 108), size=14))
    items.append(
        card(
            "action-explanation",
            "Decision and outcome context",
            "Action Explanation",
            (24, 284, 1232, 90),
            size=14,
        )
    )
    items.append(
        table(
            "action-status",
            "Current actions",
            AO,
            ("action_display_name", "action_status_display"),
            "Action Row Visible",
            (24, 386, 604, 176),
        )
    )
    items.append(
        table(
            "source-details",
            "Source details — current action identities",
            AO,
            (
                "action_kind",
                "action_status",
                "case_key",
                "decision_key",
                "action_key",
            ),
            "Action Row Visible",
            (24, 574, 604, 96),
        )
    )
    # Both display fields include case/decision GroupByColumns. Put them on one
    # table axis: separate chart Category/Series axes overlap those identity keys
    # and fail in Power BI before the visibility measure can filter empty data.
    variance_table = table(
        "predicted-observed-variance",
        "Observed variance — recorded metrics only",
        AO,
        ("metric_display_name", "observation_kind_display"),
        "Observation Row Visible",
        (644, 386, 612, 176),
    )
    variance_table["visual"]["query"]["queryState"]["Values"]["projections"].append(
        measure("Observed Variance", "Variance", AO)
    )
    items.append(variance_table)
    items.append(
        table(
            "outcome-source-details",
            "Source details — recorded outcome identities",
            AO,
            ("metric", "observation_kind", "case_key", "decision_key", "action_key"),
            "Observation Row Visible",
            (644, 574, 612, 96),
        )
    )
    return "Actions and outcomes", items, None


def artifacts():
    from fabric import traditional_pages

    result = {
        "pages/pages.json": {
            "$schema": PAGES_SCHEMA,
            "pageOrder": list(ORDER),
            "activePageName": ORDER[0],
        }
    }
    for page in ORDER:
        title, items, family = (
            traditional_pages.page(page, __import__(__name__, fromlist=["*"]))
            if page in OPERATIONAL_ORDER
            else overview()
            if page == "command-center"
            else actions()
            if page == "actions-outcomes"
            else options()
            if page == "response-options"
            else detail(page)
        )
        if page not in OPERATIONAL_ORDER:
            items.extend(walkthrough_controls(page))
        definition = {
            "$schema": PAGE_SCHEMA,
            "name": page,
            "displayName": title,
            "displayOption": "FitToPage",
            "width": 1280,
            "height": 720 if page in OPERATIONAL_ORDER else 808,
            "objects": {
                "background": obj({"color": color(CREAM), "transparency": literal(0)}),
                "pageRefresh": [
                    {
                        "properties": {
                            "show": True,
                            "refreshType": "FixedInterval",
                            "duration": 30,
                        }
                    }
                ],
            },
        }
        if page in LEGACY_ORDER:
            definition["visibility"] = "HiddenInViewMode"
        if page in OPERATIONAL_ORDER:
            filters = [
                traditional_pages.dataset_filter(__import__(__name__, fromlist=["*"]))
            ]
            if family:
                filters.append(
                    categorical_filter(
                        "OperationalRecords",
                        "record_family",
                        family,
                        "LockedOperationalFamily",
                    )
                )
            definition["filterConfig"] = {"filters": filters}
        elif family:
            definition["filterConfig"] = {"filters": [family_filter(family)]}
        for filter_item in definition.get("filterConfig", {}).get("filters", []):
            filter_item["name"] = page + "-" + filter_item["name"]
        result[f"pages/{page}/page.json"] = definition
        for order, visual in enumerate(
            sorted(items, key=lambda v: (v["position"]["y"], v["position"]["x"]))
        ):
            visual["position"].update(z=order, tabOrder=order)
            for filter_item in visual.get("filterConfig", {}).get("filters", []):
                filter_item["name"] = (
                    page + "-" + visual["name"] + "-" + filter_item["name"]
                )
            result[f"pages/{page}/visuals/{visual['name']}/visual.json"] = visual
    return result


def required_fields():
    found = set()

    def visit(value):
        if isinstance(value, dict):
            for kind in ("Column", "Measure"):
                binding = value.get(kind)
                if isinstance(binding, dict):
                    entity = (
                        binding.get("Expression", {}).get("SourceRef", {}).get("Entity")
                    )
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


def check_output_paths(definition, expected):
    for directory in (definition, *definition.parents):
        if directory.is_symlink():
            raise ValueError("Refusing symbolic-link output path")
        if directory.exists() and not directory.is_dir():
            raise ValueError("Report parent is not a directory")
    expected_dirs = {
        parent.as_posix()
        for name in expected
        for parent in Path(name).parents
        if parent.as_posix() != "."
    }
    for relative in expected:
        target = definition / relative
        if target.is_symlink():
            raise ValueError("Refusing symbolic-link output path")
        if target.exists() and not target.is_file():
            raise ValueError("Report file target is not a file")
        for directory in target.parents:
            if directory.is_symlink():
                raise ValueError("Refusing symbolic-link output path")
            if directory.exists() and not directory.is_dir():
                raise ValueError("Report parent is not a directory")
            if directory == definition:
                break
    pages = definition / "pages"
    if pages.exists():
        for path in pages.rglob("*"):
            relative = path.relative_to(definition).as_posix()
            if path.is_symlink():
                raise ValueError("Refusing symbolic-link output path")
            if path.is_file() and relative in expected:
                continue
            if path.is_dir() and relative in expected_dirs:
                continue
            raise ValueError("Unexpected existing report page path: " + relative)


def verify(definition):
    expected = artifacts()
    check_output_paths(definition, expected)
    if definition.is_symlink() or (definition / "pages").is_symlink():
        raise ValueError("Report definition and pages roots must not be symbolic links")
    paths = list((definition / "pages").rglob("*"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("Report artifacts must not contain symbolic links")
    actual = {p.relative_to(definition).as_posix() for p in paths if p.is_file()}
    if actual != set(expected):
        raise ValueError(
            "Report page file inventory differs from the approved generator"
        )
    expected_dirs = {
        parent.as_posix()
        for name in expected
        for parent in Path(name).parents
        if parent.as_posix() not in {".", "pages"}
    }
    actual_dirs = {p.relative_to(definition).as_posix() for p in paths if p.is_dir()}
    if actual_dirs != expected_dirs:
        raise ValueError(
            "Report page directory inventory differs from the approved generator"
        )
    for path, value in expected.items():
        if (definition / path).read_text(encoding="utf-8") != encoded(value):
            raise ValueError(
                "Report artifact differs from approved generation: " + path
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("definition", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verify(args.definition)
        return
    expected = artifacts()
    check_output_paths(args.definition, expected)
    # No deletion: unexpected pre-existing files require explicit reviewed migration.
    for relative, value in expected.items():
        path = args.definition / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded(value), encoding="utf-8")
    verify(args.definition)


if __name__ == "__main__":
    main()
