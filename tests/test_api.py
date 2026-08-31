from fastapi.testclient import TestClient

from apps.api.app.dependencies import build_composition
from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from services.persistence.sqlite import sqlite_store


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
        "power_bi_url": None,
        "capability_health": {
            "operational_store": "ready",
            "work_iq": "ready",
            "agent_runtime": "ready",
            "power_bi": "unavailable",
        },
    }


def _live_settings() -> Settings:
    return Settings(
        runtime_mode=RuntimeMode.LIVE,
        database_url=None,
        fabric_sql_server="example.fabric.microsoft.com",
        fabric_sql_database="supply-response",
        credential_mode="managed_identity",
    )


def test_live_runtime_reports_injected_graph_without_source_calls(tmp_path):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'live-contract.db'}",
        runtime_mode=RuntimeMode.LIVE,
    )
    services = build_composition(
        _live_settings(),
        live_components={
            "store": store,
            "analysis_service": object(),
            "auth_service": object(),
            "power_bi_url": "https://app.powerbi.com/groups/demo/reports/report",
        },
    )
    api = create_app(services=services)
    with TestClient(api) as client:
        runtime = client.get("/api/runtime")

    assert runtime.json() == {
        "runtime_mode": "live",
        "work_iq": "work_iq",
        "operational_store": "fabric_sql",
        "agent_runtime": "foundry",
        "power_bi_available": True,
        "power_bi_url": "https://app.powerbi.com/groups/demo/reports/report",
        "capability_health": {
            "operational_store": "ready",
            "work_iq": "ready",
            "agent_runtime": "ready",
            "power_bi": "ready",
        },
    }


def test_live_and_fallback_graphs_are_mutually_exclusive(tmp_path):
    live_store = sqlite_store(
        f"sqlite:///{tmp_path / 'live.db'}", runtime_mode=RuntimeMode.LIVE
    )
    services = build_composition(
        _live_settings(),
        live_components={
            "store": live_store,
            "analysis_service": object(),
            "auth_service": object(),
            "power_bi_url": "https://app.powerbi.com/groups/demo/reports/report",
        },
    )

    assert services.store is live_store
    assert services.operational_store == "fabric_sql"
    assert services.settings.database_url is None
