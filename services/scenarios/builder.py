"""Candidate scenario construction for disruptions that have no fixture scenarios.

The RL-001 demo ships with six curated scenarios. For any other disruption in
the synthetic dataset this module builds the same six shapes deterministically
from the operational data, so the API behaves identically for generated cases.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional, Sequence

from data.schemas.models import ResponseScenario, ScenarioType, TransportMode, TransportOption
from services.exposure.calculator import ExposureResult, total_usable_inventory
from services.scenarios.evaluator import EvaluationContext


def _scenario_id(index: int) -> str:
    return f"RL-SCN-{index:03d}"


def _air_option(context: EvaluationContext) -> Optional[TransportOption]:
    disruption = context.disruption
    for option in context.transport_options:
        if (
            option.origin == disruption.supplier_id
            and option.destination == disruption.plant_id
            and option.mode == TransportMode.AIR
        ):
            return option
    return None


def _road_option(context: EvaluationContext, origin: str) -> Optional[TransportOption]:
    for option in context.transport_options:
        if (
            option.origin == origin
            and option.destination == context.disruption.plant_id
            and option.mode in (TransportMode.ROAD, TransportMode.RAIL)
        ):
            return option
    return None


def _source_plant(context: EvaluationContext) -> tuple[str, int]:
    """Plant with the most usable inventory of the part, excluding the demand plant."""
    disruption = context.disruption
    plants = sorted(
        {
            position.plant_id
            for position in context.inventory_positions
            if position.part_id == disruption.part_id
            and position.plant_id != disruption.plant_id
        }
    )
    best_plant, best_qty = "", 0
    for plant in plants:
        qty = total_usable_inventory(context.inventory_positions, disruption.part_id, plant)
        if qty > best_qty:
            best_plant, best_qty = plant, qty
    return best_plant, best_qty


def _alternate_supplier(context: EvaluationContext) -> Optional[str]:
    disruption = context.disruption
    candidates = sorted(
        {
            qualification.supplier_id
            for qualification in context.quality_qualifications
            if qualification.part_id == disruption.part_id
            and qualification.supplier_id != disruption.supplier_id
        }
    )
    return candidates[0] if candidates else None


def build_scenarios(
    context: EvaluationContext, baseline: ExposureResult
) -> list[ResponseScenario]:
    """Build the candidate response set for a disruption."""
    disruption = context.disruption
    part_assumption = f"part_id={disruption.part_id}"
    shortage = baseline.max_shortage_qty
    scenarios: list[ResponseScenario] = [
        ResponseScenario(
            scenario_id=_scenario_id(1),
            disruption_id=disruption.disruption_id,
            scenario_type=ScenarioType.ACCEPT_DELAY,
            title="Accept the delay and allow backlog",
            description="Take no mitigating action and reschedule as material arrives.",
            assumptions=[part_assumption, "No additional supply is secured."],
        )
    ]

    index = 2
    air = _air_option(context)
    expedite_qty = disruption.partial_qty or min(shortage, 3000)
    available_date = disruption.partial_date or (
        disruption.original_date + timedelta(days=air.transit_days if air else 3)
    )
    if expedite_qty > 0 and air is not None:
        scenarios.append(
            ResponseScenario(
                scenario_id=_scenario_id(index),
                disruption_id=disruption.disruption_id,
                scenario_type=ScenarioType.EXPEDITE_PARTIAL,
                title=f"Expedite {expedite_qty} units from {disruption.supplier_id}",
                description=(
                    f"Air freight {expedite_qty} units arriving {available_date.isoformat()}."
                ),
                expedite_qty=expedite_qty,
                transport_option_id=air.transport_option_id,
                available_date=available_date,
                assumptions=[part_assumption, "Air freight capacity is available."],
            )
        )
        index += 1

    source_plant, source_qty = _source_plant(context)
    road = _road_option(context, source_plant) if source_plant else None
    transfer_qty = min(source_qty, shortage, road.max_qty if road else source_qty)
    if transfer_qty > 0:
        transfer_date = disruption.original_date + timedelta(
            days=road.transit_days if road else 2
        )
        scenarios.append(
            ResponseScenario(
                scenario_id=_scenario_id(index),
                disruption_id=disruption.disruption_id,
                scenario_type=ScenarioType.TRANSFER_INVENTORY,
                title=f"Transfer inventory from {source_plant}",
                description=(
                    f"Move {transfer_qty} usable units from {source_plant} to "
                    f"{disruption.plant_id}."
                ),
                transfer_qty=transfer_qty,
                transport_option_id=road.transport_option_id if road else None,
                available_date=transfer_date,
                assumptions=[
                    part_assumption,
                    f"{source_plant} can release {transfer_qty} units.",
                ],
            )
        )
        index += 1

    resequenced_qty = max(shortage // 2, 0)
    if resequenced_qty > 0:
        scenarios.append(
            ResponseScenario(
                scenario_id=_scenario_id(index),
                disruption_id=disruption.disruption_id,
                scenario_type=ScenarioType.RESEQUENCE_PRODUCTION,
                title="Resequence production toward priority customers",
                description="Defer the lowest-priority production orders.",
                resequenced_qty=resequenced_qty,
                assumptions=[
                    part_assumption,
                    "Deferred production can be rescheduled outside the horizon.",
                ],
            )
        )
        index += 1

    alternate = _alternate_supplier(context)
    if alternate:
        scenarios.append(
            ResponseScenario(
                scenario_id=_scenario_id(index),
                disruption_id=disruption.disruption_id,
                scenario_type=ScenarioType.ALTERNATE_SOURCE,
                title=f"Source from {alternate}",
                description=f"Place an emergency purchase order with {alternate}.",
                expedite_qty=max(shortage, 0),
                alternate_supplier_id=alternate,
                available_date=disruption.original_date + timedelta(days=14),
                assumptions=[part_assumption, "Quality approval is required first."],
            )
        )
        index += 1

    combined_expedite = sum(s.expedite_qty for s in scenarios if s.scenario_type == ScenarioType.EXPEDITE_PARTIAL)
    combined_transfer = sum(s.transfer_qty for s in scenarios)
    if combined_expedite or combined_transfer or resequenced_qty:
        scenarios.append(
            ResponseScenario(
                scenario_id=_scenario_id(index),
                disruption_id=disruption.disruption_id,
                scenario_type=ScenarioType.COMBINED,
                title="Combine expedite, transfer, and resequencing",
                description="Execute every feasible mitigation together.",
                expedite_qty=combined_expedite,
                transfer_qty=combined_transfer,
                resequenced_qty=resequenced_qty,
                transport_option_id=air.transport_option_id if air else None,
                available_date=available_date,
                assumptions=[part_assumption, "Actions can be executed in parallel."],
            )
        )

    return scenarios


def scenarios_for(
    context: EvaluationContext,
    baseline: ExposureResult,
    fixture_scenarios: Sequence[ResponseScenario] = (),
) -> list[ResponseScenario]:
    """Prefer curated fixture scenarios; otherwise build them from data."""
    curated = [
        scenario
        for scenario in fixture_scenarios
        if scenario.disruption_id == context.disruption.disruption_id
    ]
    if curated:
        return curated
    return build_scenarios(context, baseline)


__all__ = ["build_scenarios", "scenarios_for"]
