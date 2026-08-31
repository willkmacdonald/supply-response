from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from data.domain import (
    BomComponent,
    CalculationMetadata,
    CustomerOrder,
    ExposureResult,
    InventoryPosition,
    ProductionOrder,
    ProjectionPoint,
    TimedQuantity,
)

CALCULATION_VERSION = "exposure-v1"


def calculate_usable_inventory(position: InventoryPosition) -> int:
    return max(
        0, position.on_hand - position.quality_hold - position.protected_allocation
    )


def project_inventory(
    *,
    starting_balance: int,
    receipts: list[TimedQuantity],
    transfers: list[TimedQuantity],
    demand: list[TimedQuantity],
) -> tuple[ProjectionPoint, ...]:
    receipts_by_date: dict[date, int] = defaultdict(int)
    transfers_by_date: dict[date, int] = defaultdict(int)
    demand_by_date: dict[date, int] = defaultdict(int)
    for item in receipts:
        receipts_by_date[item.date] += item.quantity
    for item in transfers:
        transfers_by_date[item.date] += item.quantity
    for item in demand:
        demand_by_date[item.date] += item.quantity
    dates = sorted(set(receipts_by_date) | set(transfers_by_date) | set(demand_by_date))
    balance = starting_balance
    points: list[ProjectionPoint] = []
    for day in dates:
        balance += receipts_by_date[day] + transfers_by_date[day] - demand_by_date[day]
        points.append(
            ProjectionPoint(
                date=day,
                receipts=receipts_by_date[day],
                transfers=transfers_by_date[day],
                demand=demand_by_date[day],
                projected_balance=balance,
            )
        )
    return tuple(points)


def component_demand_for_part(
    *,
    part_id: str,
    plant_id: str,
    bom_components: list[BomComponent],
    production_orders: list[ProductionOrder],
) -> list[TimedQuantity]:
    qty_per_product: dict[str, int] = defaultdict(int)
    for bom in bom_components:
        if bom.component_part_id == part_id:
            qty_per_product[bom.product_id] += bom.quantity_per
    return [
        TimedQuantity(
            date=order.due_date,
            quantity=order.quantity * qty_per_product[order.product_id],
            source_id=order.production_order_id,
        )
        for order in production_orders
        if order.plant_id == plant_id and qty_per_product.get(order.product_id, 0) > 0
    ]


def calculate_exposure(
    *,
    scenario_id: str,
    part_id: str,
    plant_id: str,
    inventory_positions: list[InventoryPosition],
    receipts: list[TimedQuantity],
    transfers: list[TimedQuantity],
    bom_components: list[BomComponent],
    production_orders: list[ProductionOrder],
    customer_orders: list[CustomerOrder],
    response_cost: Decimal = Decimal("0"),
    assumptions: tuple[str, ...] = (),
    remaining_uncertainty: tuple[str, ...] = (),
) -> ExposureResult:
    relevant_positions = [
        p
        for p in inventory_positions
        if p.part_id == part_id and p.plant_id == plant_id
    ]
    usable = sum(calculate_usable_inventory(p) for p in relevant_positions)
    demand = component_demand_for_part(
        part_id=part_id,
        plant_id=plant_id,
        bom_components=bom_components,
        production_orders=production_orders,
    )
    projection = project_inventory(
        starting_balance=usable, receipts=receipts, transfers=transfers, demand=demand
    )
    stockout_points = [p for p in projection if p.projected_balance < 0]
    first_stockout = stockout_points[0].date if stockout_points else None
    max_shortage = (
        abs(min((p.projected_balance for p in projection), default=0, key=lambda x: x))
        if stockout_points
        else 0
    )

    demand_by_order = {d.source_id: d.quantity for d in demand}
    affected_prod: list[str] = []
    balance = usable
    receipt_by_date = defaultdict(int)
    transfer_by_date = defaultdict(int)
    for r in receipts:
        receipt_by_date[r.date] += r.quantity
    for t in transfers:
        transfer_by_date[t.date] += t.quantity
    orders_by_date: dict[date, list[ProductionOrder]] = defaultdict(list)
    for order in production_orders:
        if order.production_order_id in demand_by_order:
            orders_by_date[order.due_date].append(order)
    for day in sorted(
        set(orders_by_date) | set(receipt_by_date) | set(transfer_by_date)
    ):
        balance += receipt_by_date[day] + transfer_by_date[day]
        for order in sorted(orders_by_date[day], key=lambda x: x.production_order_id):
            need = demand_by_order[order.production_order_id]
            if balance < need:
                affected_prod.append(order.production_order_id)
            balance -= need

    affected_customer = [
        o for o in customer_orders if o.production_order_id in affected_prod
    ]
    revenue = sum(
        (o.unit_revenue * o.quantity for o in affected_customer), Decimal("0")
    )
    margin = sum((o.unit_margin * o.quantity for o in affected_customer), Decimal("0"))
    source_ids = tuple(
        sorted(
            {p.inventory_id for p in relevant_positions}
            | {x.source_id for x in receipts + transfers + demand}
        )
    )
    return ExposureResult(
        metadata=CalculationMetadata(
            scenario_id=scenario_id,
            calculation_version=CALCULATION_VERSION,
            assumptions=assumptions,
            source_data_lineage=source_ids,
        ),
        usable_inventory=usable,
        projected_inventory=projection,
        first_stockout_date=first_stockout,
        maximum_shortage_quantity=max_shortage,
        affected_production_order_ids=tuple(affected_prod),
        affected_customer_order_line_ids=tuple(
            o.customer_order_line_id for o in affected_customer
        ),
        revenue_at_risk=revenue,
        margin_at_risk=margin,
        otif_lines_at_risk=len(affected_customer),
        response_cost=response_cost,
        revenue_protected=Decimal("0"),
        remaining_uncertainty=remaining_uncertainty,
    )
