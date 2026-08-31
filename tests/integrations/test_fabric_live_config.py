from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
PROBE = "tests/integration/test_fabric_marker_probe.py"
SERVER = "SUPPLY_RESPONSE_FABRIC_SQL_SERVER"
DATABASE = "SUPPLY_RESPONSE_FABRIC_SQL_DATABASE"


def _run_probe(*, server: str | None, database: str | None):
    environment = os.environ.copy()
    environment.pop(SERVER, None)
    environment.pop(DATABASE, None)
    if server is not None:
        environment[SERVER] = server
    if database is not None:
        environment[DATABASE] = database
    return subprocess.run(
        [sys.executable, "-m", "pytest", PROBE, "-q", "-ra"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_both_absent_settings_skip_fabric_live_tests():
    result = _run_probe(server=None, database=None)

    assert result.returncode == 0
    assert "SKIPPED" in result.stdout
    assert "Fabric SQL live settings are not configured" in result.stdout


@pytest.mark.parametrize(
    ("server", "database"),
    [("server.example", None), (None, "supply-response")],
)
def test_partial_settings_fail_collection_without_connecting(server, database):
    result = _run_probe(server=server, database=database)
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert SERVER in output
    assert DATABASE in output
    assert "must be configured together" in output


def test_both_present_settings_enable_the_side_effect_free_marker_probe():
    result = _run_probe(server="server.example", database="supply-response")

    assert result.returncode == 0
    assert result.stdout.lstrip().startswith(".")
    assert "SKIPPED" not in result.stdout
