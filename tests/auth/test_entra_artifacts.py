from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
ENTRA = ROOT / "infra" / "entra"
FIXTURES = Path(__file__).parent / "fixtures"

TENANT_ID = "11111111-1111-4111-8111-111111111111"
API_ID = "22222222-2222-4222-8222-222222222222"
WEB_ID = "33333333-3333-4333-8333-333333333333"
WORKIQ_ID = "44444444-4444-4444-8444-444444444444"
ALEX_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
JORDAN_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
TAYLOR_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def load(name: str):
    return json.loads((ENTRA / name).read_text())


def test_manifests_define_only_two_single_tenant_apps_and_exact_permissions():
    api = load("api-app.json")
    web = load("web-app.json")

    assert api["displayName"] == "Supply Response API"
    assert web["displayName"] == "Supply Response Web"
    assert api["signInAudience"] == web["signInAudience"] == "AzureADMyOrg"
    scope = api["api"]["oauth2PermissionScopes"]
    assert [(item["value"], item["type"], item["isEnabled"]) for item in scope] == [
        ("access_as_user", "User", True)
    ]
    assert {
        (role["value"], tuple(role["allowedMemberTypes"])) for role in api["appRoles"]
    } == {
        ("material_planner", ("User",)),
        ("response_approver", ("User",)),
        ("quality_approver", ("User",)),
        ("finance_approver", ("User",)),
    }
    assert api["requiredResourceAccess"] == [
        {
            "resourceAppId": "{{WORKIQ_RESOURCE_APP_ID}}",
            "resourceAccess": [
                {"id": "{{WORKIQ_AGENT_ASK_SCOPE_ID}}", "type": "Scope"}
            ],
        }
    ]
    assert web["requiredResourceAccess"] == [
        {
            "resourceAppId": "{{API_APP_ID}}",
            "resourceAccess": [{"id": scope[0]["id"], "type": "Scope"}],
        }
    ]
    serialized = json.dumps({"api": api, "web": web})
    assert "WorkIQAgent.Ask" not in json.dumps(web)
    assert "clientSecret" not in serialized
    assert "passwordCredentials" not in serialized


def _env() -> dict[str, str]:
    return {
        **os.environ,
        "SUPPLY_RESPONSE_CONFIRM_TENANT": "willmacdonald.com",
        "SUPPLY_RESPONSE_EXPECTED_TENANT_ID": TENANT_ID,
        "SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID": WORKIQ_ID,
        "SUPPLY_RESPONSE_REDIRECT_URI": "http://localhost:5173/auth/callback",
        "SUPPLY_RESPONSE_API_CLIENT_ID": API_ID,
        "SUPPLY_RESPONSE_WEB_CLIENT_ID": WEB_ID,
        "SUPPLY_RESPONSE_ALEX_OBJECT_ID": ALEX_ID,
        "SUPPLY_RESPONSE_JORDAN_OBJECT_ID": JORDAN_ID,
        "SUPPLY_RESPONSE_TAYLOR_OBJECT_ID": TAYLOR_ID,
    }


def run(script: str, fixture: str, *, env: dict[str, str] | None = None):
    return subprocess.run(
        [str(ENTRA / script), "--dry-run", "--fixture", str(FIXTURES / fixture)],
        cwd=ROOT,
        env=env or _env(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_configure_dry_run_validates_fixture_without_azure_calls():
    result = run("configure.sh", "configure.json")
    assert result.returncode == 0, result.stderr
    assert "DRY_RUN_VALID" in result.stdout
    assert "WorkIQAgent.Ask" in result.stdout
    assert not (ENTRA / ".env.tenant").exists()


def test_configure_fails_closed_on_tenant_mismatch():
    env = _env()
    env["SUPPLY_RESPONSE_EXPECTED_TENANT_ID"] = "99999999-9999-4999-8999-999999999999"
    result = run("configure.sh", "configure.json", env=env)
    assert result.returncode != 0
    assert "tenant" in result.stderr.lower()


def test_assign_personas_dry_run_uses_only_exact_object_ids_and_role_values():
    result = run("assign-personas.sh", "assignments.json")
    assert result.returncode == 0, result.stderr
    for object_id, role in [
        (ALEX_ID, "material_planner"),
        (ALEX_ID, "response_approver"),
        (JORDAN_ID, "quality_approver"),
        (TAYLOR_ID, "finance_approver"),
    ]:
        assert f"{object_id} {role}" in result.stdout
    assert "@" not in result.stdout


def test_assign_personas_rejects_duplicate_or_non_uuid_bindings():
    env = _env()
    env["SUPPLY_RESPONSE_TAYLOR_OBJECT_ID"] = JORDAN_ID
    result = run("assign-personas.sh", "assignments.json", env=env)
    assert result.returncode != 0
    assert "distinct" in result.stderr

    env = _env()
    env["SUPPLY_RESPONSE_ALEX_OBJECT_ID"] = "alex@willmacdonald.com"
    result = run("assign-personas.sh", "assignments.json", env=env)
    assert result.returncode != 0
    assert "UUID" in result.stderr


@pytest.mark.parametrize("script", ["configure.sh", "assign-personas.sh"])
def test_scripts_expose_separate_nonmutating_check_and_explicit_apply(script):
    text = (ENTRA / script).read_text()
    assert "--dry-run" in text
    assert "--check" in text
    assert "--apply" in text
    assert "credential reset" not in text
    assert 'source "$script_dir/.env.tenant"' not in text
    assert "userPrincipalName" not in text
    assert "displayName eq" not in text


def test_tenant_binding_file_is_ignored():
    assert ".env.tenant" in (ROOT / ".gitignore").read_text().splitlines()
