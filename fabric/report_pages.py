from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
PAGE_SCHEMA = BASE + "page/2.0.0/schema.json"
VISUAL_SCHEMA = BASE + "visualContainer/2.9.0/schema.json"
PAGES_SCHEMA = BASE + "pagesMetadata/1.1.0/schema.json"
ORDER = (
    "command-center",
    "actions-outcomes",
    "supplier-shipment",
    "plant-transfer",
    "supplier-qualification",
    "available-stock",
    "customer-orders",
    "response-options",
)
GREEN, TEAL, AMBER, CREAM, WHITE = "#183E35", "#187D78", "#9A641C", "#F5F3EA", "#FFFFFF"
CC, SR, SO, AO = "CaseCommandCenter", "SavedRecords", "SavedOptions", "ActionOutcomes"


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
    return projection("Column", table, name, name.replace("_", " ").capitalize())


def gate(name):
    return {
        "name": "Locked" + name.replace(" ", ""),
        "field": field("Measure", CC, name),
        "type": "Advanced",
        "howCreated": "User",
        "isHiddenInViewMode": True,
        "isLockedInViewMode": True,
        "filter": {
            "Version": 2,
            "From": [{"Name": "c", "Entity": CC, "Type": 0}],
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


def card(name, title, value, rect, accent=TEAL, size=18):
    v = base_visual(name, "cardVisual", rect, title)
    v["visual"]["query"] = {
        "queryState": {"Data": {"projections": [measure(value, title)]}}
    }
    v["visual"]["objects"] = {
        "value": obj({"fontSize": literal(size), "fontColor": color(GREEN)}, True),
        "label": obj(
            {"show": literal(True), "text": literal(""), "fontSize": literal(12)}, True
        ),
        "outline": obj({"show": literal(False)}, True),
        "padding": obj({"paddingUniform": literal(4)}, True),
        "layout": obj({"paddingUniform": literal(0)}, True),
        "spacing": obj({"verticalSpacing": literal(0)}, True),
        "accentBar": obj(
            {
                "show": literal(True),
                "position": literal("Left"),
                "width": literal(3),
                "color": color(accent),
            },
            True,
        ),
    }
    # Explicit padding/title/value/label heights; leave room for the always-rendered label.
    assert 8 + 18 + 8 + int(size * 1.5 + 0.999) + 18 <= rect[3]
    return v


def table(name, title, entity, names, scope, rect):
    v = base_visual(name, "tableEx", rect, title)
    v["visual"]["query"] = {
        "queryState": {"Values": {"projections": [column(entity, n) for n in names]}}
    }
    v["filterConfig"] = {"filters": [gate(scope)]}
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
        "What can the original supplier still supply?",
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
                "Order lines expected to miss on-time, in-full",
                "Orders Baseline OTIF Display",
            ),
            ("Order lines in this saved plan", "Affected Lines Display"),
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
            "Snapshot used for this analysis · Demo corpus — fictional · Use page tabs to explore this case",
            (24, 682, 1232, 29),
            13,
        ),
    ]


def detail(page):
    title, family, state, metrics, explanation, scope, fields = DETAILS[page]
    items = common(title, state)
    for i, (label, value) in enumerate(metrics):
        items.append(
            card(
                "answer-" + str(i + 1),
                label,
                value,
                (24 + 416 * i, 164, 400, 108),
                (TEAL, GREEN, AMBER)[i],
            )
        )
    items.append(
        card(
            "explanation",
            "What this means for the response",
            explanation,
            (24, 284, 1232, 90),
            size=14,
        )
    )
    supporting = table(
        "supporting-records",
        "Supporting saved records",
        SR,
        fields,
        scope,
        (24, 386, 1232, 166),
    )
    if page == "available-stock":
        visual = supporting["visual"]
        visual["visualType"] = "pivotTable"
        rows = [column(SR, "part_id"), column(SR, "plant_id")]
        visual["query"]["queryState"] = {
            "Rows": {"projections": rows},
            "Values": {
                "projections": [
                    measure("Stock On Hand Row", "On hand"),
                    measure("Stock Held Row", "Quality hold"),
                    measure("Stock Protected Row", "Protected allocation"),
                    measure("Stock Usable Row", "Usable units"),
                ]
            },
        }
        visual["expansionStates"] = [
            {
                "roles": ["Rows"],
                "levels": [
                    {
                        "queryRefs": [item["queryRef"]],
                        "identityKeys": [item["field"]],
                        "isCollapsed": False,
                        "isPinned": True,
                    }
                    for item in rows
                ],
            }
        ]
        objects = visual["objects"]
        del objects["total"]
        objects["rowHeaders"] = obj(
            {
                "stepped": literal(False),
                "repeatRowHeaders": literal(True),
                "showExpandCollapseButtons": literal(False),
                "fontColor": color(GREEN),
                "backColor": color(WHITE),
                "fontSize": literal(11),
            }
        )
        totals = {
            "rowSubtotals": literal(False),
            "columnSubtotals": literal(False),
        }
        objects["subTotals"] = [
            {"properties": totals},
            {"selector": {"id": "Row"}, "properties": totals},
            {"selector": {"id": "Column"}, "properties": totals},
        ]
        objects["columnHeaders"][0]["properties"].update(
            {
                "autoSizeColumnWidth": literal(True),
                "columnAdjustment": literal("growToFit"),
            }
        )
        objects["values"][0]["properties"]["fontColorSecondary"] = color(GREEN)
        visual["visualContainerObjects"]["stylePreset"] = obj({"name": literal("None")})
    elif page == "customer-orders":
        supporting["visual"]["query"]["queryState"]["Values"]["projections"].insert(
            0, projection("Column", SR, "source_record_id", "Order line")
        )
    items.append(supporting)
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
    items = common("Case dashboard", "Overview State")
    rows = (
        (
            "1. Understand\nthe disruption",
            (
                ("active-cases", "What changed?", "Disruption Answer"),
                (
                    "revenue-at-risk",
                    "What do we have available?",
                    "Availability Answer",
                ),
                ("otif-loss", "What does that put at risk?", "Exposure Answer"),
            ),
        ),
        (
            "2. Investigate\nresponses",
            (
                (
                    "scenario-effective-time",
                    "What can the original supplier still supply?",
                    "Shipment Answer",
                ),
                ("showcase-cases", "Can another plant help?", "Transfer Answer"),
                (
                    "qualification-answer",
                    "Can we use the alternate supplier?",
                    "Qualification Answer",
                ),
            ),
        ),
        (
            "3. Make\nthe decision",
            (
                ("options-answer", "Compare the options", "Options Answer"),
                (
                    "recommendation-answer",
                    "Saved recommendation",
                    "Recommendation Answer",
                ),
                ("current-decision", "Recorded decision", "Decision Answer"),
            ),
        ),
    )
    for row, (label, cards) in enumerate(rows):
        y = 166 + row * 170
        items.append(
            text("row-label-" + str(row + 1), label, (24, y + 20, 190, 96), 20)
        )
        for col, (name, question, value) in enumerate(cards):
            items.append(
                card(
                    name,
                    question,
                    value,
                    (226 + col * 348, y, 334, 156),
                    (TEAL, GREEN, AMBER)[row],
                    size=14,
                )
            )
    return "Case dashboard", items, None


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
    items.append(
        table(
            "option-comparison",
            "Saved options — expected results, subject to planning requirements",
            SO,
            (
                "option_name",
                "is_baseline",
                "executable",
                "response_cost",
                "revenue_at_risk",
                "otif_loss_percentage",
                "uncovered_part_demand",
                "blockers_text",
                "required_roles_text",
            ),
            "Option Row Visible",
            (24, 386, 1232, 176),
        )
    )
    items.append(
        table(
            "source-details",
            "Source details — saved option identities",
            SO,
            ("option_name", "option_id") + OPTION_IDS,
            "Option Row Visible",
            (24, 574, 1232, 96),
        )
    )
    return "Response options", items, None


def actions():
    items = common("Current decision: actions and outcomes", "Actions State")
    for i, (name, title, value) in enumerate(
        (
            ("decision-id", "Current governing decision", "Current Decision Display"),
            ("observation-kind", "Observation context", "Current Observation Display"),
            ("scenario-effective-time", "In this scenario, as of", "Scenario Context"),
            ("projection-refresh", "Projection updated", "Projection Updated Display"),
        )
    ):
        items.append(card(name, title, value, (24 + 312 * i, 164, 296, 108), size=14))
    items.append(
        card(
            "action-explanation",
            "Current decision lineage",
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
            ("action_kind", "action_status"),
            "Action Row Visible",
            (24, 386, 604, 176),
        )
    )
    items.append(
        table(
            "source-details",
            "Source details — current action identities",
            AO,
            ("action_kind", "case_key", "decision_key", "action_key"),
            "Action Row Visible",
            (24, 574, 604, 96),
        )
    )
    chart = base_visual(
        "predicted-observed-variance",
        "clusteredColumnChart",
        (644, 386, 612, 284),
        "Observed variance — recorded metrics only",
    )
    chart["visual"]["query"] = {
        "queryState": {
            "Category": {"projections": [column(AO, "metric")]},
            "Series": {"projections": [column(AO, "observation_kind")]},
            "Y": {"projections": [measure("Observed Variance", "Variance", AO)]},
        }
    }
    chart["visual"]["objects"] = {
        "labels": obj({"show": literal(True), "fontSize": literal(11)}),
        "dataPoint": obj({"defaultColor": color(TEAL)}),
        "legend": obj({"show": literal(True), "fontSize": literal(11)}),
        "categoryAxis": obj({"fontSize": literal(11)}),
        "valueAxis": obj({"show": literal(True), "fontSize": literal(11)}),
    }
    chart["filterConfig"] = {"filters": [gate("Observation Row Visible")]}
    items.append(chart)
    return "Actions and outcomes", items, None


def artifacts():
    result = {
        "pages/pages.json": {
            "$schema": PAGES_SCHEMA,
            "pageOrder": list(ORDER),
            "activePageName": ORDER[0],
        }
    }
    for page in ORDER:
        title, items, family = (
            overview()
            if page == ORDER[0]
            else actions()
            if page == ORDER[1]
            else options()
            if page == "response-options"
            else detail(page)
        )
        definition = {
            "$schema": PAGE_SCHEMA,
            "name": page,
            "displayName": title,
            "displayOption": "FitToPage",
            "width": 1280,
            "height": 720,
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
        if family:
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
