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


def test_azd_is_infrastructure_only_and_uses_environment_parameters():
    azure_yaml = _read("azure.yaml")
    parameters = json.loads(_read("infra/main.parameters.json"))

    assert "services:" not in azure_yaml
    assert (
        parameters["parameters"]["subscriptionId"]["value"]
        == "${AZURE_SUBSCRIPTION_ID}"
    )
    assert parameters["parameters"]["tenantId"]["value"] == "${AZURE_TENANT_ID}"
    assert parameters["parameters"]["resourceGroupName"]["value"] == (
        "${SUPPLY_RESPONSE_RESOURCE_GROUP}"
    )
    assert parameters["parameters"]["containerAppName"]["value"] == (
        "${SUPPLY_RESPONSE_CONTAINER_APP_NAME}"
    )
    assert not (ROOT / "infra/main.bicepparam").exists()


def test_container_app_name_is_explicit_bounded_and_decoupled_from_azd_name():
    main = _read("infra/main.bicep")
    preflight = _read("scripts/preflight_personal_tenant.sh")
    docs = _read("docs/deployment/personal-tenant.md")

    assert "param containerAppName string" in main
    assert "appName: containerAppName" in main
    assert "ca-supply-response-${environmentName}" not in main
    assert "SUPPLY_RESPONSE_CONTAINER_APP_NAME:?" in preflight
    assert "${#EXPECTED_CONTAINER_APP_NAME} > 32" in preflight
    assert "1–32" in docs


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


def test_production_bundle_requires_exact_entra_build_contract():
    dockerfile = _read("Dockerfile")

    for setting in (
        "VITE_ENTRA_TENANT_ID",
        "VITE_ENTRA_WEB_CLIENT_ID",
        "VITE_ENTRA_API_SCOPE",
        "VITE_ENTRA_REDIRECT_URI",
    ):
        assert f"ARG {setting}" in dockerfile
        assert f"{setting}=${{{setting}}}" in dockerfile
        assert f'test -n "${{{setting}}}"' in dockerfile


def test_one_argument_aware_image_build_path_is_explicit_and_immutable():
    deploy = _read("scripts/deploy_personal_tenant.sh")
    docs = _read("docs/deployment/personal-tenant.md")

    assert "az acr build" in deploy
    assert deploy.count('--build-arg "VITE_ENTRA_') == 4
    assert "public_config_digest" in deploy
    assert "git_revision" in deploy
    assert "SUPPLY_RESPONSE_IMAGE_TAG:-" not in deploy
    assert "azd package" in docs
    assert "azd deploy" in docs
    assert "docker build" in docs


def test_vite_production_bundle_embeds_exact_entra_values(tmp_path):
    expected = {
        "VITE_ENTRA_TENANT_ID": "11111111-1111-4111-8111-111111111111",
        "VITE_ENTRA_WEB_CLIENT_ID": "22222222-2222-4222-8222-222222222222",
        "VITE_ENTRA_API_SCOPE": (
            "api://33333333-3333-4333-8333-333333333333/access_as_user"
        ),
        "VITE_ENTRA_REDIRECT_URI": "https://demo.example.test/auth/callback",
    }
    output = tmp_path / "web-dist"
    completed = subprocess.run(
        ["npm", "run", "build", "--", "--outDir", str(output)],
        cwd=ROOT / "apps/web",
        env={**os.environ, **expected},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    bundle = "\n".join(path.read_text() for path in output.rglob("*.js"))
    for value in expected.values():
        assert value in bundle


def test_final_revision_declares_every_live_backend_setting():
    source = _read("infra/modules/container-apps.bicep")
    main = _read("infra/main.bicep")
    parameters = _read("infra/main.parameters.json")
    required = {
        "SUPPLY_RESPONSE_FRONTEND_ORIGIN",
        "SUPPLY_RESPONSE_API_CLIENT_ID",
        "SUPPLY_RESPONSE_ALEX_OBJECT_ID",
        "SUPPLY_RESPONSE_FABRIC_SQL_SERVER",
        "SUPPLY_RESPONSE_FABRIC_SQL_DATABASE",
        "SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SOURCE_ID",
        "SUPPLY_RESPONSE_WORKIQ_QUALITY_SOURCE_ID",
        "SUPPLY_RESPONSE_WORKIQ_CORPUS_VERSION",
        "SUPPLY_RESPONSE_WORKIQ_DEPLOYMENT_RECEIPT",
        "SUPPLY_RESPONSE_TENANT_SHAREPOINT_HOST",
        "SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT",
        "SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_NAME",
        "SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_VERSION",
        "SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_NAME",
        "SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_VERSION",
        "SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_NAME",
        "SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_VERSION",
        "SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT",
        "SUPPLY_RESPONSE_POWER_BI_REPORT_URL",
        "SUPPLY_RESPONSE_POWER_BI_DEPLOYMENT_RECEIPT",
        "SUPPLY_RESPONSE_FABRIC_CITATION_BASE_URL",
    }
    combined = source + main + parameters

    for setting in required:
        assert setting in combined
    assert "az containerapp update" not in _read("scripts/deploy_personal_tenant.sh")


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


def test_deployment_preserves_bootstrap_during_bounded_identity_propagation():
    deploy = _read("scripts/deploy_personal_tenant.sh")

    assert "FINAL_PROVISION_MAX_ATTEMPTS" in deploy
    assert "recognized_identity_binding_failure" in deploy
    assert "restore_bootstrap_revision" in deploy
    assert "SUPPLY_RESPONSE_BOOTSTRAP_MODE true" in deploy
    assert "SUPPLY_RESPONSE_BOOTSTRAP_MODE false" in deploy
    assert "sleep" in deploy


def test_preflight_requires_exact_foundry_fabric_and_azd_environment_contracts():
    preflight = _read("scripts/preflight_personal_tenant.sh")

    assert "SUPPLY_RESPONSE_FOUNDRY_PROJECT_RESOURCE_ID:?" in preflight
    assert "Microsoft.CognitiveServices/accounts/projects" in preflight
    assert "expected_foundry_endpoint" in preflight
    assert "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID:?" in preflight
    assert "SUPPLY_RESPONSE_FABRIC_SQL_DATABASE_ID:?" in preflight
    assert '"type" "SQLDatabase"' in preflight
    assert "fabric_token_tid" in preflight
    assert "EXPECTED_TENANT_ID" in preflight
    assert "azd env get-value AZURE_ENV_NAME" in preflight
    assert "EXPECTED_AZD_ENVIRONMENT" in preflight
    assert "az ad app show" in preflight
    assert "access_as_user" in preflight
    assert "registered Container App redirect" in preflight
    assert "accessToken" in preflight
    assert "printf '%s' \"$fabric_access_token\"" in preflight


def test_secret_file_and_live_smoke_gate_fail_closed():
    deploy = _read("scripts/deploy_personal_tenant.sh")

    assert (
        "secret file must contain exactly one line without a trailing newline" in deploy
    )
    assert "SMOKE_MAX_ATTEMPTS" in deploy
    assert 'health["runtime_mode"] == "live"' in deploy
    assert 'runtime["capability_health"]["operational_store"] == "ready"' in deploy
    assert 'runtime["capability_health"]["agent_runtime"] == "ready"' in deploy
    smoke_body = deploy.split("smoke_gate()", 1)[1].split("\n}\n", 1)[0]
    assert "SUPPLY_RESPONSE_WORKIQ" not in smoke_body
    assert "os.path.islink" in deploy
    assert "st_uid == os.getuid()" in deploy
    assert "stat.S_IMODE" in deploy
    assert "mode & 0o077 == 0" in deploy


def test_provision_diagnostics_are_protected_sanitized_and_not_streamed():
    deploy = _read("scripts/deploy_personal_tenant.sh")

    assert "deployment_tmp" in deploy
    assert "chmod 700" in deploy
    assert "chmod 600" in deploy
    assert "run_provision" in deploy
    assert "sanitized_provision_summary" in deploy
    assert "sed -n '1,120p'" not in deploy
    assert not re.search(r"(?m)^azd provision --no-prompt\s*$", deploy)


def test_restart_safe_upgrade_never_replaces_final_with_placeholder():
    deploy = _read("scripts/deploy_personal_tenant.sh")

    assert "existing_app_image" in deploy
    assert "started_from_bootstrap" in deploy
    assert "verify_existing_final_health" in deploy
    assert 'if [[ "$started_from_bootstrap" == true ]]' in deploy
    assert "prior healthy final revision remains" in deploy


def test_docker_context_excludes_local_operator_and_security_artifacts():
    ignored = set(_read(".dockerignore").splitlines())

    assert {".superpowers", ".artifacts", ".tmp", "infra/entra/.env.tenant"} <= ignored


def test_operator_runbook_has_actionable_external_access_and_recovery_steps():
    docs = _read("docs/deployment/personal-tenant.md")

    assert "azd env new" in docs
    assert "azd env select" in docs
    assert "CREATE USER" in docs
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::app" in docs
    assert "sys.database_permissions" in docs
    from integrations.fabric.health import FABRIC_SCHEMA_VERSION

    assert f"schema version (`{FABRIC_SCHEMA_VERSION}`)" in docs
    assert f"must be `{FABRIC_SCHEMA_VERSION}`" in docs
    analytics = _read("fabric/sql/002_analytics_views.sql")
    assert f"SET schema_version = {FABRIC_SCHEMA_VERSION}" in analytics
    assert "scripts/verify_foundry_agents.py --live" in docs
    assert "SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT" in docs
    assert "separate approval" in docs
    assert "revoke" in docs.lower()


def test_operator_permissions_are_exact_for_every_deployment_scope():
    docs = _read("docs/deployment/personal-tenant.md")

    for permission in (
        "Microsoft.Resources/subscriptions/resourceGroups/write",
        "Microsoft.Authorization/roleAssignments/write",
        "Microsoft.ContainerRegistry/registries/scheduleRun/action",
        "Microsoft.KeyVault/vaults/secrets/write",
    ):
        assert permission in docs
    for scope in (
        "subscription scope",
        "shared ACR resource scope",
        "project resource-group scope",
        "Foundry project scope",
    ):
        assert scope in docs


def test_shared_resource_and_monitoring_claims_are_accurate():
    plan = _read(".azure/deployment-plan.md")
    docs = _read("docs/deployment/personal-tenant.md")
    combined = plan + docs

    assert "lower configured daily cap" not in combined
    assert "without modifying them" not in docs
    assert "AcrPull" in docs
    assert "repository" in docs.lower()


def test_plan_does_not_claim_unverified_final_image_or_stale_test_counts():
    plan = _read(".azure/deployment-plan.md")

    assert "Complete; locally built and smoke-tested" not in plan
    assert "Complete; 6 tests pass" not in plan
    assert "Run Python, web, infrastructure, shell, Docker, and Bicep" not in plan


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
