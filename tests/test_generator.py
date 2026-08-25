from data.synthetic.generator import generate_dataset


def test_generator_is_deterministic_and_fictional():
    a = generate_dataset(seed=7, supplier_count=5, part_count=20, bom_relationship_count=30, customer_order_count=20)
    b = generate_dataset(seed=7, supplier_count=5, part_count=20, bom_relationship_count=30, customer_order_count=20)
    assert a == b
    assert all(x.supplier_id.startswith("RL-") and x.name.startswith("RL-") for x in a.suppliers)
    assert a.disruptions[0].recovery_date is None
