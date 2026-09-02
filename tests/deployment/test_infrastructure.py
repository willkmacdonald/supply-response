from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

_COMMITTED_TARGET_ID = re.compile(
    r"\b(?:tenant|subscription)[\s_-]*(?:id|uuid)\b(?:\s+is\s+|\s*(?::|=|-)\s*|\s+)"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    flags=re.IGNORECASE,
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


def _contains_committed_target_id(text: str) -> bool:
    return bool(_COMMITTED_TARGET_ID.search(text))


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
    assert "deploymentPrincipalId" not in parameters["parameters"]
    assert "deploymentPrincipalType" not in parameters["parameters"]
    assert not (ROOT / "infra/main.bicepparam").exists()


def test_container_app_name_is_explicit_bounded_and_decoupled_from_azd_name():
    main = _read("infra/main.bicep")
    preflight = _read("scripts/preflight_personal_tenant.sh")
    docs = _read("docs/deployment/personal-tenant.md")

    assert "param containerAppName string" in main
    assert "ca-supply-response-${environmentName}" not in main
    assert "SUPPLY_RESPONSE_CONTAINER_APP_NAME:?" in preflight
    assert "@minLength(2)" in main
    assert "@maxLength(32)" in main
    assert "validatedContainerAppName" in main
    assert "contains(containerAppName, '--') ? '' : containerAppName" in main
    assert "appName: validatedContainerAppName" in main
    container_module = _read("infra/modules/container-apps.bicep")
    assert "@minLength(2)" in container_module
    assert "@maxLength(32)" in container_module
    assert "valid_container_app_name" in preflight
    assert "2–32" in docs
    assert "consecutive hyphens" in docs


def test_container_app_name_contract_rejects_invalid_values():
    invalid_names = (
        "a",
        "-ab",
        "ab-",
        "ab--cd",
        "Ab",
        "a" * 33,
    )
    valid_names = ("ab", "ca-sr-demo", "a" * 32)

    for name in invalid_names:
        completed = subprocess.run(
            [
                "bash",
                "-c",
                'source scripts/lib/safe_command.sh; valid_container_app_name "$1"',
                "contract",
                name,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode != 0, name
    for name in valid_names:
        completed = subprocess.run(
            [
                "bash",
                "-c",
                'source scripts/lib/safe_command.sh; valid_container_app_name "$1"',
                "contract",
                name,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, name


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
    assert "az acr repository show" in deploy
    assert "sha256:[0-9a-f]{64}" in deploy
    assert 'image="${registry_server}/supply-response@${image_digest}"' in deploy
    assert "build_context_changes" in deploy
    for path in (
        ".dockerignore",
        "Dockerfile",
        "pyproject.toml",
        "uv.lock",
        "apps",
        "agents",
        "data",
        "integrations",
        "services",
        "migrations",
    ):
        assert path in deploy
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
    helper = _read("scripts/lib/safe_command.sh")
    health_helper = _read("scripts/lib/deployment_health.sh")

    assert (
        "secret file must contain exactly one line without a trailing newline" in deploy
    )
    assert "SMOKE_MAX_ATTEMPTS" in deploy
    assert 'health.get("runtime_mode") == "live"' in health_helper
    assert 'capabilities.get("operational_store") == "ready"' in health_helper
    assert 'capabilities.get("agent_runtime") == "ready"' in health_helper
    assert 'type(health.get("schema_version")) is int' in health_helper
    assert "raise SystemExit(1)" in health_helper
    smoke_body = deploy.split("smoke_gate()", 1)[1].split("\n}\n", 1)[0]
    assert "SUPPLY_RESPONSE_WORKIQ" not in smoke_body
    assert "valid_secret_file" in deploy
    assert "os.path.islink" in helper
    assert "st_uid == os.getuid()" in helper
    assert "stat.S_IMODE" in helper
    assert "mode & 0o077 == 0" in helper


def test_provision_diagnostics_are_protected_sanitized_and_not_streamed():
    deploy = _read("scripts/deploy_personal_tenant.sh")
    preflight = _read("scripts/preflight_personal_tenant.sh")
    helper = _read("scripts/lib/safe_command.sh")

    assert 'source "${script_dir}/lib/safe_command.sh"' in deploy
    assert 'source "${script_dir}/lib/safe_command.sh"' in preflight
    assert "safe_init_diagnostics" in deploy
    assert "safe_init_diagnostics" in preflight
    assert "chmod 700" in helper
    assert "chmod 600" in helper
    assert "safe_sanitized_summary" in helper
    assert "sed -n '1,120p'" not in deploy
    assert not re.search(r"(?m)^azd provision --no-prompt\s*$", deploy)

    for source in (deploy, preflight):
        for line in source.splitlines():
            stripped = line.strip()
            if re.search(r"(^|[$(])(?:az|azd) ", stripped):
                assert "safe_capture" in stripped or "safe_run" in stripped, stripped


def test_sensitive_capture_deletes_success_stdout_and_retains_only_failure_stderr():
    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail; source scripts/lib/safe_command.sh; "
                "safe_init_diagnostics; token=''; "
                "safe_capture_ephemeral token token-success printf token-value; "
                '[[ "$token" == token-value ]]; '
                '[[ ! -e "$SAFE_DIAGNOSTICS_DIR/token-success.stdout" ]]; '
                '[[ ! -e "$SAFE_DIAGNOSTICS_DIR/token-success.stderr" ]]; '
                "if safe_capture_ephemeral token token-failure bash -c "
                "'printf partial-token; printf ERROR >&2; exit 7'; then exit 9; fi; "
                '[[ ! -e "$SAFE_DIAGNOSTICS_DIR/token-failure.stdout" ]]; '
                '[[ -f "$SAFE_DIAGNOSTICS_DIR/token-failure.stderr" ]]; '
                "! grep -R 'token-value\\|partial-token' \"$SAFE_DIAGNOSTICS_DIR\""
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    preflight = _read("scripts/preflight_personal_tenant.sh")
    assert "safe_capture_ephemeral fabric_access_token fabric-token" in preflight


def test_safe_command_failure_summary_never_echoes_identifiers():
    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "source scripts/lib/safe_command.sh; safe_init_diagnostics; "
                "safe_run deliberate-failure bash -c "
                "'printf \"ERROR vault=myvault-tenantname "
                "/subscriptions/11111111-1111-1111-1111-111111111111 "
                "https://tenant.example.test user@example.test\\n\" >&2; exit 7'"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    for sensitive in (
        "myvault-tenantname",
        "11111111-1111-1111-1111-111111111111",
        "tenant.example.test",
        "user@example.test",
    ):
        assert sensitive not in completed.stderr
    assert "error category detected" in completed.stderr.lower()


def test_secret_is_seeded_only_during_true_bootstrap_and_rotation_is_separate():
    deploy = _read("scripts/deploy_personal_tenant.sh")
    docs = _read("docs/deployment/personal-tenant.md")
    rotation = _read("scripts/rotate_entra_client_secret.sh")

    seed = deploy.index("az keyvault secret set")
    bootstrap_guard = deploy.rfind(
        'if [[ "$started_from_bootstrap" == true ]]', 0, seed
    )
    assert bootstrap_guard >= 0
    assert "wait_for_bootstrap_operator_access" in deploy[bootstrap_guard:seed]
    assert "keyvault secret list" in deploy
    assert "existing seed version" in deploy
    assert "normal apply does not rotate" in docs.lower()
    assert "new_secret_id" in rotation
    assert "restore-prior-secret" in rotation
    assert "valid_secret_file" in rotation
    assert "--project=live" in docs
    assert "test_workiq_live.py" not in docs


def test_bootstrap_operator_access_is_exact_temporary_and_confirmed():
    main = _read("infra/main.bicep")
    rbac = _read("infra/modules/rbac.bicep")
    parameters = _read("infra/main.parameters.json")
    preflight = _read("scripts/preflight_personal_tenant.sh")
    deploy = _read("scripts/deploy_personal_tenant.sh")
    lifecycle = _read("scripts/lib/key_vault_operator_access.sh")
    docs = _read("docs/deployment/personal-tenant.md")

    assert "deploymentPrincipalId" not in main + parameters
    assert "deploymentPrincipalType" not in main + parameters
    assert "bootstrapOperatorAccess" not in main
    assert "principalType: 'ServicePrincipal'" in rbac

    assert "SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_ID:?" in preflight
    assert "SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE:?" in preflight
    assert "safe_capture_ephemeral arm_access_token current-arm-token" in preflight
    assert 'claims["oid"]' in preflight
    assert "az ad signed-in-user show" not in preflight
    assert "az ad sp show" not in preflight
    assert "current deployment principal" in preflight

    assert 'source "${script_dir}/lib/key_vault_operator_access.sh"' in deploy
    assert "create_temporary_kv_operator_access" in deploy
    assert "wait_for_bootstrap_operator_access" in deploy
    assert "cleanup_temporary_kv_operator_access" in deploy
    assert "az role assignment create" in lifecycle
    assert "az role assignment delete --ids" in lifecycle
    assert "uuid.uuid5" in lifecycle
    assert "keyvault secret list" in deploy
    assert "safe_before_diagnostics_cleanup" in deploy
    assert "interrupted bootstrap" in docs.lower()
    assert "temporary Key Vault Secrets Officer" in docs

    restore_body = deploy.split("restore_bootstrap_revision()", 1)[1].split("\n}", 1)[0]
    assert "role assignment create" not in restore_body
    assert deploy.index("cleanup_temporary_kv_operator_access") < deploy.index(
        "for ((attempt=1; attempt<=FINAL_PROVISION_MAX_ATTEMPTS"
    )


def test_temporary_kv_operator_access_lifecycle_with_partial_failures(tmp_path):
    lifecycle = ROOT / "scripts/lib/key_vault_operator_access.sh"
    helper = ROOT / "scripts/lib/safe_command.sh"
    assert lifecycle.exists()

    scenarios = {
        "before-create": "cleanup_temporary_kv_operator_access",
        "create-failure": (
            "export FAKE_CREATE_MODE=fail; "
            "create_temporary_kv_operator_access || true; "
            "cleanup_temporary_kv_operator_access"
        ),
        "partial-create": (
            "export FAKE_CREATE_MODE=partial; "
            "create_temporary_kv_operator_access || true; "
            "cleanup_temporary_kv_operator_access"
        ),
        "success": (
            "export FAKE_CREATE_MODE=success; "
            "create_temporary_kv_operator_access; "
            "cleanup_temporary_kv_operator_access"
        ),
        "exit-cleanup": (
            "export FAKE_CREATE_MODE=success; "
            "safe_before_diagnostics_cleanup() { cleanup_temporary_kv_operator_access; }; "
            "create_temporary_kv_operator_access"
        ),
    }

    for scenario, body in scenarios.items():
        scenario_dir = tmp_path / scenario
        scenario_dir.mkdir()
        fake_az = scenario_dir / "az"
        fake_az.write_text(
            """#!/usr/bin/env bash
set -eu
state="$FAKE_STATE"
if [[ "$*" == *"role assignment create"* ]]; then
  case "$FAKE_CREATE_MODE" in
    fail) exit 7 ;;
    partial) printf present >"$state"; exit 7 ;;
    success) printf present >"$state"; printf '{}'; exit 0 ;;
  esac
elif [[ "$*" == *"role assignment list"* ]]; then
  if [[ -f "$state" ]]; then
    printf '[{"id":"%s","principalId":"%s","principalType":"%s","scope":"%s","roleDefinitionId":"%s"}]' "$KV_OPERATOR_ASSIGNMENT_ID" "$KV_OPERATOR_PRINCIPAL_ID" "$KV_OPERATOR_PRINCIPAL_TYPE" "$KV_OPERATOR_SCOPE" "$KV_OPERATOR_ROLE_RESOURCE_ID"
  else
    printf '[]'
  fi
elif [[ "$*" == *"role assignment delete"* ]]; then
  rm -f "$state"
fi
"""
        )
        fake_az.chmod(0o700)
        state = scenario_dir / "assignment-state"
        script = (
            "set -euo pipefail; "
            f"source {helper}; source {lifecycle}; safe_init_diagnostics; "
            "configure_temporary_kv_operator_access "
            "'/subscriptions/sub/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv' "
            "'11111111-1111-4111-8111-111111111111' User; "
            f"{body}"
        )
        completed = subprocess.run(
            ["/bin/bash", "-c", script],
            env={
                **os.environ,
                "PATH": f"{scenario_dir}:{os.environ['PATH']}",
                "FAKE_STATE": str(state),
                "FAKE_CREATE_MODE": "success",
            },
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (scenario, completed.stderr)
        assert not state.exists(), scenario


def test_rotation_script_is_dry_run_exact_scoped_and_always_cleans_secret_file():
    rotation = _read("scripts/rotate_entra_client_secret.sh")
    docs = _read("docs/deployment/personal-tenant.md")

    assert "MODE=dry-run" in rotation
    assert "--apply" in rotation
    assert "CONFIRM_SUBSCRIPTION_ID" in rotation
    assert "CONFIRM_TENANT_ID" in rotation
    assert "CONFIRM_VAULT_ID" in rotation
    assert "CONFIRM_CONTAINER_APP_ID" in rotation
    assert "CONFIRM_CONTAINER_APP_NAME" in rotation
    assert "SUPPLY_RESPONSE_KEY_VAULT_URI" in rotation
    assert "SUPPLY_RESPONSE_LIVE_BASE_URL" in rotation
    assert "SUPPLY_RESPONSE_EXPECTED_DEPLOYMENT_ORIGIN" in rotation
    assert '.get("configuration", {}).get("secrets", [])' in rotation
    assert "create_temporary_kv_operator_access" in rotation
    assert "cleanup_temporary_kv_operator_access" in rotation
    assert "safe_before_diagnostics_cleanup" in rotation
    assert 'rm -f "$rollback_secret_file"' in rotation
    assert '--version "$old_version"' in rotation
    assert rotation.index("rotation_needs_rollback=true") < rotation.index(
        "rotation-new-secret"
    )
    assert "--project=live" in rotation
    assert "valid_secret_file" in rotation
    assert "scripts/rotate_entra_client_secret.sh --apply" in docs


def _rotation_environment(tmp_path: Path, scenario: str) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    state = tmp_path / "state.json"
    state.write_text("{}")
    replacement = tmp_path / "replacement-secret"
    replacement.write_text("replacement-value")
    replacement.chmod(0o600)
    tenant = "22222222-2222-4222-8222-222222222222"
    principal = "11111111-1111-4111-8111-111111111111"
    subscription = "33333333-3333-4333-8333-333333333333"
    resource_group = "rg-supply-response-demo"
    app_name = "ca-sr-demo"
    vault_name = "kv-sr-demo"
    app_id = f"/subscriptions/{subscription}/resourceGroups/{resource_group}/providers/Microsoft.App/containerApps/{app_name}"
    vault_id = f"/subscriptions/{subscription}/resourceGroups/{resource_group}/providers/Microsoft.KeyVault/vaults/{vault_name}"
    vault_uri = f"https://{vault_name}.vault.azure.net/"
    origin = "https://ca-sr-demo.example.test"

    header = json.dumps({"alg": "none"}, separators=(",", ":"))
    claims = json.dumps({"oid": principal, "tid": tenant}, separators=(",", ":"))
    import base64

    encode = lambda value: base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")
    token = f"{encode(header)}.{encode(claims)}.signature"

    fake_az = fake_bin / "az"
    fake_az.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json, os, signal, sys
            from pathlib import Path

            args = sys.argv[1:]
            state_path = Path(os.environ["FAKE_STATE"])
            state = json.loads(state_path.read_text())
            state.setdefault("calls", []).append(args)
            scenario = os.environ["FAKE_SCENARIO"]

            def save():
                state_path.write_text(json.dumps(state))

            def output(value):
                if isinstance(value, (dict, list)):
                    print(json.dumps(value))
                else:
                    print(value)
                save()
                raise SystemExit(0)

            if args[:2] == ["account", "show"]:
                query = args[args.index("--query") + 1]
                output({"id": os.environ["FAKE_SUBSCRIPTION"], "tenantId": os.environ["FAKE_TENANT"], "user.type": "user"}[query])
            if args[:2] == ["account", "get-access-token"]:
                output(os.environ["FAKE_TOKEN"])
            if args[:2] == ["keyvault", "show"]:
                value = {"id": os.environ["FAKE_VAULT_ID"], "properties": {"vaultUri": os.environ["FAKE_VAULT_URI"]}}
                if scenario == "wrong-vault":
                    value["id"] += "-wrong"
                output(value)
            if args[:2] == ["containerapp", "show"]:
                secret_url = os.environ["FAKE_VAULT_URI"] + "secrets/entra-client-secret"
                value = {
                    "id": os.environ["FAKE_APP_ID"],
                    "name": os.environ["FAKE_APP_NAME"],
                    "identity": {"type": "SystemAssigned"},
                    "properties": {
                        "configuration": {"secrets": [{"name": "entra-client-secret", "keyVaultUrl": secret_url, "identity": "system"}], "ingress": {"fqdn": os.environ["FAKE_FQDN"]}},
                        "latestReadyRevisionName": os.environ["FAKE_REVISION"],
                    },
                }
                if scenario == "wrong-app":
                    value["id"] += "-wrong"
                if scenario == "wrong-secret-reference":
                    value["properties"]["configuration"]["secrets"][0]["keyVaultUrl"] += "-wrong"
                output(value)
            if args[:3] == ["containerapp", "revision", "list"]:
                revision_id = os.environ["FAKE_APP_ID"] + "/revisions/" + os.environ["FAKE_REVISION"]
                if scenario == "wrong-revision-parent":
                    revision_id = revision_id.replace("/containerApps/", "/containerApps/wrong-")
                output([{"id": revision_id, "name": os.environ["FAKE_REVISION"], "properties": {"active": True}}])
            if args[:3] == ["role", "assignment", "create"]:
                state["role"] = True
                save()
                if scenario == "partial-role-create":
                    raise SystemExit(7)
                output({})
            if args[:3] == ["role", "assignment", "list"]:
                if state.get("role"):
                    output([{
                        "id": os.environ["KV_OPERATOR_ASSIGNMENT_ID"],
                        "principalId": os.environ["KV_OPERATOR_PRINCIPAL_ID"],
                        "principalType": os.environ["KV_OPERATOR_PRINCIPAL_TYPE"],
                        "scope": os.environ["KV_OPERATOR_SCOPE"],
                        "roleDefinitionId": os.environ["KV_OPERATOR_ROLE_RESOURCE_ID"],
                    }])
                output([])
            if args[:3] == ["role", "assignment", "delete"]:
                state["role"] = False
                state["role_deleted"] = state.get("role_deleted", 0) + 1
                save()
                raise SystemExit(0)
            if args[:3] == ["keyvault", "secret", "list"]:
                output([{"name": "entra-client-secret"}])
            if args[:3] == ["keyvault", "secret", "show"]:
                output(os.environ["FAKE_VAULT_URI"] + "secrets/entra-client-secret/old-version")
            if args[:3] == ["keyvault", "secret", "download"]:
                target = Path(args[args.index("--file") + 1])
                target.write_text("prior-value")
                target.chmod(0o600)
                state["rollback_file"] = str(target)
                save()
                raise SystemExit(0)
            if args[:3] == ["keyvault", "secret", "set"]:
                source = args[args.index("--file") + 1]
                is_rollback = "rotation-rollback-secret" in source
                state["rollback_sets" if is_rollback else "new_sets"] = state.get("rollback_sets" if is_rollback else "new_sets", 0) + 1
                save()
                if not is_rollback and scenario == "ambiguous-secret-set":
                    raise SystemExit(9)
                if is_rollback and scenario == "rollback-failure":
                    raise SystemExit(10)
                output(os.environ["FAKE_VAULT_URI"] + "secrets/entra-client-secret/new-version")
            if args[:3] == ["containerapp", "revision", "restart"]:
                state["restarts"] = state.get("restarts", 0) + 1
                save()
                if scenario in ("restart-failure", "rollback-failure") and state["restarts"] == 1:
                    raise SystemExit(11)
                raise SystemExit(0)
            save()
            print("unsupported fake az command", args, file=sys.stderr)
            raise SystemExit(99)
            """
        )
    )
    fake_az.chmod(0o700)

    fake_npm = fake_bin / "npm"
    fake_npm.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json, os, signal, sys
            from pathlib import Path
            path = Path(os.environ["FAKE_STATE"])
            state = json.loads(path.read_text())
            state.setdefault("calls", []).append(["npm", *sys.argv[1:]])
            state["npm_calls"] = state.get("npm_calls", 0) + 1
            path.write_text(json.dumps(state))
            if os.environ["FAKE_SCENARIO"] == "live-gate-failure" and state["npm_calls"] == 1:
                raise SystemExit(12)
            if os.environ["FAKE_SCENARIO"] == "signal-exit" and state["npm_calls"] == 1:
                os.kill(os.getppid(), signal.SIGTERM)
                raise SystemExit(13)
            raise SystemExit(0)
            """
        )
    )
    fake_npm.chmod(0o700)

    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_STATE": str(state),
        "FAKE_SCENARIO": scenario,
        "FAKE_SUBSCRIPTION": subscription,
        "FAKE_TENANT": tenant,
        "FAKE_TOKEN": token,
        "FAKE_VAULT_ID": vault_id,
        "FAKE_VAULT_URI": vault_uri,
        "FAKE_APP_ID": app_id,
        "FAKE_APP_NAME": app_name,
        "FAKE_FQDN": origin.removeprefix("https://"),
        "FAKE_REVISION": f"{app_name}--rev1",
        "AZURE_SUBSCRIPTION_ID": subscription,
        "AZURE_TENANT_ID": tenant,
        "SUPPLY_RESPONSE_KEY_VAULT_ID": vault_id,
        "SUPPLY_RESPONSE_KEY_VAULT_URI": vault_uri,
        "SUPPLY_RESPONSE_KEY_VAULT_NAME": vault_name,
        "SUPPLY_RESPONSE_RESOURCE_GROUP": resource_group,
        "SUPPLY_RESPONSE_CONTAINER_APP_ID": app_id,
        "SUPPLY_RESPONSE_CONTAINER_APP_NAME": app_name,
        "SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_ID": principal,
        "SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE": "User",
        "SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE": str(replacement),
        "SUPPLY_RESPONSE_LIVE_BASE_URL": origin,
        "SUPPLY_RESPONSE_EXPECTED_DEPLOYMENT_ORIGIN": origin,
        "CONFIRM_SUBSCRIPTION_ID": subscription,
        "CONFIRM_TENANT_ID": tenant,
        "CONFIRM_VAULT_ID": vault_id,
        "CONFIRM_CONTAINER_APP_ID": app_id,
        "CONFIRM_CONTAINER_APP_NAME": app_name,
    }
    return environment, state


def _run_rotation(
    tmp_path: Path, scenario: str
) -> tuple[subprocess.CompletedProcess[str], dict]:
    environment, state_path = _rotation_environment(tmp_path, scenario)
    if scenario == "wrong-origin":
        environment["SUPPLY_RESPONSE_LIVE_BASE_URL"] = "https://wrong.example.test"
    completed = subprocess.run(
        ["/bin/bash", "scripts/rotate_entra_client_secret.sh", "--apply"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return completed, json.loads(state_path.read_text())


def test_rotation_rejects_wrong_app_vault_reference_and_origin_before_mutation(
    tmp_path,
):
    for scenario in (
        "wrong-app",
        "wrong-vault",
        "wrong-secret-reference",
        "wrong-origin",
        "wrong-revision-parent",
    ):
        scenario_path = tmp_path / scenario
        scenario_path.mkdir()
        completed, state = _run_rotation(scenario_path, scenario)
        assert completed.returncode != 0, scenario
        assert state.get("new_sets", 0) == 0, scenario
        assert not state.get("role", False), scenario


def test_rotation_behaves_safely_across_command_failures_and_signal(tmp_path):
    expected_rollbacks = {
        "partial-role-create": 0,
        "ambiguous-secret-set": 1,
        "restart-failure": 1,
        "live-gate-failure": 1,
        "rollback-failure": 2,
        "signal-exit": 1,
    }
    for scenario, minimum_rollbacks in expected_rollbacks.items():
        scenario_path = tmp_path / scenario
        scenario_path.mkdir()
        completed, state = _run_rotation(scenario_path, scenario)
        assert completed.returncode != 0, scenario
        assert state.get("rollback_sets", 0) >= minimum_rollbacks, scenario
        assert not state.get("role", False), scenario
        assert state.get("role_deleted", 0) == 1, scenario
        if scenario != "partial-role-create":
            assert not Path(state["rollback_file"]).exists(), scenario

    success_path = tmp_path / "success"
    success_path.mkdir()
    completed, state = _run_rotation(success_path, "success")
    assert completed.returncode == 0, completed.stderr
    assert state.get("new_sets", 0) == 1
    assert state.get("rollback_sets", 0) == 0
    assert state.get("npm_calls", 0) == 1
    assert state.get("role_deleted", 0) == 1
    assert not state.get("role", False)
    assert not Path(state["rollback_file"]).exists()


def test_personal_tenant_operator_is_interactive_user_only(tmp_path):
    preflight = _read("scripts/preflight_personal_tenant.sh")
    deploy = _read("scripts/deploy_personal_tenant.sh")
    rotation = _read("scripts/rotate_entra_client_secret.sh")
    docs = _read("docs/deployment/personal-tenant.md")

    for source in (preflight, deploy, rotation):
        assert "ServicePrincipal is not supported" in source
        assert "== User" in source
    assert "az login" in docs
    assert "interactive User" in docs
    assert "or ServicePrincipal" not in docs

    environment, state_path = _rotation_environment(tmp_path, "success")
    environment["SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE"] = "ServicePrincipal"
    completed = subprocess.run(
        ["/bin/bash", "scripts/rotate_entra_client_secret.sh", "--apply"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode != 0
    assert json.loads(state_path.read_text()).get("calls", []) == []


def test_optimized_python_cannot_bypass_rotation_binding(tmp_path):
    for scenario in ("wrong-app", "wrong-secret-reference"):
        scenario_path = tmp_path / scenario
        scenario_path.mkdir()
        environment, state_path = _rotation_environment(scenario_path, scenario)
        environment["PYTHONOPTIMIZE"] = "1"
        completed = subprocess.run(
            ["/bin/bash", "scripts/rotate_entra_client_secret.sh", "--apply"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        state = json.loads(state_path.read_text())
        assert completed.returncode != 0, scenario
        assert state.get("new_sets", 0) == 0, scenario
        assert not state.get("role", False), scenario


def test_optimized_python_cannot_bypass_deployment_health_guards(tmp_path):
    helper = ROOT / "scripts/lib/deployment_health.sh"
    assert helper.exists()
    health = tmp_path / "health.json"
    runtime = tmp_path / "runtime.json"

    bad_contracts = (
        (
            "validate_live_smoke_contract",
            {
                "status": "broken",
                "runtime_mode": "fallback",
                "operational_store": "sqlite",
                "schema_version": "12",
            },
            {
                "runtime_mode": "fallback",
                "capability_health": {
                    "operational_store": "ready",
                    "agent_runtime": "ready",
                },
            },
        ),
        (
            "validate_live_smoke_contract",
            {
                "status": "ok",
                "runtime_mode": "live",
                "operational_store": "fabric_sql",
                "schema_version": 12,
            },
            {
                "runtime_mode": "live",
                "capability_health": {
                    "operational_store": "unverified",
                    "agent_runtime": "ready",
                },
            },
        ),
        (
            "validate_existing_final_health_contract",
            {"status": "broken", "runtime_mode": "live"},
            {},
        ),
    )
    for index, (function, health_payload, runtime_payload) in enumerate(bad_contracts):
        health.write_text(json.dumps(health_payload))
        runtime.write_text(json.dumps(runtime_payload))
        command = f'source "{helper}"; {function} "$HEALTH_FILE" "$RUNTIME_FILE"'
        completed = subprocess.run(
            ["/bin/bash", "-c", command],
            env={
                **os.environ,
                "PYTHONOPTIMIZE": "1",
                "HEALTH_FILE": str(health),
                "RUNTIME_FILE": str(runtime),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode != 0, index

    health.write_text(
        json.dumps(
            {
                "status": "ok",
                "runtime_mode": "live",
                "operational_store": "fabric_sql",
                "schema_version": 12,
            }
        )
    )
    runtime.write_text(
        json.dumps(
            {
                "runtime_mode": "live",
                "capability_health": {
                    "operational_store": "ready",
                    "agent_runtime": "ready",
                },
            }
        )
    )
    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            f'source "{helper}"; validate_live_smoke_contract "$HEALTH_FILE" "$RUNTIME_FILE"',
        ],
        env={
            **os.environ,
            "PYTHONOPTIMIZE": "1",
            "HEALTH_FILE": str(health),
            "RUNTIME_FILE": str(runtime),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    health.write_text(json.dumps({"status": "ok", "runtime_mode": "live"}))
    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            f'source "{helper}"; validate_existing_final_health_contract "$HEALTH_FILE"',
        ],
        env={**os.environ, "PYTHONOPTIMIZE": "1", "HEALTH_FILE": str(health)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_deployment_shell_runtime_python_contains_no_assert_statements():
    shell_sources = [
        *ROOT.glob("scripts/*.sh"),
        *ROOT.glob("scripts/lib/*.sh"),
    ]
    runtime_assert = re.compile(r"\bassert\b")
    offenders = [
        path.relative_to(ROOT)
        for path in shell_sources
        if runtime_assert.search(path.read_text())
    ]
    assert offenders == []


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
        "Microsoft.KeyVault/vaults/secrets/readMetadata/action",
        "Microsoft.KeyVault/vaults/secrets/setSecret/action",
    ):
        assert permission in docs
    assert "Key Vault Secrets Officer" in docs
    assert "Microsoft.KeyVault/vaults/secrets/write" not in docs
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
    assert not _contains_committed_target_id(deployment_assets)


@pytest.mark.parametrize(
    "labelled_target",
    (
        "tenant ID: 11111111-1111-4111-8111-111111111111",
        "tenant_id=22222222-2222-4222-8222-222222222222",
        "subscription-id 33333333-3333-4333-8333-333333333333",
        "subscription UUID is 44444444-4444-4444-8444-444444444444",
        "tenantId=55555555-5555-4555-8555-555555555555",
        "subscriptionId: 66666666-6666-4666-8666-666666666666",
        "tenantUuid=77777777-7777-4777-8777-777777777777",
        "subscriptionUuid: 88888888-8888-4888-8888-888888888888",
    ),
)
def test_target_id_guard_rejects_semantically_labelled_uuid(labelled_target):
    assert _contains_committed_target_id(labelled_target)


@pytest.mark.parametrize(
    "public_identifier_prose",
    (
        (
            "Use the public Work IQ application ID "
            "fdcc1f0c-4f76-4d4a-9c0a-9f8a8b8cf7a1 for tenant enablement."
        ),
        "Tenant enablement: public scope UUID 55555555-5555-4555-8555-555555555555.",
    ),
)
def test_target_id_guard_accepts_unrelated_public_identifier_uuid_prose(
    public_identifier_prose,
):
    assert not _contains_committed_target_id(public_identifier_prose)


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
