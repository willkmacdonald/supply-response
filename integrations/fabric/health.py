"""Fabric SQL Database readiness checks."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Engine, text

FABRIC_SCHEMA_VERSION = 12
REQUIRED_ANALYTICS_VIEW_COUNT = 4


class FabricSchemaError(RuntimeError):
    """Raised when the configured database is not at the required schema."""


@dataclass(frozen=True)
class FabricHealth:
    operational_store: Literal["fabric_sql"]
    power_bi_available: Literal[True]
    schema_version: int


def check_fabric_health(engine: Engine) -> FabricHealth:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1")).scalar_one()
        schema_version = connection.execute(
            text(
                "SELECT schema_version FROM app.schema_version "
                "WHERE component = 'operational'"
            )
        ).scalar_one()
        if schema_version != FABRIC_SCHEMA_VERSION:
            raise FabricSchemaError(
                "Fabric SQL schema version mismatch: "
                f"expected {FABRIC_SCHEMA_VERSION}, found {schema_version}"
            )
        required_view_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM sys.views AS v JOIN sys.schemas AS s "
                "ON s.schema_id = v.schema_id WHERE (s.name = 'app' AND v.name IN "
                "('analysis_projection', 'decision_projection')) OR "
                "(s.name = 'analytics' AND v.name IN "
                "('case_command_center', 'action_outcomes'))"
            )
        ).scalar_one()
    if required_view_count != REQUIRED_ANALYTICS_VIEW_COUNT:
        raise FabricSchemaError(
            "Fabric SQL required analytics views are missing: "
            f"expected {REQUIRED_ANALYTICS_VIEW_COUNT}, found {required_view_count}"
        )
    return FabricHealth(
        operational_store="fabric_sql",
        power_bi_available=True,
        schema_version=schema_version,
    )
