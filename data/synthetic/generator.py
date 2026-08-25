"""Deterministic synthetic dataset generator for Supply Response.

The brief targets 250 suppliers / 10,000 parts / 100,000 BOM rows. That scale is
generated in Fabric; locally we generate a scaled-down but structurally
identical dataset (~50 suppliers, ~500 parts) that runs in well under a second.

The generator is fully deterministic: the same ``seed`` always produces the same
dataset. The RL-001 demo fixtures are always merged in last so the demo scenario
is present in every generated dataset.

Usage::

    python -m data.synthetic.generator --seed 42 --out data/synthetic/dataset.json
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence, TypeVar

from data.fixtures import demo as demo_fixtures
from data.schemas.models import (
    ActionLedgerEntry,
    BomComponent,
    Customer,
    CustomerOrder,
    CustomerOrderStatus,
    Dataset,
    Disruption,
    DisruptionSeverity,
    DisruptionStatus,
    InventoryPosition,
    OutcomeHistory,
    Part,
    PartType,
    POStatus,
    ProductionOrder,
    ProductionOrderStatus,
    PurchaseOrder,
    QualificationStatus,
    QualityQualification,
    RiskTier,
    Supplier,
    SupplierPart,
    TransportMode,
    TransportOption,
)

GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 42

SUPPLIER_COUNT = 50
COMPONENT_COUNT = 400
FINISHED_GOOD_COUNT = 100
CUSTOMER_COUNT = 40
PLANTS = ("RL-PLANT-01", "RL-PLANT-02", "RL-PLANT-03", "RL-PLANT-04")
HORIZON_START = date(2025, 9, 1)
HISTORY_MONTHS = 12

# Demo part ids are owned by the RL-001 fixtures. Generated rows never reference
# them, so the demo case produces identical results in any generated dataset.
RESERVED_PART_IDS = frozenset(
    {demo_fixtures.DEMO_PART_ID, demo_fixtures.DEMO_FINISHED_PART_ID}
)

_SUPPLIER_WORDS = (
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta",
    "Iota", "Kappa", "Lambda", "Sigma", "Omega", "Nova", "Vector", "Quanta",
)
_PART_WORDS = (
    "valve", "bracket", "housing", "seal", "rotor", "shaft", "bearing",
    "manifold", "gasket", "actuator", "sensor", "coupling",
)
_CUSTOMER_WORDS = (
    "Northwind", "Contoso", "Fabrikam", "Litware", "Adventure", "Proseware",
    "Wingtip", "Tailspin", "Coho", "Relecloud",
)
_SEGMENTS = ("Industrial", "Automotive", "Aerospace", "Aftermarket", "Energy")
_REGIONS = ("RL-Region-North", "RL-Region-South", "RL-Region-East", "RL-Region-West")

T = TypeVar("T")


def _merge(generated: Sequence[T], overrides: Sequence[T], key: Callable[[T], Any]) -> list[T]:
    """Replace generated rows with fixture rows that share the same key."""
    merged: dict[Any, T] = {key(row): row for row in generated}
    for row in overrides:
        merged[key(row)] = row
    return [merged[k] for k in sorted(merged, key=str)]


def _supplier_name(rng: random.Random, index: int) -> str:
    word = _SUPPLIER_WORDS[index % len(_SUPPLIER_WORDS)]
    return f"RL Supplier {word}" if index < len(_SUPPLIER_WORDS) else f"RL Supplier {word} {index:03d}"


def generate_suppliers(rng: random.Random) -> list[Supplier]:
    suppliers: list[Supplier] = []
    for index in range(1, SUPPLIER_COUNT + 1):
        suppliers.append(
            Supplier(
                supplier_id=f"RL-SUP-{index:04d}",
                supplier_name=_supplier_name(rng, index - 1),
                country=f"RL-Country-{chr(ord('A') + index % 8)}",
                region=rng.choice(_REGIONS),
                risk_tier=rng.choice(list(RiskTier)),
                on_time_delivery_rate=round(rng.uniform(0.80, 0.99), 3),
                quality_score=round(rng.uniform(0.85, 0.99), 3),
                preferred=rng.random() < 0.3,
            )
        )
    return suppliers


def generate_parts(rng: random.Random) -> list[Part]:
    parts: list[Part] = []
    offset = -1
    while len([p for p in parts if p.part_type == PartType.COMPONENT]) < COMPONENT_COUNT:
        offset += 1
        number = 10000 + offset
        if f"RL-PART-{number:05d}" in RESERVED_PART_IDS:
            continue
        parts.append(
            Part(
                part_id=f"RL-PART-{number:05d}",
                part_number=f"MAT-{number}",
                description=f"RL {rng.choice(_PART_WORDS)} component {number}",
                part_type=PartType.COMPONENT,
                standard_cost=round(rng.uniform(2.5, 95.0), 2),
                lead_time_days=rng.randint(5, 45),
                safety_stock=rng.randrange(200, 3000, 100),
                critical=rng.random() < 0.2,
            )
        )
    offset = -1
    while len([p for p in parts if p.part_type == PartType.FINISHED_GOOD]) < FINISHED_GOOD_COUNT:
        offset += 1
        number = 20000 + offset
        if f"RL-PART-{number:05d}" in RESERVED_PART_IDS:
            continue
        parts.append(
            Part(
                part_id=f"RL-PART-{number:05d}",
                part_number=f"FG-{number}",
                description=f"RL {rng.choice(_PART_WORDS)} assembly {number}",
                part_type=PartType.FINISHED_GOOD,
                standard_cost=round(rng.uniform(120.0, 640.0), 2),
                lead_time_days=rng.randint(3, 21),
                safety_stock=rng.randrange(50, 500, 50),
                critical=rng.random() < 0.35,
            )
        )
    return parts


def generate_supplier_parts(
    rng: random.Random, suppliers: Sequence[Supplier], parts: Sequence[Part]
) -> list[SupplierPart]:
    components = [p for p in parts if p.part_type == PartType.COMPONENT]
    rows: list[SupplierPart] = []
    counter = 1000
    for part in components:
        sources = rng.sample(suppliers, k=rng.randint(1, 2))
        for position, supplier in enumerate(sources):
            counter += 1
            rows.append(
                SupplierPart(
                    supplier_part_id=f"RL-SP-{counter:06d}",
                    supplier_id=supplier.supplier_id,
                    part_id=part.part_id,
                    unit_price=round(part.standard_cost * rng.uniform(0.95, 1.2), 2),
                    lead_time_days=part.lead_time_days + rng.randint(-3, 7),
                    min_order_qty=rng.randrange(100, 1500, 100),
                    is_primary_source=position == 0,
                )
            )
    return rows


def generate_bom_components(
    rng: random.Random, parts: Sequence[Part]
) -> list[BomComponent]:
    components = [p for p in parts if p.part_type == PartType.COMPONENT]
    finished = [p for p in parts if p.part_type == PartType.FINISHED_GOOD]
    rows: list[BomComponent] = []
    counter = 1000
    for product in finished:
        for component in rng.sample(components, k=rng.randint(4, 10)):
            counter += 1
            rows.append(
                BomComponent(
                    bom_id=f"RL-BOM-{counter:06d}",
                    parent_part_id=product.part_id,
                    component_part_id=component.part_id,
                    qty_per=float(rng.randint(1, 6)),
                    scrap_factor=round(rng.choice([0.0, 0.01, 0.02, 0.05]), 2),
                    level=1,
                )
            )
    return rows


def generate_inventory_positions(
    rng: random.Random, parts: Sequence[Part]
) -> list[InventoryPosition]:
    rows: list[InventoryPosition] = []
    counter = 1000
    for part in parts:
        for plant in rng.sample(PLANTS, k=rng.randint(1, 3)):
            counter += 1
            on_hand = rng.randrange(0, 9000, 50)
            rows.append(
                InventoryPosition(
                    inventory_id=f"RL-INV-{counter:06d}",
                    part_id=part.part_id,
                    plant_id=plant,
                    location_id=f"RL-LOC-{plant[-2:]}{counter % 100:02d}",
                    on_hand=on_hand,
                    quality_hold=int(on_hand * rng.choice([0.0, 0.0, 0.05, 0.1])),
                    protected_allocation=int(on_hand * rng.choice([0.0, 0.1, 0.2])),
                    in_transit=rng.randrange(0, 2000, 100),
                    as_of_date=HORIZON_START,
                )
            )
    return rows


def generate_purchase_orders(
    rng: random.Random, supplier_parts: Sequence[SupplierPart]
) -> list[PurchaseOrder]:
    rows: list[PurchaseOrder] = []
    counter = 1000
    for supplier_part in supplier_parts:
        for _ in range(rng.randint(0, 2)):
            counter += 1
            order_qty = rng.randrange(500, 9000, 250)
            status = rng.choices(
                [POStatus.OPEN, POStatus.CONFIRMED, POStatus.PARTIAL, POStatus.DELAYED],
                weights=[35, 45, 12, 8],
                k=1,
            )[0]
            promised = HORIZON_START + timedelta(days=rng.randint(0, 60))
            revised = (
                promised + timedelta(days=rng.randint(3, 21))
                if status == POStatus.DELAYED and rng.random() < 0.5
                else None
            )
            rows.append(
                PurchaseOrder(
                    po_id=f"RL-PO-{counter:06d}",
                    po_line=1,
                    supplier_id=supplier_part.supplier_id,
                    part_id=supplier_part.part_id,
                    plant_id=rng.choice(PLANTS),
                    order_qty=order_qty,
                    received_qty=int(order_qty * 0.4) if status == POStatus.PARTIAL else 0,
                    promised_date=promised,
                    revised_date=revised,
                    status=status,
                    unit_price=supplier_part.unit_price,
                )
            )
    return rows


def generate_production_orders(
    rng: random.Random, parts: Sequence[Part]
) -> list[ProductionOrder]:
    finished = [p for p in parts if p.part_type == PartType.FINISHED_GOOD]
    rows: list[ProductionOrder] = []
    counter = 1000
    for product in finished:
        for _ in range(rng.randint(1, 4)):
            counter += 1
            start = HORIZON_START + timedelta(days=rng.randint(0, 45))
            rows.append(
                ProductionOrder(
                    production_order_id=f"RL-PRD-{counter:06d}",
                    plant_id=rng.choice(PLANTS),
                    part_id=product.part_id,
                    quantity=rng.randrange(100, 2500, 50),
                    start_date=start,
                    due_date=start + timedelta(days=rng.randint(3, 14)),
                    status=rng.choice(
                        [
                            ProductionOrderStatus.PLANNED,
                            ProductionOrderStatus.RELEASED,
                            ProductionOrderStatus.IN_PROGRESS,
                        ]
                    ),
                    priority=rng.randint(1, 5),
                )
            )
    return rows


def generate_customers(rng: random.Random) -> list[Customer]:
    rows: list[Customer] = []
    for index in range(1, CUSTOMER_COUNT + 1):
        word = _CUSTOMER_WORDS[(index - 1) % len(_CUSTOMER_WORDS)]
        rows.append(
            Customer(
                customer_id=f"RL-CUST-{index:04d}",
                customer_name=f"RL {word} {index:03d}",
                segment=rng.choice(_SEGMENTS),
                region=rng.choice(_REGIONS),
                priority_tier=rng.randint(1, 3),
                otif_target=round(rng.uniform(0.90, 0.98), 2),
            )
        )
    return rows


def generate_customer_orders(
    rng: random.Random, parts: Sequence[Part], customers: Sequence[Customer]
) -> list[CustomerOrder]:
    finished = [p for p in parts if p.part_type == PartType.FINISHED_GOOD]
    rows: list[CustomerOrder] = []
    counter = 1000
    for product in finished:
        for _ in range(rng.randint(2, 6)):
            counter += 1
            customer = rng.choice(customers)
            requested = HORIZON_START + timedelta(days=rng.randint(2, 60))
            unit_cost = round(product.standard_cost, 2)
            rows.append(
                CustomerOrder(
                    customer_order_id=f"RL-CO-{counter:06d}",
                    order_line=1,
                    customer_id=customer.customer_id,
                    part_id=product.part_id,
                    plant_id=rng.choice(PLANTS),
                    quantity=rng.randrange(50, 1200, 50),
                    requested_date=requested,
                    promised_date=requested + timedelta(days=rng.randint(0, 3)),
                    unit_price=round(unit_cost * rng.uniform(1.25, 1.8), 2),
                    unit_cost=unit_cost,
                    status=rng.choices(
                        [
                            CustomerOrderStatus.OPEN,
                            CustomerOrderStatus.ALLOCATED,
                            CustomerOrderStatus.SHIPPED,
                        ],
                        weights=[60, 25, 15],
                        k=1,
                    )[0],
                )
            )
    return rows


def generate_transport_options(
    rng: random.Random, suppliers: Sequence[Supplier]
) -> list[TransportOption]:
    rows: list[TransportOption] = []
    counter = 10
    for supplier in suppliers:
        for plant in rng.sample(PLANTS, k=2):
            for mode in (TransportMode.AIR, TransportMode.OCEAN):
                counter += 1
                rows.append(
                    TransportOption(
                        transport_option_id=f"RL-TRN-{counter:05d}",
                        origin=supplier.supplier_id,
                        destination=plant,
                        mode=mode,
                        transit_days=2 if mode == TransportMode.AIR else rng.randint(18, 35),
                        cost_per_unit=round(
                            rng.uniform(5.0, 12.0) if mode == TransportMode.AIR else rng.uniform(0.4, 1.5),
                            2,
                        ),
                        fixed_cost=round(
                            rng.uniform(2500.0, 6000.0) if mode == TransportMode.AIR else rng.uniform(400.0, 1200.0),
                            2,
                        ),
                        max_qty=rng.randrange(2000, 9000, 500),
                    )
                )
    for origin in PLANTS:
        for destination in PLANTS:
            if origin == destination:
                continue
            counter += 1
            rows.append(
                TransportOption(
                    transport_option_id=f"RL-TRN-{counter:05d}",
                    origin=origin,
                    destination=destination,
                    mode=TransportMode.ROAD,
                    transit_days=rng.randint(1, 4),
                    cost_per_unit=round(rng.uniform(0.8, 2.5), 2),
                    fixed_cost=round(rng.uniform(900.0, 2500.0), 2),
                    max_qty=rng.randrange(1000, 4000, 500),
                )
            )
    return rows


def generate_quality_qualifications(
    rng: random.Random, supplier_parts: Sequence[SupplierPart]
) -> list[QualityQualification]:
    rows: list[QualityQualification] = []
    counter = 100
    for supplier_part in supplier_parts:
        if counter >= 999:
            break
        counter += 1
        approved = rng.random() < 0.85
        status = QualificationStatus.APPROVED if approved else rng.choice(
            [QualificationStatus.NOT_APPROVED, QualificationStatus.CONDITIONAL]
        )
        rows.append(
            QualityQualification(
                qualification_id=f"RL-QUALITY-{counter:03d}",
                supplier_id=supplier_part.supplier_id,
                part_id=supplier_part.part_id,
                status=status,
                audit_complete=approved,
                first_article_complete=approved,
                expected_decision_date=None if approved else HORIZON_START + timedelta(days=14),
                note="RL synthetic qualification record.",
                source_reference=f"RL-QMS-RECORD-{counter:03d}",
            )
        )
    return rows


def generate_history(
    rng: random.Random, disruptions: Sequence[Disruption]
) -> tuple[list[ActionLedgerEntry], list[OutcomeHistory]]:
    """Twelve months of closed disruption outcomes."""
    actions: list[ActionLedgerEntry] = []
    outcomes: list[OutcomeHistory] = []
    for index, disruption in enumerate(disruptions, start=1):
        if disruption.status != DisruptionStatus.CLOSED:
            continue
        decided_at = datetime.combine(
            disruption.original_date, datetime.min.time(), tzinfo=timezone.utc
        )
        action_id = f"RL-ACT-{index:06d}"
        predicted_cost = round(rng.uniform(2000.0, 60000.0), 2)
        predicted_revenue = round(rng.uniform(50000.0, 900000.0), 2)
        actions.append(
            ActionLedgerEntry(
                action_id=action_id,
                disruption_id=disruption.disruption_id,
                scenario_id=None,
                action_type="historical_response",
                status="approved",
                decided_by="RL Historical Planner",
                decided_at=decided_at,
                rationale="Historical synthetic response retained for benchmarking.",
                evidence=[f"disruption:{disruption.disruption_id}"],
                calculation_version=GENERATOR_VERSION,
            )
        )
        outcomes.append(
            OutcomeHistory(
                outcome_id=f"RL-OUT-{index:06d}",
                disruption_id=disruption.disruption_id,
                scenario_id=None,
                action_id=action_id,
                predicted_revenue_protected=predicted_revenue,
                actual_revenue_protected=round(predicted_revenue * rng.uniform(0.8, 1.1), 2),
                predicted_cost=predicted_cost,
                actual_cost=round(predicted_cost * rng.uniform(0.9, 1.3), 2),
                predicted_otif_impact=round(rng.uniform(0.0, 0.08), 3),
                actual_otif_impact=round(rng.uniform(0.0, 0.08), 3),
                recorded_at=decided_at,
                lessons_learned="RL synthetic retrospective note.",
            )
        )
    return actions, outcomes


def generate_disruptions(
    rng: random.Random, purchase_orders: Sequence[PurchaseOrder]
) -> list[Disruption]:
    """Historical and active disruptions (ids RL-100 upward; RL-001 is the demo)."""
    delayed = [po for po in purchase_orders if po.status == POStatus.DELAYED]
    rows: list[Disruption] = []
    for index, po in enumerate(delayed[:80], start=100):
        signal_date = po.promised_date - timedelta(days=rng.randint(1, 20))
        closed = signal_date < HORIZON_START
        rows.append(
            Disruption(
                disruption_id=f"RL-{index:03d}",
                supplier_id=po.supplier_id,
                part_id=po.part_id,
                plant_id=po.plant_id,
                po_id=po.po_id,
                po_line=po.po_line,
                delayed_qty=po.open_qty,
                original_date=po.promised_date,
                revised_date=po.revised_date,
                partial_qty=0,
                partial_date=None,
                recovery_date_confirmed=po.revised_date is not None,
                severity=rng.choice(list(DisruptionSeverity)),
                status=DisruptionStatus.CLOSED if closed else DisruptionStatus.NEW,
                signal_received_at=datetime.combine(
                    signal_date, datetime.min.time(), tzinfo=timezone.utc
                ),
                signal_source=rng.choice(["email", "teams", "portal"]),
                signal_reference=f"RL synthetic supplier notice {index:03d}",
                summary=(
                    f"RL synthetic delay of {po.open_qty} units of {po.part_id} "
                    f"for {po.plant_id}."
                ),
            )
        )
    return rows


def generate_dataset(seed: int = DEFAULT_SEED) -> Dataset:
    """Generate the full synthetic dataset, with the RL-001 demo merged in."""
    rng = random.Random(seed)

    suppliers = generate_suppliers(rng)
    parts = generate_parts(rng)
    supplier_parts = generate_supplier_parts(rng, suppliers, parts)
    bom_components = generate_bom_components(rng, parts)
    inventory_positions = generate_inventory_positions(rng, parts)
    purchase_orders = generate_purchase_orders(rng, supplier_parts)
    production_orders = generate_production_orders(rng, parts)
    customers = generate_customers(rng)
    customer_orders = generate_customer_orders(rng, parts, customers)
    transport_options = generate_transport_options(rng, suppliers)
    quality_qualifications = generate_quality_qualifications(rng, supplier_parts)
    disruptions = generate_disruptions(rng, purchase_orders)
    action_ledger, outcome_history = generate_history(rng, disruptions)

    demo = demo_fixtures.demo_dataset()

    dataset = Dataset(
        seed=seed,
        suppliers=_merge(suppliers, demo.suppliers, lambda r: r.supplier_id),
        parts=_merge(parts, demo.parts, lambda r: r.part_id),
        supplier_parts=_merge(
            supplier_parts, demo.supplier_parts, lambda r: (r.supplier_id, r.part_id)
        ),
        purchase_orders=_merge(
            purchase_orders, demo.purchase_orders, lambda r: (r.po_id, r.po_line)
        ),
        inventory_positions=_merge(
            inventory_positions,
            demo.inventory_positions,
            lambda r: (r.part_id, r.plant_id),
        ),
        bom_components=_merge(
            bom_components,
            demo.bom_components,
            lambda r: (r.parent_part_id, r.component_part_id),
        ),
        production_orders=_merge(
            production_orders, demo.production_orders, lambda r: r.production_order_id
        ),
        customers=_merge(customers, demo.customers, lambda r: r.customer_id),
        customer_orders=_merge(
            customer_orders, demo.customer_orders, lambda r: (r.customer_order_id, r.order_line)
        ),
        transport_options=_merge(
            transport_options, demo.transport_options, lambda r: r.transport_option_id
        ),
        quality_qualifications=_merge(
            quality_qualifications,
            demo.quality_qualifications,
            lambda r: (r.supplier_id, r.part_id),
        ),
        disruptions=_merge(disruptions, demo.disruptions, lambda r: r.disruption_id),
        response_scenarios=_merge(
            [], demo.response_scenarios, lambda r: r.scenario_id
        ),
        action_ledger=action_ledger,
        outcome_history=outcome_history,
    )
    return dataset


def write_dataset(dataset: Dataset, path: Path | str) -> Path:
    """Write the dataset to JSON (used to seed the local SQLite database)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_dataset(path: Path | str) -> Dataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return Dataset.model_validate(payload)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the Supply Response synthetic dataset.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", default="data/synthetic/dataset.json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    dataset = generate_dataset(args.seed)
    out_path = write_dataset(dataset, args.out)
    counts = dataset.row_counts()
    print(f"seed={args.seed} -> {out_path}")
    for name, count in counts.items():
        print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
