from __future__ import annotations

import pytest

from integrations.fabric.config import (
    FabricEnvironmentState,
    PartialFabricConfigurationError,
    fabric_environment_state,
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    try:
        state = fabric_environment_state()
    except PartialFabricConfigurationError as error:
        raise pytest.UsageError(str(error)) from error
    if state is FabricEnvironmentState.COMPLETE:
        return
    skip = pytest.mark.skip(reason="Fabric SQL live settings are not configured")
    for item in items:
        if "fabric_live" in item.keywords:
            item.add_marker(skip)
