from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote_plus, urlsplit

import pytest
from pydantic import ValidationError

from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from services.persistence import fabric_sql
from services.persistence import store as store_module


def test_fabric_sql_adapter_module_exists():
    assert find_spec("services.persistence.fabric_sql") is not None


def test_fabric_sql_adapter_exposes_required_contract():
    assert hasattr(fabric_sql, "build_fabric_engine")
    assert hasattr(fabric_sql, "fabric_store")
    assert hasattr(fabric_sql, "fabric_store_from_environment")


class RotatingCredential:
    def __init__(self) -> None:
        self.calls = 0

    def get_token(self, scope: str):
        assert scope == "https://database.windows.net/.default"
        self.calls += 1
        return SimpleNamespace(token=f"token-{self.calls}")


def _settings(**overrides):
    values = {
        "fabric_sql_server": "example.datawarehouse.fabric.microsoft.com",
        "fabric_sql_database": "supply-response",
        "credential_mode": "azure_cli",
        "allowed_tenant_id": "00000000-0000-0000-0000-000000000001",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _validated_live_settings() -> Settings:
    return Settings(
        runtime_mode=RuntimeMode.LIVE,
        database_url=None,
        fabric_sql_server="example.fabric.microsoft.com",
        fabric_sql_database="supply-response",
        credential_mode="managed_identity",
    )


def test_build_engine_uses_driver_18_encryption_and_no_secret(monkeypatch):
    captured: dict[str, object] = {}
    fake_engine = object()

    def fake_create_engine(url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return fake_engine

    def fake_listens_for(target, event_name):
        assert target is fake_engine
        assert event_name == "do_connect"
        return lambda callback: captured.update(callback=callback) or callback

    monkeypatch.setattr(fabric_sql, "create_engine", fake_create_engine)
    monkeypatch.setattr(fabric_sql.event, "listens_for", fake_listens_for)

    assert (
        fabric_sql.build_fabric_engine(_settings(), RotatingCredential()) is fake_engine
    )

    url = str(captured["url"])
    query = parse_qs(urlsplit(url).query)
    connection_string = unquote_plus(query["odbc_connect"][0])
    assert "Driver={ODBC Driver 18 for SQL Server}" in connection_string
    assert "Encrypt=yes" in connection_string
    assert "TrustServerCertificate=no" in connection_string
    assert "Server=example.datawarehouse.fabric.microsoft.com" in connection_string
    assert "Database=supply-response" in connection_string
    assert "UID=" not in connection_string
    assert "PWD=" not in connection_string
    assert "password" not in connection_string.lower()
    assert captured["kwargs"] == {
        "pool_pre_ping": True,
        "execution_options": {"schema_translate_map": {None: "app"}},
    }


def test_each_physical_connect_gets_a_fresh_utf16_access_token(monkeypatch):
    captured: dict[str, object] = {}
    credential = RotatingCredential()
    fake_engine = object()
    monkeypatch.setattr(
        fabric_sql, "create_engine", lambda *args, **kwargs: fake_engine
    )

    def fake_listens_for(target, event_name):
        return lambda callback: captured.update(callback=callback) or callback

    monkeypatch.setattr(fabric_sql.event, "listens_for", fake_listens_for)
    fabric_sql.build_fabric_engine(_settings(), credential)
    callback = captured["callback"]
    first_params: dict[str, object] = {}
    second_params: dict[str, object] = {}

    callback(None, None, [], first_params)
    callback(None, None, [], second_params)

    first = first_params["attrs_before"][fabric_sql.SQL_COPT_SS_ACCESS_TOKEN]
    second = second_params["attrs_before"][fabric_sql.SQL_COPT_SS_ACCESS_TOKEN]
    assert first == b"\x0e\x00\x00\x00t\x00o\x00k\x00e\x00n\x00-\x001\x00"
    assert second == b"\x0e\x00\x00\x00t\x00o\x00k\x00e\x00n\x00-\x002\x00"
    assert credential.calls == 2


@pytest.mark.parametrize(
    ("mode", "expected", "expected_kwargs"),
    [
        (
            "azure_cli",
            "cli",
            {"tenant_id": "00000000-0000-0000-0000-000000000001"},
        ),
        ("managed_identity", "managed", {}),
    ],
)
def test_credential_selection_is_explicit(
    monkeypatch,
    mode,
    expected,
    expected_kwargs,
):
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        fabric_sql,
        "AzureCliCredential",
        lambda **kwargs: calls.append(("cli", kwargs)) or "cli-credential",
    )
    monkeypatch.setattr(
        fabric_sql,
        "ManagedIdentityCredential",
        lambda **kwargs: calls.append(("managed", kwargs)) or "managed-credential",
    )

    credential = fabric_sql.build_credential(_settings(credential_mode=mode))

    assert credential == f"{expected}-credential"
    assert calls == [(expected, expected_kwargs)]


def test_unknown_credential_mode_is_rejected():
    with pytest.raises(ValueError, match="unsupported Fabric credential mode"):
        fabric_sql.build_credential(_settings(credential_mode="default_chain"))


def test_live_settings_require_fabric_server_database_and_credential_mode():
    with pytest.raises(ValidationError) as raised:
        Settings(
            runtime_mode=RuntimeMode.LIVE,
            database_url=None,
            allowed_tenant_id="00000000-0000-0000-0000-000000000001",
        )

    message = str(raised.value)
    assert "SUPPLY_RESPONSE_FABRIC_SQL_SERVER" in message
    assert "SUPPLY_RESPONSE_FABRIC_SQL_DATABASE" in message
    assert "SUPPLY_RESPONSE_CREDENTIAL_MODE" in message


def test_azure_cli_mode_requires_the_allowed_tenant():
    with pytest.raises(
        ValidationError,
        match="SUPPLY_RESPONSE_ALLOWED_TENANT_ID",
    ):
        Settings(
            runtime_mode=RuntimeMode.LIVE,
            database_url=None,
            fabric_sql_server="example.fabric.microsoft.com",
            fabric_sql_database="supply-response",
            credential_mode="azure_cli",
        )


def test_managed_identity_mode_does_not_require_a_user_secret_or_tenant():
    settings = Settings(
        runtime_mode=RuntimeMode.LIVE,
        database_url=None,
        fabric_sql_server="example.fabric.microsoft.com",
        fabric_sql_database="supply-response",
        credential_mode="managed_identity",
    )

    assert settings.allowed_tenant_id is None
    assert not hasattr(settings, "password")
    assert not hasattr(settings, "username")


def test_fallback_mode_still_requires_a_sqlite_database_url():
    with pytest.raises(ValidationError, match="SUPPLY_RESPONSE_DATABASE_URL"):
        Settings(runtime_mode=RuntimeMode.FALLBACK, database_url=None)


def test_canonical_store_does_not_embed_sqlite_only_dml():
    source = Path("services/persistence/store.py").read_text(encoding="utf-8")

    assert "sqlalchemy.dialects.sqlite" not in source
    assert "sqlite_insert" not in source


def test_canonical_store_factory_routes_live_mode_to_fabric(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(fabric_sql, "fabric_store", lambda settings: sentinel)

    result = store_module.build_store(_validated_live_settings())

    assert result is sentinel
