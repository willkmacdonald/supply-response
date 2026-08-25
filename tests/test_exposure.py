from datetime import date
from decimal import Decimal

from data.schemas.models import BomComponent, CustomerOrder, InventoryPosition, ProductionOrder, TimedQuantity
from services.exposure.calculator import calculate_exposure, calculate_usable_inventory, project_inventory


def test_usable_inventory_formula():
    p = InventoryPosition(inventory_id="RL-I", part_id="RL-P", plant_id="RL-X", on_hand=100, quality_hold=10, protected_allocation=15)
    assert calculate_usable_inventory(p) == 75


def test_projected_balance_and_stockout_are_deterministic():
    points = project_inventory(starting_balance=100, receipts=[TimedQuantity(date=date(2026,9,2), quantity=25, source_id="RL-R")], transfers=[], demand=[TimedQuantity(date=date(2026,9,2), quantity=80, source_id="RL-D1"), TimedQuantity(date=date(2026,9,3), quantity=60, source_id="RL-D2")])
    assert [p.projected_balance for p in points] == [45, -15]


def test_exposure_identifies_orders_and_financial_risk():
    inventory = [InventoryPosition(inventory_id="RL-I", part_id="RL-MAT", plant_id="RL-PLANT", on_hand=100, quality_hold=0, protected_allocation=0)]
    bom = [BomComponent(bom_id="RL-B", product_id="RL-PROD", component_part_id="RL-MAT", quantity_per=1)]
    prod = [ProductionOrder(production_order_id="RL-MO-1", product_id="RL-PROD", plant_id="RL-PLANT", quantity=150, due_date=date(2026,9,5))]
    orders = [CustomerOrder(customer_order_line_id="RL-CO-1", customer_id="RL-C", product_id="RL-PROD", plant_id="RL-PLANT", production_order_id="RL-MO-1", quantity=150, due_date=date(2026,9,5), unit_revenue=Decimal("10"), unit_margin=Decimal("4"))]
    result = calculate_exposure(scenario_id="RL-S", part_id="RL-MAT", plant_id="RL-PLANT", inventory_positions=inventory, receipts=[], transfers=[], bom_components=bom, production_orders=prod, customer_orders=orders)
    assert result.first_stockout_date == date(2026,9,5)
    assert result.maximum_shortage_quantity == 50
    assert result.affected_production_order_ids == ("RL-MO-1",)
    assert result.revenue_at_risk == Decimal("1500")
    assert result.margin_at_risk == Decimal("600")
    assert result.otif_lines_at_risk == 1
