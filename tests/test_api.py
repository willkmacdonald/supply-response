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
        "deployment_contract": None,
    }


def _live_settings() -> Settings:
    return Settings(
        runtime_mode=RuntimeMode.LIVE,
        database_url=None,
        fabric_sql_server="example.fabric.microsoft.com",
        fabric_sql_database="supply-response",
        credential_mode="managed_identity",
    )


def test_live_runtime_reports_injected_graph_as_unverified_without_readiness_port(
    tmp_path,
):
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
        "power_bi_available": False,
        "power_bi_url": None,
        "capability_health": {
            "operational_store": "unverified",
            "work_iq": "unverified",
            "agent_runtime": "unverified",
            "power_bi": "unverified",
        },
        "deployment_contract": {
            "scenario_effective_time": "2026-09-01T09:00:00-05:00",
            "corpus_version": "",
            "supplier_source_id": "",
            "quality_source_id": "",
            "signal_agent_version": "",
            "context_agent_version": "",
            "decision_agent_version": "",
        },
    }


def test_live_runtime_uses_typed_readiness_instead_of_store_enum(tmp_path):
    from apps.api.app.readiness import ReadinessSnapshot

    class Ready:
        def check(self):
            return ReadinessSnapshot(
                capability_health={
                    "operational_store": "ready",
                    "work_iq": "ready",
                    "agent_runtime": "ready",
                    "power_bi": "ready",
                },
                fabric_schema_version=12,
                power_bi_verified=True,
            )

    store = sqlite_store(
        f"sqlite:///{tmp_path / 'typed-ready.db'}", runtime_mode=RuntimeMode.LIVE
    )
    services = build_composition(
        _live_settings(),
        live_components={
            "store": store,
            "analysis_service": object(),
            "auth_service": object(),
            "power_bi_url": "https://app.powerbi.com/groups/demo/reports/report",
            "readiness": Ready(),
        },
    )
    with TestClient(create_app(services=services)) as client:
        payload = client.get("/api/runtime").json()
    assert payload["power_bi_available"] is True
    assert payload["capability_health"]["operational_store"] == "ready"


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
