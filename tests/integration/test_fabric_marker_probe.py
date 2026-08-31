import pytest


pytestmark = pytest.mark.fabric_live


def test_fabric_live_marker_probe_has_no_external_side_effects():
    assert True
