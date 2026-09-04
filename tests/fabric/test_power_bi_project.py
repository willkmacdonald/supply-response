from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWER_BI = ROOT / "fabric" / "power-bi"
SEMANTIC_MODEL = POWER_BI / "SupplyResponse.SemanticModel" / "definition"
REPORT = POWER_BI / "SupplyResponse.Report" / "definition"
PLATFORM_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/"
    "platformProperties/2.0.0/schema.json"
)
SCHEMA_CATALOG = ROOT / "fabric" / "schemas" / "microsoft"
MICROSOFT_SCHEMA_SOURCE = "https://developer.microsoft.com/json-schemas/fabric/"
MICROSOFT_SCHEMA_ROOTS = (
    PLATFORM_SCHEMA,
    "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json",
)

PAGES = {
    "command-center": "Command Center",
    "actions-outcomes": "Actions and Outcomes",
}

EXPECTED_VISUAL_IDS = {
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

QUERY_REF_ALLOWLIST = {
    "command-center": {
        "CaseCommandCenter.case_id",
        "CaseCommandCenter.purpose",
        "CaseCommandCenter.status",
        "CaseCommandCenter.Latest Showcase Case",
        "CaseCommandCenter.Current Decision ID",
        "CaseCommandCenter.Current Decision Status",
        "CaseCommandCenter.Revenue At Risk",
        "CaseCommandCenter.OTIF Loss %",
        "CaseCommandCenter.Scenario Effective Time",
    },
    "actions-outcomes": {
        "CaseCommandCenter.Current Decision ID",
        "ActionOutcomes.action_kind",
        "ActionOutcomes.Current Action Status",
        "ActionOutcomes.metric",
        "ActionOutcomes.observation_kind",
        "ActionOutcomes.Current Observation Kind",
        "ActionOutcomes.Observed Variance",
        "ActionOutcomes.Projection Refresh Time",
        "ActionOutcomes.Action Scenario Effective Time",
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


def _copy_schema_catalog(tmp_path: Path) -> Path:
    catalog = tmp_path / "microsoft"
    shutil.copytree(SCHEMA_CATALOG, catalog)
    return catalog


def _mutate_manifest(catalog: Path, mutation) -> None:
    manifest_path = catalog / "manifest.json"
    manifest = _load(manifest_path)
    mutation(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def test_schema_manifest_has_exact_approved_source_roots_and_reference_closure() -> (
    None
):
    from fabric import deploy

    manifest = _load(SCHEMA_CATALOG / "manifest.json")
    assert deploy.MICROSOFT_SCHEMA_SOURCE == MICROSOFT_SCHEMA_SOURCE
    assert deploy.MICROSOFT_SCHEMA_ROOTS == MICROSOFT_SCHEMA_ROOTS
    assert manifest["source"] == MICROSOFT_SCHEMA_SOURCE
    assert tuple(manifest["roots"]) == MICROSOFT_SCHEMA_ROOTS
    deploy._validate_offline_json_schemas(POWER_BI)


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("off-host", "origin"),
        ("unused", "closure"),
        ("missing-transitive", "transitive|missing"),
        ("extra-root", "roots"),
        ("wrong-source", "source"),
        ("bad-hash", "integrity"),
        ("path-traversal", "path"),
        ("duplicate-file", "duplicate"),
        ("duplicate-hash", "duplicate"),
    ),
)
def test_schema_manifest_rejects_untrusted_or_nonclosed_catalogs(
    tmp_path: Path, case: str, message: str
) -> None:
    from fabric import deploy

    catalog = _copy_schema_catalog(tmp_path)

    def mutate(manifest: dict[str, Any]) -> None:
        schemas = manifest["schemas"]
        assert isinstance(schemas, dict)
        if case == "off-host":
            first = next(iter(schemas.values()))
            schemas["https://example.com/foreign-schema.json"] = dict(first)
        elif case == "unused":
            content = b'{"$schema":"http://json-schema.org/draft-07/schema#","type":"object"}\n'
            digest = hashlib.sha256(content).hexdigest()
            filename = f"{digest[:20]}.json"
            (catalog / filename).write_bytes(content)
            schemas[
                "https://developer.microsoft.com/json-schemas/fabric/unused/schema.json"
            ] = {
                "file": filename,
                "sha256": digest,
            }
        elif case == "missing-transitive":
            url = next(url for url in schemas if "filterConfiguration" in url)
            filename = schemas.pop(url)["file"]
            (catalog / filename).unlink()
        elif case == "extra-root":
            manifest["roots"].append(
                "https://developer.microsoft.com/json-schemas/fabric/extra/schema.json"
            )
        elif case == "wrong-source":
            manifest["source"] = "https://developer.microsoft.com/json-schemas/"
        elif case == "bad-hash":
            next(iter(schemas.values()))["sha256"] = "0" * 64
        elif case == "path-traversal":
            next(iter(schemas.values()))["file"] = "../manifest.json"
        elif case == "duplicate-file":
            first, second = list(schemas.values())[:2]
            second["file"] = first["file"]
            second["sha256"] = first["sha256"]
        elif case == "duplicate-hash":
            first, second = list(schemas.values())[:2]
            second["sha256"] = first["sha256"]
        else:  # pragma: no cover - parametrization is exhaustive
            raise AssertionError(case)

    _mutate_manifest(catalog, mutate)
    with pytest.raises(deploy.PreflightError, match=message):
        deploy._validate_offline_json_schemas(POWER_BI, schema_catalog=catalog)


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


def _copy_power_bi(tmp_path: Path, name: str) -> Path:
    repository = tmp_path / name
    shutil.copytree(POWER_BI, repository)
    return repository


def _staged_visual_mutation_repository(tmp_path: Path, name: str) -> Path:
    repository = _copy_power_bi(tmp_path, name)
    (repository / "parameter.yml").write_text(
        json.dumps(
            {
                "find_replace": [
                    {
                        "find_value": "__FABRIC_SQL_SERVER__",
                        "replace_value": {"dev": "server.example.invalid"},
                        "item_type": "SemanticModel",
                        "file_path": "**/expressions.tmdl",
                    },
                    {
                        "find_value": "__FABRIC_SQL_DATABASE__",
                        "replace_value": {"dev": "database-name"},
                        "item_type": "SemanticModel",
                        "file_path": "**/expressions.tmdl",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return repository


VISUAL_PREFLIGHT_VALUES = {
    "SUPPLY_RESPONSE_ALLOWED_TENANT_ID": "00000000-0000-4000-8000-000000000001",
    "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID": "00000000-0000-4000-8000-000000000002",
    "FABRIC_SQL_SERVER": "server.example.invalid",
    "FABRIC_SQL_DATABASE": "database-name",
}


def _visual_path(repository: Path, page: str, visual: str) -> Path:
    return (
        repository
        / "SupplyResponse.Report"
        / "definition"
        / "pages"
        / page
        / "visuals"
        / visual
        / "visual.json"
    )


def _mutate_projection_field_queryref_disagreement(value: dict[str, Any]) -> None:
    projection = value["visual"]["query"]["queryState"]["Data"]["projections"][0]
    projection["field"]["Measure"]["Property"] = "Revenue At Risk"


def _mutate_projection_measure_to_column(value: dict[str, Any]) -> None:
    projection = value["visual"]["query"]["queryState"]["Data"]["projections"][0]
    projection["field"] = {
        "Column": {
            "Expression": {"SourceRef": {"Entity": "ActionOutcomes"}},
            "Property": "decision_id",
        }
    }


def _mutate_aggregation_function(value: dict[str, Any]) -> None:
    projection = value["visual"]["query"]["queryState"]["Data"]["projections"][0]
    projection["field"]["Aggregation"]["Function"] = 0


def _mutate_projection_display_name(value: dict[str, Any]) -> None:
    projection = value["visual"]["query"]["queryState"]["Data"]["projections"][0]
    projection["displayName"] = "Different Decision Label"


def _mutate_projection_role(value: dict[str, Any]) -> None:
    query_state = value["visual"]["query"]["queryState"]
    query_state["Values"] = query_state.pop("Data")


def _mutate_filter_type(value: dict[str, Any]) -> None:
    value["filterConfig"]["filters"][0]["type"] = "Advanced"


def _mutate_unknown_projection_shape(value: dict[str, Any]) -> None:
    projection = value["visual"]["query"]["queryState"]["Data"]["projections"][0]
    projection["hidden"] = True


def _mutate_unknown_filter_shape(value: dict[str, Any]) -> None:
    value["filterConfig"]["filters"][0]["ordinal"] = 0


@pytest.mark.parametrize(
    ("page", "visual", "mutation"),
    [
        (
            "actions-outcomes",
            "decision-id",
            _mutate_projection_field_queryref_disagreement,
        ),
        ("actions-outcomes", "decision-id", _mutate_projection_measure_to_column),
        ("command-center", "active-cases", _mutate_aggregation_function),
        ("actions-outcomes", "decision-id", _mutate_projection_display_name),
        ("actions-outcomes", "decision-id", _mutate_projection_role),
        ("actions-outcomes", "action-status", _mutate_filter_type),
        ("actions-outcomes", "decision-id", _mutate_unknown_projection_shape),
        ("actions-outcomes", "action-status", _mutate_unknown_filter_shape),
    ],
    ids=(
        "field-queryref-disagreement",
        "measure-to-column",
        "aggregation-function",
        "display-name",
        "role",
        "filter-type",
        "unknown-projection-shape",
        "unknown-filter-shape",
    ),
)
def test_staged_preflight_rejects_schema_valid_visual_semantic_mutations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    page: str,
    visual: str,
    mutation: Any,
) -> None:
    from fabric import deploy

    repository = _staged_visual_mutation_repository(tmp_path, mutation.__name__)
    path = _visual_path(repository, page, visual)
    value = _load(path)
    mutation(value)
    path.write_text(json.dumps(value), encoding="utf-8")

    # Every adversarial mutation is accepted by Microsoft's declared JSON schema.
    # The local semantic contract must therefore supply the fail-closed boundary.
    deploy._validate_offline_json_schemas(repository)
    monkeypatch.setattr(deploy, "_validate_tmdl", lambda _: None)
    with pytest.raises(deploy.PreflightError, match="visual"):
        deploy._validate_staged_repository(repository, VISUAL_PREFLIGHT_VALUES)


def test_preflight_has_exact_visual_inventory_and_per_visual_contracts() -> None:
    from fabric import deploy

    assert {
        page: tuple(visuals) for page, visuals in deploy.EXPECTED_VISUALS.items()
    } == EXPECTED_VISUAL_IDS
    deploy._validate_visual_inventory(POWER_BI / "SupplyResponse.Report" / "definition")


def test_visual_inventory_rejects_schema_valid_thirteenth_reused_queryref(
    tmp_path: Path,
) -> None:
    from fabric import deploy

    repository = _copy_power_bi(tmp_path, "extra")
    source = (
        repository
        / "SupplyResponse.Report"
        / "definition"
        / "pages"
        / "actions-outcomes"
        / "visuals"
        / "decision-id"
        / "visual.json"
    )
    extra = source.parents[1] / "extra-decision-id" / "visual.json"
    extra.parent.mkdir()
    visual = _load(source)
    visual["name"] = "extra-decision-id"
    extra.write_text(json.dumps(visual), encoding="utf-8")
    deploy._validate_offline_json_schemas(repository)

    with pytest.raises(deploy.PreflightError, match="visual inventory"):
        deploy._validate_visual_inventory(
            repository / "SupplyResponse.Report" / "definition"
        )


def test_visual_inventory_rejects_swapped_or_missing_visuals(tmp_path: Path) -> None:
    from fabric import deploy

    repository = _copy_power_bi(tmp_path, "swapped")
    visuals = (
        repository
        / "SupplyResponse.Report"
        / "definition"
        / "pages"
        / "actions-outcomes"
        / "visuals"
    )
    action_path = visuals / "action-status" / "visual.json"
    decision_path = visuals / "decision-id" / "visual.json"
    action = _load(action_path)
    decision = _load(decision_path)
    action["name"] = "decision-id"
    decision["name"] = "action-status"
    action_path.write_text(json.dumps(decision), encoding="utf-8")
    decision_path.write_text(json.dumps(action), encoding="utf-8")
    with pytest.raises(deploy.PreflightError, match="visual contract"):
        deploy._validate_visual_inventory(
            repository / "SupplyResponse.Report" / "definition"
        )

    repository = _copy_power_bi(tmp_path, "missing")
    missing = (
        repository
        / "SupplyResponse.Report"
        / "definition"
        / "pages"
        / "command-center"
        / "visuals"
        / "otif-loss"
        / "visual.json"
    )
    missing.unlink()
    with pytest.raises(deploy.PreflightError, match="visual inventory"):
        deploy._validate_visual_inventory(
            repository / "SupplyResponse.Report" / "definition"
        )


def test_visual_inventory_rejects_wrong_page_and_altered_locked_filter(
    tmp_path: Path,
) -> None:
    from fabric import deploy

    repository = _copy_power_bi(tmp_path, "wrong-page")
    pages = repository / "SupplyResponse.Report" / "definition" / "pages"
    source = pages / "command-center" / "visuals" / "otif-loss"
    destination = pages / "actions-outcomes" / "visuals" / "otif-loss"
    shutil.move(source, destination)
    with pytest.raises(deploy.PreflightError, match="visual inventory"):
        deploy._validate_visual_inventory(
            repository / "SupplyResponse.Report" / "definition"
        )

    repository = _copy_power_bi(tmp_path, "altered-filter")
    action = (
        repository
        / "SupplyResponse.Report"
        / "definition"
        / "pages"
        / "actions-outcomes"
        / "visuals"
        / "action-status"
        / "visual.json"
    )
    visual = _load(action)
    values = visual["filterConfig"]["filters"][0]["filter"]["Where"][0]["Condition"][
        "In"
    ]["Values"]
    values[0][0]["Literal"]["Value"] = "'observation'"
    action.write_text(json.dumps(visual), encoding="utf-8")
    with pytest.raises(deploy.PreflightError, match="visual filter"):
        deploy._validate_visual_inventory(
            repository / "SupplyResponse.Report" / "definition"
        )


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
        "ActionOutcomes.Action Scenario Effective Time"
    ]
    assert projections[0]["field"]["Measure"]["Property"] == (
        "Action Scenario Effective Time"
    )
    assert projections[0]["displayName"] == "Scenario Effective Time"


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
    assert actions_page.get("filterConfig", {}).get("filters", []) == []

    decision_card = _load(
        REPORT
        / "pages"
        / "actions-outcomes"
        / "visuals"
        / "decision-id"
        / "visual.json"
    )
    decision_projection = decision_card["visual"]["query"]["queryState"]["Data"][
        "projections"
    ][0]
    assert decision_projection["queryRef"] == "CaseCommandCenter.Current Decision ID"

    action_table = _load(
        REPORT
        / "pages"
        / "actions-outcomes"
        / "visuals"
        / "action-status"
        / "visual.json"
    )
    action_refs = {
        item["queryRef"]
        for item in action_table["visual"]["query"]["queryState"]["Values"][
            "projections"
        ]
    }
    assert action_refs == {
        "ActionOutcomes.action_kind",
        "ActionOutcomes.Current Action Status",
    }

    observation_card = _load(
        REPORT
        / "pages"
        / "actions-outcomes"
        / "visuals"
        / "observation-kind"
        / "visual.json"
    )
    observation_projection = observation_card["visual"]["query"]["queryState"]["Data"][
        "projections"
    ][0]
    assert observation_projection["queryRef"] == (
        "ActionOutcomes.Current Observation Kind"
    )

    current_decision = _load(
        REPORT
        / "pages"
        / "command-center"
        / "visuals"
        / "current-decision"
        / "visual.json"
    )
    assert current_decision.get("filterConfig", {}).get("filters", []) == []
    projections = current_decision["visual"]["query"]["queryState"]["Values"][
        "projections"
    ]
    assert [projection["queryRef"] for projection in projections] == [
        "CaseCommandCenter.Current Decision ID",
        "CaseCommandCenter.Current Decision Status",
    ]


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
        "Current Decision Status",
        "Current Action Status",
        "Current Observation Kind",
        "Revenue At Risk",
        "OTIF Loss %",
        "Action Completion %",
        "Observed Variance",
        "Projection Refresh Time",
        "Scenario Effective Time",
    ):
        assert f"measure '{required}'" in text


def test_semantic_model_measure_names_are_unique() -> None:
    declarations = [
        (match.group(1), path.relative_to(ROOT))
        for path in sorted(SEMANTIC_MODEL.rglob("*.tmdl"))
        for match in re.finditer(
            r"^  measure '([^']+)'", path.read_text(), re.MULTILINE
        )
    ]
    by_name: dict[str, list[Path]] = {}
    for name, path in declarations:
        by_name.setdefault(name, []).append(path)

    duplicates = {
        name: [str(path) for path in paths]
        for name, paths in by_name.items()
        if len(paths) > 1
    }
    assert duplicates == {}


def test_current_context_measures_are_scoped_to_latest_showcase_decision() -> None:
    case_text = (SEMANTIC_MODEL / "tables" / "CaseCommandCenter.tmdl").read_text(
        encoding="utf-8"
    )
    action_text = (SEMANTIC_MODEL / "tables" / "ActionOutcomes.tmdl").read_text(
        encoding="utf-8"
    )

    status_body = case_text.split("measure 'Current Decision Status' =", 1)[1].split(
        "measure 'Revenue At Risk' =", 1
    )[0]
    assert "VAR LatestCase = [Latest Showcase Case]" in status_body
    assert "REMOVEFILTERS(CaseCommandCenter)" in status_body
    assert "CaseCommandCenter[case_id] = LatestCase" in status_body

    action_status_body = action_text.split("measure 'Current Action Status' =", 1)[
        1
    ].split("measure 'Current Observation Kind' =", 1)[0]
    assert "VAR DecisionId = [Current Decision ID]" in action_status_body
    assert "REMOVEFILTERS(ActionOutcomes)" in action_status_body
    assert 'ActionOutcomes[record_type] = "action"' in action_status_body
    assert "ActionOutcomes[action_kind] = ActionKind" in action_status_body

    observation_body = action_text.split("measure 'Current Observation Kind' =", 1)[
        1
    ].split("measure 'Observed Variance' =", 1)[0]
    assert "VAR DecisionId = [Current Decision ID]" in observation_body
    assert "REMOVEFILTERS(ActionOutcomes)" in observation_body
    assert 'ActionOutcomes[record_type] = "observation"' in observation_body


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
    assert "measure 'Action Scenario Effective Time'" in action_text
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


def test_tmdl_validator_has_committed_locked_restore_configuration() -> None:
    validator = ROOT / "tests" / "fabric" / "tmdl-validator"
    project = (validator / "TmdlValidator.csproj").read_text(encoding="utf-8")
    lock = _load(validator / "packages.lock.json")
    assert "<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>" in project
    assert "<RestoreLockedMode>true</RestoreLockedMode>" in project
    assert lock["version"] == 1
    assert "net10.0" in lock["dependencies"]
    analysis_services = lock["dependencies"]["net10.0"]["Microsoft.AnalysisServices"]
    assert analysis_services["requested"] == "[19.114.8, 19.114.8]"
    assert analysis_services["resolved"] == "19.114.8"
    assert analysis_services["contentHash"]


def test_tmdl_validation_restores_builds_and_runs_from_clean_tracked_copy(
    tmp_path: Path,
) -> None:
    from fabric import deploy

    source = ROOT / "tests" / "fabric" / "tmdl-validator"
    validator = tmp_path / "tmdl-validator"
    validator.mkdir()
    tracked = ("TmdlValidator.csproj", "Program.cs", "packages.lock.json")
    for filename in tracked:
        shutil.copy2(source / filename, validator / filename)
    assert {path.name for path in validator.iterdir()} == set(tracked)
    assert not (validator / "bin").exists()
    assert not (validator / "obj").exists()

    deploy._validate_tmdl(
        SEMANTIC_MODEL,
        validator_project=validator / "TmdlValidator.csproj",
    )
    assert (validator / "obj" / "project.assets.json").is_file()
    assert (validator / "bin" / "Release" / "net10.0").is_dir()


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
        "Dry run only: no Azure/Fabric authentication or workspace changes were made.",
        "TOM validation uses a locked restore and may access public NuGet when packages are not cached.",
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


def test_publish_resolves_aliased_staged_repository_for_report_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fabric import deploy

    values = {
        "SUPPLY_RESPONSE_ALLOWED_TENANT_ID": "00000000-0000-4000-8000-000000000001",
        "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID": "00000000-0000-4000-8000-000000000002",
        "FABRIC_SQL_SERVER": "server.example.invalid",
        "FABRIC_SQL_DATABASE": "database-name",
    }
    monkeypatch.setattr(deploy, "_validate_staged_repository", lambda *_args: None)
    publish_physical_root = tmp_path / "publish-physical"
    publish_physical_root.mkdir()
    publish_aliased_root = tmp_path / "publish-aliased"
    publish_aliased_root.symlink_to(publish_physical_root, target_is_directory=True)
    captured: dict[str, object] = {}

    class CapturingWorkspace:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    class AliasTemporaryDirectory:
        def __enter__(self) -> str:
            return str(publish_aliased_root)

        def __exit__(self, *_args: object) -> None:
            return None

    class SyntheticCredential:
        def __init__(self, **_kwargs: object) -> None:
            pass

    class FakeIdentity:
        AzureCliCredential = SyntheticCredential

    class FakeFabricCicd:
        FabricWorkspace = CapturingWorkspace

        @staticmethod
        def publish_all_items(_workspace: CapturingWorkspace) -> None:
            return None

    def fake_import(module_name: str) -> object:
        if module_name == "azure.identity":
            return FakeIdentity
        if module_name == "fabric_cicd":
            return FakeFabricCicd
        raise AssertionError(f"unexpected import: {module_name}")

    monkeypatch.setattr(deploy.importlib, "import_module", fake_import)
    monkeypatch.setattr(
        deploy.tempfile,
        "TemporaryDirectory",
        lambda **_kwargs: AliasTemporaryDirectory(),
    )
    deploy._publish(values)

    assert captured["repository_directory"] == str(
        (publish_aliased_root / "power-bi").resolve()
    )
    assert captured["item_type_in_scope"] == ["SemanticModel", "Report"]
    assert isinstance(captured["token_credential"], SyntheticCredential)


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
        "ActionOutcomes[Action Scenario Effective Time]",
        "ActionOutcomes[Projection Refresh Time]",
        'ActionOutcomes[metric] = "response_cost"',
        'ActionOutcomes[metric] = "remaining_alpha_recovery_date"',
    ):
        assert required in live_test
    variance_source = live_test.split("variance_dax =", maxsplit=1)[1]
    assert variance_source.count('ActionOutcomes[observation_kind] = "simulated"') == 2


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
