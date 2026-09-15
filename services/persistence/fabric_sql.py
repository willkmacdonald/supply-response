"""Fabric SQL Database persistence over ODBC Driver 18 and Entra tokens."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

from azure.core.credentials import TokenCredential
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from sqlalchemy import Connection, Engine, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError

from data.domain import RuntimeMode
from data.domain.execution import Playback
from services.persistence.presenter_runs import PresenterRetentionLockUnavailable
from services.persistence.store import SqlAlchemyStore, serialize_model

if TYPE_CHECKING:
    from apps.api.app.settings import Settings


SQL_COPT_SS_ACCESS_TOKEN = 1256
SQL_DATABASE_SCOPE = "https://database.windows.net/.default"


class FabricSqlStore(SqlAlchemyStore):
    def _acquire_presenter_retention_lock(self, connection: Connection) -> None:
        # Application locks are scoped by database/principal/resource. A fixed
        # resource serializes every presenter run across connections/processes;
        # transaction ownership holds it through commit or rollback.
        try:
            result = connection.execute(
                text(
                    """
                    IF @@TRANCOUNT = 0 BEGIN TRANSACTION;
                    DECLARE @lock_result int;
                    EXEC @lock_result = sys.sp_getapplock
                        @Resource = :resource,
                        @LockMode = 'Exclusive',
                        @LockOwner = 'Transaction',
                        @LockTimeout = :lock_timeout_ms,
                        @DbPrincipal = 'public';
                    SELECT @lock_result;
                    """
                ),
                {
                    "resource": "supply-response:app:presenter-retention:v1",
                    "lock_timeout_ms": 5_000,
                },
            ).scalar_one()
        except SQLAlchemyError as error:
            raise PresenterRetentionLockUnavailable(
                "could not acquire presenter retention lock"
            ) from error
        if type(result) is not int or result not in (0, 1):
            raise PresenterRetentionLockUnavailable(
                "could not acquire presenter retention lock"
            )

    def _insert_playback_if_absent(
        self,
        connection: Connection,
        playback: Playback,
    ) -> bool:
        result = connection.execute(
            text(
                """
                MERGE app.playbacks WITH (HOLDLOCK) AS target
                USING (SELECT
                    :playback_id AS playback_id,
                    :case_id AS case_id,
                    :decision_id AS decision_id,
                    :status AS status,
                    :started_at AS started_at,
                    :completed_at AS completed_at,
                    :failed_at AS failed_at,
                    :error_code AS error_code,
                    :payload_json AS payload_json
                ) AS source
                ON target.decision_id = source.decision_id
                WHEN NOT MATCHED THEN
                    INSERT (
                        playback_id, case_id, decision_id, status,
                        started_at, completed_at, failed_at, error_code, payload_json
                    )
                    VALUES (
                        source.playback_id, source.case_id, source.decision_id,
                        source.status, source.started_at, source.completed_at,
                        source.failed_at, source.error_code,
                        source.payload_json
                    )
                OUTPUT $action;
                """
            ),
            {
                "playback_id": playback.playback_id,
                "case_id": playback.case_id,
                "decision_id": playback.decision_id,
                "status": playback.status.value,
                "started_at": playback.started_at,
                "completed_at": playback.completed_at,
                "failed_at": playback.failed_at,
                "error_code": playback.error_code,
                "payload_json": serialize_model(playback),
            },
        )
        return result.scalar_one_or_none() == "INSERT"


def _pack_access_token(token: str) -> bytes:
    raw = token.encode("utf-16-le")
    return struct.pack(f"<I{len(raw)}s", len(raw), raw)


def build_fabric_engine(settings: Settings, credential: TokenCredential) -> Engine:
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={settings.fabric_sql_server};"
        f"Database={settings.fabric_sql_database};"
        "Encrypt=yes;TrustServerCertificate=no;LongAsMax=Yes;"
    )
    quoted = quote_plus(connection_string)
    engine = create_engine(
        f"mssql+pyodbc:///?odbc_connect={quoted}",
        pool_pre_ping=True,
        execution_options={"schema_translate_map": {None: "app"}},
    )

    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams) -> None:
        del dialect, conn_rec, cargs
        token = credential.get_token(SQL_DATABASE_SCOPE).token
        attrs_before = dict(cparams.get("attrs_before", {}))
        attrs_before[SQL_COPT_SS_ACCESS_TOKEN] = _pack_access_token(token)
        cparams["attrs_before"] = attrs_before

    return engine


def build_credential(settings: Settings) -> TokenCredential:
    mode = settings.credential_mode
    if mode == "azure_cli":
        tenant_id = settings.allowed_tenant_id
        if tenant_id is None:
            raise ValueError("Azure CLI credential requires an allowed tenant ID")
        return AzureCliCredential(tenant_id=tenant_id)
    if mode == "managed_identity":
        return ManagedIdentityCredential()
    raise ValueError(f"unsupported Fabric credential mode: {mode}")


def fabric_store(
    settings: Settings,
    credential: TokenCredential | None = None,
) -> SqlAlchemyStore:
    if settings.runtime_mode is not RuntimeMode.LIVE:
        raise ValueError("Fabric SQL store requires live runtime mode")
    active_credential = credential or build_credential(settings)
    return FabricSqlStore(
        build_fabric_engine(settings, active_credential),
        runtime_mode=RuntimeMode.LIVE,
    )


def fabric_store_from_environment() -> SqlAlchemyStore:
    from apps.api.app.settings import Settings

    return fabric_store(Settings())  # pyright: ignore[reportCallIssue]
