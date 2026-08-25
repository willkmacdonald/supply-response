"""Tests for the deterministic synthetic dataset generator."""

from __future__ import annotations

import re

import pytest

from data.fixtures.demo import (
    DEMO_DISRUPTION_ID,
    DEMO_FINISHED_PART_ID,
    DEMO_PART_ID,
    DEMO_PLANT_ID,
    QUALITY_CONSTRAINT_ID,
    SUPPLIER_ALPHA_ID,
    SUPPLIER_BETA_ID,
    demo_dataset,
)
from data.schemas.models import (
    Dataset,
    PartType,
    QualificationStatus,
    TABLE_NAMES,
)
from data.synthetic.generator import (
    COMPONENT_COUNT,
    DEFAULT_SEED,
    FINISHED_GOOD_COUNT,
    SUPPLIER_COUNT,
    generate_dataset,
    load_dataset,
    write_dataset,
)

ID_FIELDS = {
    "suppliers": "supplier_id",
    "parts": "part_id",
    "supplier_parts": "supplier_part_id",
    "purchase_orders": "po_id",
    "inventory_positions": "inventory_id",
    "bom_components": "bom_id",
    "production_orders": "production_order_id",
    "customers": "customer_id",
    "customer_orders": "customer_order_id",
    "transport_options": "transport_option_id",
    "quality_qualifications": "qualification_id",
    "disruptions": "disruption_id",
    "response_scenarios": "scenario_id",
    "action_ledger": "action_id",
    "outcome_history": "outcome_id",
}


@pytest.fixture(scope="module")
def dataset() -> Dataset:
    return generate_dataset(DEFAULT_SEED)


def test_generator_is_deterministic():
    assert generate_dataset(7).model_dump_json() == generate_dataset(7).model_dump_json()


def test_different_seeds_produce_different_data():
    assert generate_dataset(1).model_dump_json() != generate_dataset(2).model_dump_json()


def test_all_tables_are_populated(dataset: Dataset):
    counts = dataset.row_counts()
    assert set(counts) == set(TABLE_NAMES)
    for name in TABLE_NAMES:
        assert counts[name] > 0, name


def test_scale(dataset: Dataset):
    assert len(dataset.suppliers) == SUPPLIER_COUNT
    # The two demo parts are merged in on top of the generated catalogue.
    assert len(dataset.parts) == COMPONENT_COUNT + FINISHED_GOOD_COUNT + 2
    assert (
        sum(1 for p in dataset.parts if p.part_type == PartType.FINISHED_GOOD)
        == FINISHED_GOOD_COUNT + 1
    )


def test_generated_rows_never_reference_demo_parts(dataset: Dataset):
    """The RL-001 case must produce identical numbers in any generated dataset."""
    demo = demo_dataset()
    demo_parts = {p.part_id for p in demo.parts}
    demo_boms = {row.bom_id for row in demo.bom_components}
    demo_orders = {row.production_order_id for row in demo.production_orders}

    for row in dataset.bom_components:
        if row.bom_id in demo_boms:
            continue
        assert row.component_part_id not in demo_parts
        assert row.parent_part_id not in demo_parts

    for row in dataset.production_orders:
        if row.production_order_id in demo_orders:
            continue
        assert row.part_id not in demo_parts


def test_all_business_ids_use_the_rl_prefix(dataset: Dataset):
    for table in TABLE_NAMES:
        field = ID_FIELDS[table]
        for row in dataset.table(table):
            assert getattr(row, field).startswith("RL-"), (table, field)


def test_ids_are_unique(dataset: Dataset):
    for table in TABLE_NAMES:
        field = ID_FIELDS[table]
        ids = [getattr(row, field) for row in dataset.table(table)]
        if table in {"purchase_orders", "customer_orders"}:
            continue  # composite key with the line number
        assert len(ids) == len(set(ids)), table


def test_plants_use_the_rl_prefix(dataset: Dataset):
    pattern = re.compile(r"^RL-PLANT-\d{2}$")
    for position in dataset.inventory_positions:
        assert pattern.match(position.plant_id)


def test_referential_integrity(dataset: Dataset):
    supplier_ids = {s.supplier_id for s in dataset.suppliers}
    part_ids = {p.part_id for p in dataset.parts}
    customer_ids = {c.customer_id for c in dataset.customers}

    for supplier_part in dataset.supplier_parts:
        assert supplier_part.supplier_id in supplier_ids
        assert supplier_part.part_id in part_ids
    for po in dataset.purchase_orders:
        assert po.supplier_id in supplier_ids
        assert po.part_id in part_ids
    for bom in dataset.bom_components:
        assert bom.parent_part_id in part_ids
        assert bom.component_part_id in part_ids
    for order in dataset.customer_orders:
        assert order.customer_id in customer_ids
        assert order.part_id in part_ids
    for disruption in dataset.disruptions:
        assert disruption.supplier_id in supplier_ids
        assert disruption.part_id in part_ids


def test_demo_scenario_is_merged_into_every_dataset(dataset: Dataset):
    disruption = next(
        d for d in dataset.disruptions if d.disruption_id == DEMO_DISRUPTION_ID
    )
    assert disruption.supplier_id == SUPPLIER_ALPHA_ID
    assert disruption.part_id == DEMO_PART_ID
    assert disruption.plant_id == DEMO_PLANT_ID
    assert disruption.delayed_qty == 8000
    assert disruption.partial_qty == 3000

    part_ids = {p.part_id for p in dataset.parts}
    assert {DEMO_PART_ID, DEMO_FINISHED_PART_ID} <= part_ids

    scenario_ids = {s.scenario_id for s in dataset.response_scenarios}
    assert scenario_ids == {f"RL-SCN-{i:03d}" for i in range(1, 7)}


def test_demo_quality_constraint_survives_generation(dataset: Dataset):
    constraint = next(
        q
        for q in dataset.quality_qualifications
        if q.qualification_id == QUALITY_CONSTRAINT_ID
    )
    assert constraint.supplier_id == SUPPLIER_BETA_ID
    assert constraint.part_id == DEMO_PART_ID
    assert constraint.status == QualificationStatus.NOT_APPROVED
    assert constraint.executable is False


def test_demo_inventory_is_not_overwritten(dataset: Dataset):
    position = next(
        p
        for p in dataset.inventory_positions
        if p.part_id == DEMO_PART_ID and p.plant_id == DEMO_PLANT_ID
    )
    assert position.on_hand == 5200
    assert position.quality_hold == 400
    assert position.protected_allocation == 800


def test_round_trip_json(tmp_path, dataset: Dataset):
    path = write_dataset(dataset, tmp_path / "dataset.json")
    reloaded = load_dataset(path)
    assert reloaded.row_counts() == dataset.row_counts()
    assert reloaded.model_dump_json() == dataset.model_dump_json()


def test_history_is_recorded_for_closed_disruptions(dataset: Dataset):
    closed_ids = {
        d.disruption_id for d in dataset.disruptions if d.status.value == "closed"
    }
    assert closed_ids
    for outcome in dataset.outcome_history:
        assert outcome.disruption_id in closed_ids
    action_ids = {a.action_id for a in dataset.action_ledger}
    for outcome in dataset.outcome_history:
        assert outcome.action_id in action_ids


def test_generated_dataset_can_be_analyzed():
    """Every generated disruption must be analyzable end to end."""
    from apps.api.services import analyze

    dataset = generate_dataset(11)
    disruption = next(d for d in dataset.disruptions if d.disruption_id != DEMO_DISRUPTION_ID)
    exposure, evaluations = analyze(dataset, disruption)
    assert exposure.calculation_version
    assert evaluations
    assert all(e.rank > 0 for e in evaluations)
