from data.synthetic.generator import generate_dataset


def test_generator_is_deterministic_and_fictional():
    a = generate_dataset(
        seed=7,
        supplier_count=5,
        part_count=20,
        bom_relationship_count=30,
        customer_order_count=20,
    )
    b = generate_dataset(
        seed=7,
        supplier_count=5,
        part_count=20,
        bom_relationship_count=30,
        customer_order_count=20,
    )
    assert a == b
    assert all(
        x.supplier_id.startswith("RL-") and x.name.startswith("RL-")
        for x in a.suppliers
    )
    assert a.disruptions[0].recovery_date is None


def test_generator_uses_unique_business_keys():
    dataset = generate_dataset(seed=42)
    part_ids = [part.part_id for part in dataset.parts]
    po_line_ids = [order.po_line_id for order in dataset.purchase_orders]
    assert len(part_ids) == len(set(part_ids))
    assert len(po_line_ids) == len(set(po_line_ids))


def test_demo_calculation_rows_are_explicit():
    dataset = generate_dataset(seed=42)
    critical_boms = [
        bom for bom in dataset.bom_components if bom.component_part_id == "RL-MAT-10247"
    ]
    demo_production_ids = {"RL-MO-DEMO-1", "RL-MO-DEMO-2"}
    linked_customer_ids = {
        order.customer_order_line_id
        for order in dataset.customer_orders
        if order.production_order_id in demo_production_ids
    }
    chicago = next(
        position
        for position in dataset.inventory_positions
        if position.inventory_id == "RL-INV-DEMO-CHI"
    )

    assert [(bom.product_id, bom.quantity_per) for bom in critical_boms] == [
        ("RL-PROD-00000", 2)
    ]
    assert linked_customer_ids == {"RL-CO-DEMO-1", "RL-CO-DEMO-2"}
    assert chicago.on_hand - chicago.quality_hold - chicago.protected_allocation == 4000
