from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode


def test_health_and_runtime_report_the_composed_fallback_graph(tmp_path):
    api = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'smoke.db'}",
        )
    )

    with TestClient(api) as client:
        health = client.get("/health")
        runtime = client.get("/api/runtime")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "runtime_mode": "fallback"}
    assert runtime.json() == {
        "runtime_mode": "fallback",
        "work_iq": "synthetic",
        "operational_store": "sqlite",
        "agent_runtime": "local",
        "power_bi_available": False,
    }
