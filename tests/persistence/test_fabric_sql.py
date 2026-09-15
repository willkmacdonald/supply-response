from contextlib import contextmanager
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote_plus, urlsplit

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from integrations.fabric.schema import split_go_batches
from services.persistence import fabric_sql
from services.persistence import store as store_module


@pytest.mark.parametrize("operation", ["create", "apply"])
@pytest.mark.parametrize(
    "lock_result", [0, 1, -1, -2, -3, -999, None, "0", "sql-error"]
)
def test_fabric_retention_lock_is_transaction_owned_and_fails_closed(
    monkeypatch, operation, lock_result
):
    from sqlalchemy.dialects import mssql

    from services.persistence import presenter_runs
    from services.persistence.presenter_runs import (
        PresenterRetentionLockUnavailable,
        PresenterRetentionPlan,
        PresenterRetentionResult,
    )
    from tests.persistence.test_presenter_runs import bound_case

    calls = []
    case, snapshot = bound_case("lock-case")
    plan = PresenterRetentionPlan(case.case_id, (case.case_id,), ())

    def execute(statement, parameters):
        calls.append("lock")
        sql = str(statement.compile(dialect=mssql.dialect()))
        assert "IF @@TRANCOUNT = 0 BEGIN TRANSACTION" in sql
        assert "sys.sp_getapplock" in sql
        assert "@LockMode = 'Exclusive'" in sql
        assert "@LockOwner = 'Transaction'" in sql
        assert "@DbPrincipal = 'public'" in sql
        assert "sp_releaseapplock" not in sql
        assert "COMMIT" not in sql
        assert parameters == {
            "resource": "supply-response:app:presenter-retention:v1",
            "lock_timeout_ms": 5_000,
        }
        if lock_result == "sql-error":
            raise OperationalError("lock SQL", {}, RuntimeError("unavailable"))
        return SimpleNamespace(scalar_one=lambda: lock_result)

    connection = SimpleNamespace(execute=execute)

    @contextmanager
    def transaction():
        calls.append("begin")
        try:
            yield connection
        except Exception:
            calls.append("rollback")
            raise
        else:
            calls.append("commit")

    store = fabric_sql.FabricSqlStore(
        SimpleNamespace(begin=transaction), runtime_mode=RuntimeMode.LIVE
    )
    monkeypatch.setattr(
        store, "_insert_case_connection", lambda *args: calls.append("insert")
    )

    def plan_retention(*args, **kwargs):
        calls.append("plan")
        return plan

    def delete_aggregates(*args):  # allowed: record transaction ordering in this test
        calls.append("delete")
        return PresenterRetentionResult(plan, dict(plan.planned_deletions))

    monkeypatch.setattr(presenter_runs, "plan_presenter_retention", plan_retention)
    monkeypatch.setattr(
        presenter_runs, "delete_presenter_aggregates", delete_aggregates
    )

    def invoke():
        if operation == "create":
            return store.create_presenter_case(case, snapshot)
        return store.apply_presenter_retention(plan)

    if lock_result in (0, 1):
        assert invoke().plan == plan
        assert calls == [
            "begin",
            "lock",
            *(["insert"] if operation == "create" else []),
            "plan",
            "delete",
            "commit",
        ]
    else:
        with pytest.raises(PresenterRetentionLockUnavailable):
            invoke()
        assert calls == ["begin", "lock", "rollback"]


@pytest.mark.parametrize("dialect_name", ["sqlite", "mssql"])
def test_presenter_retention_statements_compile_portably(dialect_name):
    from sqlalchemy.dialects import mssql, sqlite

    from services.persistence.presenter_runs import (
        PRESENTER_AGGREGATE_DELETE_ORDER,
        PresenterRetentionPlan,
        presenter_aggregate_delete_statements,
    )

    dialect = mssql.dialect() if dialect_name == "mssql" else sqlite.dialect()
    statements = tuple(
        presenter_aggregate_delete_statements(
            PresenterRetentionPlan("current", ("current",), ("expired",))
        )
    )
    assert len(statements) == len(PRESENTER_AGGREGATE_DELETE_ORDER) + 1
    assert (
        tuple(statement.table.name for statement in statements if statement.is_delete)
        == PRESENTER_AGGREGATE_DELETE_ORDER
    )
    for statement in statements:
        sql = str(
            statement.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
        )
        assert "expired" in sql and "WHERE" in sql
        assert "reporting" not in sql and "operational_source" not in sql


def test_fabric_sql_adapter_module_exists():
    assert find_spec("services.persistence.fabric_sql") is not None


def test_finance_review_schema_is_additive_and_bound():
    sql = Path("fabric/sql/001_operational_schema.sql").read_text()
    assert "CREATE TABLE app.finance_review_revisions" in sql
    assert "PRIMARY KEY (review_id, revision)" in sql
    assert "UNIQUE (idempotency_key)" in sql
    assert "CHECK (revision > 0)" in sql
    assert "CHECK (ISJSON(payload_json) = 1)" in sql
    assert "REFERENCES app.case_instances (case_id)" in sql
    assert "REFERENCES app.analysis_versions (analysis_id)" in sql
    for column in (
        "case_id",
        "analysis_id",
        "analysis_material_hash",
        "option_id",
        "status",
        "recorded_at",
    ):
        assert f"ix_finance_review_revisions_{column}" in sql


def test_proposal_selection_schema_is_guarded_and_ordered():
    sql = Path("fabric/sql/001_operational_schema.sql").read_text()
    assert "CREATE TABLE app.case_proposal_selections" in sql
    assert "FOREIGN KEY (finance_review_id, finance_review_revision)" in sql
    assert (
        "finance_review_id IS NOT NULL AND finance_review_revision IS NOT NULL" in sql
    )
    assert "WHERE finance_review_id IS NOT NULL" in sql
    assert "CHECK (ISJSON(payload_json) = 1)" in sql
    assert "DEFAULT (0) WITH VALUES" in sql
    batches = split_go_batches(sql)
    generation_add = next(
        index
        for index, batch in enumerate(batches)
        if "ADD proposal_generation" in batch
    )
    pointer_add = next(
        index
        for index, batch in enumerate(batches)
        if "ADD current_selection_id" in batch
    )
    for token, added in (
        ("proposal_generation >= 0", generation_add),
        ("FOREIGN KEY (current_selection_id)", pointer_add),
        ("ix_case_projection_current_selection_id", pointer_add),
    ):
        assert any(token in batch for batch in batches[added + 1 :])
        assert token not in batches[added]


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
