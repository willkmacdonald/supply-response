from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from data.schemas.models import (
    BomComponent, Customer, CustomerOrder, Disruption, InventoryPosition, Part,
    ProductionOrder, PurchaseOrder, QualificationStatus, QualityQualification,
    Supplier, SupplierPart, TransportOption,
)


@dataclass(frozen=True)
class SyntheticDataset:
    suppliers: list[Supplier]
    parts: list[Part]
    supplier_parts: list[SupplierPart]
    purchase_orders: list[PurchaseOrder]
    inventory_positions: list[InventoryPosition]
    bom_components: list[BomComponent]
    production_orders: list[ProductionOrder]
    customers: list[Customer]
    customer_orders: list[CustomerOrder]
    transport_options: list[TransportOption]
    quality_qualifications: list[QualityQualification]
    disruptions: list[Disruption]


def generate_dataset(
    *, seed: int = 42, supplier_count: int = 25, part_count: int = 250,
    bom_relationship_count: int = 1000, customer_order_count: int = 500,
) -> SyntheticDataset:
    """Generate deterministic fictional RL-prefixed data suitable for local tests/demos."""
    rng = random.Random(seed)
    base = date(2026, 9, 1)
    plants = ["RL-PLANT-CHI", "RL-PLANT-DAL", "RL-PLANT-RNO"]

    suppliers = [Supplier(supplier_id=f"RL-SUP-{i:04d}", name=f"RL-Supplier-{i:04d}") for i in range(supplier_count)]
    # Reserve the canonical demo IDs.
    suppliers[:2] = [
        Supplier(supplier_id="RL-SUP-ALPHA", name="RL-Supplier Alpha"),
        Supplier(supplier_id="RL-SUP-BETA", name="RL-Supplier Beta"),
    ]
    parts = [Part(part_id=f"RL-MAT-{10000+i}", description=f"RL-Part {i}", unit_cost=Decimal(rng.randint(5, 80))) for i in range(part_count)]
    if parts:
        parts[0] = Part(part_id="RL-MAT-10247", description="RL-Critical component", unit_cost=Decimal("18"))

    supplier_parts: list[SupplierPart] = []
    for idx, part in enumerate(parts):
        primary = suppliers[idx % len(suppliers)]
        supplier_parts.append(SupplierPart(supplier_id=primary.supplier_id, part_id=part.part_id, lead_time_days=rng.randint(5, 30), is_primary=True))
        alt = suppliers[(idx + 1) % len(suppliers)]
        supplier_parts.append(SupplierPart(supplier_id=alt.supplier_id, part_id=part.part_id, lead_time_days=rng.randint(7, 40), is_primary=False))
    if parts:
        supplier_parts[0] = SupplierPart(supplier_id="RL-SUP-ALPHA", part_id="RL-MAT-10247", lead_time_days=14, is_primary=True)
        supplier_parts[1] = SupplierPart(supplier_id="RL-SUP-BETA", part_id="RL-MAT-10247", lead_time_days=10, is_primary=False)

    purchase_orders = [
        PurchaseOrder(po_line_id=f"RL-PO-{i:06d}", supplier_id=supplier_parts[i % len(supplier_parts)].supplier_id,
                      part_id=parts[i % len(parts)].part_id, plant_id=plants[i % len(plants)],
                      quantity=rng.randint(500, 10000), due_date=base + timedelta(days=rng.randint(0, 60)))
        for i in range(max(part_count // 2, 1))
    ]
    purchase_orders[0] = PurchaseOrder(po_line_id="RL-PO-000001", supplier_id="RL-SUP-ALPHA", part_id="RL-MAT-10247", plant_id="RL-PLANT-CHI", quantity=8000, due_date=date(2026, 9, 3))

    inventory_positions = [
        InventoryPosition(inventory_id=f"RL-INV-{i:06d}", part_id=p.part_id, plant_id=plants[j],
                          on_hand=rng.randint(0, 5000), quality_hold=rng.randint(0, 200), protected_allocation=rng.randint(0, 300))
        for i, p in enumerate(parts) for j in range(min(2, len(plants)))
    ]
    inventory_positions[0] = InventoryPosition(inventory_id="RL-INV-DEMO-CHI", part_id="RL-MAT-10247", plant_id="RL-PLANT-CHI", on_hand=2500, quality_hold=200, protected_allocation=300)
    inventory_positions[1] = InventoryPosition(inventory_id="RL-INV-DEMO-DAL", part_id="RL-MAT-10247", plant_id="RL-PLANT-DAL", on_hand=1800, quality_hold=0, protected_allocation=300)

    product_count = max(10, min(part_count, 500))
    products = [f"RL-PROD-{i:05d}" for i in range(product_count)]
    bom_components = [
        BomComponent(bom_id=f"RL-BOM-{i:07d}", product_id=products[i % product_count], component_part_id=parts[rng.randrange(len(parts))].part_id, quantity_per=rng.randint(1, 4))
        for i in range(bom_relationship_count)
    ]
    # Guarantee demo component traceability.
    if bom_components:
        bom_components[0] = BomComponent(bom_id="RL-BOM-DEMO", product_id="RL-PROD-00000", component_part_id="RL-MAT-10247", quantity_per=2)

    production_orders = [
        ProductionOrder(production_order_id=f"RL-MO-{i:06d}", product_id=products[i % product_count], plant_id=plants[i % len(plants)], quantity=rng.randint(100, 1500), due_date=base + timedelta(days=rng.randint(1, 45)))
        for i in range(max(customer_order_count // 4, 20))
    ]
    production_orders[0] = ProductionOrder(production_order_id="RL-MO-DEMO-1", product_id="RL-PROD-00000", plant_id="RL-PLANT-CHI", quantity=1000, due_date=date(2026, 9, 5))
    production_orders[1] = ProductionOrder(production_order_id="RL-MO-DEMO-2", product_id="RL-PROD-00000", plant_id="RL-PLANT-CHI", quantity=1200, due_date=date(2026, 9, 8))

    customers = [Customer(customer_id=f"RL-CUST-{i:04d}", name=f"RL-Customer-{i:04d}", priority=rng.randint(1, 5)) for i in range(max(25, customer_order_count // 20))]
    customer_orders = [
        CustomerOrder(customer_order_line_id=f"RL-CO-{i:07d}", customer_id=customers[i % len(customers)].customer_id,
                      product_id=production_orders[i % len(production_orders)].product_id, plant_id=production_orders[i % len(production_orders)].plant_id,
                      production_order_id=production_orders[i % len(production_orders)].production_order_id,
                      quantity=rng.randint(25, 500), due_date=production_orders[i % len(production_orders)].due_date,
                      unit_revenue=Decimal(rng.randint(80, 300)), unit_margin=Decimal(rng.randint(20, 100)))
        for i in range(customer_order_count)
    ]
    if customer_orders:
        customer_orders[0] = CustomerOrder(customer_order_line_id="RL-CO-DEMO-1", customer_id=customers[0].customer_id, product_id="RL-PROD-00000", plant_id="RL-PLANT-CHI", production_order_id="RL-MO-DEMO-1", quantity=1000, due_date=date(2026, 9, 5), unit_revenue=Decimal("150"), unit_margin=Decimal("50"))
        customer_orders[1] = CustomerOrder(customer_order_line_id="RL-CO-DEMO-2", customer_id=customers[1].customer_id, product_id="RL-PROD-00000", plant_id="RL-PLANT-CHI", production_order_id="RL-MO-DEMO-2", quantity=1200, due_date=date(2026, 9, 8), unit_revenue=Decimal("200"), unit_margin=Decimal("70"))

    transport_options = [TransportOption(transport_option_id="RL-TRANS-AIR", supplier_id="RL-SUP-ALPHA", plant_id="RL-PLANT-CHI", mode="air", max_quantity=3000, incremental_cost_per_unit=Decimal("7.50"), transit_days=3)]
    qualifications = [
        QualityQualification(qualification_id="RL-QUAL-ALPHA", supplier_id="RL-SUP-ALPHA", part_id="RL-MAT-10247", status=QualificationStatus.APPROVED, effective_date=date(2020,1,1), evidence_ref="RL-QUALITY-ALPHA"),
        QualityQualification(qualification_id="RL-QUAL-BETA", supplier_id="RL-SUP-BETA", part_id="RL-MAT-10247", status=QualificationStatus.NOT_APPROVED, effective_date=None, evidence_ref="RL-QUALITY-001"),
    ]
    disruptions = [Disruption(disruption_id="RL-DISRUPTION-001", supplier_id="RL-SUP-ALPHA", po_line_id="RL-PO-000001", part_id="RL-MAT-10247", original_quantity=8000, original_due_date=date(2026,9,3), partial_quantity=3000, partial_due_date=date(2026,9,6), recovery_date=None, source_ref="RL-001")]

    return SyntheticDataset(suppliers, parts, supplier_parts, purchase_orders, inventory_positions, bom_components, production_orders, customers, customer_orders, transport_options, qualifications, disruptions)


def generate_demo_scale_dataset(*, seed: int = 42) -> SyntheticDataset:
    """Generate the target demonstration scale from the project brief."""
    return generate_dataset(seed=seed, supplier_count=250, part_count=10_000, bom_relationship_count=100_000, customer_order_count=50_000)
