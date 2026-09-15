from __future__ import annotations

import json
import os
import stat
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
    assert api["api"]["knownClientApplications"] == []
    assert api["api"]["preAuthorizedApplications"] == []
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
            "resourceAppId": "00000003-0000-0000-c000-000000000000",
            "resourceAccess": [
                {"id": "{{GRAPH_MAIL_READWRITE_SCOPE_ID}}", "type": "Scope"},
                {"id": "{{GRAPH_MAIL_SEND_SCOPE_ID}}", "type": "Scope"},
            ],
        },
        {
            "resourceAppId": "{{WORKIQ_RESOURCE_APP_ID}}",
            "resourceAccess": [
                {"id": "{{WORKIQ_AGENT_ASK_SCOPE_ID}}", "type": "Scope"}
            ],
        },
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
    for role in api["appRoles"]:
        assert "origin" not in role


def test_manifest_write_payload_contains_no_graph_read_only_fields():
    api = load("api-app.json")
    forbidden = {"origin", "publisherDomain", "verifiedPublisher", "createdDateTime"}
    assert not forbidden.intersection(api)
    assert all(not forbidden.intersection(role) for role in api["appRoles"])


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


def test_configure_dry_run_validates_fixture_without_azure_calls(tmp_path: Path):
    state_file = tmp_path / ".env.tenant"
    env = _env()
    env["SUPPLY_RESPONSE_ENTRA_STATE_FILE"] = str(state_file)

    result = run("configure.sh", "configure.json", env=env)
    assert result.returncode == 0, result.stderr
    assert "DRY_RUN_VALID" in result.stdout
    assert "WorkIQAgent.Ask" in result.stdout
    assert not state_file.exists()


def test_configure_fails_closed_on_tenant_mismatch():
    env = _env()
    env["SUPPLY_RESPONSE_EXPECTED_TENANT_ID"] = "99999999-9999-4999-8999-999999999999"
    result = run("configure.sh", "configure.json", env=env)
    assert result.returncode != 0
    assert "tenant" in result.stderr.lower()


@pytest.mark.parametrize(
    "redirect",
    [
        "https://example.com/callback?next=1",
        "https://example.com/callback#fragment",
        "http://example.com/callback",
    ],
)
def test_configure_rejects_redirects_the_spa_would_reject(redirect):
    env = _env()
    env["SUPPLY_RESPONSE_REDIRECT_URI"] = redirect
    result = run("configure.sh", "configure.json", env=env)
    assert result.returncode != 0
    assert "redirect" in result.stderr.lower()


def test_configure_normalizes_a_single_trailing_slash():
    env = _env()
    env["SUPPLY_RESPONSE_REDIRECT_URI"] = "https://example.com/auth/callback/"
    result = run("configure.sh", "configure.json", env=env)
    assert result.returncode == 0, result.stderr
    assert "redirect=https://example.com/auth/callback" in result.stdout


@pytest.mark.parametrize(
    "redirect",
    [
        "https://EXAMPLE.com/auth/callback/",
        "https://example.com:443/auth/callback/",
        "http://localhost:80/auth/callback/",
    ],
)
def test_configure_rejects_redirect_authorities_the_spa_would_canonicalize(redirect):
    env = _env()
    env["SUPPLY_RESPONSE_REDIRECT_URI"] = redirect
    result = run("configure.sh", "configure.json", env=env)
    assert result.returncode != 0
    assert "canonical" in result.stderr.lower()


@pytest.mark.parametrize(
    "redirect",
    [
        "https://example.com/a/../auth/callback",
        "https://example.com/./auth/callback",
        "https://example.com/a/%2e%2e/auth/callback",
    ],
)
def test_configure_rejects_redirect_paths_the_spa_would_canonicalize(redirect):
    env = _env()
    env["SUPPLY_RESPONSE_REDIRECT_URI"] = redirect
    result = run("configure.sh", "configure.json", env=env)
    assert result.returncode != 0
    assert "canonical" in result.stderr.lower()


def _fake_az(tmp_path: Path) -> tuple[Path, Path]:
    state = tmp_path / "fake-az-state"
    executable = tmp_path / "supply-response-fake-az"
    executable.write_text(
        """#!/usr/bin/env python3
import json, os, pathlib, sys
state = pathlib.Path(os.environ["FAKE_AZ_STATE"])
state.mkdir(exist_ok=True)
args = sys.argv[1:]
if args == ["__supply_response_fake_adapter_probe__"]:
    print("SUPPLY_RESPONSE_FAKE_AZ_V1")
    sys.exit(0)
counter = state / "mutations"
creates = state / "creates"
mutations = int(counter.read_text()) if counter.exists() else 0
def mutate():
    global mutations
    mutations += 1
    counter.write_text(str(mutations))
if args[:2] == ["account", "show"]:
    print("11111111-1111-4111-8111-111111111111")
elif args[:2] == ["rest", "--method"] and "GET" in args:
    uri = args[args.index("--uri") + 1]
    if "organization" in uri:
        print(json.dumps({"verifiedDomains":[{"name":"willmacdonald.com","isVerified":True}]}))
    else:
        print("[]")
elif args[:3] == ["ad", "sp", "show"] and "44444444-4444-4444-8444-444444444444" in args:
    print(json.dumps({"appId":"44444444-4444-4444-8444-444444444444","oauth2PermissionScopes":[{"id":"55555555-5555-4555-8555-555555555555","value":"WorkIQAgent.Ask","isEnabled":True}]}))
elif args[:3] == ["ad", "app", "create"]:
    mutate()
    creates.write_text(str(int(creates.read_text()) + 1 if creates.exists() else 1))
    name = args[args.index("--display-name") + 1]
    api = name.endswith("API")
    record = {"appId":"22222222-2222-4222-8222-222222222222" if api else "33333333-3333-4333-8333-333333333333", "id":"77777777-7777-4777-8777-777777777777" if api else "88888888-8888-4888-8888-888888888888"}
    (state / ("app-" + record["appId"] + ".json")).write_text(json.dumps(record))
    print(json.dumps(record))
elif args[:3] == ["ad", "app", "show"]:
    client = args[args.index("--id") + 1]
    record = state / ("app-" + client + ".json")
    if not record.exists(): sys.exit(1)
    document = json.loads(record.read_text())
    if os.environ.get("FAKE_AZ_DRIFT") == "1" and "signInAudience" in document:
        document["signInAudience"] = "AzureADMultipleOrgs"
    print(json.dumps(document))
elif args[:2] == ["rest", "--method"] and "PATCH" in args:
    body = args[args.index("--body") + 1]
    payload = json.loads(pathlib.Path(body[1:]).read_text())
    forbidden = {"origin", "publisherDomain", "verifiedPublisher", "createdDateTime"}
    assert not forbidden.intersection(payload)
    assert all(not forbidden.intersection(role) for role in payload.get("appRoles", []))
    object_id = args[args.index("--uri") + 1].rsplit("/", 1)[-1]
    client = "22222222-2222-4222-8222-222222222222" if object_id.startswith("7777") else "33333333-3333-4333-8333-333333333333"
    payload.update({"appId": client, "id": object_id})
    for role in payload.get("appRoles", []):
        role["origin"] = "Application"
    (state / ("app-" + client + ".json")).write_text(json.dumps(payload))
    mutate()
elif args[:3] == ["ad", "sp", "show"]:
    client = args[args.index("--id") + 1]
    marker = state / ("sp-" + client)
    if not marker.exists(): sys.exit(1)
    print(json.dumps({"id":client}))
elif args[:3] == ["ad", "sp", "create"]:
    mutate()
    client = args[args.index("--id") + 1]
    (state / ("sp-" + client)).write_text("yes")
else:
    print("unsupported fake az: " + repr(args), file=sys.stderr)
    sys.exit(3)
"""
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable, state


@pytest.mark.parametrize(
    "failure_boundary",
    ["api_app", "web_app", "api_patch", "web_patch", "api_sp", "web_sp"],
)
def test_configure_apply_persists_progress_and_reuses_apps_after_each_failure(
    tmp_path, failure_boundary
):
    adapter, state = _fake_az(tmp_path)
    env = _env()
    env.pop("SUPPLY_RESPONSE_API_CLIENT_ID")
    env.pop("SUPPLY_RESPONSE_WEB_CLIENT_ID")
    env.update(
        {
            "FAKE_AZ_STATE": str(state),
            "SUPPLY_RESPONSE_TEST_MODE": "1",
            "SUPPLY_RESPONSE_TEST_AZ_ADAPTER": str(adapter),
            "SUPPLY_RESPONSE_INJECT_FAILURE_AFTER": failure_boundary,
            "SUPPLY_RESPONSE_ENTRA_STATE_FILE": str(tmp_path / ".env.tenant"),
        }
    )
    first = subprocess.run(
        [str(ENTRA / "configure.sh"), "--apply"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode != 0
    state_file = tmp_path / ".env.tenant"
    assert state_file.exists()
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600
    assert "SUPPLY_RESPONSE_ENTRA_STATE=INCOMPLETE" in state_file.read_text()

    env.pop("SUPPLY_RESPONSE_INJECT_FAILURE_AFTER")
    second = subprocess.run(
        [str(ENTRA / "configure.sh"), "--apply"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    assert "SUPPLY_RESPONSE_ENTRA_STATE=COMPLETE" in state_file.read_text()
    assert (state / "creates").read_text() == "2"
    stored_api = json.loads((state / f"app-{API_ID}.json").read_text())
    assert stored_api["api"]["knownClientApplications"] == []
    assert stored_api["api"]["preAuthorizedApplications"] == []


def test_apply_test_controls_require_the_exact_fake_adapter(tmp_path):
    fake_real_az = tmp_path / "az"
    called = tmp_path / "called"
    fake_real_az.write_text(
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {called}\nexit 2\n"
    )
    fake_real_az.chmod(fake_real_az.stat().st_mode | stat.S_IXUSR)
    env = _env()
    env.update(
        {
            "SUPPLY_RESPONSE_TEST_MODE": "1",
            "SUPPLY_RESPONSE_TEST_AZ_ADAPTER": str(fake_real_az),
            "SUPPLY_RESPONSE_ENTRA_STATE_FILE": str(tmp_path / ".env.tenant"),
            "SUPPLY_RESPONSE_INJECT_FAILURE_AFTER": "api_app",
        }
    )
    result = subprocess.run(
        [str(ENTRA / "configure.sh"), "--apply"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "fake adapter" in result.stderr.lower()
    assert not called.exists()
    assert not (tmp_path / ".env.tenant").exists()


def test_apply_never_marks_state_complete_when_final_validation_fails(tmp_path):
    adapter, state = _fake_az(tmp_path)
    env = _env()
    env.pop("SUPPLY_RESPONSE_API_CLIENT_ID")
    env.pop("SUPPLY_RESPONSE_WEB_CLIENT_ID")
    env.update(
        {
            "FAKE_AZ_STATE": str(state),
            "FAKE_AZ_DRIFT": "1",
            "SUPPLY_RESPONSE_TEST_MODE": "1",
            "SUPPLY_RESPONSE_TEST_AZ_ADAPTER": str(adapter),
            "SUPPLY_RESPONSE_ENTRA_STATE_FILE": str(tmp_path / ".env.tenant"),
            # This legacy variable must have no effect.
            "SUPPLY_RESPONSE_SKIP_FINAL_CHECK": "1",
        }
    )
    result = subprocess.run(
        [str(ENTRA / "configure.sh"), "--apply"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "exactly match" in result.stderr
    assert (
        "SUPPLY_RESPONSE_ENTRA_STATE=INCOMPLETE"
        in (tmp_path / ".env.tenant").read_text()
    )


def test_exact_check_logic_rejects_excess_permissions_roles_and_assignments():
    configure = (ENTRA / "configure.sh").read_text()
    assign = (ENTRA / "assign-personas.sh").read_text()
    assert "canonical_api_contract" in configure
    assert "canonical_web_contract" in configure
    assert "exact_persona_assignments" in assign


def _check_fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    fixture = json.loads((FIXTURES / "configure.json").read_text())
    api_text = json.dumps(load("api-app.json"))
    api_text = api_text.replace("{{API_APP_ID}}", API_ID)
    api_text = api_text.replace("{{WORKIQ_RESOURCE_APP_ID}}", WORKIQ_ID)
    api_text = api_text.replace(
        "{{WORKIQ_AGENT_ASK_SCOPE_ID}}", "55555555-5555-4555-8555-555555555555"
    )
    api_text = api_text.replace(
        "{{GRAPH_MAIL_READWRITE_SCOPE_ID}}", "66666666-6666-4666-8666-666666666666"
    )
    api_text = api_text.replace(
        "{{GRAPH_MAIL_SEND_SCOPE_ID}}", "77777777-7777-4777-8777-777777777777"
    )
    web_text = json.dumps(load("web-app.json"))
    web_text = web_text.replace("{{API_APP_ID}}", API_ID)
    web_text = web_text.replace(
        "{{REDIRECT_URI}}", _env()["SUPPLY_RESPONSE_REDIRECT_URI"]
    )
    fixture["apiApplication"] = json.loads(api_text)
    fixture["webApplication"] = json.loads(web_text)
    path = tmp_path / "configure-check.json"
    path.write_text(json.dumps(fixture))
    state_file = tmp_path / ".env.tenant"
    state_file.write_text(
        "SUPPLY_RESPONSE_ENTRA_STATE=COMPLETE\n"
        f"SUPPLY_RESPONSE_API_CLIENT_ID={API_ID}\n"
        f"SUPPLY_RESPONSE_WEB_CLIENT_ID={WEB_ID}\n"
    )
    env = _env()
    env.update(
        {
            "SUPPLY_RESPONSE_TEST_MODE": "1",
            "SUPPLY_RESPONSE_ENTRA_STATE_FILE": str(state_file),
        }
    )
    return path, env


@pytest.mark.parametrize("drift", ["excess_permission", "altered_role"])
def test_configure_check_rejects_permission_or_role_drift(tmp_path, drift):
    path, env = _check_fixture(tmp_path)
    fixture = json.loads(path.read_text())
    if drift == "excess_permission":
        fixture["apiApplication"]["requiredResourceAccess"].append(
            {
                "resourceAppId": "99999999-9999-4999-8999-999999999999",
                "resourceAccess": [
                    {"id": "98888888-8888-4888-8888-888888888888", "type": "Scope"}
                ],
            }
        )
    else:
        fixture["apiApplication"]["appRoles"][0]["description"] = "Drifted role"
    path.write_text(json.dumps(fixture))
    result = subprocess.run(
        [str(ENTRA / "configure.sh"), "--check", "--fixture", str(path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "exactly match" in result.stderr


def test_configure_check_accepts_graph_response_only_role_origin(tmp_path):
    path, env = _check_fixture(tmp_path)
    fixture = json.loads(path.read_text())
    for role in fixture["apiApplication"]["appRoles"]:
        role["origin"] = "Application"
    path.write_text(json.dumps(fixture))
    result = subprocess.run(
        [str(ENTRA / "configure.sh"), "--check", "--fixture", str(path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CHECK_VALID" in result.stdout


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("knownClientApplications", ["99999999-9999-4999-8999-999999999999"]),
        (
            "preAuthorizedApplications",
            [
                {
                    "appId": "99999999-9999-4999-8999-999999999999",
                    "delegatedPermissionIds": ["98888888-8888-4888-8888-888888888888"],
                }
            ],
        ),
    ],
)
def test_configure_check_rejects_client_preauthorization_drift(tmp_path, field, value):
    path, env = _check_fixture(tmp_path)
    fixture = json.loads(path.read_text())
    fixture["apiApplication"]["api"][field] = value
    path.write_text(json.dumps(fixture))
    result = subprocess.run(
        [str(ENTRA / "configure.sh"), "--check", "--fixture", str(path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "exactly match" in result.stderr


def test_configure_check_accepts_empty_client_preauthorization_collections(tmp_path):
    path, env = _check_fixture(tmp_path)
    fixture = json.loads(path.read_text())
    assert fixture["apiApplication"]["api"]["knownClientApplications"] == []
    assert fixture["apiApplication"]["api"]["preAuthorizedApplications"] == []
    for role in fixture["apiApplication"]["appRoles"]:
        role["origin"] = "Application"
    path.write_text(json.dumps(fixture))
    result = subprocess.run(
        [str(ENTRA / "configure.sh"), "--check", "--fixture", str(path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CHECK_VALID" in result.stdout


def test_configure_check_rejects_security_field_drift(tmp_path):
    path, env = _check_fixture(tmp_path)
    fixture = json.loads(path.read_text())
    fixture["apiApplication"]["api"]["acceptMappedClaims"] = True
    path.write_text(json.dumps(fixture))
    result = subprocess.run(
        [str(ENTRA / "configure.sh"), "--check", "--fixture", str(path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "exactly match" in result.stderr


def test_assignment_check_rejects_an_excess_persona_role(tmp_path):
    fixture = json.loads((FIXTURES / "assignments.json").read_text())
    roles = {role["value"]: role["id"] for role in fixture["appRoles"]}
    fixture["assignments"] = [
        {
            "principalId": ALEX_ID,
            "resourceId": fixture["apiServicePrincipalId"],
            "appRoleId": roles["material_planner"],
        },
        {
            "principalId": ALEX_ID,
            "resourceId": fixture["apiServicePrincipalId"],
            "appRoleId": roles["response_approver"],
        },
        {
            "principalId": ALEX_ID,
            "resourceId": fixture["apiServicePrincipalId"],
            "appRoleId": roles["quality_approver"],
        },
        {
            "principalId": JORDAN_ID,
            "resourceId": fixture["apiServicePrincipalId"],
            "appRoleId": roles["quality_approver"],
        },
        {
            "principalId": TAYLOR_ID,
            "resourceId": fixture["apiServicePrincipalId"],
            "appRoleId": roles["finance_approver"],
        },
    ]
    path = tmp_path / "assignments-extra.json"
    path.write_text(json.dumps(fixture))
    result = subprocess.run(
        [str(ENTRA / "assign-personas.sh"), "--check", "--fixture", str(path)],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "exactly match" in result.stderr


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
