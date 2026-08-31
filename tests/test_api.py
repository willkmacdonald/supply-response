import pytest
from fastapi.testclient import TestClient

from apps.api.app import dependencies
from apps.api.app.dependencies import build_composition
from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from integrations.fabric.health import FABRIC_SCHEMA_VERSION, FabricHealth
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
    }


def _live_settings() -> Settings:
    return Settings(
        runtime_mode=RuntimeMode.LIVE,
        database_url=None,
        fabric_sql_server="example.fabric.microsoft.com",
        fabric_sql_database="supply-response",
        credential_mode="managed_identity",
    )


def test_live_runtime_is_reported_only_after_fabric_health_succeeds(
    tmp_path,
    monkeypatch,
):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'live-contract.db'}",
        runtime_mode=RuntimeMode.LIVE,
    )
    monkeypatch.setattr(dependencies, "fabric_store", lambda settings: store)
    monkeypatch.setattr(
        dependencies,
        "check_fabric_health",
        lambda engine: FabricHealth(
            operational_store="fabric_sql",
            power_bi_available=True,
            schema_version=FABRIC_SCHEMA_VERSION,
        ),
    )

    services = build_composition(_live_settings())
    api = create_app(services=services)
    with TestClient(api) as client:
        runtime = client.get("/api/runtime")

    assert runtime.json() == {
        "runtime_mode": "live",
        "work_iq": "synthetic",
        "operational_store": "fabric_sql",
        "agent_runtime": "local",
        "power_bi_available": True,
    }


def test_live_composition_never_falls_back_when_fabric_connection_fails(monkeypatch):
    fallback_called = False

    def fail_fabric(settings):
        raise RuntimeError("Fabric token rejected")

    def record_fallback(*args, **kwargs):
        nonlocal fallback_called
        fallback_called = True
        raise AssertionError("SQLite fallback must not be constructed")

    monkeypatch.setattr(dependencies, "fabric_store", fail_fabric)
    monkeypatch.setattr(dependencies, "sqlite_store", record_fallback)

    with pytest.raises(RuntimeError, match="Fabric token rejected"):
        build_composition(_live_settings())

    assert fallback_called is False


def test_live_composition_propagates_schema_health_failure(tmp_path, monkeypatch):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'bad-schema.db'}",
        runtime_mode=RuntimeMode.LIVE,
    )
    monkeypatch.setattr(dependencies, "fabric_store", lambda settings: store)
    monkeypatch.setattr(
        dependencies,
        "check_fabric_health",
        lambda engine: (_ for _ in ()).throw(RuntimeError("schema mismatch")),
    )

    with pytest.raises(RuntimeError, match="schema mismatch"):
        build_composition(_live_settings())
