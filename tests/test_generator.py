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
    id_sets = {
        "supplier IDs": [supplier.supplier_id for supplier in dataset.suppliers],
        "part IDs": [part.part_id for part in dataset.parts],
        "purchase-order line IDs": [
            order.po_line_id for order in dataset.purchase_orders
        ],
        "inventory IDs": [
            position.inventory_id for position in dataset.inventory_positions
        ],
        "BOM IDs": [component.bom_id for component in dataset.bom_components],
        "production-order IDs": [
            order.production_order_id for order in dataset.production_orders
        ],
        "customer IDs": [customer.customer_id for customer in dataset.customers],
        "customer-order line IDs": [
            order.customer_order_line_id for order in dataset.customer_orders
        ],
        "transport-option IDs": [
            option.transport_option_id for option in dataset.transport_options
        ],
        "qualification IDs": [
            qualification.qualification_id
            for qualification in dataset.quality_qualifications
        ],
        "disruption IDs": [
            disruption.disruption_id for disruption in dataset.disruptions
        ],
    }
    for label, values in id_sets.items():
        assert len(values) == len(set(values)), f"duplicate {label}"

    supplier_part_keys = [
        (supplier_part.supplier_id, supplier_part.part_id)
        for supplier_part in dataset.supplier_parts
    ]
    inventory_keys = [
        (position.part_id, position.plant_id)
        for position in dataset.inventory_positions
    ]
    assert len(supplier_part_keys) == len(set(supplier_part_keys))
    assert len(inventory_keys) == len(set(inventory_keys))


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


def test_generic_production_orders_never_use_reserved_demo_product_at_scale():
    dataset = generate_dataset(
        seed=42,
        supplier_count=5,
        part_count=10,
        bom_relationship_count=20,
        customer_order_count=100,
    )
    demo_product_orders = {
        order.production_order_id
        for order in dataset.production_orders
        if order.product_id == "RL-PROD-00000"
    }
    assert demo_product_orders == {"RL-MO-DEMO-1", "RL-MO-DEMO-2"}
