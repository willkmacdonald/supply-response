from sqlalchemy import Engine, create_engine, event

from data.domain import RuntimeMode
from services.persistence.store import SqlAlchemyStore
from services.persistence.tables import metadata


def build_sqlite_engine(database_url: str) -> Engine:
    if not database_url.startswith("sqlite:"):
        raise ValueError("SQLite store requires a sqlite: database URL")
    engine = create_engine(database_url)

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
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
