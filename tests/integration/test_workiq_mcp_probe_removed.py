"""The approved one-shot MCP probe must not remain in the application."""

from importlib.util import find_spec
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode


def test_temporary_mcp_probe_is_removed_from_runtime():
    for module in (
        "integrations.workiq.mcp_probe",
        "integrations.workiq.probe_binding",
        "integrations.workiq.probe_http",
        "apps.api.app.routes.workiq_probe",
    ):
        assert find_spec(module) is None
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "apps/api/app/main.py",
        "apps/web/src/App.tsx",
        "apps/web/src/api.ts",
    ):
        source = (root / relative).read_text()
        assert "workiq_probe" not in source
        assert "WorkIQProbe" not in source
        assert "/diagnostics/workiq-fetch" not in source
    assert not (root / "apps/web/src/components/WorkIQProbe.tsx").exists()
    assert not (root / "apps/web/src/components/WorkIQProbe.test.tsx").exists()


@pytest.mark.parametrize("with_static_assets", [False, True])
def test_retired_mcp_probe_endpoint_is_not_registered(tmp_path, with_static_assets):
    static_directory = None
    if with_static_assets:
        static_directory = tmp_path / "static"
        static_directory.mkdir()
        (static_directory / "index.html").write_text("<html>Fixture SPA</html>")
    app = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'retired-probe.db'}",
        ),
        static_directory=static_directory,
    )
    endpoint = "/api/diagnostics/workiq-fetch"
    assert endpoint not in app.openapi()["paths"]
    with TestClient(app) as client:
        assert client.get(endpoint).status_code == 404
        # The unchanged production SPA GET catch-all rejects POST with 405.
        assert client.post(endpoint).status_code == (405 if with_static_assets else 404)
