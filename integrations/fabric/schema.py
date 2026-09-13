"""Explicit Fabric SQL schema application."""

import re
from pathlib import Path

from sqlalchemy import Engine

FABRIC_SQL_DIRECTORY = Path(__file__).resolve().parents[2] / "fabric" / "sql"
FABRIC_SCHEMA_SCRIPTS = (
    FABRIC_SQL_DIRECTORY / "001_operational_schema.sql",
    FABRIC_SQL_DIRECTORY / "002_analytics_views.sql",
    FABRIC_SQL_DIRECTORY / "003_reporting_dataset.sql",
)


def split_go_batches(sql: str) -> tuple[str, ...]:
    return tuple(
        batch for part in re.split(r"(?im)^\s*GO\s*$", sql) if (batch := part.strip())
    )


def apply_sql_script(engine: Engine, sql: str) -> None:
    for batch in split_go_batches(sql):
        with engine.begin() as connection:
            connection.exec_driver_sql(batch)


def apply_fabric_schema(engine: Engine) -> None:
    for script_path in FABRIC_SCHEMA_SCRIPTS:
        apply_sql_script(engine, script_path.read_text(encoding="utf-8"))
