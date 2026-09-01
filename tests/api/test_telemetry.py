from apps.api.app.telemetry import configure_azure_monitor_from_environment


def test_telemetry_is_disabled_without_application_insights_connection_string(
    monkeypatch,
):
    calls = []
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=ambient"
    )

    enabled = configure_azure_monitor_from_environment(
        {}, configurator=lambda **kwargs: calls.append(kwargs)
    )

    assert enabled is False
    assert calls == []


def test_telemetry_uses_bounded_sampling_when_connection_string_exists():
    calls = []

    enabled = configure_azure_monitor_from_environment(
        {"APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=example"},
        configurator=lambda **kwargs: calls.append(kwargs),
    )

    assert enabled is True
    assert calls == [
        {
            "connection_string": "InstrumentationKey=example",
            "sampling_ratio": 0.25,
            "logger_name": "supply_response",
        }
    ]
