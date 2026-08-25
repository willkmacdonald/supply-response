"""RL-001 demo fixtures: Supplier Alpha delays MAT-10247.

Everything here is fictional. The fixture reproduces the demo scenario from the
project brief:

* Supplier Alpha (``RL-SUP-0001``) cannot deliver 8,000 units of MAT-10247
  (``RL-PART-10247``) on 2025-09-03 and offers 3,000 units on 2025-09-06 by air
  freight. The remaining recovery date is unconfirmed.
* Quality constraint ``RL-QUALITY-001`` states Supplier Beta (``RL-SUP-0002``)
  is not approved for MAT-10247, so scenario ``RL-SCN-005`` is not executable.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from data.schemas.models import (
    BomComponent,
    Customer,
    CustomerOrder,
    CustomerOrderStatus,
    Dataset,
    Disruption,
    DisruptionSeverity,
    DisruptionStatus,
    InventoryPosition,
    Part,
    PartType,
    POStatus,
    ProductionOrder,
    ProductionOrderStatus,
    PurchaseOrder,
    QualificationStatus,
    QualityQualification,
    ResponseScenario,
    RiskTier,
    ScenarioType,
    Supplier,
    SupplierPart,
    TransportMode,
    TransportOption,
)

DEMO_DISRUPTION_ID = "RL-001"
DEMO_PART_ID = "RL-PART-10247"
DEMO_PART_NUMBER = "MAT-10247"
DEMO_FINISHED_PART_ID = "RL-PART-20001"
DEMO_PLANT_ID = "RL-PLANT-01"
ALTERNATE_PLANT_ID = "RL-PLANT-02"
SUPPLIER_ALPHA_ID = "RL-SUP-0001"
SUPPLIER_BETA_ID = "RL-SUP-0002"
QUALITY_CONSTRAINT_ID = "RL-QUALITY-001"

HORIZON_START = date(2025, 9, 1)
HORIZON_END = date(2025, 9, 30)
SIGNAL_RECEIVED_AT = datetime(2025, 9, 1, 8, 15, tzinfo=timezone.utc)

DEMO_EMAIL = {
    "reference": "RL-001",
    "subject": "RL-001 Supplier Alpha delivery delay",
    "sender": "orders@rl-supplier-alpha.example",
    "received_at": SIGNAL_RECEIVED_AT.isoformat(),
    "body": (
        "Supplier Alpha cannot deliver 8,000 units of MAT-10247 on September 3. "
        "It can provide 3,000 units on September 6 by air freight. The remaining "
        "delivery date is unconfirmed."
    ),
}

DEMO_TEAMS_MESSAGE = {
    "reference": QUALITY_CONSTRAINT_ID,
    "sender": "Jordan Lee (Quality Manager)",
    "channel": "Teams direct message to Alex Morgan",
    "sent_at": datetime(2025, 9, 1, 9, 40, tzinfo=timezone.utc).isoformat(),
    "body": (
        "Supplier Beta is not approved for MAT-10247. The supplier audit and "
        "first-article approval remain incomplete. Do not place an emergency "
        "purchase order until both are complete. Earliest expected decision: "
        "September 15."
    ),
}


def demo_suppliers() -> list[Supplier]:
    return [
        Supplier(
            supplier_id=SUPPLIER_ALPHA_ID,
            supplier_name="RL Supplier Alpha",
            country="RL-Country-A",
            region="RL-Region-North",
            risk_tier=RiskTier.MEDIUM,
            on_time_delivery_rate=0.91,
            quality_score=0.97,
            preferred=True,
        ),
        Supplier(
            supplier_id=SUPPLIER_BETA_ID,
            supplier_name="RL Supplier Beta",
            country="RL-Country-B",
            region="RL-Region-South",
            risk_tier=RiskTier.HIGH,
            on_time_delivery_rate=0.86,
            quality_score=0.88,
            preferred=False,
        ),
    ]


def demo_parts() -> list[Part]:
    return [
        Part(
            part_id=DEMO_PART_ID,
            part_number=DEMO_PART_NUMBER,
            description="RL precision valve body",
            part_type=PartType.COMPONENT,
            standard_cost=18.40,
            lead_time_days=21,
            safety_stock=1500,
            critical=True,
        ),
        Part(
            part_id=DEMO_FINISHED_PART_ID,
            part_number="FG-20001",
            description="RL hydraulic control module",
            part_type=PartType.FINISHED_GOOD,
            standard_cost=260.00,
            lead_time_days=7,
            safety_stock=200,
            critical=True,
        ),
    ]


def demo_supplier_parts() -> list[SupplierPart]:
    return [
        SupplierPart(
            supplier_part_id="RL-SP-000001",
            supplier_id=SUPPLIER_ALPHA_ID,
            part_id=DEMO_PART_ID,
            unit_price=18.40,
            lead_time_days=21,
            min_order_qty=500,
            is_primary_source=True,
        ),
        SupplierPart(
            supplier_part_id="RL-SP-000002",
            supplier_id=SUPPLIER_BETA_ID,
            part_id=DEMO_PART_ID,
            unit_price=21.10,
            lead_time_days=14,
            min_order_qty=1000,
            is_primary_source=False,
        ),
    ]


def demo_purchase_orders() -> list[PurchaseOrder]:
    return [
        PurchaseOrder(
            po_id="RL-PO-000101",
            po_line=1,
            supplier_id=SUPPLIER_ALPHA_ID,
            part_id=DEMO_PART_ID,
            plant_id=DEMO_PLANT_ID,
            order_qty=8000,
            received_qty=0,
            promised_date=date(2025, 9, 3),
            revised_date=None,
            status=POStatus.DELAYED,
            unit_price=18.40,
        ),
        PurchaseOrder(
            po_id="RL-PO-000102",
            po_line=1,
            supplier_id=SUPPLIER_ALPHA_ID,
            part_id=DEMO_PART_ID,
            plant_id=DEMO_PLANT_ID,
            order_qty=2000,
            received_qty=0,
            promised_date=date(2025, 9, 18),
            status=POStatus.CONFIRMED,
            unit_price=18.40,
        ),
    ]


def demo_inventory_positions() -> list[InventoryPosition]:
    return [
        InventoryPosition(
            inventory_id="RL-INV-000101",
            part_id=DEMO_PART_ID,
            plant_id=DEMO_PLANT_ID,
            location_id="RL-LOC-0101",
            on_hand=5200,
            quality_hold=400,
            protected_allocation=800,
            in_transit=0,
            as_of_date=HORIZON_START,
        ),
        InventoryPosition(
            inventory_id="RL-INV-000102",
            part_id=DEMO_PART_ID,
            plant_id=ALTERNATE_PLANT_ID,
            location_id="RL-LOC-0201",
            on_hand=3600,
            quality_hold=0,
            protected_allocation=1100,
            in_transit=0,
            as_of_date=HORIZON_START,
        ),
    ]


def demo_bom_components() -> list[BomComponent]:
    return [
        BomComponent(
            bom_id="RL-BOM-000101",
            parent_part_id=DEMO_FINISHED_PART_ID,
            component_part_id=DEMO_PART_ID,
            qty_per=2.0,
            scrap_factor=0.0,
            level=1,
        )
    ]


def demo_production_orders() -> list[ProductionOrder]:
    return [
        ProductionOrder(
            production_order_id="RL-PRD-000101",
            plant_id=DEMO_PLANT_ID,
            part_id=DEMO_FINISHED_PART_ID,
            quantity=1500,
            start_date=date(2025, 9, 2),
            due_date=date(2025, 9, 8),
            status=ProductionOrderStatus.RELEASED,
            priority=1,
        ),
        ProductionOrder(
            production_order_id="RL-PRD-000102",
            plant_id=DEMO_PLANT_ID,
            part_id=DEMO_FINISHED_PART_ID,
            quantity=1200,
            start_date=date(2025, 9, 5),
            due_date=date(2025, 9, 12),
            status=ProductionOrderStatus.RELEASED,
            priority=2,
        ),
        ProductionOrder(
            production_order_id="RL-PRD-000103",
            plant_id=DEMO_PLANT_ID,
            part_id=DEMO_FINISHED_PART_ID,
            quantity=1000,
            start_date=date(2025, 9, 9),
            due_date=date(2025, 9, 16),
            status=ProductionOrderStatus.PLANNED,
            priority=3,
        ),
        ProductionOrder(
            production_order_id="RL-PRD-000104",
            plant_id=DEMO_PLANT_ID,
            part_id=DEMO_FINISHED_PART_ID,
            quantity=900,
            start_date=date(2025, 9, 12),
            due_date=date(2025, 9, 19),
            status=ProductionOrderStatus.PLANNED,
            priority=4,
        ),
        ProductionOrder(
            production_order_id="RL-PRD-000105",
            plant_id=DEMO_PLANT_ID,
            part_id=DEMO_FINISHED_PART_ID,
            quantity=800,
            start_date=date(2025, 9, 16),
            due_date=date(2025, 9, 23),
            status=ProductionOrderStatus.PLANNED,
            priority=5,
        ),
    ]


def demo_customers() -> list[Customer]:
    return [
        Customer(
            customer_id="RL-CUST-0001",
            customer_name="RL Northwind Machinery",
            segment="Industrial",
            region="RL-Region-North",
            priority_tier=1,
            otif_target=0.97,
        ),
        Customer(
            customer_id="RL-CUST-0002",
            customer_name="RL Contoso Equipment",
            segment="Automotive",
            region="RL-Region-East",
            priority_tier=2,
            otif_target=0.95,
        ),
        Customer(
            customer_id="RL-CUST-0003",
            customer_name="RL Fabrikam Systems",
            segment="Aftermarket",
            region="RL-Region-West",
            priority_tier=3,
            otif_target=0.92,
        ),
    ]


def demo_customer_orders() -> list[CustomerOrder]:
    common = {
        "part_id": DEMO_FINISHED_PART_ID,
        "plant_id": DEMO_PLANT_ID,
        "unit_price": 420.00,
        "unit_cost": 260.00,
        "status": CustomerOrderStatus.OPEN,
        "order_line": 1,
    }
    return [
        CustomerOrder(
            customer_order_id="RL-CO-000101",
            customer_id="RL-CUST-0001",
            quantity=600,
            requested_date=date(2025, 9, 9),
            promised_date=date(2025, 9, 10),
            **common,
        ),
        CustomerOrder(
            customer_order_id="RL-CO-000102",
            customer_id="RL-CUST-0001",
            quantity=900,
            requested_date=date(2025, 9, 14),
            promised_date=date(2025, 9, 15),
            **common,
        ),
        CustomerOrder(
            customer_order_id="RL-CO-000103",
            customer_id="RL-CUST-0002",
            quantity=750,
            requested_date=date(2025, 9, 17),
            promised_date=date(2025, 9, 18),
            **common,
        ),
        CustomerOrder(
            customer_order_id="RL-CO-000104",
            customer_id="RL-CUST-0003",
            quantity=500,
            requested_date=date(2025, 9, 21),
            promised_date=date(2025, 9, 22),
            **common,
        ),
        CustomerOrder(
            customer_order_id="RL-CO-000105",
            customer_id="RL-CUST-0002",
            quantity=400,
            requested_date=date(2025, 9, 25),
            promised_date=date(2025, 9, 26),
            **common,
        ),
    ]


def demo_transport_options() -> list[TransportOption]:
    return [
        TransportOption(
            transport_option_id="RL-TRN-00001",
            origin=SUPPLIER_ALPHA_ID,
            destination=DEMO_PLANT_ID,
            mode=TransportMode.AIR,
            transit_days=2,
            cost_per_unit=8.00,
            fixed_cost=4000.00,
            max_qty=5000,
        ),
        TransportOption(
            transport_option_id="RL-TRN-00002",
            origin=ALTERNATE_PLANT_ID,
            destination=DEMO_PLANT_ID,
            mode=TransportMode.ROAD,
            transit_days=2,
            cost_per_unit=1.20,
            fixed_cost=1800.00,
            max_qty=2500,
        ),
        TransportOption(
            transport_option_id="RL-TRN-00003",
            origin=SUPPLIER_BETA_ID,
            destination=DEMO_PLANT_ID,
            mode=TransportMode.OCEAN,
            transit_days=21,
            cost_per_unit=0.90,
            fixed_cost=600.00,
            max_qty=8000,
        ),
    ]


def demo_quality_qualifications() -> list[QualityQualification]:
    return [
        QualityQualification(
            qualification_id="RL-QUALITY-002",
            supplier_id=SUPPLIER_ALPHA_ID,
            part_id=DEMO_PART_ID,
            status=QualificationStatus.APPROVED,
            audit_complete=True,
            first_article_complete=True,
            note="RL Supplier Alpha is the approved source for MAT-10247.",
            source_reference="RL-QMS-RECORD-002",
        ),
        QualityQualification(
            qualification_id=QUALITY_CONSTRAINT_ID,
            supplier_id=SUPPLIER_BETA_ID,
            part_id=DEMO_PART_ID,
            status=QualificationStatus.NOT_APPROVED,
            audit_complete=False,
            first_article_complete=False,
            expected_decision_date=date(2025, 9, 15),
            note=(
                "Jordan Lee (Quality Manager): do not place an emergency purchase "
                "order with RL Supplier Beta until the supplier audit and "
                "first-article approval are complete."
            ),
            source_reference="Teams message RL-QUALITY-001",
        ),
    ]


def demo_disruption() -> Disruption:
    return Disruption(
        disruption_id=DEMO_DISRUPTION_ID,
        supplier_id=SUPPLIER_ALPHA_ID,
        part_id=DEMO_PART_ID,
        plant_id=DEMO_PLANT_ID,
        po_id="RL-PO-000101",
        po_line=1,
        delayed_qty=8000,
        original_date=date(2025, 9, 3),
        revised_date=None,
        partial_qty=3000,
        partial_date=date(2025, 9, 6),
        recovery_date_confirmed=False,
        severity=DisruptionSeverity.HIGH,
        status=DisruptionStatus.NEW,
        signal_received_at=SIGNAL_RECEIVED_AT,
        signal_source="email",
        signal_reference=DEMO_EMAIL["subject"],
        summary=DEMO_EMAIL["body"],
    )


def demo_response_scenarios() -> list[ResponseScenario]:
    part_assumption = f"part_id={DEMO_PART_ID}"
    return [
        ResponseScenario(
            scenario_id="RL-SCN-001",
            disruption_id=DEMO_DISRUPTION_ID,
            scenario_type=ScenarioType.ACCEPT_DELAY,
            title="Accept the delay and allow backlog",
            description=(
                "Take no mitigating action. Production is rescheduled as material "
                "arrives and customer commitments slip."
            ),
            executable=True,
            requires_approval=True,
            assumptions=[
                part_assumption,
                "No supplier recovery date is available, so no additional receipts are planned.",
                "Backlog penalty is applied per short unit.",
            ],
        ),
        ResponseScenario(
            scenario_id="RL-SCN-002",
            disruption_id=DEMO_DISRUPTION_ID,
            scenario_type=ScenarioType.EXPEDITE_PARTIAL,
            title="Expedite Supplier Alpha's 3,000-unit partial shipment",
            description=(
                "Accept the offered air-freight partial shipment of 3,000 units "
                "arriving 2025-09-06."
            ),
            expedite_qty=3000,
            transport_option_id="RL-TRN-00001",
            available_date=date(2025, 9, 6),
            executable=True,
            requires_approval=True,
            assumptions=[
                part_assumption,
                "Air freight capacity is available for the full 3,000 units.",
                "Supplier Alpha holds the 2025-09-06 partial commitment.",
            ],
        ),
        ResponseScenario(
            scenario_id="RL-SCN-003",
            disruption_id=DEMO_DISRUPTION_ID,
            scenario_type=ScenarioType.TRANSFER_INVENTORY,
            title="Transfer inventory from RL-PLANT-02",
            description=(
                "Move 2,500 usable units of MAT-10247 from RL-PLANT-02 to "
                "RL-PLANT-01 by road, arriving 2025-09-08."
            ),
            transfer_qty=2500,
            transport_option_id="RL-TRN-00002",
            available_date=date(2025, 9, 8),
            executable=True,
            requires_approval=True,
            assumptions=[
                part_assumption,
                "RL-PLANT-02 can release 2,500 units without breaching its own safety stock.",
            ],
        ),
        ResponseScenario(
            scenario_id="RL-SCN-004",
            disruption_id=DEMO_DISRUPTION_ID,
            scenario_type=ScenarioType.RESEQUENCE_PRODUCTION,
            title="Resequence production toward priority customers",
            description=(
                "Defer the lowest-priority production orders so remaining material "
                "protects tier 1 and tier 2 customers."
            ),
            resequenced_qty=1700,
            executable=True,
            requires_approval=True,
            assumptions=[
                part_assumption,
                "Deferred production orders can be rescheduled outside the 30-day horizon.",
                "Changeover cost is booked per resequenced production order.",
            ],
        ),
        ResponseScenario(
            scenario_id="RL-SCN-005",
            disruption_id=DEMO_DISRUPTION_ID,
            scenario_type=ScenarioType.ALTERNATE_SOURCE,
            title="Source from Supplier Beta",
            description=(
                "Place an emergency purchase order with RL Supplier Beta for the "
                "outstanding 5,000 units."
            ),
            expedite_qty=5000,
            alternate_supplier_id=SUPPLIER_BETA_ID,
            transport_option_id="RL-TRN-00003",
            available_date=date(2025, 9, 14),
            executable=False,
            blocking_constraint=(
                "RL-QUALITY-001: RL Supplier Beta is not approved for MAT-10247."
            ),
            requires_approval=True,
            assumptions=[
                part_assumption,
                "Quality approval would be required before any order is placed.",
                "Earliest quality decision is 2025-09-15.",
            ],
        ),
        ResponseScenario(
            scenario_id="RL-SCN-006",
            disruption_id=DEMO_DISRUPTION_ID,
            scenario_type=ScenarioType.COMBINED,
            title="Combine expedite, transfer, and resequencing",
            description=(
                "Expedite the 3,000-unit partial shipment, transfer 2,500 units "
                "from RL-PLANT-02, and defer the lowest-priority production orders."
            ),
            expedite_qty=3000,
            transfer_qty=2500,
            resequenced_qty=1700,
            transport_option_id="RL-TRN-00001",
            available_date=date(2025, 9, 6),
            executable=True,
            requires_approval=True,
            assumptions=[
                part_assumption,
                "Air freight and the inter-plant transfer can be executed in parallel.",
                "Transfer arrives with the expedited shipment window.",
            ],
        ),
    ]


def demo_dataset() -> Dataset:
    """The complete RL-001 fixture dataset."""
    return Dataset(
        seed=0,
        suppliers=demo_suppliers(),
        parts=demo_parts(),
        supplier_parts=demo_supplier_parts(),
        purchase_orders=demo_purchase_orders(),
        inventory_positions=demo_inventory_positions(),
        bom_components=demo_bom_components(),
        production_orders=demo_production_orders(),
        customers=demo_customers(),
        customer_orders=demo_customer_orders(),
        transport_options=demo_transport_options(),
        quality_qualifications=demo_quality_qualifications(),
        disruptions=[demo_disruption()],
        response_scenarios=demo_response_scenarios(),
        action_ledger=[],
        outcome_history=[],
    )


def demo_evidence() -> list[dict[str, str]]:
    """Work IQ style evidence records backing the RL-001 case."""
    return [
        {
            "evidence_id": "RL-EVD-001",
            "source": "email",
            "reference": DEMO_EMAIL["reference"],
            "title": DEMO_EMAIL["subject"],
            "content": DEMO_EMAIL["body"],
            "captured_at": DEMO_EMAIL["received_at"],
        },
        {
            "evidence_id": "RL-EVD-002",
            "source": "teams",
            "reference": DEMO_TEAMS_MESSAGE["reference"],
            "title": "RL-QUALITY-001 Supplier Beta qualification status",
            "content": DEMO_TEAMS_MESSAGE["body"],
            "captured_at": DEMO_TEAMS_MESSAGE["sent_at"],
        },
        {
            "evidence_id": "RL-EVD-003",
            "source": "erp",
            "reference": "RL-PO-000101",
            "title": "Purchase order RL-PO-000101 line 1",
            "content": "8,000 units of MAT-10247 promised 2025-09-03, status delayed.",
            "captured_at": SIGNAL_RECEIVED_AT.isoformat(),
        },
    ]


__all__ = [
    "ALTERNATE_PLANT_ID",
    "DEMO_DISRUPTION_ID",
    "DEMO_EMAIL",
    "DEMO_FINISHED_PART_ID",
    "DEMO_PART_ID",
    "DEMO_PART_NUMBER",
    "DEMO_PLANT_ID",
    "DEMO_TEAMS_MESSAGE",
    "HORIZON_END",
    "HORIZON_START",
    "QUALITY_CONSTRAINT_ID",
    "SIGNAL_RECEIVED_AT",
    "SUPPLIER_ALPHA_ID",
    "SUPPLIER_BETA_ID",
    "demo_bom_components",
    "demo_customer_orders",
    "demo_customers",
    "demo_dataset",
    "demo_disruption",
    "demo_evidence",
    "demo_inventory_positions",
    "demo_parts",
    "demo_production_orders",
    "demo_purchase_orders",
    "demo_quality_qualifications",
    "demo_response_scenarios",
    "demo_supplier_parts",
    "demo_suppliers",
    "demo_transport_options",
]
