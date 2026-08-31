from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any
from decimal import Decimal

import pytest


ROOT = Path(__file__).resolve().parents[2]
POWER_BI = ROOT / "fabric" / "power-bi"
SEMANTIC_MODEL = POWER_BI / "SupplyResponse.SemanticModel" / "definition"
REPORT = POWER_BI / "SupplyResponse.Report" / "definition"
PLATFORM_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/"
    "platformProperties/2.0.0/schema.json"
)

PAGES = {
    "command-center": "Command Center",
    "actions-outcomes": "Actions and Outcomes",
}

QUERY_REF_ALLOWLIST = {
    "command-center": {
        "CaseCommandCenter.case_id",
        "CaseCommandCenter.purpose",
        "CaseCommandCenter.status",
        "CaseCommandCenter.Latest Showcase Case",
        "CaseCommandCenter.Current Decision ID",
        "CaseCommandCenter.Revenue At Risk",
        "CaseCommandCenter.OTIF Loss %",
        "CaseCommandCenter.Scenario Effective Time",
    },
    "actions-outcomes": {
        "ActionOutcomes.decision_id",
        "ActionOutcomes.action_kind",
        "ActionOutcomes.action_status",
        "ActionOutcomes.metric",
        "ActionOutcomes.observation_kind",
        "ActionOutcomes.Observed Variance",
        "ActionOutcomes.Projection Refresh Time",
        "ActionOutcomes.Scenario Effective Time",
    },
}

JSON_SCHEMAS = {
    "SupplyResponse.pbip": (
        "https://developer.microsoft.com/json-schemas/fabric/pbip/"
        "pbipProperties/1.0.0/schema.json"
    ),
    "SupplyResponse.SemanticModel/definition.pbism": (
        "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/"
        "definitionProperties/1.0.0/schema.json"
    ),
    "SupplyResponse.Report/definition.pbir": (
        "https://developer.microsoft.com/json-schemas/fabric/item/report/"
        "definitionProperties/2.0.0/schema.json"
    ),
    "SupplyResponse.Report/definition/version.json": (
        "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
        "versionMetadata/1.0.0/schema.json"
    ),
    "SupplyResponse.Report/definition/report.json": (
        "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
        "report/1.0.0/schema.json"
    ),
    "SupplyResponse.Report/definition/pages/pages.json": (
        "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
        "pagesMetadata/1.1.0/schema.json"
    ),
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _query_refs(value: object) -> list[str]:
    if isinstance(value, dict):
        matches = [value["queryRef"]] if isinstance(value.get("queryRef"), str) else []
        for child in value.values():
            matches.extend(_query_refs(child))
        return matches
    if isinstance(value, list):
        return [match for child in value for match in _query_refs(child)]
    return []


def _visual_files(page_name: str) -> list[Path]:
    return sorted((REPORT / "pages" / page_name / "visuals").glob("*/visual.json"))


def test_required_power_bi_artifacts_exist() -> None:
    required = [
        POWER_BI / "SupplyResponse.pbip",
        POWER_BI / "SupplyResponse.SemanticModel" / "definition.pbism",
        POWER_BI / "SupplyResponse.SemanticModel" / ".platform",
        SEMANTIC_MODEL / "model.tmdl",
        SEMANTIC_MODEL / "tables" / "CaseCommandCenter.tmdl",
        SEMANTIC_MODEL / "tables" / "ActionOutcomes.tmdl",
        POWER_BI / "SupplyResponse.Report" / "definition.pbir",
        POWER_BI / "SupplyResponse.Report" / ".platform",
        REPORT / "version.json",
        REPORT / "report.json",
        REPORT / "pages" / "pages.json",
        *(REPORT / "pages" / name / "page.json" for name in PAGES),
        ROOT / "fabric" / "deploy.py",
    ]

    assert [
        str(path.relative_to(ROOT)) for path in required if not path.is_file()
    ] == []


def test_platform_metadata_has_stable_exact_item_identity() -> None:
    expected = {
        "SupplyResponse.SemanticModel": {
            "type": "SemanticModel",
            "logicalId": "1808b468-5fe3-542e-9004-ae82d8cbd452",
        },
        "SupplyResponse.Report": {
            "type": "Report",
            "logicalId": "8ff233ca-a127-5ff7-a559-cfbbb6fc8046",
        },
    }
    for directory, identity in expected.items():
        assert _load(POWER_BI / directory / ".platform") == {
            "$schema": PLATFORM_SCHEMA,
            "metadata": {
                "type": identity["type"],
                "displayName": "SupplyResponse",
            },
            "config": {
                "version": "2.0",
                "logicalId": identity["logicalId"],
            },
        }


def test_fabric_cicd_discovers_exact_publishable_item_order() -> None:
    import importlib.metadata

    from fabric import deploy

    assert importlib.metadata.version("fabric-cicd") == "1.3.0"
    assert deploy._discover_publish_items(POWER_BI) == (
        ("SemanticModel", "SupplyResponse"),
        ("Report", "SupplyResponse"),
    )


def test_fabric_cicd_discovery_is_empty_without_platform_metadata(
    tmp_path: Path,
) -> None:
    from fabric import deploy

    repository = tmp_path / "power-bi"
    shutil.copytree(POWER_BI, repository)
    for platform in repository.glob("*/.platform"):
        platform.unlink()

    assert deploy._discover_publish_items(repository) == ()


def test_all_project_json_validates_offline_against_vendored_microsoft_schemas() -> (
    None
):
    from fabric import deploy

    manifest = ROOT / "fabric" / "schemas" / "microsoft" / "manifest.json"
    assert manifest.is_file()
    deploy._validate_offline_json_schemas(POWER_BI)


def test_project_json_files_declare_current_official_schemas() -> None:
    for relative_path, schema in JSON_SCHEMAS.items():
        assert _load(POWER_BI / relative_path)["$schema"] == schema

    for page_name in PAGES:
        page = _load(REPORT / "pages" / page_name / "page.json")
        assert page["$schema"] == (
            "https://developer.microsoft.com/json-schemas/fabric/item/report/"
            "definition/page/2.0.0/schema.json"
        )
        for visual_file in _visual_files(page_name):
            assert _load(visual_file)["$schema"] == (
                "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                "definition/visualContainer/2.9.0/schema.json"
            )

    for directory in ("SupplyResponse.SemanticModel", "SupplyResponse.Report"):
        assert _load(POWER_BI / directory / ".platform")["$schema"] == PLATFORM_SCHEMA


def test_power_bi_project_has_only_the_two_required_pages() -> None:
    pages = _load(REPORT / "pages" / "pages.json")
    assert pages == {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
            "pagesMetadata/1.1.0/schema.json"
        ),
        "pageOrder": list(PAGES),
        "activePageName": "command-center",
    }

    page_directories = sorted(
        path.name for path in (REPORT / "pages").iterdir() if path.is_dir()
    )
    assert page_directories == sorted(PAGES)
    assert {
        name: _load(REPORT / "pages" / name / "page.json")["displayName"]
        for name in PAGES
    } == PAGES


def test_pages_have_exact_identity_size_and_thirty_second_refresh() -> None:
    for page_name, display_name in PAGES.items():
        page = _load(REPORT / "pages" / page_name / "page.json")
        assert page["name"] == page_name
        assert page["displayName"] == display_name
        assert page["displayOption"] == "FitToPage"
        assert page["width"] == 1280
        assert page["height"] == 720
        page_refresh = page["objects"]["pageRefresh"]
        assert page_refresh == [
            {
                "properties": {
                    "show": True,
                    "refreshType": "FixedInterval",
                    "duration": 30,
                }
            }
        ]


def test_every_visual_is_schema_shaped_and_inside_its_page() -> None:
    required_top_level = {"$schema", "name", "position", "visual"}
    for page_name in PAGES:
        visual_files = _visual_files(page_name)
        assert visual_files, f"{page_name} has no visual containers"
        names: list[str] = []
        for visual_file in visual_files:
            visual_container = _load(visual_file)
            assert set(visual_container) <= required_top_level | {"filterConfig"}
            assert set(visual_container) >= required_top_level
            names.append(str(visual_container["name"]))
            assert visual_file.parent.name == visual_container["name"]
            position = visual_container["position"]
            assert set(position) == {"x", "y", "z", "width", "height", "tabOrder"}
            assert position["x"] >= 0 and position["y"] >= 0
            assert position["x"] + position["width"] <= 1280
            assert position["y"] + position["height"] <= 720
            assert set(visual_container["visual"]) <= {
                "visualType",
                "query",
                "objects",
                "visualContainerObjects",
            }
            assert isinstance(visual_container["visual"]["visualType"], str)
            query_state = visual_container["visual"]["query"]["queryState"]
            assert query_state
            for projection_state in query_state.values():
                assert set(projection_state) == {"projections"}
                for projection in projection_state["projections"]:
                    assert set(projection) <= {"field", "queryRef", "displayName"}
                    assert set(projection) >= {"field", "queryRef"}
                    field = projection["field"]
                    assert set(field) in ({"Column"}, {"Measure"}, {"Aggregation"})
                    if "Aggregation" in field:
                        aggregation = field["Aggregation"]
                        assert set(aggregation) == {"Expression", "Function"}
                        assert aggregation["Function"] in range(9)
                        assert set(aggregation["Expression"]) == {"Column"}
                        expression = aggregation["Expression"]["Column"]
                    else:
                        expression = next(iter(field.values()))
                    assert set(expression) == {"Expression", "Property"}
                    assert set(expression["Expression"]) == {"SourceRef"}
                    assert set(expression["Expression"]["SourceRef"]) == {"Entity"}
        assert len(names) == len(set(names))


def test_visual_query_refs_exactly_match_each_page_allowlist() -> None:
    for page_name, expected in QUERY_REF_ALLOWLIST.items():
        query_refs: list[str] = []
        for visual_file in _visual_files(page_name):
            query_refs.extend(_query_refs(_load(visual_file)))
        assert set(query_refs) == expected
        assert all(query_ref in expected for query_ref in query_refs)


def test_showcase_table_binds_latest_case_and_showcase_filters() -> None:
    table = _load(
        REPORT
        / "pages"
        / "command-center"
        / "visuals"
        / "showcase-cases"
        / "visual.json"
    )
    projections = table["visual"]["query"]["queryState"]["Values"]["projections"]
    assert {projection["queryRef"] for projection in projections} >= {
        "CaseCommandCenter.case_id",
        "CaseCommandCenter.purpose",
        "CaseCommandCenter.Latest Showcase Case",
    }
    filters = table["filterConfig"]["filters"]
    assert {item["name"] for item in filters} == {
        "FilterShowcasePurpose",
        "FilterLatestShowcaseCase",
    }
    purpose = next(item for item in filters if item["name"] == "FilterShowcasePurpose")
    latest = next(
        item for item in filters if item["name"] == "FilterLatestShowcaseCase"
    )
    assert purpose["field"]["Column"]["Property"] == "purpose"
    assert purpose["filter"]["Where"][0]["Condition"]["In"]["Values"] == [
        [{"Literal": {"Value": "'showcase'"}}]
    ]
    comparison = latest["filter"]["Where"][0]["Condition"]["Comparison"]
    assert comparison["ComparisonKind"] == 0
    assert comparison["Left"]["Column"]["Property"] == "case_id"
    assert comparison["Right"]["Measure"]["Property"] == "Latest Showcase Case"


def test_active_cases_card_counts_distinct_non_closed_cases() -> None:
    card = _load(
        REPORT / "pages" / "command-center" / "visuals" / "active-cases" / "visual.json"
    )
    projection = card["visual"]["query"]["queryState"]["Data"]["projections"][0]
    aggregation = projection["field"]["Aggregation"]
    assert projection["queryRef"] == "CaseCommandCenter.case_id"
    assert aggregation["Function"] == 2
    assert aggregation["Expression"]["Column"]["Property"] == "case_id"
    status_filter = card["filterConfig"]["filters"]
    assert [item["name"] for item in status_filter] == ["FilterActiveCases"]
    condition = status_filter[0]["filter"]["Where"][0]["Condition"]
    assert condition["Not"]["Expression"]["In"]["Values"] == [
        [{"Literal": {"Value": "'closed'"}}]
    ]


def test_actions_page_binds_scenario_effective_time_card() -> None:
    scenario = _load(
        REPORT
        / "pages"
        / "actions-outcomes"
        / "visuals"
        / "scenario-effective-time"
        / "visual.json"
    )
    projections = scenario["visual"]["query"]["queryState"]["Data"]["projections"]
    assert [projection["queryRef"] for projection in projections] == [
        "ActionOutcomes.Scenario Effective Time"
    ]
    assert projections[0]["field"]["Measure"]["Property"] == ("Scenario Effective Time")


def test_action_and_observation_visuals_have_locked_record_type_scope() -> None:
    expected = {
        "action-status": "action",
        "observation-kind": "observation",
        "predicted-observed-variance": "observation",
    }
    for visual_name, record_type in expected.items():
        visual = _load(
            REPORT
            / "pages"
            / "actions-outcomes"
            / "visuals"
            / visual_name
            / "visual.json"
        )
        filters = visual["filterConfig"]["filters"]
        assert [item["name"] for item in filters] == [
            f"Filter{visual_name.title().replace('-', '')}RecordType"
        ]
        assert filters[0]["field"]["Column"]["Property"] == "record_type"
        values = filters[0]["filter"]["Where"][0]["Condition"]["In"]["Values"]
        assert values == [[{"Literal": {"Value": f"'{record_type}'"}}]]
        assert filters[0]["isHiddenInViewMode"] is True
        assert filters[0]["isLockedInViewMode"] is True

    variance = _load(
        REPORT
        / "pages"
        / "actions-outcomes"
        / "visuals"
        / "predicted-observed-variance"
        / "visual.json"
    )
    query_state = variance["visual"]["query"]["queryState"]
    assert query_state["Category"]["projections"][0]["queryRef"] == (
        "ActionOutcomes.metric"
    )
    assert query_state["Series"]["projections"][0]["queryRef"] == (
        "ActionOutcomes.observation_kind"
    )
    assert query_state["Y"]["projections"][0]["queryRef"] == (
        "ActionOutcomes.Observed Variance"
    )


def test_latest_showcase_decision_is_the_default_visual_context() -> None:
    actions_page = _load(REPORT / "pages" / "actions-outcomes" / "page.json")
    actions_filters = actions_page["filterConfig"]["filters"]
    assert [item["name"] for item in actions_filters] == [
        "FilterCurrentShowcaseDecision"
    ]
    actions_comparison = actions_filters[0]["filter"]["Where"][0]["Condition"][
        "Comparison"
    ]
    assert actions_comparison["ComparisonKind"] == 0
    assert actions_comparison["Left"]["Column"]["Property"] == "decision_id"
    assert actions_comparison["Right"]["Measure"]["Property"] == ("Current Decision ID")

    current_decision = _load(
        REPORT
        / "pages"
        / "command-center"
        / "visuals"
        / "current-decision"
        / "visual.json"
    )
    latest_filter = current_decision["filterConfig"]["filters"]
    assert [item["name"] for item in latest_filter] == [
        "FilterCurrentDecisionLatestCase"
    ]
    current_comparison = latest_filter[0]["filter"]["Where"][0]["Condition"][
        "Comparison"
    ]
    assert current_comparison["Left"]["Column"]["Property"] == "case_id"
    assert current_comparison["Right"]["Measure"]["Property"] == (
        "Latest Showcase Case"
    )


def test_report_has_no_embedded_rows_or_environment_specific_identifiers() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in POWER_BI.rglob("*")
        if path.is_file() and path.name != ".platform"
    )
    lowered = text.lower()
    assert '"staticdata":' not in lowered
    assert '"datavalues":' not in lowered
    assert '"rows":' not in lowered
    assert "analysis.windows.net" not in lowered
    assert not re.search(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", lowered)
    assert ".datawarehouse.fabric.microsoft.com" not in lowered


def test_semantic_model_exposes_decision_and_simulation_measures() -> None:
    text = "\n".join(path.read_text() for path in SEMANTIC_MODEL.rglob("*.tmdl"))
    for required in (
        "Latest Showcase Case",
        "Current Decision ID",
        "Revenue At Risk",
        "OTIF Loss %",
        "Action Completion %",
        "Observed Variance",
        "Projection Refresh Time",
        "Scenario Effective Time",
    ):
        assert f"measure '{required}'" in text


def test_tmdl_folder_has_strong_structural_contract() -> None:
    model = (SEMANTIC_MODEL / "model.tmdl").read_text(encoding="utf-8")
    assert model.startswith("model Model\n")
    assert "\tculture:" not in model
    assert "  culture: en-US\n" in model
    assert "  defaultPowerBIDataSourceVersion: powerBI_V3\n" in model
    assert re.findall(r"^ref table (\w+)$", model, re.MULTILINE) == [
        "CaseCommandCenter",
        "ActionOutcomes",
    ]

    expected = {
        "CaseCommandCenter": {
            "columns": {
                "case_id",
                "purpose",
                "status",
                "runtime_mode",
                "scenario_effective_time",
                "recommended_option_id",
                "revenue_at_risk",
                "otif_loss_percentage",
                "decision_id",
                "decision_kind",
                "decided_at",
            },
            "view": "analytics.case_command_center",
        },
        "ActionOutcomes": {
            "columns": {
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
            },
            "view": "analytics.action_outcomes",
        },
    }
    for table_name, contract in expected.items():
        text = (SEMANTIC_MODEL / "tables" / f"{table_name}.tmdl").read_text()
        assert text.startswith(f"table {table_name}\n")
        assert "\t" not in text
        assert (
            set(re.findall(r"^  column ([a-z_]+)$", text, re.MULTILINE))
            == contract["columns"]
        )
        assert re.findall(rf"^  partition ({table_name}) = m$", text, re.MULTILINE) == [
            table_name
        ]
        assert "    mode: directQuery\n" in text
        assert f"SELECT * FROM {contract['view']}" in text
        assert text.count("Sql.Database(") == 1

    case_text = (SEMANTIC_MODEL / "tables" / "CaseCommandCenter.tmdl").read_text()
    action_text = (SEMANTIC_MODEL / "tables" / "ActionOutcomes.tmdl").read_text()
    assert 'CaseCommandCenter[purpose] = "showcase"' in case_text
    assert "CaseCommandCenter[decided_at], DESC" in case_text
    assert "CaseCommandCenter[case_id], DESC" in case_text
    assert "MAXX(LatestRow, CaseCommandCenter[case_id])" in case_text
    assert "  column observation_kind\n" in action_text
    assert "    sourceColumn: observation_kind\n" in action_text
    assert "ActionOutcomes[projection_updated_at]" in action_text
    assert "ActionOutcomes[observed_value]" in action_text
    assert "ActionOutcomes[predicted_value]" in action_text
    assert "measure 'Scenario Effective Time'" in action_text
    assert "ActionOutcomes[scenario_effective_time]" in action_text

    variance = re.search(
        r"  measure 'Observed Variance' =\n(?P<body>.*?)(?=\n  measure |\n  partition )",
        action_text,
        re.DOTALL,
    )
    assert variance is not None
    variance_body = variance.group("body")
    assert "ALL(ActionOutcomes)" not in variance_body
    assert "AVERAGEX" not in variance_body
    assert "SELECTEDVALUE(ActionOutcomes[metric])" in variance_body
    assert "SELECTEDVALUE(ActionOutcomes[record_type])" in variance_body
    assert "VAR DecisionId = [Current Decision ID]" in variance_body
    assert (
        "CALCULATE(SELECTEDVALUE(ActionOutcomes[predicted_value]), "
        "ActionOutcomes[decision_id] = DecisionId)"
    ) in variance_body
    assert (
        "CALCULATE(SELECTEDVALUE(ActionOutcomes[observed_value]), "
        "ActionOutcomes[decision_id] = DecisionId)"
    ) in variance_body
    assert "REMOVEFILTERS" not in variance_body
    assert "IFERROR(VALUE(PredictedText), BLANK())" in variance_body
    assert "IFERROR(VALUE(ObservedText), BLANK())" in variance_body
    assert "ABS(Predicted)" in variance_body
    assert '"remaining_alpha_recovery_date"' not in variance_body


FROZEN_OBSERVATIONS = (
    ("alpha_expedited_quantity", "3000", "2800", "units"),
    ("dallas_transfer_quantity", "1500", "1500", "units"),
    ("total_response_arranged_supply", "4500", "4300", "units"),
    ("uncovered_part_demand", "2300", "2500", "units"),
    ("response_cost", "24750", "25000", "USD"),
    ("protected_customer_orders", "1", "1", "orders"),
    ("revenue_protected", "580000", "580000", "USD"),
    ("margin_protected", "203000", "203000", "USD"),
    ("otif_loss_percentage", "50", "50", "percent"),
    ("remaining_alpha_recovery_date", "unknown", "2026-09-12", "date"),
)
SUPPORTED_VARIANCE_METRICS = {metric for metric, *_ in FROZEN_OBSERVATIONS[:-1]}


def _relative_variance_oracle(
    metric: str, predicted: str, observed: str
) -> Decimal | None:
    if metric not in SUPPORTED_VARIANCE_METRICS:
        return None
    predicted_number = Decimal(predicted)
    if predicted_number == 0:
        return None
    return (Decimal(observed) - predicted_number) / abs(predicted_number)


@pytest.mark.parametrize(
    ("metric", "predicted", "observed", "unit"), FROZEN_OBSERVATIONS
)
def test_observed_variance_reference_oracle_is_per_metric_and_safe(
    metric: str, predicted: str, observed: str, unit: str
) -> None:
    result = _relative_variance_oracle(metric, predicted, observed)
    if metric == "remaining_alpha_recovery_date":
        assert unit == "date"
        assert result is None
    else:
        assert result == (Decimal(observed) - Decimal(predicted)) / abs(
            Decimal(predicted)
        )


def test_observed_variance_oracle_returns_blank_for_unknown_and_zero_baseline() -> None:
    assert _relative_variance_oracle("unknown_metric", "10", "11") is None
    assert _relative_variance_oracle("response_cost", "0", "1") is None


def test_model_links_actions_to_the_selected_decision() -> None:
    relationship_file = SEMANTIC_MODEL / "relationships.tmdl"
    relationship = relationship_file.read_text(encoding="utf-8")
    assert re.search(r"^relationship DecisionLink$", relationship, re.MULTILINE)
    assert "  fromColumn: ActionOutcomes.decision_id\n" in relationship
    assert "  toColumn: CaseCommandCenter.decision_id\n" in relationship


def test_tmdl_deserializes_with_microsoft_tom_parser() -> None:
    if shutil.which("dotnet") is None:
        raise AssertionError(
            "dotnet is required for the official Microsoft TMDL parser"
        )
    environment = os.environ.copy()
    environment["DOTNET_CLI_HOME"] = "/tmp/supply-response-dotnet-home"
    environment["NUGET_PACKAGES"] = "/tmp/supply-response-nuget-packages"
    result = subprocess.run(
        [
            "dotnet",
            "run",
            "--project",
            "tests/fabric/tmdl-validator/TmdlValidator.csproj",
            "--",
            str(SEMANTIC_MODEL),
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TMDL deserialized successfully" in result.stdout


def test_deploy_dry_run_is_deterministic_and_does_not_authenticate() -> None:
    environment = {
        "PATH": os.environ["PATH"],
        "SUPPLY_RESPONSE_ALLOWED_TENANT_ID": "00000000-0000-4000-8000-000000000001",
        "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID": "00000000-0000-4000-8000-000000000002",
        "FABRIC_SQL_SERVER": "server.example.invalid",
        "FABRIC_SQL_DATABASE": "database-name",
    }
    result = subprocess.run(
        [sys.executable, "fabric/deploy.py", "--dry-run"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "Task 13 Power BI deployment preflight passed.",
        "Dry run only: no authentication, network calls, or workspace changes were made.",
    ]


def test_deploy_preflight_stages_complete_environment_substitution(
    tmp_path: Path,
) -> None:
    from fabric import deploy

    values = {
        "SUPPLY_RESPONSE_ALLOWED_TENANT_ID": "00000000-0000-4000-8000-000000000001",
        "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID": "00000000-0000-4000-8000-000000000002",
        "FABRIC_SQL_SERVER": "server.example.invalid",
        "FABRIC_SQL_DATABASE": "database-name",
    }
    repository = deploy._staged_repository(values, tmp_path)
    source = (
        repository / "SupplyResponse.SemanticModel" / "definition" / "expressions.tmdl"
    ).read_text(encoding="utf-8")
    parameters = _load(repository / "parameter.yml")
    assert "__FABRIC_SQL_SERVER__" in source
    assert "__FABRIC_SQL_DATABASE__" in source
    assert values["FABRIC_SQL_SERVER"] not in source
    assert values["FABRIC_SQL_DATABASE"] not in source
    assert parameters == {
        "find_replace": [
            {
                "find_value": "__FABRIC_SQL_SERVER__",
                "replace_value": {"dev": values["FABRIC_SQL_SERVER"]},
                "item_type": "SemanticModel",
                "file_path": "**/expressions.tmdl",
            },
            {
                "find_value": "__FABRIC_SQL_DATABASE__",
                "replace_value": {"dev": values["FABRIC_SQL_DATABASE"]},
                "item_type": "SemanticModel",
                "file_path": "**/expressions.tmdl",
            },
        ]
    }


def test_staged_preflight_fails_on_missing_extra_or_broken_items(
    tmp_path: Path,
) -> None:
    from fabric import deploy

    values = {
        "SUPPLY_RESPONSE_ALLOWED_TENANT_ID": "00000000-0000-4000-8000-000000000001",
        "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID": "00000000-0000-4000-8000-000000000002",
        "FABRIC_SQL_SERVER": "server.example.invalid",
        "FABRIC_SQL_DATABASE": "database-name",
    }
    repository = deploy._staged_repository(values, tmp_path / "missing")
    (repository / "SupplyResponse.Report" / ".platform").unlink()
    with pytest.raises(
        deploy.PreflightError, match="platform|SemanticModel then Report"
    ):
        deploy._validate_staged_repository(repository, values)

    repository = deploy._staged_repository(values, tmp_path / "broken")
    definition = repository / "SupplyResponse.Report" / "definition.pbir"
    broken = _load(definition)
    broken["datasetReference"]["byPath"]["path"] = "../Missing.SemanticModel"
    definition.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(deploy.PreflightError, match="datasetReference"):
        deploy._validate_staged_repository(repository, values)

    repository = deploy._staged_repository(values, tmp_path / "broken-pbip")
    project = repository / "SupplyResponse.pbip"
    broken = _load(project)
    broken["artifacts"][0]["report"]["path"] = "Missing.Report"
    project.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(deploy.PreflightError, match="PBIP report path"):
        deploy._validate_staged_repository(repository, values)

    repository = deploy._staged_repository(values, tmp_path / "extra")
    extra = repository / "Extra.Report"
    extra.mkdir()
    (extra / ".platform").write_text(
        json.dumps(
            {
                "$schema": PLATFORM_SCHEMA,
                "metadata": {"type": "Report", "displayName": "Extra"},
                "config": {
                    "version": "2.0",
                    "logicalId": "11111111-1111-5111-8111-111111111111",
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        deploy.PreflightError, match="exactly SemanticModel then Report"
    ):
        deploy._validate_staged_repository(repository, values)


def test_deploy_fails_closed_on_missing_or_partial_environment() -> None:
    result = subprocess.run(
        [sys.executable, "fabric/deploy.py", "--dry-run"],
        cwd=ROOT,
        env={"PATH": "/usr/bin:/bin", "FABRIC_SQL_SERVER": "partial.invalid"},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    for name in (
        "SUPPLY_RESPONSE_ALLOWED_TENANT_ID",
        "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID",
        "FABRIC_SQL_DATABASE",
    ):
        assert name in result.stderr


def test_deploy_imports_sdks_only_after_preflight() -> None:
    deploy = (ROOT / "fabric" / "deploy.py").read_text(encoding="utf-8")
    assert "from azure.identity import AzureCliCredential" not in deploy
    assert "from fabric_cicd import FabricWorkspace" not in deploy
    assert "import fabric_cicd" not in deploy
    assert "AzureCliCredential" in deploy
    assert "FabricWorkspace" in deploy
    assert "publish_all_items" in deploy
    assert 'item_type_in_scope=["SemanticModel", "Report"]' in deploy


def test_live_contract_queries_required_measures_and_variance_contexts() -> None:
    live_test = (ROOT / "tests" / "fabric" / "test_power_bi_live.py").read_text()
    for required in (
        "CaseCommandCenter[Current Decision ID]",
        "ActionOutcomes[Action Completion %]",
        "ActionOutcomes[Observed Variance]",
        "ActionOutcomes[Scenario Effective Time]",
        "ActionOutcomes[Projection Refresh Time]",
        'ActionOutcomes[metric] = "response_cost"',
        'ActionOutcomes[metric] = "remaining_alpha_recovery_date"',
    ):
        assert required in live_test


def test_power_bi_live_collection_fails_closed_on_partial_configuration() -> None:
    environment = {
        "PATH": os.environ["PATH"],
        "SUPPLY_RESPONSE_API_BASE_URL": "https://api.example.invalid",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "tests/fabric/test_power_bi_live.py",
            "-q",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Power BI live settings must be configured together" in output
    assert "SUPPLY_RESPONSE_ALLOWED_TENANT_ID" in output
    assert "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID" in output
    assert "SUPPLY_RESPONSE_POWER_BI_SEMANTIC_MODEL_ID" in output
