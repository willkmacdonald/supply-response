from datetime import date

from data.schemas.models import InventoryPosition, ResponseScenario
from services.policy.thresholds import collaboration_evidence_is_stale, dates_conflict
from services.scenarios.evaluator import has_feasible_mitigation, transfer_inventory_available


def test_conflicting_email_and_operational_dates_are_detected():
    assert dates_conflict(communicated_date=date(2026, 9, 6), operational_date=date(2026, 9, 8))
    assert not dates_conflict(communicated_date=date(2026, 9, 6), operational_date=date(2026, 9, 6))


def test_inventory_available_at_another_plant():
    positions = [InventoryPosition(inventory_id="RL-I", part_id="RL-MAT", plant_id="RL-OTHER", on_hand=1200, quality_hold=100, protected_allocation=100)]
    assert transfer_inventory_available(part_id="RL-MAT", source_plant_id="RL-OTHER", required_quantity=1000, inventory_positions=positions)


def test_no_feasible_mitigation():
    scenarios = [
        ResponseScenario(scenario_id="RL-SCENARIO-1", disruption_id="RL-D", name="Backlog", executable=True),
        ResponseScenario(scenario_id="RL-SCENARIO-2", disruption_id="RL-D", name="Expedite", executable=False),
        ResponseScenario(scenario_id="RL-SCENARIO-3", disruption_id="RL-D", name="Transfer", executable=False),
    ]
    assert not has_feasible_mitigation(scenarios)


def test_missing_or_stale_collaboration_evidence():
    assert collaboration_evidence_is_stale(evidence_date=None, as_of=date(2026, 9, 20))
    assert collaboration_evidence_is_stale(evidence_date=date(2026, 8, 1), as_of=date(2026, 9, 20))
    assert not collaboration_evidence_is_stale(evidence_date=date(2026, 9, 15), as_of=date(2026, 9, 20))
