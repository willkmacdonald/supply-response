from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

CC, SA, SR, SO, AO = (
    "CaseCommandCenter",
    "SavedAnalyses",
    "SavedRecords",
    "SavedOptions",
    "ActionOutcomes",
)
TABLES = (CC, AO, SA, SR, SO)
COLUMNS = {
    CC: [
        "case_id",
        "purpose",
        "status",
        "runtime_mode",
        "walkthrough_route",
        "scenario_effective_time",
        "current_analysis_id",
        "current_decision_id",
        "analysis_created_at",
        "snapshot_state",
        "recommended_option_id",
        "baseline_option_id",
        "decision_kind",
        "decision_analysis_id",
        "decided_at",
        "approved_option_id",
        "baseline_revenue_at_risk",
        "baseline_otif_loss_percentage",
        "baseline_uncovered_part_demand",
        "baseline_response_cost",
        "recommended_revenue_at_risk",
        "recommended_otif_loss_percentage",
        "recommended_uncovered_part_demand",
        "recommended_response_cost",
        "approved_revenue_at_risk",
        "approved_otif_loss_percentage",
        "approved_uncovered_part_demand",
        "approved_response_cost",
        "case_key",
        "current_analysis_key",
        "current_decision_key",
        "decision_analysis_key",
        "approved_option_key",
    ],
    SA: [
        "case_id",
        "analysis_id",
        "runtime_mode",
        "analysis_started_at",
        "retrieval_window_ends_at",
        "analysis_created_at",
        "scenario_effective_time",
        "calculation_version",
        "recommended_option_id",
        "payload_state",
        "snapshot_state",
        "inventory_complete",
        "production_orders_complete",
        "customer_orders_complete",
        "case_key",
        "analysis_key",
        "recommended_option_key",
    ],
    SO: [
        "case_id",
        "analysis_id",
        "option_id",
        "option_kind",
        "option_name",
        "is_baseline",
        "is_recommended",
        "executable",
        "active_mitigation",
        "uncovered_part_demand",
        "otif_loss_percentage",
        "revenue_at_risk",
        "margin_at_risk",
        "response_cost",
        "blockers_text",
        "required_roles_text",
        "assumptions_text",
        "protected_customer_order_count",
        "case_key",
        "analysis_key",
        "option_key",
    ],
    AO: [
        "case_id",
        "decision_id",
        "selected_option_id",
        "record_type",
        "action_id",
        "action_kind",
        "action_status",
        "metric",
        "predicted_value",
        "observed_value",
        "unit",
        "observation_kind",
        "scenario_effective_time",
        "projection_updated_at",
        "case_key",
        "decision_key",
        "action_key",
    ],
    SR: [
        "case_id",
        "analysis_id",
        "record_family",
        "source_record_id",
        "runtime_mode",
        "analysis_created_at",
        "scenario_effective_time",
        "record_state",
        "supplier_id",
        "part_id",
        "plant_id",
        "source_plant_id",
        "destination_plant_id",
        "product_id",
        "customer_id",
        "production_order_id",
        "customer_order_id",
        "po_line_id",
        "quantity",
        "due_date",
        "dispatch_date",
        "arrival_date",
        "incremental_cost_per_unit",
        "status",
        "evidence_ref",
        "audit_complete",
        "first_article_complete",
        "effective_date",
        "expected_decision_date",
        "on_hand",
        "quality_hold",
        "protected_allocation",
        "usable_inventory",
        "component_demand",
        "customer_priority",
        "customer_revenue",
        "customer_margin",
        "unit_revenue",
        "unit_margin",
        "line_revenue",
        "original_quantity",
        "partial_quantity",
        "original_due_date",
        "partial_due_date",
        "recovery_date",
        "source_ref",
        "evidence_state",
        "provenance",
        "evidence_id",
        "source_id",
        "source_system",
        "synthetic",
        "source_timestamp",
        "retrieved_at",
        "case_key",
        "analysis_key",
        "record_key",
        "part_key",
        "plant_key",
        "product_key",
        "source_plant_key",
        "destination_plant_key",
        "production_order_key",
        "in_disruption_scope",
    ],
}
EXCEPTIONS = {
    CC: {
        "dateTime": "scenario_effective_time analysis_created_at decided_at",
        "int64": "baseline_otif_loss_percentage baseline_uncovered_part_demand recommended_otif_loss_percentage recommended_uncovered_part_demand approved_otif_loss_percentage approved_uncovered_part_demand",
        "decimal": "baseline_revenue_at_risk baseline_response_cost recommended_revenue_at_risk recommended_response_cost approved_revenue_at_risk approved_response_cost",
    },
    SA: {
        "dateTime": "analysis_started_at retrieval_window_ends_at analysis_created_at scenario_effective_time",
        "boolean": "inventory_complete production_orders_complete customer_orders_complete",
    },
    SO: {
        "boolean": "is_baseline is_recommended executable active_mitigation",
        "int64": "uncovered_part_demand otif_loss_percentage protected_customer_order_count",
        "decimal": "revenue_at_risk margin_at_risk response_cost",
    },
    AO: {"dateTime": "scenario_effective_time projection_updated_at"},
    SR: {
        "dateTime": "analysis_created_at scenario_effective_time due_date dispatch_date arrival_date effective_date expected_decision_date original_due_date partial_due_date recovery_date source_timestamp retrieved_at",
        "boolean": "audit_complete first_article_complete synthetic in_disruption_scope",
        "int64": "quantity on_hand quality_hold protected_allocation usable_inventory component_demand customer_priority original_quantity partial_quantity",
        "decimal": "incremental_cost_per_unit customer_revenue customer_margin unit_revenue unit_margin line_revenue",
    },
}
TYPES = {t: {c: "string" for c in COLUMNS[t]} for t in TABLES}
for _table, _groups in EXCEPTIONS.items():
    for _type, _names in _groups.items():
        for _column in _names.split():
            assert _column in TYPES[_table]
            TYPES[_table][_column] = _type
DATE_ONLY = {
    "due_date",
    "dispatch_date",
    "arrival_date",
    "effective_date",
    "expected_decision_date",
    "original_due_date",
    "partial_due_date",
    "recovery_date",
}


def column_format(table, name):
    kind = TYPES[table][name]
    if kind == "dateTime":
        return "MMM d, yyyy" if name in DATE_ONLY else 'MMM d, yyyy HH:mm "UTC"'
    if kind == "decimal":
        return "#,0.00"
    if kind == "int64":
        return '0"%"' if name.endswith("otif_loss_percentage") else "#,0"
    return None


def col(table, name):
    return table + "[" + name + "]"


def lit(value):
    return '"' + value.replace('"', '""') + '"'


def calc(expression, filters):
    return "CALCULATE(" + expression + ", " + ", ".join(filters) + ")"


def key_filter(table, field, variable):
    return "KEEPFILTERS(TREATAS({" + variable + "}, " + col(table, field) + "))"


def eq(table, field, value):
    return "KEEPFILTERS(" + col(table, field) + " == " + value + ")"


def scoped(
    table,
    expression,
    *,
    analysis="[Selected Analysis Key]",
    family=None,
    extra=(),
    clear=False,
    decision=False,
):
    variables = "VAR C = [Selected Case Key]\n"
    variables += (
        "VAR A = " + ("[Current Decision Key]" if decision else analysis) + "\n"
    )
    filters = ["REMOVEFILTERS(" + table + ")"] if clear else []
    filters += [
        key_filter(table, "case_key", "C"),
        key_filter(table, "decision_key" if decision else "analysis_key", "A"),
    ]
    if family:
        filters += [eq(table, "record_family", lit(family))]
    filters += list(extra)
    return (
        variables
        + "RETURN IF(NOT ISBLANK(C) && NOT ISBLANK(A), "
        + calc(expression, filters)
        + ")"
    )


def rename_scope_variables(expression):
    # DAX string literals escape a quotation mark by doubling it.
    segments = re.split(r'("(?:[^"]|"")*")', expression)
    return "".join(
        segment
        if index % 2
        else re.sub(
            r"\b[CA]\b",
            lambda match: {"C": "ScopeCase", "A": "ScopeAnalysis"}[match.group()],
            segment,
        )
        for index, segment in enumerate(segments)
    )


@dataclass(frozen=True)
class Measure:
    expression: str
    result_type: str = "string"
    format_string: str | None = None
    hidden: bool = False


def measures():
    result = {t: {} for t in TABLES}
    used_names = {}

    def add(name, expression, kind="string", fmt=None, hidden=False, table=CC):
        assert name not in result[table], name
        normalized = name.casefold()
        assert normalized not in used_names, (used_names.get(normalized), name)
        used_names[normalized] = name
        # Avoid R1C1-reserved single-letter C as a DAX variable name.
        expression = rename_scope_variables(expression)
        result[table][name] = Measure(expression, kind, fmt, hidden)

    def external(name, expression, table, kind="string"):
        helper = "External " + name
        add(helper, expression, kind, hidden=True)
        add(
            name,
            calc("[" + helper + "]", ["ALLSELECTED(" + table + ")"]),
            kind,
            hidden=True,
        )

    external(
        "Walkthrough Requested",
        "INT(ISFILTERED(CaseCommandCenter[walkthrough_route]))",
        CC,
        "int64",
    )
    external(
        "Traditional Mode",
        """INT(ISFILTERED(CaseCommandCenter[walkthrough_route])
        && HASONEFILTER(CaseCommandCenter[walkthrough_route])
        && SELECTEDVALUE(CaseCommandCenter[walkthrough_route]) == "traditional")""",
        CC,
        "int64",
    )
    add(
        "Review Approach",
        """IF([Walkthrough Requested] == 1,
        IF([Traditional Mode] == 1,
            "Compare cost, service exposure, parts still needed and planning blockers. State your proposed response before reviewing AI assistance.",
            "Walkthrough selection unavailable"),
        [Recommendation Answer])""",
    )

    def display(name, source, suffix="", fmt="#,0.##"):
        add(
            name,
            "VAR V = ["
            + source
            + '] RETURN IF(ISBLANK(V), "Unavailable", FORMAT(V, '
            + lit(fmt)
            + ") & "
            + lit(suffix)
            + ")",
        )

    def textvalue(name, source):
        add(name, "VAR V = [" + source + '] RETURN IF(ISBLANK(V), "Unavailable", V)')

    def entity(name, source, kind):
        pairs = (
            {
                "RL-SUP-ALPHA": "RL-Supplier Alpha — Current supplier",
                "RL-SUP-BETA": "RL-Supplier Beta — Alternate supplier",
            }
            if kind == "Supplier"
            else {"RL-PLANT-DAL": "Dallas plant", "RL-PLANT-CHI": "Chicago plant"}
        )
        mapping = ",".join(
            "EXACT(V," + lit(k) + ")," + lit(v) for k, v in pairs.items()
        )
        add(
            name,
            "VAR V = ["
            + source
            + "] RETURN IF(ISBLANK(V),"
            + lit(kind + " unavailable")
            + ",SWITCH(TRUE(),"
            + mapping
            + ","
            + lit(kind + " ")
            + " & V))",
            hidden=True,
        )

    def qualification(name, source):
        add(
            name,
            "VAR V = ["
            + source
            + '] RETURN SWITCH(TRUE(),ISBLANK(V),"Qualification unavailable",'
            'EXACT(V,"approved"),"Qualification approved",EXACT(V,"pending"),"Not yet qualified — review pending",'
            'EXACT(V,"not_approved"),"Qualification not approved",EXACT(V,"conditional"),'
            '"Conditional qualification — requirements remain","Qualification status unresolved (" & V & ")")',
            hidden=True,
        )

    external(
        "Case Requested",
        "INT(ISFILTERED(CaseCommandCenter[case_key]) || ISFILTERED(CaseCommandCenter[case_id]))",
        CC,
        "int64",
    )

    external(
        "Selected Case Key",
        """IF(
        (ISFILTERED(CaseCommandCenter[case_key]) || ISFILTERED(CaseCommandCenter[case_id]))
        && (NOT ISFILTERED(CaseCommandCenter[case_key]) || HASONEFILTER(CaseCommandCenter[case_key]))
        && (NOT ISFILTERED(CaseCommandCenter[case_id]) || HASONEFILTER(CaseCommandCenter[case_id]))
        && COUNTROWS(CaseCommandCenter) == 1,
        SELECTEDVALUE(CaseCommandCenter[case_key]))""",
        CC,
    )
    external(
        "Analysis Requested",
        "INT(ISFILTERED(SavedAnalyses[analysis_key]))",
        SA,
        "int64",
    )
    external(
        "Selected Analysis Key",
        """VAR C = [Selected Case Key]
        VAR N = CALCULATE(COUNTROWS(SavedAnalyses), KEEPFILTERS(TREATAS({C},SavedAnalyses[case_key])),
            KEEPFILTERS(SavedAnalyses[payload_state] == "available"),
            KEEPFILTERS(SavedAnalyses[snapshot_state] == "available"))
        RETURN IF(NOT ISBLANK(C) && ISFILTERED(SavedAnalyses[analysis_key])
        && HASONEFILTER(SavedAnalyses[analysis_key]) && N == 1,
        SELECTEDVALUE(SavedAnalyses[analysis_key]))""",
        SA,
    )
    for name, field in (
        ("Case Current Analysis Key", "current_analysis_key"),
        ("Current Decision Key", "current_decision_key"),
        ("Decision Analysis Key", "decision_analysis_key"),
        ("Approved Option Key", "approved_option_key"),
        ("Current Decision ID", "current_decision_id"),
        ("Case Status", "status"),
        ("Decision Kind", "decision_kind"),
        ("Case Runtime", "runtime_mode"),
        ("Case Display ID", "case_id"),
    ):
        add(
            name,
            "IF(NOT ISBLANK([Selected Case Key]), "
            + calc("SELECTEDVALUE(" + col(CC, field) + ")", ["ALLSELECTED(" + CC + ")"])
            + ")",
            hidden=True,
        )
    add(
        "Overview Analysis Key",
        """VAR C = [Selected Case Key]
        VAR A = [Case Current Analysis Key]
        VAR N = CALCULATE(COUNTROWS(SavedAnalyses), REMOVEFILTERS(SavedAnalyses),
            TREATAS({C},SavedAnalyses[case_key]),TREATAS({A},SavedAnalyses[analysis_key]),
            SavedAnalyses[payload_state] == "available",SavedAnalyses[snapshot_state] == "available")
        RETURN IF([Walkthrough Requested] == 1 || [Analysis Requested] == 1,
            [Selected Analysis Key],
            IF(NOT ISBLANK(C) && NOT ISBLANK(A) && N == 1,A))""",
        hidden=True,
    )
    for prefix, basis in (
        ("Selected", "[Selected Analysis Key]"),
        ("Overview", "[Overview Analysis Key]"),
    ):
        for field in (
            "analysis_id",
            "analysis_created_at",
            "scenario_effective_time",
            "snapshot_state",
            "payload_state",
            "runtime_mode",
            "inventory_complete",
            "production_orders_complete",
            "customer_orders_complete",
        ):
            add(
                prefix + " " + field,
                scoped(
                    SA,
                    "SELECTEDVALUE(" + col(SA, field) + ")",
                    analysis=basis,
                    clear=True,
                ),
                TYPES[SA][field],
                hidden=True,
            )
    add(
        "Case Selection State",
        'IF([Case Requested] == 0,"Select a case",IF(ISBLANK([Selected Case Key]),"Case selection unavailable — unknown, multiple or conflicting selections","Case " & [Case Display ID]))',
    )
    add(
        "Overview State",
        """SWITCH(TRUE(),ISBLANK([Selected Case Key]),[Case Selection State],
        [Analysis Requested] == 1 && ISBLANK([Selected Analysis Key]),"This analysis is unavailable in the report",
        ISBLANK([Case Current Analysis Key]) && [Analysis Requested] == 0,"Not analyzed yet",
        ISBLANK([Overview Analysis Key]),"Saved analysis or operational snapshot unavailable",
        [Overview payload_state] <> "available","Saved analysis unavailable",
        "Case " & [Case Display ID] & " · Analysis " & [Overview analysis_id] & " · " & [Overview Provenance])""",
    )
    for prefix in ("Selected", "Overview"):
        add(
            prefix + " Provenance",
            "VAR V = ["
            + prefix
            + " runtime_mode] RETURN IF(ISBLANK(["
            + prefix
            + " analysis_id]),BLANK(),"
            'SWITCH(V,"fallback","Saved demo fixture · fictional",'
            '"live","Saved analysis from live-service mode · fictional scenario · no new retrieval",'
            '"Saved analysis · source mode unavailable"))',
            hidden=True,
        )
    add(
        "Scenario Context",
        """VAR V = [Overview scenario_effective_time]
        RETURN IF(NOT ISBLANK([Selected Case Key]),IF(ISBLANK(V),"Scenario time unavailable",
        "In this scenario, as of " & FORMAT(V,"MMM d, yyyy HH:mm") & " UTC"))""",
    )
    add(
        "Snapshot Context",
        """VAR V = [Selected analysis_created_at]
        RETURN IF(NOT ISBLANK([Selected Analysis Key]),
        "Snapshot used for this analysis · " & IF(ISBLANK(V),"Analysis time unavailable",
        FORMAT(V,"MMM d, yyyy HH:mm") & " UTC") & " · " & [Selected Provenance])""",
    )

    external(
        "Explicit Selected Record Key",
        """VAR C = [Selected Case Key] VAR A = [Selected Analysis Key]
        VAR N = CALCULATE(COUNTROWS(SavedRecords),
            KEEPFILTERS(TREATAS({C},SavedRecords[case_key])),
            KEEPFILTERS(TREATAS({A},SavedRecords[analysis_key])),
            KEEPFILTERS(SavedRecords[record_state] == "available"),
            KEEPFILTERS(SavedRecords[evidence_state] == "available"))
        RETURN IF(NOT ISBLANK(C) && NOT ISBLANK(A)
            && ISFILTERED(SavedRecords[record_key]) && HASONEFILTER(SavedRecords[record_key])
            && ISFILTERED(SavedRecords[record_family]) && HASONEFILTER(SavedRecords[record_family])
            && SELECTEDVALUE(SavedRecords[record_family]) IN {"shipment","transfer","qualification"}
            && N == 1,SELECTEDVALUE(SavedRecords[record_key]))""",
        SR,
    )
    external(
        "Record Identity Requested",
        """INT(ISFILTERED(SavedRecords[record_key])
        || ISFILTERED(SavedRecords[source_record_id]))""",
        SR,
        "int64",
    )
    external(
        "Walkthrough Record Key",
        """VAR CaseKey = [Selected Case Key]
        VAR AnalysisKey = [Selected Analysis Key]
        VAR Family = SELECTEDVALUE(SavedRecords[record_family])
        VAR Candidates = CALCULATETABLE(SavedRecords,
            REMOVEFILTERS(SavedRecords),
            TREATAS({CaseKey}, SavedRecords[case_key]),
            TREATAS({AnalysisKey}, SavedRecords[analysis_key]),
            TREATAS({Family}, SavedRecords[record_family]))
        VAR ValidCandidates = FILTER(Candidates,
            SavedRecords[record_state] == "available"
            && SavedRecords[evidence_state] == "available"
            && SavedRecords[runtime_mode] == "live"
            && SavedRecords[provenance] == "saved_fabric")
        RETURN IF([Traditional Mode] == 1
            && [Record Identity Requested] == 0
            && NOT ISBLANK(CaseKey) && NOT ISBLANK(AnalysisKey)
            && ISFILTERED(SavedRecords[record_family])
            && HASONEFILTER(SavedRecords[record_family])
            && Family IN {"shipment","transfer","qualification"}
            && COUNTROWS(Candidates) == 1 && COUNTROWS(ValidCandidates) == 1,
            MAXX(ValidCandidates, SavedRecords[record_key]))""",
        SR,
    )
    add(
        "Selected Record Key",
        """IF([Record Identity Requested] == 1,
        [Explicit Selected Record Key],
        [Walkthrough Record Key])""",
        hidden=True,
    )
    external(
        "Selected Record Family",
        "IF(NOT ISBLANK([Selected Record Key]), SELECTEDVALUE(SavedRecords[record_family]))",
        SR,
    )
    record_filters = [
        key_filter(SR, "record_key", "[Selected Record Key]"),
        key_filter(SR, "record_family", "[Selected Record Family]"),
        eq(SR, "record_state", '"available"'),
        eq(SR, "evidence_state", '"available"'),
    ]
    for field in (
        "quantity",
        "due_date",
        "arrival_date",
        "incremental_cost_per_unit",
        "status",
        "audit_complete",
        "first_article_complete",
        "expected_decision_date",
        "supplier_id",
        "source_plant_id",
        "destination_plant_id",
        "part_id",
        "retrieved_at",
        "provenance",
        "runtime_mode",
        "source_system",
        "source_timestamp",
    ):
        add(
            "Record " + field,
            "IF(NOT ISBLANK([Selected Record Key]), ("
            + scoped(
                SR,
                "SELECTEDVALUE(" + col(SR, field) + ")",
                extra=record_filters,
                clear=True,
            )
            + "))",
            TYPES[SR][field],
            hidden=True,
        )
    add(
        "Record Row Visible",
        "IF(NOT ISBLANK([Selected Record Key]), INT(("
        + scoped(SR, "COUNTROWS(SavedRecords)", extra=record_filters)
        + ") > 0),0)",
        "int64",
        hidden=True,
    )
    entity("Record Supplier", "Record supplier_id", "Supplier")
    entity("Record Source Plant", "Record source_plant_id", "Plant")
    entity("Record Destination Plant", "Record destination_plant_id", "Plant")
    qualification("Record Qualification", "Record status")
    add(
        "Record Provenance Display",
        """IF(NOT ISBLANK([Selected Record Key]),SWITCH([Record provenance],
        "saved_fabric","Saved Microsoft Fabric record · fictional scenario",
        "demo_fixture","Saved demo fixture · fictional",
        "Saved record · provenance unavailable") & " · Retrieved for this analysis: "
        & IF(ISBLANK([Record retrieved_at]),"Unavailable",FORMAT([Record retrieved_at],"MMM d, yyyy HH:mm") & " UTC"))""",
        hidden=True,
    )
    add(
        "Record State",
        """IF(ISBLANK([Selected Record Key]),"Supporting record unavailable — select the exact case, analysis and record",
        SWITCH([Selected Record Family],"shipment",[Record Supplier] & " · Partial shipment",
        "qualification",[Record Supplier] & " · Qualification",
        "transfer",[Record Source Plant] & " to " & [Record Destination Plant])
        & " · " & [Record Provenance Display])""",
    )
    for name, source, suffix, fmt in (
        ("Record Quantity Display", "Record quantity", " component units", "#,0"),
        ("Record Due Date Display", "Record due_date", "", "MMM d, yyyy"),
        ("Record Arrival Date Display", "Record arrival_date", "", "MMM d, yyyy"),
        (
            "Record Unit Cost Display",
            "Record incremental_cost_per_unit",
            " per unit; currency not specified",
            "#,0.00",
        ),
    ):
        display(name, source, suffix, fmt)
    textvalue("Record Status Display", "Record Qualification")
    for name, field in (
        ("Record Audit Display", "audit_complete"),
        ("Record First Article Display", "first_article_complete"),
    ):
        add(
            name,
            "VAR V = [Record "
            + field
            + '] RETURN IF(ISBLANK(V),"Unavailable",IF(V,"Complete","Outstanding"))',
        )
    add(
        "Record Explanation",
        """IF(NOT ISBLANK([Selected Record Key]),SWITCH([Selected Record Family],
        "shipment","Scheduled receipt from the saved shipment record. Supplier statements remain in the original supplier email. This is not approval or execution.",
        "transfer","Saved dispatch and arrival dates describe the planned plant transfer. Approval and execution are separate.",
        "qualification","Audit: " & [Record Audit Display] & "; first article: " & [Record First Article Display]
            & ". Review date: " & IF(ISBLANK([Record expected_decision_date]),"Unavailable",FORMAT([Record expected_decision_date],"MMM d, yyyy"))
            & ". A review date is not an approval or delivery date."))""",
    )

    for prefix, family, gate in (
        ("Stock", "inventory", "Stock Row Visible"),
        ("Orders", "customer_order_line", "Order Row Visible"),
    ):
        filters = [
            eq(SR, "in_disruption_scope", "TRUE()"),
            eq(SR, "record_state", '"available"'),
        ]
        complete = (
            "[Selected inventory_complete] == TRUE()"
            if prefix == "Stock"
            else "[Selected production_orders_complete] == TRUE() && [Selected customer_orders_complete] == TRUE()"
        )
        add(
            prefix + " Rows Valid",
            "IF("
            + complete
            + ",("
            + scoped(
                SR,
                'IF(COUNTROWS(SavedRecords)>0 && COUNTROWS(FILTER(SavedRecords,SavedRecords[record_state] <> "available")) == 0,1,0)',
                family=family,
                clear=True,
            )
            + "),0)",
            "int64",
            hidden=True,
        )
        add(
            gate,
            "IF(["
            + prefix
            + " Rows Valid] == 1,INT(("
            + scoped(SR, "COUNTROWS(SavedRecords)", family=family, extra=filters)
            + ") > 0),0)",
            "int64",
            hidden=True,
        )
        add(
            prefix + " Count",
            "IF(["
            + prefix
            + " Rows Valid] == 1,("
            + scoped(
                SR, "COUNTROWS(SavedRecords)", family=family, extra=filters, clear=True
            )
            + "))",
            "int64",
            hidden=True,
        )
        add(
            prefix + " State",
            "IF(ISBLANK([Selected Case Key]),[Case Selection State],"
            'IF(ISBLANK([Selected Analysis Key]),"Select an available saved analysis",'
            "IF(ISBLANK(["
            + prefix
            + " Count]) || ["
            + prefix
            + ' Count] == 0,"Supporting records unavailable",[Snapshot Context])))',
        )
    for prefix, family, field, measure in (
        ("Stock", "inventory", "usable_inventory", "Stock Usable"),
        ("Stock", "inventory", "quality_hold", "Stock Held"),
        ("Stock", "inventory", "protected_allocation", "Stock Protected"),
        ("Orders", "customer_order_line", "line_revenue", "Affected Revenue"),
    ):
        # A missing cell never becomes a fabricated zero subtotal.
        expression = (
            "IF(COUNTROWS(SavedRecords) > 0 && COUNTBLANK("
            + col(SR, field)
            + ") == 0, SUM("
            + col(SR, field)
            + "))"
        )
        add(
            measure,
            "IF(["
            + prefix
            + " Rows Valid] == 1,("
            + scoped(
                SR,
                expression,
                family=family,
                extra=[
                    eq(SR, "in_disruption_scope", "TRUE()"),
                    eq(SR, "record_state", '"available"'),
                ],
                clear=True,
            )
            + "))",
            TYPES[SR][field],
            hidden=True,
        )
        display(
            measure + " Display",
            measure,
            "; currency not specified"
            if field == "line_revenue"
            else " component units",
        )
    display(
        "Affected Lines Display", "Orders Count", " saved customer order lines", "#,0"
    )
    for name, field in (
        ("Stock On Hand Row", "on_hand"),
        ("Stock Held Row", "quality_hold"),
        ("Stock Protected Row", "protected_allocation"),
        ("Stock Usable Row", "usable_inventory"),
    ):
        add(
            name,
            "IF([Stock Rows Valid] == 1,("
            + scoped(
                SR,
                "IF(COUNTROWS(SavedRecords)>0 && COUNTBLANK("
                + col(SR, field)
                + ") == 0,SUM("
                + col(SR, field)
                + "))",
                family="inventory",
                extra=[
                    eq(SR, "in_disruption_scope", "TRUE()"),
                    eq(SR, "record_state", '"available"'),
                ],
            )
            + "))",
            "int64",
            "#,0",
        )
    add(
        "Stock Explanation",
        'IF(NOT ISBLANK([Selected Analysis Key]),"Usable component stock = on hand − quality holds − protected allocations, for the disruption’s exact part and plant.")',
    )
    add(
        "Orders Basis Display",
        'IF(NOT ISBLANK([Selected Analysis Key]),"Customer lines participating in this saved plan")',
    )
    add(
        "Orders Baseline Revenue",
        "IF(NOT ISBLANK([Selected Analysis Key]),[Baseline revenue_at_risk])",
        "decimal",
        hidden=True,
    )
    add(
        "Orders Baseline OTIF",
        "IF(NOT ISBLANK([Selected Analysis Key]),[Baseline otif_loss_percentage])",
        "int64",
        hidden=True,
    )
    display(
        "Orders Baseline Revenue Display",
        "Orders Baseline Revenue",
        "; currency not specified",
    )
    display("Orders Baseline OTIF Display", "Orders Baseline OTIF", "%", "0")
    add(
        "Orders Explanation",
        'IF(NOT ISBLANK([Selected Analysis Key]),"Without a response: saved baseline predictions from the same calculation as the card. The supporting rows are customer lines included in this plan; their line values are not predicted revenue at risk, and these rows do not identify individual missed service targets.")',
    )

    external(
        "Option Requested", "INT(ISFILTERED(SavedOptions[option_key]))", SO, "int64"
    )
    external(
        "Selected Option Key",
        """VAR C = [Selected Case Key] VAR A = [Selected Analysis Key]
        VAR N = CALCULATE(COUNTROWS(SavedOptions),KEEPFILTERS(TREATAS({C},SavedOptions[case_key])),
            KEEPFILTERS(TREATAS({A},SavedOptions[analysis_key])))
        RETURN IF(NOT ISBLANK(C) && NOT ISBLANK(A) && ISFILTERED(SavedOptions[option_key])
            && HASONEFILTER(SavedOptions[option_key]) && N == 1,SELECTEDVALUE(SavedOptions[option_key]))""",
        SO,
    )
    add(
        "Option Row Visible",
        "IF([Option Requested] == 0 || NOT ISBLANK([Selected Option Key]),INT(("
        + scoped(SO, "COUNTROWS(SavedOptions)")
        + ") > 0),0)",
        "int64",
        hidden=True,
    )
    for name, field in (
        ("Option Revenue", "revenue_at_risk"),
        ("Option Response Cost", "response_cost"),
    ):
        add(
            name,
            "IF([Option Row Visible] == 1,("
            + scoped(
                SO,
                "IF(COUNTROWS(SavedOptions) == 1,SELECTEDVALUE("
                + col(SO, field)
                + "))",
            )
            + "))",
            "decimal",
            "#,0.00",
        )
    for field in (
        "option_name",
        "revenue_at_risk",
        "response_cost",
        "blockers_text",
        "required_roles_text",
        "assumptions_text",
    ):
        add(
            "Selected Option " + field,
            "IF(NOT ISBLANK([Selected Option Key]),("
            + scoped(
                SO,
                "SELECTEDVALUE(" + col(SO, field) + ")",
                extra=[key_filter(SO, "option_key", "[Selected Option Key]")],
                clear=True,
            )
            + "))",
            TYPES[SO][field],
            hidden=True,
        )
    add(
        "Options State",
        'IF(ISBLANK([Selected Case Key]),[Case Selection State],IF(ISBLANK([Selected Analysis Key]),"Saved analysis or operational snapshot unavailable",IF([Option Requested] == 1 && ISBLANK([Selected Option Key]),"Selected option unavailable",[Snapshot Context])))',
    )
    add(
        "Selected Option Display",
        'IF([Option Requested] == 0,"Compare the saved options",IF(ISBLANK([Selected Option Key]),"Selected option unavailable",[Selected Option option_name]))',
    )
    display(
        "Option Revenue Display",
        "Selected Option revenue_at_risk",
        "; currency not specified",
    )
    display(
        "Option Cost Display",
        "Selected Option response_cost",
        "; currency not specified",
    )
    add(
        "Options Explanation",
        'IF(NOT ISBLANK([Selected Analysis Key]),IF([Option Requested] == 0,"Expected results from the shared saved calculation engine. Meeting planning requirements is separate from approval.",IF(NOT ISBLANK([Selected Option Key]),COALESCE([Selected Option blockers_text],"Planning blockers unavailable") & ". " & COALESCE([Selected Option required_roles_text],"Required roles unavailable"))))',
    )

    # Overview basis measures ignore detail/option selection only after exact overview scope is captured.
    for basis, flag in (("Baseline", "is_baseline"), ("Recommended", "is_recommended")):
        for field in (
            "option_name",
            "revenue_at_risk",
            "response_cost",
            "otif_loss_percentage",
            "uncovered_part_demand",
            "blockers_text",
        ):
            add(
                basis + " " + field,
                scoped(
                    SO,
                    "IF(COUNTROWS(SavedOptions) == 1,SELECTEDVALUE("
                    + col(SO, field)
                    + "))",
                    analysis="[Overview Analysis Key]",
                    extra=[eq(SO, flag, "TRUE()")],
                    clear=True,
                ),
                TYPES[SO][field],
                hidden=True,
            )
    for field in (
        "option_name",
        "revenue_at_risk",
        "response_cost",
        "otif_loss_percentage",
        "uncovered_part_demand",
    ):
        add(
            "Approved " + field,
            'IF([Decision Kind] == "approved" && NOT ISBLANK([Approved Option Key]),('
            + scoped(
                SO,
                "IF(COUNTROWS(SavedOptions) == 1,SELECTEDVALUE("
                + col(SO, field)
                + "))",
                analysis="[Decision Analysis Key]",
                extra=[key_filter(SO, "option_key", "[Approved Option Key]")],
                clear=True,
            )
            + "))",
            TYPES[SO][field],
            hidden=True,
        )
    for family in ("disruption", "shipment", "transfer", "qualification"):
        fields = {
            "disruption": (
                "original_quantity",
                "partial_quantity",
                "original_due_date",
                "partial_due_date",
                "supplier_id",
                "part_id",
                "plant_id",
            ),
            "shipment": ("quantity", "due_date", "supplier_id"),
            "transfer": (
                "quantity",
                "arrival_date",
                "source_plant_id",
                "destination_plant_id",
            ),
            "qualification": ("status", "supplier_id"),
        }[family]
        for field in fields:
            guards = [eq(SR, "record_state", '"available"')]
            if family != "disruption":
                guards += [eq(SR, "evidence_state", '"available"')]
            add(
                "Overview " + family + " " + field,
                scoped(
                    SR,
                    "IF(COUNTROWS(SavedRecords) == 1,SELECTEDVALUE("
                    + col(SR, field)
                    + "))",
                    analysis="[Overview Analysis Key]",
                    family=family,
                    extra=guards,
                    clear=True,
                ),
                TYPES[SR][field],
                hidden=True,
            )
    add(
        "Overview Stock Rows Valid",
        "IF([Overview inventory_complete] == TRUE(),("
        + scoped(
            SR,
            'IF(COUNTROWS(SavedRecords)>0 && COUNTROWS(FILTER(SavedRecords,SavedRecords[record_state] <> "available")) == 0,1,0)',
            analysis="[Overview Analysis Key]",
            family="inventory",
            clear=True,
        )
        + "),0)",
        "int64",
        hidden=True,
    )
    add(
        "Overview Stock",
        "IF([Overview Stock Rows Valid] == 1,("
        + scoped(
            SR,
            "IF(COUNTROWS(SavedRecords)>0 && COUNTBLANK(SavedRecords[usable_inventory]) == 0,SUM(SavedRecords[usable_inventory]))",
            analysis="[Overview Analysis Key]",
            family="inventory",
            extra=[
                eq(SR, "in_disruption_scope", "TRUE()"),
                eq(SR, "record_state", '"available"'),
            ],
            clear=True,
        )
        + "))",
        "int64",
        hidden=True,
    )
    for family in ("disruption", "shipment", "qualification"):
        entity(
            "Overview " + family + " Supplier",
            "Overview " + family + " supplier_id",
            "Supplier",
        )
    entity("Overview Transfer Source", "Overview transfer source_plant_id", "Plant")
    entity(
        "Overview Transfer Destination",
        "Overview transfer destination_plant_id",
        "Plant",
    )
    entity("Overview Disruption Plant", "Overview disruption plant_id", "Plant")
    qualification(
        "Overview Qualification Status Display", "Overview qualification status"
    )
    add(
        "Disruption Answer",
        """VAR Q = [Overview disruption original_quantity] VAR P = [Overview disruption partial_quantity]
        RETURN IF(NOT ISBLANK([Overview Analysis Key]),IF(ISBLANK(Q)||ISBLANK(P),"Disruption details unavailable",
        [Overview disruption Supplier] & "; part " & COALESCE([Overview disruption part_id],"unavailable")
        & " at " & [Overview Disruption Plant] & ": " & FORMAT(Q,"#,0") & " component units originally due "
        & IF(ISBLANK([Overview disruption original_due_date]),"date unavailable",FORMAT([Overview disruption original_due_date],"MMM d"))
        & "; " & FORMAT(P,"#,0") & " in the partial response."))""",
    )
    add(
        "Availability Answer",
        'IF(NOT ISBLANK([Overview Analysis Key]),IF(ISBLANK([Overview Stock]),"Available stock unavailable",FORMAT([Overview Stock],"#,0") & " usable component units after holds and protected allocations"))',
    )
    add(
        "Exposure Answer",
        """VAR V = [Baseline revenue_at_risk] VAR P = [Baseline otif_loss_percentage]
        RETURN IF(NOT ISBLANK([Overview Analysis Key]),"Without a response: "
        & IF(ISBLANK(V),"revenue exposure unavailable",FORMAT(V,"#,0.00") & " revenue at risk; currency not specified")
        & ". Service-target exposure: " & IF(ISBLANK(P),"Unavailable",FORMAT(P,"0") & "%"))""",
    )
    for label, family, datefield, entity_expression in (
        ("Shipment", "shipment", "due_date", "[Overview shipment Supplier]"),
        (
            "Transfer",
            "transfer",
            "arrival_date",
            '[Overview Transfer Source] & " to " & [Overview Transfer Destination]',
        ),
    ):
        add(
            label + " Answer",
            "VAR Q = [Overview "
            + family
            + " quantity] VAR D = [Overview "
            + family
            + " "
            + datefield
            + "] "
            'RETURN IF(NOT ISBLANK([Overview Analysis Key]),IF(ISBLANK(Q),"Supporting record unavailable",'
            + "("
            + entity_expression
            + ') & ": " & FORMAT(Q,"#,0") & " component units; " & IF(ISBLANK(D),"date unavailable",FORMAT(D,"MMM d, yyyy"))))',
        )
    add(
        "Qualification Answer",
        'IF(NOT ISBLANK([Overview Analysis Key]),[Overview qualification Supplier] & ": " & [Overview Qualification Status Display])',
    )
    add(
        "Options Answer",
        'IF(NOT ISBLANK([Overview Analysis Key]),"Compare saved baseline and response options by cost, service exposure, and parts still needed. Predictions are not observed results.")',
    )
    add(
        "Recommendation Answer",
        """IF(NOT ISBLANK([Overview Analysis Key]),IF(ISBLANK([Recommended option_name]),"Recommendation unavailable",
        [Recommended option_name] & "; " & IF(ISBLANK([Recommended uncovered_part_demand]),"parts still needed unavailable",
        FORMAT([Recommended uncovered_part_demand],"#,0") & " component units still needed")
        & "; revenue at risk " & IF(ISBLANK([Recommended revenue_at_risk]),"unavailable",FORMAT([Recommended revenue_at_risk],"#,0.00"))
        & "; response cost " & IF(ISBLANK([Recommended response_cost]),"unavailable",FORMAT([Recommended response_cost],"#,0.00"))
        & " (currency not specified)"
        & ". Saved recommendation. Current decision is shown separately."))""",
    )
    add(
        "Decision Answer",
        """IF(NOT ISBLANK([Selected Case Key]),IF(ISBLANK([Current Decision Key]),
        IF([Case Status] == "awaiting_decision","Awaiting approval","No current decision recorded · " & [Case Status]),
        IF([Decision Kind] == "approved","Approved option: " & COALESCE([Approved option_name],"Unavailable"),
        "Recorded decision: " & COALESCE([Decision Kind],"Unavailable"))) & ". Approval remains an explicit action in the demo.")""",
    )

    action_filters = [eq(AO, "record_type", '"action"')]
    observation_filters = [eq(AO, "record_type", '"observation"')]
    add(
        "Action Row Visible",
        "INT(("
        + scoped(AO, "COUNTROWS(ActionOutcomes)", extra=action_filters, decision=True)
        + ") > 0)",
        "int64",
        hidden=True,
    )
    unit_pairs = {
        "alpha_expedited_quantity": "units",
        "dallas_transfer_quantity": "units",
        "total_response_arranged_supply": "units",
        "uncovered_part_demand": "units",
        "response_cost": "USD",
        "protected_customer_orders": "orders",
        "revenue_protected": "USD",
        "margin_protected": "USD",
        "otif_loss_percentage": "percent",
    }
    expected = (
        "SWITCH(M,"
        + ",".join(lit(k) + "," + lit(v) for k, v in unit_pairs.items())
        + ",BLANK())"
    )
    obs_gate = (
        """VAR M = SELECTEDVALUE(ActionOutcomes[metric]) VAR U = SELECTEDVALUE(ActionOutcomes[unit])
        VAR K = SELECTEDVALUE(ActionOutcomes[observation_kind])
        VAR E = """
        + expected
        + """
        RETURN IF(COUNTROWS(ActionOutcomes)>0 && NOT ISBLANK(M) && NOT ISBLANK(U)
        && NOT ISBLANK(K) && NOT ISBLANK(E) && U == E,1,0)"""
    )
    add(
        "Observation Row Visible",
        scoped(AO, obs_gate, extra=observation_filters, decision=True),
        "int64",
        hidden=True,
    )
    variance = """VAR PredictedText = SELECTEDVALUE(ActionOutcomes[predicted_value])
        VAR ObservedText = SELECTEDVALUE(ActionOutcomes[observed_value])
        VAR Predicted = IFERROR(VALUE(PredictedText), BLANK())
        VAR Observed = IFERROR(VALUE(ObservedText), BLANK())
        RETURN IF(ISBLANK(Predicted) || ISBLANK(Observed) || Predicted == 0,BLANK(),
            DIVIDE(Observed - Predicted, ABS(Predicted)))"""
    add(
        "Observed Variance",
        "IF([Observation Row Visible] == 1,("
        + scoped(AO, variance, extra=observation_filters, decision=True)
        + "))",
        "double",
        "0.00%;-0.00%;0.00%",
        table=AO,
    )
    for name, expr, filters, kind in (
        ("Current Actions Count", "COUNTROWS(ActionOutcomes)", action_filters, "int64"),
        (
            "Current Observations Count",
            "COUNTROWS(ActionOutcomes)",
            observation_filters,
            "int64",
        ),
        (
            "Current Action Status",
            "SELECTEDVALUE(ActionOutcomes[action_status])",
            action_filters,
            "string",
        ),
        (
            "Current Observation Kind",
            "SELECTEDVALUE(ActionOutcomes[observation_kind])",
            observation_filters,
            "string",
        ),
        (
            "Projection Refresh Time",
            "MAX(ActionOutcomes[projection_updated_at])",
            [],
            "dateTime",
        ),
    ):
        add(
            name,
            scoped(AO, expr, extra=filters, decision=True, clear=True),
            kind,
            hidden=True,
        )
    add(
        "Current Decision Display",
        'IF(ISBLANK([Selected Case Key]),[Case Selection State],IF(ISBLANK([Current Decision Key]),"No current decision recorded",COALESCE([Decision Kind],"Decision kind unavailable")))',
    )
    add(
        "Current Action Status Display",
        'IF(ISBLANK([Current Actions Count]) || [Current Actions Count] == 0,"No actions recorded",COALESCE([Current Action Status],"Multiple action states — see current actions"))',
    )
    add(
        "Current Observation Display",
        'IF(ISBLANK([Current Observations Count]) || [Current Observations Count] == 0,"No outcomes recorded",IF([Current Observation Kind] == "simulated","Simulated",COALESCE([Current Observation Kind],"Mixed observation kinds — see each series")))',
    )
    display(
        "Projection Updated Display",
        "Projection Refresh Time",
        " UTC",
        "MMM d, yyyy HH:mm",
    )
    add(
        "Actions State",
        'IF(ISBLANK([Selected Case Key]),[Case Selection State],IF(ISBLANK([Current Decision Key]),"No current decision recorded","Current governing decision" & IF([Analysis Requested] == 1 && ISBLANK([Selected Analysis Key])," · Requested analysis unavailable; these are current-decision records",IF(NOT ISBLANK([Selected Analysis Key]) && [Selected Analysis Key] <> [Decision Analysis Key]," · Decision belongs to a different saved analysis from the one being viewed",""))))',
    )
    add(
        "Action Explanation",
        'IF(NOT ISBLANK([Selected Case Key]),[Current Action Status Display] & ". " & [Current Observation Display] & ". Predictions and observations remain separate. Simulated observations are not real-world outcomes.")',
    )
    return result


def manifest():
    definitions = measures()
    return {
        "tables": {
            t: {
                "columns": dict(TYPES[t]),
                "column_formats": {c: column_format(t, c) for c in COLUMNS[t]},
                "partition": t,
                "mode": "directQuery",
                "query_file": "fabric/reporting/queries/" + t + ".sql",
                "measures": {
                    n: {
                        "expression": m.expression,
                        "result_type": m.result_type,
                        "format_string": m.format_string,
                        "hidden": m.hidden,
                    }
                    for n, m in definitions[t].items()
                },
            }
            for t in TABLES
        },
        "relationships": [],
    }


def check_required_fields(required):
    current = manifest()["tables"]
    for kind, table, name in required:
        group = (
            "columns" if kind == "Column" else "measures" if kind == "Measure" else None
        )
        if group is None or table not in current or name not in current[table][group]:
            raise ValueError("Unknown report binding: " + repr((kind, table, name)))


def m_string(value):
    return (
        '"'
        + value.replace("#", "#(#)")
        .replace('"', '""')
        .replace("\r", "")
        .replace("\n", "#(lf)")
        + '"'
    )


def artifacts(query_directory):
    reject_symlink_chain(query_directory)
    output = {}
    definitions = measures()
    for table in TABLES:
        query_path = query_directory / (table + ".sql")
        if query_path.is_symlink():
            raise ValueError("SQL source must not be a symlink")
        query = query_path.read_text(encoding="utf-8")
        if not query.strip():
            raise ValueError("Empty partition query")
        lines = ["table " + table]
        for name in COLUMNS[table]:
            lines += [
                "  column " + name,
                "    dataType: " + TYPES[table][name],
                "    sourceColumn: " + name,
                "    summarizeBy: none",
            ]
            if column_format(table, name):
                lines += ["    formatString: " + column_format(table, name)]
            lines += [""]
        for name, measure in definitions[table].items():
            lines += ["  measure '" + name.replace("'", "''") + "' ="]
            lines += ["      " + line for line in measure.expression.splitlines()]
            if measure.format_string:
                lines += ["    formatString: " + measure.format_string]
            if measure.hidden:
                lines += ["    isHidden"]
            lines += [""]
        lines += [
            "  partition " + table + " = m",
            "    mode: directQuery",
            "    source =",
            "        Sql.Database(FABRIC_SQL_SERVER, FABRIC_SQL_DATABASE, [Query="
            + m_string(query)
            + "])",
            "",
        ]
        output["tables/" + table + ".tmdl"] = "\n".join(lines)
    output["model.tmdl"] = (
        "model Model\n  culture: en-US\n  defaultPowerBIDataSourceVersion: powerBI_V3\n"
        "  sourceQueryCulture: en-US\n\n  dataAccessOptions\n    legacyRedirects\n    returnErrorValuesAsNull\n\n"
        "ref expression FABRIC_SQL_SERVER\nref expression FABRIC_SQL_DATABASE\n"
        + "".join("ref table " + table + "\n" for table in TABLES)
    )
    output["relationships.tmdl"] = ""
    return output


def reject_symlink_chain(path):
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise ValueError("Symlink in semantic/query path: " + str(candidate))


def check_output_paths(definition, expected):
    reject_symlink_chain(definition)
    reject_symlink_chain(definition / "tables")
    for name in expected:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid generated relative path")
        target = definition / relative
        reject_symlink_chain(target)
        if target.exists() and not target.is_file():
            raise ValueError("Generated file target is not a file: " + str(target))
        for directory in target.parents:
            if directory.exists() and not directory.is_dir():
                raise ValueError(
                    "Generated parent is not a directory: " + str(directory)
                )
    table_directory = definition / "tables"
    if table_directory.exists():
        allowed = {t + ".tmdl" for t in TABLES}
        if any(
            p.name not in allowed or not p.is_file() or p.is_symlink()
            for p in table_directory.iterdir()
        ):
            raise ValueError("Unexpected existing semantic table path")


def verify(definition, query_directory):
    reject_symlink_chain(query_directory)
    expected = artifacts(query_directory)
    check_output_paths(definition, expected)
    actual_tables = {p.name for p in (definition / "tables").iterdir()}
    if actual_tables != {t + ".tmdl" for t in TABLES}:
        raise ValueError("Unexpected semantic table inventory")
    for name, value in expected.items():
        target = definition / name
        if target.is_symlink() or target.read_text(encoding="utf-8") != value:
            raise ValueError("Semantic artifact drift: " + name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("definition", type=Path)
    parser.add_argument("queries", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    reject_symlink_chain(args.queries)
    from fabric.report_pages import required_fields

    check_required_fields(required_fields())
    if args.check:
        verify(args.definition, args.queries)
        return
    planned = artifacts(args.queries)
    check_output_paths(args.definition, planned)
    # All targets/ancestors checked before the first mkdir or write.
    for name, value in planned.items():
        target = args.definition / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ValueError("Refusing symlink target")
        target.write_text(value, encoding="utf-8")
    verify(args.definition, args.queries)


if __name__ == "__main__":
    main()
