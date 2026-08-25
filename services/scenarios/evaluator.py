from __future__ import annotations

from decimal import Decimal

from data.schemas.models import Disruption, QualityQualification, QualificationStatus, ResponseScenario


def build_initial_scenarios(disruption: Disruption, qualifications: list[QualityQualification]) -> list[ResponseScenario]:
    beta = next((q for q in qualifications if q.part_id == disruption.part_id and q.supplier_id == "RL-SUP-BETA"), None)
    beta_ok = bool(beta and beta.status == QualificationStatus.APPROVED)
    beta_violation = () if beta_ok else ("RL-QUALITY-001: alternate supplier is not approved",)
    beta_uncertainty = () if beta_ok else ("Supplier Beta approval date remains conditional",)
    return [
        ResponseScenario(scenario_id="RL-SCENARIO-1", disruption_id=disruption.disruption_id, name="Accept delay and backlog", executable=True),
        ResponseScenario(scenario_id="RL-SCENARIO-2", disruption_id=disruption.disruption_id, name="Expedite Supplier Alpha partial shipment", executable=disruption.partial_quantity > 0, response_cost=Decimal(disruption.partial_quantity) * Decimal("7.50"), remaining_uncertainty=("Recovery date for remaining quantity is unconfirmed",) if disruption.recovery_date is None else ()),
        ResponseScenario(scenario_id="RL-SCENARIO-3", disruption_id=disruption.disruption_id, name="Transfer inventory from another plant", executable=True),
        ResponseScenario(scenario_id="RL-SCENARIO-4", disruption_id=disruption.disruption_id, name="Resequence production toward priority customers", executable=True),
        ResponseScenario(scenario_id="RL-SCENARIO-5", disruption_id=disruption.disruption_id, name="Source from Supplier Beta", executable=beta_ok, constraint_violations=beta_violation, remaining_uncertainty=beta_uncertainty),
        ResponseScenario(scenario_id="RL-SCENARIO-6", disruption_id=disruption.disruption_id, name="Combine expedite, transfer, and resequencing", executable=disruption.partial_quantity > 0),
    ]


def transfer_inventory_available(*, part_id: str, source_plant_id: str, required_quantity: int, inventory_positions) -> bool:
    from services.exposure.calculator import calculate_usable_inventory
    available = sum(calculate_usable_inventory(p) for p in inventory_positions if p.part_id == part_id and p.plant_id == source_plant_id)
    return available >= required_quantity


def has_feasible_mitigation(scenarios: list[ResponseScenario]) -> bool:
    # Backlog is the baseline consequence, not a mitigation.
    return any(s.executable for s in scenarios if s.scenario_id != "RL-SCENARIO-1")
