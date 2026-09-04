"""Compatibility coverage for fabric-cicd 1.3.0 path handling internals."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWER_BI = ROOT / "fabric" / "power-bi"


def test_fabric_cicd_1_3_0_rejects_aliased_repository_report_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pin the upstream private-API reproduction to the supported version."""
    from azure.core.credentials import AccessToken, TokenCredential
    from fabric_cicd import FabricWorkspace
    from fabric_cicd._common._exceptions import ItemDependencyError
    from fabric_cicd._items._report import func_process_file

    from fabric import deploy

    class SyntheticTokenCredential(TokenCredential):
        def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
            return AccessToken("synthetic-token", 4_000_000_000)

    assert importlib.metadata.version("fabric-cicd") == "1.3.0"
    values = {
        "SUPPLY_RESPONSE_ALLOWED_TENANT_ID": "00000000-0000-4000-8000-000000000001",
        "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID": "00000000-0000-4000-8000-000000000002",
        "FABRIC_SQL_SERVER": "server.example.invalid",
        "FABRIC_SQL_DATABASE": "database-name",
    }
    physical_root = tmp_path / "physical"
    physical_root.mkdir()
    aliased_root = tmp_path / "aliased"
    aliased_root.symlink_to(physical_root, target_is_directory=True)
    monkeypatch.setattr(deploy, "_validate_staged_repository", lambda *_args: None)

    staged_repository = deploy._staged_repository(values, aliased_root)
    workspace = FabricWorkspace(
        workspace_id=values["SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID"],
        environment="dev",
        repository_directory=str(staged_repository),
        item_type_in_scope=["SemanticModel", "Report"],
        token_credential=SyntheticTokenCredential(),
    )
    workspace._refresh_repository_items()
    report = workspace.repository_items["Report"]["SupplyResponse"]
    definition = next(
        file for file in report.item_files if file.name == "definition.pbir"
    )

    with pytest.raises(ItemDependencyError, match="Semantic model not found"):
        func_process_file(workspace, report, definition)
