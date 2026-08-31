from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, NoReturn
from uuid import UUID


POWER_BI = Path(__file__).resolve().parent / "power-bi"
SCHEMA_CATALOG = Path(__file__).resolve().parent / "schemas" / "microsoft"
TMDL_VALIDATOR = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fabric"
    / "tmdl-validator"
    / "TmdlValidator.csproj"
)
REQUIRED_ENVIRONMENT = (
    "SUPPLY_RESPONSE_ALLOWED_TENANT_ID",
    "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID",
    "FABRIC_SQL_SERVER",
    "FABRIC_SQL_DATABASE",
)
EXPECTED_PAGE_ORDER = ("command-center", "actions-outcomes")
EXPECTED_PUBLISH_ITEMS = (
    ("SemanticModel", "SupplyResponse"),
    ("Report", "SupplyResponse"),
)
EXPECTED_PLATFORM = {
    "SupplyResponse.SemanticModel": {
        "type": "SemanticModel",
        "logicalId": "1808b468-5fe3-542e-9004-ae82d8cbd452",
    },
    "SupplyResponse.Report": {
        "type": "Report",
        "logicalId": "8ff233ca-a127-5ff7-a559-cfbbb6fc8046",
    },
}
EXPECTED_QUERY_REFS = {
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


class PreflightError(ValueError):
    pass


def _fail(message: str) -> NoReturn:
    print(f"deployment preflight failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _validate_python() -> None:
    if sys.version_info[:2] != (3, 12):
        raise PreflightError(
            "fabric-cicd deployment requires Python 3.12; "
            f"running {sys.version_info.major}.{sys.version_info.minor}"
        )


def _required_environment() -> dict[str, str]:
    values = {name: os.environ.get(name, "").strip() for name in REQUIRED_ENVIRONMENT}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise PreflightError(
            "the following variables must all be configured: " + ", ".join(missing)
        )
    for name in (
        "SUPPLY_RESPONSE_ALLOWED_TENANT_ID",
        "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID",
    ):
        try:
            UUID(values[name])
        except ValueError as error:
            raise PreflightError(f"{name} must be a UUID") from error
    return values


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PreflightError(f"invalid or missing JSON file: {path}") from error
    if not isinstance(value, dict):
        raise PreflightError(f"JSON root must be an object: {path}")
    return value


def _query_refs(value: object) -> list[str]:
    if isinstance(value, dict):
        result = [value["queryRef"]] if isinstance(value.get("queryRef"), str) else []
        for child in value.values():
            result.extend(_query_refs(child))
        return result
    if isinstance(value, list):
        return [match for child in value for match in _query_refs(child)]
    return []


def _validate_offline_json_schemas(repository: Path) -> None:
    try:
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT7
    except ImportError as error:
        raise PreflightError(
            "offline schema validation requires the fabric-deploy dependency group"
        ) from error

    manifest_path = SCHEMA_CATALOG / "manifest.json"
    manifest = _load_json(manifest_path)
    entries = manifest.get("schemas")
    if not isinstance(entries, dict) or not entries:
        raise PreflightError("Microsoft schema manifest is empty or invalid")

    registry = Registry()
    schemas: dict[str, dict[str, Any]] = {}
    expected_files: set[str] = set()
    for url, entry in entries.items():
        if not isinstance(url, str) or not isinstance(entry, dict):
            raise PreflightError("Microsoft schema manifest entry is invalid")
        filename = entry.get("file")
        expected_digest = entry.get("sha256")
        if not isinstance(filename, str) or not isinstance(expected_digest, str):
            raise PreflightError(
                f"Microsoft schema manifest metadata is invalid: {url}"
            )
        if Path(filename).name != filename:
            raise PreflightError(f"Microsoft schema manifest path is invalid: {url}")
        expected_files.add(filename)
        schema_path = SCHEMA_CATALOG / filename
        try:
            content = schema_path.read_bytes()
        except OSError as error:
            raise PreflightError(
                f"vendored Microsoft schema is missing: {url}"
            ) from error
        if hashlib.sha256(content).hexdigest() != expected_digest:
            raise PreflightError(f"vendored Microsoft schema integrity failed: {url}")
        schema = _load_json(schema_path)
        schemas[url] = schema
        resource = Resource.from_contents(schema, default_specification=DRAFT7)
        registry = registry.with_resource(url, resource)
        schema_id = schema.get("$id")
        if isinstance(schema_id, str):
            registry = registry.with_resource(schema_id, resource)

    actual_files = {
        path.name
        for path in SCHEMA_CATALOG.glob("*.json")
        if path.name != "manifest.json"
    }
    if actual_files != expected_files:
        raise PreflightError(
            "vendored Microsoft schema catalog does not match manifest"
        )

    json_files = sorted(
        path
        for path in repository.rglob("*")
        if path.is_file()
        and (
            path.name == ".platform"
            or path.suffix in {".json", ".pbip", ".pbir", ".pbism"}
        )
    )
    if not json_files:
        raise PreflightError("Power BI package contains no JSON artifacts")
    for path in json_files:
        instance = _load_json(path)
        schema_url = instance.get("$schema")
        if not isinstance(schema_url, str) or schema_url not in schemas:
            raise PreflightError(
                f"artifact does not declare a pinned Microsoft schema: {path}"
            )
        errors = sorted(
            Draft7Validator(schemas[schema_url], registry=registry).iter_errors(
                instance
            ),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
        if errors:
            location = "/".join(str(part) for part in errors[0].absolute_path)
            raise PreflightError(
                f"Microsoft schema validation failed for {path} at {location or '<root>'}: "
                f"{errors[0].message}"
            )


def _validate_item_references(repository: Path) -> None:
    pbip = _load_json(repository / "SupplyResponse.pbip")
    artifacts = pbip.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1:
        raise PreflightError("PBIP must reference exactly one report")
    report = artifacts[0].get("report") if isinstance(artifacts[0], dict) else None
    report_path = report.get("path") if isinstance(report, dict) else None
    if (
        report_path != "SupplyResponse.Report"
        or not (repository / report_path).is_dir()
    ):
        raise PreflightError("PBIP report path reference is broken")

    pbir_path = repository / report_path / "definition.pbir"
    pbir = _load_json(pbir_path)
    dataset_reference = pbir.get("datasetReference")
    by_path = (
        dataset_reference.get("byPath") if isinstance(dataset_reference, dict) else None
    )
    semantic_path = by_path.get("path") if isinstance(by_path, dict) else None
    expected_semantic = "../SupplyResponse.SemanticModel"
    if semantic_path != expected_semantic:
        raise PreflightError("PBIR datasetReference path is broken")
    resolved_semantic = (pbir_path.parent / semantic_path).resolve()
    if resolved_semantic != (repository / "SupplyResponse.SemanticModel").resolve():
        raise PreflightError(
            "PBIR datasetReference does not resolve to the semantic model"
        )

    for directory, expected in EXPECTED_PLATFORM.items():
        platform = _load_json(repository / directory / ".platform")
        metadata = platform.get("metadata")
        config = platform.get("config")
        if (
            not isinstance(metadata, dict)
            or metadata.get("type") != expected["type"]
            or metadata.get("displayName") != "SupplyResponse"
            or not isinstance(config, dict)
            or config.get("version") != "2.0"
            or config.get("logicalId") != expected["logicalId"]
        ):
            raise PreflightError(f"invalid stable .platform metadata: {directory}")


def _discover_publish_items(repository: Path) -> tuple[tuple[str, str], ...]:
    try:
        workspace_module = importlib.import_module("fabric_cicd.fabric_workspace")
        publisher_module = importlib.import_module("fabric_cicd._items._base_publisher")
        workspace = object.__new__(workspace_module.FabricWorkspace)
        workspace.repository_directory = repository.resolve()
        workspace.item_type_in_scope = ["SemanticModel", "Report"]
        workspace.repository_items = {}
        workspace.repository_folders = {}
        workspace.deployed_items = {}
        workspace.bulk_publish_enabled = False
        workspace._refresh_repository_items()
        discovered: list[tuple[str, str]] = []
        for _, item_type in publisher_module.ItemPublisher.get_item_types_to_publish(
            workspace
        ):
            discovered.extend(
                (item_type.value, name)
                for name in sorted(workspace.repository_items[item_type.value])
            )
        return tuple(discovered)
    except Exception as error:
        raise PreflightError(
            f"fabric-cicd repository discovery failed: {error}"
        ) from error


def _validate_tmdl(semantic_definition: Path) -> None:
    if shutil.which("dotnet") is None:
        raise PreflightError("dotnet is required for offline TOM/TMDL validation")
    with tempfile.TemporaryDirectory(
        prefix="supply-response-dotnet-preflight-"
    ) as dotnet_home:
        environment = os.environ.copy()
        environment["DOTNET_CLI_HOME"] = dotnet_home
        environment["DOTNET_NOLOGO"] = "1"
        environment["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"] = "1"
        result = subprocess.run(
            [
                "dotnet",
                "run",
                "--no-restore",
                "--project",
                str(TMDL_VALIDATOR),
                "--",
                str(semantic_definition),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env=environment,
        )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise PreflightError(
            "TOM/TMDL validation failed; run dotnet restore for the validator first: "
            + detail
        )


def _validate_project() -> None:
    semantic_definition = POWER_BI / "SupplyResponse.SemanticModel" / "definition"
    report_definition = POWER_BI / "SupplyResponse.Report" / "definition"
    required = (
        POWER_BI / "SupplyResponse.pbip",
        POWER_BI / "SupplyResponse.SemanticModel" / ".platform",
        POWER_BI / "SupplyResponse.SemanticModel" / "definition.pbism",
        semantic_definition / "model.tmdl",
        semantic_definition / "expressions.tmdl",
        semantic_definition / "relationships.tmdl",
        semantic_definition / "tables" / "CaseCommandCenter.tmdl",
        semantic_definition / "tables" / "ActionOutcomes.tmdl",
        POWER_BI / "SupplyResponse.Report" / ".platform",
        POWER_BI / "SupplyResponse.Report" / "definition.pbir",
        report_definition / "version.json",
        report_definition / "report.json",
        report_definition / "pages" / "pages.json",
    )
    missing = [
        str(path.relative_to(POWER_BI)) for path in required if not path.is_file()
    ]
    if missing:
        raise PreflightError("missing project artifacts: " + ", ".join(missing))

    pages = _load_json(report_definition / "pages" / "pages.json")
    if tuple(pages.get("pageOrder", ())) != EXPECTED_PAGE_ORDER:
        raise PreflightError(
            "report page order must contain exactly the two approved pages"
        )
    if pages.get("activePageName") != "command-center":
        raise PreflightError("Command Center must be the active landing page")

    actual_page_directories = {
        path.name for path in (report_definition / "pages").iterdir() if path.is_dir()
    }
    if actual_page_directories != set(EXPECTED_PAGE_ORDER):
        raise PreflightError("report must not contain unapproved page directories")

    for page_name, expected_refs in EXPECTED_QUERY_REFS.items():
        page = _load_json(report_definition / "pages" / page_name / "page.json")
        if (
            page.get("displayOption") != "FitToPage"
            or page.get("width") != 1280
            or page.get("height") != 720
        ):
            raise PreflightError(
                f"{page_name} has an invalid page size or display option"
            )
        refresh = page.get("objects", {}).get("pageRefresh", [])  # type: ignore[union-attr]
        if refresh != [
            {
                "properties": {
                    "show": True,
                    "refreshType": "FixedInterval",
                    "duration": 30,
                }
            }
        ]:
            raise PreflightError(f"{page_name} must refresh every 30 seconds")

        visual_files = sorted(
            (report_definition / "pages" / page_name / "visuals").glob("*/visual.json")
        )
        if not visual_files:
            raise PreflightError(f"{page_name} must contain visual definitions")
        actual_refs = {
            query_ref
            for visual_file in visual_files
            for query_ref in _query_refs(_load_json(visual_file))
        }
        if actual_refs != expected_refs:
            raise PreflightError(f"{page_name} query references do not match allowlist")

    tmdl = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(semantic_definition.rglob("*.tmdl"))
    )
    if "mode: directQuery" not in tmdl:
        raise PreflightError("semantic model must use DirectQuery")
    for view in ("analytics.case_command_center", "analytics.action_outcomes"):
        if tmdl.count(view) != 1:
            raise PreflightError(f"semantic model must consume only {view}")
    if "__FABRIC_SQL_SERVER__" not in tmdl or "__FABRIC_SQL_DATABASE__" not in tmdl:
        raise PreflightError("semantic model deployment placeholders are missing")


def _staged_repository(values: dict[str, str], target: Path) -> Path:
    repository = target / "power-bi"
    shutil.copytree(POWER_BI, repository)
    parameter_rules = {
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
    # JSON is valid YAML. Writing it this way avoids adding a YAML parser to the
    # authentication-free preflight while retaining fabric-cicd's parameter.yml API.
    (repository / "parameter.yml").write_text(
        json.dumps(parameter_rules, indent=2) + "\n", encoding="utf-8"
    )
    _validate_staged_repository(repository, values)
    return repository


def _validate_staged_repository(repository: Path, values: dict[str, str]) -> None:
    _validate_offline_json_schemas(repository)
    _validate_item_references(repository)
    discovered = _discover_publish_items(repository)
    if discovered != EXPECTED_PUBLISH_ITEMS:
        raise PreflightError(
            "fabric-cicd must discover exactly SemanticModel then Report; "
            f"found {discovered!r}"
        )
    _validate_tmdl(repository / "SupplyResponse.SemanticModel" / "definition")

    expressions = (
        repository / "SupplyResponse.SemanticModel" / "definition" / "expressions.tmdl"
    )
    source = expressions.read_text(encoding="utf-8")
    parameters = _load_json(repository / "parameter.yml")
    rules = parameters.get("find_replace")
    if not isinstance(rules, list) or len(rules) != 2:
        raise PreflightError("parameter.yml must define exactly two replacements")
    rendered = source
    for rule in rules:
        if not isinstance(rule, dict):
            raise PreflightError("parameter.yml replacement must be an object")
        find_value = rule.get("find_value")
        replace_value = rule.get("replace_value")
        if not isinstance(find_value, str) or not isinstance(replace_value, dict):
            raise PreflightError("parameter.yml replacement is malformed")
        replacement = replace_value.get("dev")
        if not isinstance(replacement, str) or not replacement:
            raise PreflightError("parameter.yml dev replacement is missing")
        if find_value not in rendered:
            raise PreflightError(f"missing deployment placeholder {find_value}")
        rendered = rendered.replace(find_value, replacement)
    unresolved = sorted(set(re.findall(r"__[A-Z][A-Z0-9_]+__", rendered)))
    if unresolved:
        raise PreflightError(
            "unresolved deployment placeholder: " + ", ".join(unresolved)
        )
    for name in ("FABRIC_SQL_SERVER", "FABRIC_SQL_DATABASE"):
        if values[name] not in rendered:
            raise PreflightError(f"staged semantic model is missing substituted {name}")


def _preflight_substitution(values: dict[str, str]) -> None:
    with tempfile.TemporaryDirectory(
        prefix="supply-response-power-bi-preflight-"
    ) as directory:
        _staged_repository(values, Path(directory))


def _publish(values: dict[str, str]) -> None:
    identity = importlib.import_module("azure.identity")
    fabric_cicd = importlib.import_module("fabric_cicd")
    credential = identity.AzureCliCredential(
        tenant_id=values["SUPPLY_RESPONSE_ALLOWED_TENANT_ID"]
    )
    with tempfile.TemporaryDirectory(prefix="supply-response-power-bi-") as directory:
        repository = _staged_repository(values, Path(directory))
        workspace = fabric_cicd.FabricWorkspace(
            workspace_id=values["SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID"],
            environment="dev",
            repository_directory=str(repository),
            item_type_in_scope=["SemanticModel", "Report"],
            token_credential=credential,
        )
        fabric_cicd.publish_all_items(workspace)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy the Supply Response Power BI project to Microsoft Fabric."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate configuration and artifacts without authentication or network calls",
    )
    arguments = parser.parse_args()
    try:
        _validate_python()
        values = _required_environment()
        _validate_project()
        _preflight_substitution(values)
        if arguments.dry_run:
            print("Task 13 Power BI deployment preflight passed.")
            print(
                "Dry run only: no authentication, network calls, or workspace changes were made."
            )
            return 0
        _publish(values)
    except PreflightError as error:
        _fail(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
