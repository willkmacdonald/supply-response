from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any


def configure_azure_monitor_from_environment(
    environ: Mapping[str, str] | None = None,
    *,
    configurator: Callable[..., Any] | None = None,
) -> bool:
    """Configure bounded Azure Monitor telemetry only when explicitly enabled."""
    source = os.environ if environ is None else environ
    connection_string = source.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        return False

    if configurator is None:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configurator = configure_azure_monitor
    configurator(
        connection_string=connection_string,
        sampling_ratio=0.25,
        logger_name="supply_response",
    )
    return True
