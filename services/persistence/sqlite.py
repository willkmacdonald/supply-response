from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import make_url

from data.domain import RuntimeMode
from data.domain.execution import Playback
from services.persistence.store import SqlAlchemyStore, serialize_model
from services.persistence.tables import metadata, playbacks

SQLITE_BUSY_TIMEOUT_MS = 5_000


class SqliteStore(SqlAlchemyStore):
    def _insert_playback_if_absent(
        self,
        connection: Connection,
        playback: Playback,
    ) -> bool:
        result = connection.execute(
            sqlite_insert(playbacks)
            .values(
                playback_id=playback.playback_id,
                case_id=playback.case_id,
                decision_id=playback.decision_id,
                status=playback.status.value,
                started_at=playback.started_at,
                completed_at=playback.completed_at,
                failed_at=playback.failed_at,
                error_code=playback.error_code,
                payload_json=serialize_model(playback),
            )
            .on_conflict_do_nothing(index_elements=[playbacks.c.decision_id])
        )
        return result.rowcount == 1


def build_sqlite_engine(database_url: str) -> Engine:
    if not database_url.startswith("sqlite:"):
        raise ValueError("SQLite store requires a sqlite: database URL")
    url = make_url(database_url)
    database = url.database
    file_backed = (
        database not in (None, "", ":memory:") and url.query.get("mode") != "memory"
    )
    engine = create_engine(
        database_url,
        connect_args={"timeout": SQLITE_BUSY_TIMEOUT_MS / 1_000},
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        if file_backed:
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def sqlite_store(
    database_url: str,
    *,
    runtime_mode: RuntimeMode = RuntimeMode.FALLBACK,
) -> SqlAlchemyStore:
    engine = build_sqlite_engine(database_url)
    metadata.create_all(engine)
    return SqliteStore(engine, runtime_mode=runtime_mode)
