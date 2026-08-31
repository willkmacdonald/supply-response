import pytest
from sqlalchemy import text

from integrations.fabric.health import check_fabric_health
from integrations.fabric.schema import apply_fabric_schema
from services.persistence.fabric_sql import fabric_store_from_environment


pytestmark = pytest.mark.fabric_live


def test_configured_fabric_schema_applies_twice_and_passes_live_health_checks():
    store = fabric_store_from_environment()
    apply_fabric_schema(store.engine)
    apply_fabric_schema(store.engine)

    health = check_fabric_health(store.engine)
    with store.engine.connect() as connection:
        views = set(
            connection.execute(
                text(
                    "SELECT CONCAT(SCHEMA_NAME(schema_id), '.', name) "
                    "FROM sys.views "
                    "WHERE name IN ('case_command_center', 'action_outcomes')"
                )
            ).scalars()
        )

    assert health.operational_store == "fabric_sql"
    assert health.power_bi_available is True
    assert health.schema_version == 12
    assert views == {
        "analytics.case_command_center",
        "analytics.action_outcomes",
    }
