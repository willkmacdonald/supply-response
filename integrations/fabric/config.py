"""Fail-closed classification of the Fabric SQL live environment pair."""

from enum import StrEnum
from collections.abc import Mapping
import os


FABRIC_SQL_SERVER_ENV = "SUPPLY_RESPONSE_FABRIC_SQL_SERVER"
FABRIC_SQL_DATABASE_ENV = "SUPPLY_RESPONSE_FABRIC_SQL_DATABASE"


class FabricEnvironmentState(StrEnum):
    ABSENT = "absent"
    COMPLETE = "complete"


class PartialFabricConfigurationError(ValueError):
    """Raised before connection when only half of the Fabric pair exists."""


def fabric_environment_state(
    environment: Mapping[str, str] | None = None,
) -> FabricEnvironmentState:
    values = environment if environment is not None else os.environ
    has_server = bool(values.get(FABRIC_SQL_SERVER_ENV))
    has_database = bool(values.get(FABRIC_SQL_DATABASE_ENV))
    if has_server != has_database:
        raise PartialFabricConfigurationError(
            f"{FABRIC_SQL_SERVER_ENV} and {FABRIC_SQL_DATABASE_ENV} "
            "must be configured together"
        )
    if has_server:
        return FabricEnvironmentState.COMPLETE
    return FabricEnvironmentState.ABSENT
