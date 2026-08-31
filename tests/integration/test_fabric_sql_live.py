import pytest

from integrations.fabric.health import check_fabric_health
from services.persistence.fabric_sql import fabric_store_from_environment


pytestmark = pytest.mark.fabric_live


def test_configured_fabric_database_passes_live_health_checks():
    store = fabric_store_from_environment()

    health = check_fabric_health(store.engine)

    assert health.operational_store == "fabric_sql"
    assert health.power_bi_available is True
