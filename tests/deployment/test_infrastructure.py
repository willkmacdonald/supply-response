from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_azd_uses_environment_parameters_and_root_docker_context():
    azure_yaml = _read("azure.yaml")
    parameters = json.loads(_read("infra/main.parameters.json"))

    assert "host: containerapp" in azure_yaml
    assert "context: ." in azure_yaml
    assert (
        parameters["parameters"]["subscriptionId"]["value"]
        == "${AZURE_SUBSCRIPTION_ID}"
    )
    assert parameters["parameters"]["tenantId"]["value"] == "${AZURE_TENANT_ID}"
    assert parameters["parameters"]["resourceGroupName"]["value"] == (
        "${SUPPLY_RESPONSE_RESOURCE_GROUP}"
    )
    assert not (ROOT / "infra/main.bicepparam").exists()


def test_template_reuses_shared_resources_and_contains_no_fixed_target_ids():
    main = _read("infra/main.bicep")
    modules = "\n".join(
        path.read_text() for path in (ROOT / "infra/modules").glob("*.bicep")
    )
    combined = main + modules

    assert "existing" in combined
    assert "Microsoft.App/managedEnvironments" in combined
    assert "Microsoft.ContainerRegistry/registries" in combined
    assert "Microsoft.OperationalInsights/workspaces" in combined
    assert combined.count("Microsoft.App/managedEnvironments") == 1
    assert combined.count("Microsoft.ContainerRegistry/registries") == 1
    assert combined.count("Microsoft.OperationalInsights/workspaces") == 1
    assert "administratorLogin" not in combined


def test_container_app_has_viable_bootstrap_and_final_runtime_contracts():
    source = _read("infra/modules/container-apps.bicep")

    assert "SystemAssigned" in source
    assert "mcr.microsoft.com/k8se/quickstart:latest" in source
    assert "bootstrapMode ? 80 : 8000" in source
    assert "bootstrapMode ? []" in source
    assert "external: true" in source
    assert "allowInsecure: false" in source
    assert "minReplicas: minReplicas" in source
    assert "maxReplicas: 2" in source
    assert "type: 'Startup'" in source
    assert "type: 'Liveness'" in source
    assert "type: 'Readiness'" in source
    assert "cpu: json('0.5')" in source
    assert "memory: '1Gi'" in source
    assert "secretRef: 'entra-client-secret'" in source
    assert "keyVaultUrl:" in source
    assert "identity: 'system'" in source


def test_key_vault_is_protected_and_runtime_secrets_are_not_iac_values():
    vault = _read("infra/modules/key-vault.bicep")
    all_bicep = "\n".join(
        path.read_text() for path in (ROOT / "infra").rglob("*.bicep")
    )

    assert "enableRbacAuthorization: true" in vault
    assert "enablePurgeProtection: true" in vault
    assert "softDeleteRetentionInDays: 90" in vault
    assert "@secure()" not in all_bicep
    assert not re.search(
        r"name:\s*'SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET'\s*,?\s*value:", all_bicep
    )
    assert "FABRIC_CONNECTION_STRING" not in all_bicep
    assert "ACCESS_TOKEN" not in all_bicep
    assert "listCredentials" not in all_bicep


def test_deploy_scripts_are_default_dry_run_and_require_exact_apply_confirmation():
    preflight = _read("scripts/preflight_personal_tenant.sh")
    deploy = _read("scripts/deploy_personal_tenant.sh")

    assert "az account show" in preflight
    assert "shared-services-env" in preflight
    assert "wkmsharedservicesacr" in preflight
    assert "shared-services-logs" in preflight
    assert "--apply" in deploy
    assert "CONFIRM_SUBSCRIPTION_ID" in deploy
    assert "CONFIRM_TENANT_ID" in deploy
    assert "CONFIRM_LOCATION" in deploy
    assert "CONFIRM_RESOURCE_GROUP" in deploy
    assert "azd provision" in deploy
    assert "SUPPLY_RESPONSE_BOOTSTRAP_MODE" in deploy
    assert "AcrPull" in deploy
    assert "Key Vault Secrets User" in deploy
    assert "--scope" in deploy
    assert "keyvault secret set" in deploy
    assert "--query value" not in deploy
    assert "az acr credential" not in deploy


def test_target_ids_are_required_from_environment_not_committed_literals():
    deployment_assets = "\n".join(
        _read(path)
        for path in (
            "scripts/preflight_personal_tenant.sh",
            "scripts/deploy_personal_tenant.sh",
            "docs/deployment/personal-tenant.md",
            ".azure/deployment-plan.md",
        )
    )
    assert "AZURE_SUBSCRIPTION_ID:?" in deployment_assets
    assert "AZURE_TENANT_ID:?" in deployment_assets
    assert not re.search(
        r"(?:tenant|subscription)[^\n]{0,40}[0-9a-f]{8}-[0-9a-f-]{27}",
        deployment_assets,
        flags=re.IGNORECASE,
    )


def test_bicep_compiles_to_an_arm_template(tmp_path):
    output = tmp_path / "main.json"
    compiler = shutil.which("bicep") or str(Path.home() / ".azure/bin/bicep")
    completed = subprocess.run(
        [compiler, "build", str(ROOT / "infra/main.bicep"), "--outfile", str(output)],
        cwd=ROOT,
        env={**os.environ, "DOTNET_BUNDLE_EXTRACT_BASE_DIR": str(tmp_path / "dotnet")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    template = json.loads(output.read_text())
    assert template["$schema"].lower().endswith("deploymenttemplate.json#")
