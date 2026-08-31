from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url

from data.domain import RuntimeMode
from services.persistence.store import SqlAlchemyStore
from services.persistence.tables import metadata

SQLITE_BUSY_TIMEOUT_MS = 5_000


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
    return SqlAlchemyStore(engine, runtime_mode=runtime_mode)
