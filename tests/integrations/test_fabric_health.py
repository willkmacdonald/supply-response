from importlib.util import find_spec
from contextlib import nullcontext

import pytest

from integrations.fabric import health


def test_fabric_health_module_exists():
    assert find_spec("integrations.fabric.health") is not None


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class FakeConnection:
    def __init__(self, values):
        self._values = iter(values)
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))
        value = next(self._values)
        if isinstance(value, Exception):
            raise value
        return FakeResult(value)


class FakeEngine:
    def __init__(self, values):
        self.connection = FakeConnection(values)

    def connect(self):
        return nullcontext(self.connection)


def test_health_requires_connectivity_and_the_expected_schema_version():
    engine = FakeEngine([1, health.FABRIC_SCHEMA_VERSION])

    result = health.check_fabric_health(engine)

    assert result.operational_store == "fabric_sql"
    assert result.power_bi_available is True
    assert result.schema_version == health.FABRIC_SCHEMA_VERSION
    assert engine.connection.statements == [
        "SELECT 1",
        "SELECT schema_version FROM app.schema_version WHERE component = 'operational'",
    ]


def test_health_rejects_an_unexpected_schema_version():
    with pytest.raises(health.FabricSchemaError, match="schema version"):
        health.check_fabric_health(FakeEngine([1, health.FABRIC_SCHEMA_VERSION - 1]))


def test_health_propagates_connection_and_token_failures():
    expected = RuntimeError("token rejected")

    with pytest.raises(RuntimeError, match="token rejected"):
        health.check_fabric_health(FakeEngine([expected]))
