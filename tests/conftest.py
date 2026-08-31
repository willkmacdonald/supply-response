from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    fabric_configured = bool(
        os.getenv("SUPPLY_RESPONSE_FABRIC_SQL_SERVER")
        and os.getenv("SUPPLY_RESPONSE_FABRIC_SQL_DATABASE")
    )
    if fabric_configured:
        return
    skip = pytest.mark.skip(reason="Fabric SQL live settings are not configured")
    for item in items:
        if "fabric_live" in item.keywords:
            item.add_marker(skip)
