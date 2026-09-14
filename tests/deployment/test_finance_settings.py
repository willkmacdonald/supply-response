"""The supported release path must carry both approval settings explicitly."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_finance_settings_are_optional_and_wired_end_to_end():
    main = (ROOT / "infra/main.bicep").read_text()
    params = json.loads((ROOT / "infra/main.parameters.json").read_text())["parameters"]
    module = (ROOT / "infra/modules/container-apps.bicep").read_text()
    assert "param taylorObjectId string = ''" in main
    assert "param independentFinanceEnabled bool = false" in main
    assert "taylorObjectId: taylorObjectId" in main
    assert "independentFinanceEnabled: independentFinanceEnabled" in main
    assert params["taylorObjectId"]["value"] == "${SUPPLY_RESPONSE_TAYLOR_OBJECT_ID=}"
    assert (
        params["independentFinanceEnabled"]["value"]
        == "${SUPPLY_RESPONSE_INDEPENDENT_FINANCE_ENABLED=false}"
    )
    assert (
        "{ name: 'SUPPLY_RESPONSE_TAYLOR_OBJECT_ID', value: runtimeSettings.taylorObjectId }"
        in module
    )
    assert (
        "{ name: 'SUPPLY_RESPONSE_INDEPENDENT_FINANCE_ENABLED', value: string(runtimeSettings.independentFinanceEnabled) }"
        in module
    )


@pytest.mark.parametrize(
    "name,default,value",
    [
        ("SUPPLY_RESPONSE_TAYLOR_OBJECT_ID", "", None),
        (
            "SUPPLY_RESPONSE_TAYLOR_OBJECT_ID",
            "",
            "11111111-1111-4111-8111-111111111111",
        ),
        ("SUPPLY_RESPONSE_INDEPENDENT_FINANCE_ENABLED", "false", None),
        ("SUPPLY_RESPONSE_INDEPENDENT_FINANCE_ENABLED", "false", "true"),
        ("SUPPLY_RESPONSE_INDEPENDENT_FINANCE_ENABLED", "false", "false"),
    ],
)
def test_release_passes_explicit_value_or_safe_default(name, default, value):
    lines = (ROOT / "scripts/deploy_personal_tenant.sh").read_text().splitlines()
    line = next(
        (line for line in lines if line.startswith(f"safe_run azd-setting-{name} ")),
        None,
    )
    assert line is not None, f"{name} missing from supported deployment path"
    environment = os.environ.copy()
    environment.pop(name, None)
    if value is not None:
        environment[name] = value
    result = subprocess.run(
        [
            "bash",
            "-c",
            'safe_run() { [[ "$#" == 6 && "$2" == azd && "$3" == env && "$4" == set && "$5" == "$setting" && "$6" == "$expected" ]]; }; setting="$2"; expected="$3"; eval "$1"',
            "finance-setting-test",
            line,
            name,
            default if value is None else value,
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
