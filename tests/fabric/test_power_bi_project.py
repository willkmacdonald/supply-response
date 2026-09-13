from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pytest

from fabric import report_model, report_pages

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
        if value.get("visualType") == "textbox":
            for binding in value.get("objects", {}).get("values", []):
                measure = binding["properties"]["expr"]["expr"]["Measure"]
                matches.append(
                    measure["Expression"]["SourceRef"]["Entity"]
                    + "."
                    + measure["Property"]
                )
        for child in value.values():
            matches.extend(_query_refs(child))
        return matches
    if isinstance(value, list):
        return [match for child in value for match in _query_refs(child)]
    return []


APPROVED_REPORT = report_pages.artifacts()
PAGES = {
    page: APPROVED_REPORT[f"pages/{page}/page.json"]["displayName"]
    for page in report_pages.ORDER
}
EXPECTED_VISUAL_IDS = {
    page: tuple(
        sorted(
            Path(name).parent.name
            for name in APPROVED_REPORT
            if name.startswith(f"pages/{page}/visuals/")
        )
    )
    for page in PAGES
}
QUERY_REF_ALLOWLIST = {
    page: {
        ref
        for name, value in APPROVED_REPORT.items()
        if name.startswith(f"pages/{page}/visuals/")
        for ref in _query_refs(value)
    }
    for page in PAGES
}


def _visual_files(page_name: str) -> list[Path]:
    return sorted((REPORT / "pages" / page_name / "visuals").glob("*/visual.json"))


def test_required_power_bi_artifacts_exist() -> None:
    required = [
        POWER_BI / "SupplyResponse.pbip",
        POWER_BI / "SupplyResponse.SemanticModel" / "definition.pbism",
        POWER_BI / "SupplyResponse.SemanticModel" / ".platform",
        SEMANTIC_MODEL / "model.tmdl",
        *(SEMANTIC_MODEL / "tables" / f"{table}.tmdl" for table in report_model.TABLES),
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


def test_power_bi_project_has_exactly_the_generated_operational_and_saved_pages() -> (
    None
):
    pages = _load(REPORT / "pages" / "pages.json")
    assert pages == {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
            "pagesMetadata/1.1.0/schema.json"
        ),
        "pageOrder": list(PAGES),
        "activePageName": "operations-overview",
    }

    page_directories = sorted(
        path.name for path in (REPORT / "pages").iterdir() if path.is_dir()
    )
    assert page_directories == sorted(PAGES)
    assert {
        name: _load(REPORT / "pages" / name / "page.json")["displayName"]
        for name in PAGES
    } == PAGES
    assert len(PAGES) == len(report_pages.OPERATIONAL_ORDER) + len(
        report_pages.LEGACY_ORDER
    )


def test_pages_have_exact_identity_size_and_thirty_second_refresh() -> None:
    for page_name, display_name in PAGES.items():
        page = _load(REPORT / "pages" / page_name / "page.json")
        assert page["name"] == page_name
        assert page["displayName"] == display_name
        assert page["displayOption"] == "FitToPage"
        assert page["width"] == 1280
        assert page["height"] == (
            720 if page_name in report_pages.OPERATIONAL_ORDER else 808
        )
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
        page = _load(REPORT / "pages" / page_name / "page.json")
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
            assert position["x"] + position["width"] <= page["width"]
            assert position["y"] + position["height"] <= page["height"]
            assert set(visual_container["visual"]) <= {
                "visualType",
                "query",
                "objects",
                "visualContainerObjects",
                "syncGroup",
                "expansionStates",
            }
            assert isinstance(visual_container["visual"]["visualType"], str)
            if visual_container["visual"]["visualType"] in {"textbox", "actionButton"}:
                assert "query" not in visual_container["visual"]
                continue
            query_state = visual_container["visual"]["query"]["queryState"]
            assert query_state
            assert "rows" not in query_state
            for projection_state in query_state.values():
                assert set(projection_state) == {"projections"}
                for projection in projection_state["projections"]:
                    assert set(projection) <= {
                        "field",
                        "queryRef",
                        "nativeQueryRef",
                        "displayName",
                        "active",
                    }
                    assert set(projection) >= {
                        "field",
                        "queryRef",
                        "nativeQueryRef",
                    }
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
    projection = value["visual"]["query"]["queryState"]["Values"]["projections"][2]
    projection["field"]["Measure"]["Property"] = "Revenue At Risk"


def _mutate_projection_measure_to_column(value: dict[str, Any]) -> None:
    projection = value["visual"]["query"]["queryState"]["Values"]["projections"][2]
    projection["field"] = {
        "Column": {
            "Expression": {"SourceRef": {"Entity": "ActionOutcomes"}},
            "Property": "decision_id",
        }
    }


def _mutate_aggregation_function(value: dict[str, Any]) -> None:
    projection = value["visual"]["query"]["queryState"]["Values"]["projections"][2]
    projection["field"] = {
        "Aggregation": {
            "Expression": {
                "Column": {
                    "Expression": {"SourceRef": {"Entity": "CaseCommandCenter"}},
                    "Property": "case_id",
                }
            },
            "Function": 0,
        }
    }


def _mutate_projection_display_name(value: dict[str, Any]) -> None:
    projection = value["visual"]["query"]["queryState"]["Values"]["projections"][2]
    projection["displayName"] = "Different Decision Label"


def _mutate_projection_role(value: dict[str, Any]) -> None:
    query_state = value["visual"]["query"]["queryState"]
    query_state["Data"] = query_state.pop("Values")


def _mutate_filter_type(value: dict[str, Any]) -> None:
    value["filterConfig"]["filters"][0]["type"] = "Categorical"


def _mutate_unknown_projection_shape(value: dict[str, Any]) -> None:
    projection = value["visual"]["query"]["queryState"]["Values"]["projections"][2]
    projection["hidden"] = True


def _mutate_unknown_filter_shape(value: dict[str, Any]) -> None:
    value["filterConfig"]["filters"][0]["ordinal"] = 0


@pytest.mark.parametrize(
    ("page", "visual", "mutation"),
    [
        (
            "actions-outcomes",
            "predicted-observed-variance",
            _mutate_projection_field_queryref_disagreement,
        ),
        (
            "actions-outcomes",
            "predicted-observed-variance",
            _mutate_projection_measure_to_column,
        ),
        (
            "actions-outcomes",
            "predicted-observed-variance",
            _mutate_aggregation_function,
        ),
        (
            "actions-outcomes",
            "predicted-observed-variance",
            _mutate_projection_display_name,
        ),
        ("actions-outcomes", "predicted-observed-variance", _mutate_projection_role),
        ("actions-outcomes", "action-status", _mutate_filter_type),
        (
            "actions-outcomes",
            "predicted-observed-variance",
            _mutate_unknown_projection_shape,
        ),
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

    assert deploy.EXPECTED_PAGE_ORDER == report_pages.ORDER
    assert deploy.EXPECTED_QUERY_REFS == QUERY_REF_ALLOWLIST
    deploy._validate_visual_inventory(REPORT)
    assert {"saved-inventory-rows", "saved-order-rows"} <= set(
        EXPECTED_VISUAL_IDS["command-center"]
    )
    assert "operational-rows" in EXPECTED_VISUAL_IDS["operations-overview"]


def test_visual_inventory_rejects_schema_valid_additional_reused_queryref(
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
        / "saved-inventory-rows"
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
    source = pages / "command-center" / "visuals" / "saved-inventory-rows"
    destination = pages / "actions-outcomes" / "visuals" / "saved-inventory-rows"
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
    comparison = visual["filterConfig"]["filters"][0]["filter"]["Where"][0][
        "Condition"
    ]["Comparison"]
    comparison["Right"]["Literal"]["Value"] = "0L"
    action.write_text(json.dumps(visual), encoding="utf-8")
    with pytest.raises(deploy.PreflightError, match="visual contract/filter"):
        deploy._validate_visual_inventory(
            repository / "SupplyResponse.Report" / "definition"
        )


@pytest.mark.parametrize(
    "attack", ["unlock", "remove-gate", "alias", "picker-sync", "picker-field"]
)
def test_scope_mutations_fail_before_auth(tmp_path, monkeypatch, attack):
    from fabric import deploy

    repository = _staged_visual_mutation_repository(tmp_path, attack)
    page = "supplier-shipment"
    visual = "case-selector" if attack.startswith("picker-") else "supporting-records"
    path = _visual_path(repository, page, visual)
    value = _load(path)
    if attack == "unlock":
        value["filterConfig"]["filters"][0]["isLockedInViewMode"] = False
    elif attack == "remove-gate":
        del value["filterConfig"]
    elif attack == "alias":
        value["filterConfig"]["filters"][0]["filter"]["From"][0]["Name"] = "other"
    elif attack == "picker-sync":
        value["visual"]["syncGroup"]["filterChanges"] = False
    else:
        value["visual"]["query"]["queryState"]["Values"]["projections"][0]["field"][
            "Column"
        ]["Property"] = "status"
    path.write_text(json.dumps(value), encoding="utf-8")
    deploy._validate_offline_json_schemas(repository)
    monkeypatch.setattr(deploy, "POWER_BI", repository)
    monkeypatch.setattr(deploy, "_validate_python", lambda: None)
    monkeypatch.setattr(
        deploy, "_required_environment", lambda: VISUAL_PREFLIGHT_VALUES
    )
    monkeypatch.setattr(
        deploy, "_publish", lambda _: pytest.fail("publish/auth reached")
    )
    monkeypatch.setattr(
        deploy,
        "_discover_publish_items",
        lambda _: pytest.fail("SDK discovery reached"),
    )
    monkeypatch.setattr(sys, "argv", ["deploy.py"])
    with pytest.raises(SystemExit):
        deploy.main()


def test_case_picker_is_explicit_single_select_and_synced_on_every_page():
    for page in report_pages.LEGACY_ORDER:
        visual = _load(
            REPORT / "pages" / page / "visuals" / "case-selector" / "visual.json"
        )["visual"]
        assert visual["visualType"] == "slicer"
        assert visual["syncGroup"] == {
            "groupName": "SupplyResponseCase",
            "fieldChanges": True,
            "filterChanges": True,
        }
        assert visual["objects"]["selection"][0]["properties"]["singleSelect"] == {
            "expr": {"Literal": {"Value": "true"}}
        }
        assert "general" not in visual["objects"]
        assert (
            visual["query"]["queryState"]["Values"]["projections"][0]["queryRef"]
            == "CaseCommandCenter.case_id"
        )


def test_saved_overview_contains_exact_contributing_tables_not_ai_answers():
    assert not any(
        ref.endswith(" Answer") for ref in QUERY_REF_ALLOWLIST["command-center"]
    )
    assert "SavedRecords.part_id" in QUERY_REF_ALLOWLIST["command-center"]
    inventory = _load(
        REPORT / "pages/command-center/visuals/saved-inventory-rows/visual.json"
    )
    assert (
        inventory["filterConfig"]["filters"][0]["field"]["Measure"]["Property"]
        == "Stock Row Visible"
    )
    report_pages.verify(REPORT)


def test_actions_preserve_scenario_and_projection_context():
    refs = QUERY_REF_ALLOWLIST["actions-outcomes"]
    assert {
        "CaseCommandCenter.Scenario Context",
        "CaseCommandCenter.Projection Updated Display",
        "CaseCommandCenter.Current Decision Display",
    } <= refs
    report_pages.verify(REPORT)


def test_all_business_tables_and_variance_have_locked_scope_gates():
    for path in REPORT.glob("pages/*/visuals/*/visual.json"):
        value = _load(path)
        if value["visual"]["visualType"] not in {
            "tableEx",
            "pivotTable",
            "clusteredColumnChart",
        }:
            continue
        gates = [
            item
            for item in value["filterConfig"]["filters"]
            if "Measure" in item["field"]
        ]
        assert len(gates) == 1
        gate = gates[0]
        assert gate["isHiddenInViewMode"] and gate["isLockedInViewMode"]
        assert gate["field"]["Measure"]["Property"].endswith("Row Visible")
        assert gate["filter"]["Where"][0]["Condition"]["Comparison"]["Right"] == {
            "Literal": {"Value": "1L"}
        }
    chart = _load(
        REPORT
        / "pages/actions-outcomes/visuals/predicted-observed-variance/visual.json"
    )
    assert set(_query_refs(chart)) >= {
        "ActionOutcomes.metric_display_name",
        "ActionOutcomes.observation_kind_display",
        "ActionOutcomes.Observed Variance",
    }


def test_no_persisted_case_default_or_latest_showcase_override():
    for page in PAGES:
        filters = (
            _load(REPORT / "pages" / page / "page.json")
            .get("filterConfig", {})
            .get("filters", [])
        )
        allowed = {"record_family"}
        if page in report_pages.OPERATIONAL_ORDER:
            allowed.add("dataset_id")
        assert all(
            item["field"].get("Column", {}).get("Property") in allowed
            for item in filters
        )
    definitions = report_model.manifest()["tables"]["CaseCommandCenter"]["measures"]
    assert "Latest Showcase Case" not in definitions
    selector = definitions["External Selected Case Key"]["expression"]
    assert "ISFILTERED" in selector and "HASONEFILTER" in selector
    assert "COUNTROWS(CaseCommandCenter) == 1" in selector
    assert "ALLSELECTED" in definitions["Selected Case Key"]["expression"]


def test_report_has_no_embedded_rows_or_environment_specific_identifiers() -> None:
    def assert_rows_are_query_roles(value, path=()):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() == "rows":
                    assert key == "Rows"
                    assert path[-1:] == ("queryState",)
                    assert isinstance(child, dict)
                    assert set(child) == {"projections"}
                assert_rows_are_query_roles(child, path + (key,))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                assert_rows_are_query_roles(child, path + (index,))

    for path in POWER_BI.rglob("*.json"):
        assert_rows_are_query_roles(_load(path))
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in POWER_BI.rglob("*")
        if path.is_file() and path.name != ".platform"
    )
    lowered = text.lower()
    assert '"staticdata":' not in lowered
    assert '"datavalues":' not in lowered
    assert "analysis.windows.net" not in lowered
    assert not re.search(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", lowered)
    assert ".datawarehouse.fabric.microsoft.com" not in lowered


def test_semantic_model_exposes_decision_and_simulation_measures() -> None:
    report_model.check_required_fields(report_pages.required_fields())
    report_model.verify(SEMANTIC_MODEL, ROOT / "fabric/reporting/queries")


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


def test_current_context_measures_are_scoped_to_explicit_case_and_decision() -> None:
    definitions = report_model.manifest()["tables"]["CaseCommandCenter"]["measures"]
    for name in (
        "Action Row Visible",
        "Observation Row Visible",
        "Current Actions Count",
        "Current Observations Count",
    ):
        text = definitions[name]["expression"]
        assert "[Selected Case Key]" in text and "[Current Decision Key]" in text
        assert "KEEPFILTERS(TREATAS" in text
        assert "ISBLANK" in text


def test_tmdl_folder_has_strong_structural_contract() -> None:
    from fabric import deploy

    deploy._validate_generated_model(SEMANTIC_MODEL)
    assert len(report_model.manifest()["tables"]) == 6
    definitions = report_model.manifest()["tables"]
    expression = definitions["ActionOutcomes"]["measures"]["Observed Variance"][
        "expression"
    ]
    assert "[Observation Row Visible] == 1" in expression
    assert "IFERROR(VALUE(PredictedText), BLANK())" in expression
    assert "IFERROR(VALUE(ObservedText), BLANK())" in expression
    assert "ABS(Predicted)" in expression and "Predicted == 0" in expression
    assert "AVERAGEX" not in expression and "ALL(ActionOutcomes)" not in expression
    assert '"remaining_alpha_recovery_date"' not in expression


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
    try:
        baseline, actual = Decimal(predicted), Decimal(observed)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not baseline.is_finite() or not actual.is_finite() or baseline == 0:
        return None
    return (actual - baseline) / abs(baseline)


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


@pytest.mark.parametrize(
    ("predicted", "observed"),
    [
        ("unknown", "10"),
        ("10", "unknown"),
        ("NaN", "1"),
        ("1", "Infinity"),
        ("", "1"),
    ],
)
def test_variance_oracle_rejects_non_numeric_and_non_finite_values(predicted, observed):
    assert _relative_variance_oracle("response_cost", predicted, observed) is None


def test_variance_oracle_preserves_observed_zero_and_negative_baseline():
    assert _relative_variance_oracle("response_cost", "10", "0") == Decimal(-1)
    assert _relative_variance_oracle("response_cost", "-10", "-5") == Decimal("0.5")


def test_model_has_no_relationships_and_uses_guarded_decision_scope() -> None:
    assert (SEMANTIC_MODEL / "relationships.tmdl").read_text() == ""
    assert report_model.manifest()["relationships"] == []
    test_current_context_measures_are_scoped_to_explicit_case_and_decision()


@pytest.mark.parametrize(
    "attack",
    [
        "column-type",
        "column-source",
        "measure-expression",
        "measure-format",
        "measure-hidden",
        "partition-query",
        "relationship",
        "extra-table",
        "expression",
        "symlink",
    ],
)
def test_model_mutations_fail_before_sdk_or_auth(tmp_path, monkeypatch, attack):
    from fabric import deploy

    repository = _staged_visual_mutation_repository(tmp_path, attack)
    definition = repository / "SupplyResponse.SemanticModel/definition"
    path = definition / "tables/ActionOutcomes.tmdl"
    text = path.read_text()
    replacements = {
        "column-type": ("dataType: string", "dataType: int64"),
        "column-source": ("sourceColumn: case_id", "sourceColumn: decision_id"),
        "measure-expression": ("ABS(Predicted)", "Predicted"),
        "measure-format": ("0.00%;-0.00%;0.00%", "0.00"),
        "measure-hidden": ("    formatString:", "    isHidden\n    formatString:"),
        "partition-query": ("Sql.Database(", "Sql.Databases("),
    }
    if attack in replacements:
        old, new = replacements[attack]
        assert old in text
        path.write_text(text.replace(old, new, 1))
    elif attack == "relationship":
        (definition / "relationships.tmdl").write_text(
            "relationship Unexpected\n"
            "  fromColumn: ActionOutcomes.case_key\n"
            "  toColumn: CaseCommandCenter.case_key\n"
        )
    elif attack == "extra-table":
        (definition / "tables/Extra.tmdl").write_text("table Extra\n")
    elif attack == "expression":
        (definition / "expressions.tmdl").write_text(
            deploy.EXPECTED_EXPRESSIONS + '\nexpression Extra = "unexpected"\n'
        )
    else:
        outside = tmp_path / "external.tmdl"
        outside.write_text(text)
        path.unlink()
        path.symlink_to(outside)
    monkeypatch.setattr(
        deploy,
        "_discover_publish_items",
        lambda _: pytest.fail("SDK discovery reached"),
    )
    monkeypatch.setattr(
        deploy,
        "_validate_tmdl",
        lambda _: pytest.fail("parser reached before generated contract"),
    )
    with pytest.raises(deploy.PreflightError, match="semantic model contract"):
        deploy._validate_staged_repository(repository, VISUAL_PREFLIGHT_VALUES)


def test_tmdl_deserializes_with_microsoft_tom_parser() -> None:
    from fabric import deploy

    deploy._validate_tmdl(SEMANTIC_MODEL)


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
        "CaseCommandCenter[Current Actions Count]",
        "ActionOutcomes[Observed Variance]",
        "MAX(ActionOutcomes[scenario_effective_time])",
        "CaseCommandCenter[Projection Refresh Time]",
        'ActionOutcomes[metric] = "response_cost"',
        'ActionOutcomes[metric] = "remaining_alpha_recovery_date"',
        "TREATAS({{{selected_case}}}, CaseCommandCenter[case_id])",
        "TREATAS({{{selected_decision}}}, ActionOutcomes[decision_id])",
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
