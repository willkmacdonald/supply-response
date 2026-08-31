from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from data.domain import ProductionOrder, TimedQuantity


@dataclass(frozen=True)
class OrderAllocation:
    allocated_component_units: int
    uncovered_component_units: int
    full_and_on_time: bool


@dataclass(frozen=True)
class ComponentSupplyAllocation:
    by_production_order_id: dict[str, OrderAllocation]
    uncovered_component_units: int

    def __getitem__(self, production_order_id: str) -> OrderAllocation:
        return self.by_production_order_id[production_order_id]


def allocate_component_supply(
    *,
    starting_inventory: int,
    receipts: tuple[TimedQuantity, ...],
    transfers: tuple[TimedQuantity, ...],
    production_orders: tuple[ProductionOrder, ...] | list[ProductionOrder],
) -> ComponentSupplyAllocation:
    """Allocate available component units in the caller's deterministic order.

    Each order may consume a partial quantity, but only an order whose complete
    component demand is covered is marked protected for OTIF and financial risk.
    """
    supply_by_date: dict[date, int] = defaultdict(int)
    for supply in (*receipts, *transfers):
        supply_by_date[supply.date] += supply.quantity

    available = starting_inventory
    received_dates: set[date] = set()
    allocations: dict[str, OrderAllocation] = {}
    uncovered = 0
    for order in production_orders:
        for supply_date in sorted(supply_by_date):
            if supply_date <= order.due_date and supply_date not in received_dates:
                available += supply_by_date[supply_date]
                received_dates.add(supply_date)
        demand = order.component_demand
        if demand is None:
            raise ValueError(
                f"Production order {order.production_order_id} is missing component demand"
            )
        allocated = min(available, demand)
        available -= allocated
        order_uncovered = demand - allocated
        uncovered += order_uncovered
        allocations[order.production_order_id] = OrderAllocation(
            allocated_component_units=allocated,
            uncovered_component_units=order_uncovered,
            full_and_on_time=order_uncovered == 0,
        )

    return ComponentSupplyAllocation(
        by_production_order_id=allocations,
        uncovered_component_units=uncovered,
    )
