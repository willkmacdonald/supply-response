from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from data.domain import (
    CaseInstance,
    CasePurpose,
    CustomerOrder,
    DemoTemplate,
    Disruption,
    FrozenModel,
    InventoryPosition,
    InventoryTransfer,
    ProductionOrder,
    QualificationStatus,
    QualityQualification,
    RuntimeMode,
    SupplyReceiptOption,
)


SCENARIO_EFFECTIVE_TIME = datetime.fromisoformat("2026-09-01T09:00:00-05:00")


class OperationalSnapshot(FrozenModel):
    case_id: str
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime
    scenario_timezone: Literal["America/Chicago"] = "America/Chicago"
    analysis_horizon_start: datetime
    analysis_horizon_end: date
    inventory_positions: tuple[InventoryPosition, ...]
    production_orders: tuple[ProductionOrder, ...]
    customer_orders: tuple[CustomerOrder, ...]
    disruption: Disruption
    alpha_expedite: SupplyReceiptOption
    transfer: InventoryTransfer
    beta_qualification: QualityQualification

    def usable_inventory(self, part_id: str, plant_id: str) -> int:
        return sum(
            position.on_hand - position.quality_hold - position.protected_allocation
            for position in self.inventory_positions
            if position.part_id == part_id and position.plant_id == plant_id
        )

    @classmethod
    def rl001(
        cls,
        *,
        case_id: str = "RL-CASE-1",
        runtime_mode: RuntimeMode = RuntimeMode.FALLBACK,
    ) -> "OperationalSnapshot":
        production_orders = (
            ProductionOrder(
                production_order_id="RL-MO-DEMO-1",
                product_id="RL-PROD-00000",
                plant_id="RL-PLANT-CHI",
                quantity=2500,
                due_date=date(2026, 9, 5),
                component_demand=5000,
                customer_order_id="RL-CO-DEMO-1",
                customer_priority=3,
                customer_revenue=Decimal("375000"),
                customer_margin=Decimal("125000"),
            ),
            ProductionOrder(
                production_order_id="RL-MO-DEMO-2",
                product_id="RL-PROD-00000",
                plant_id="RL-PLANT-CHI",
                quantity=2900,
                due_date=date(2026, 9, 8),
                component_demand=5800,
                customer_order_id="RL-CO-DEMO-2",
                customer_priority=1,
                customer_revenue=Decimal("580000"),
                customer_margin=Decimal("203000"),
            ),
        )
        customer_orders = (
            CustomerOrder(
                customer_order_line_id="RL-CO-DEMO-1",
                customer_id="RL-CUST-DEMO-1",
                product_id="RL-PROD-00000",
                plant_id="RL-PLANT-CHI",
                production_order_id="RL-MO-DEMO-1",
                quantity=2500,
                due_date=date(2026, 9, 5),
                unit_revenue=Decimal("150"),
                unit_margin=Decimal("50"),
            ),
            CustomerOrder(
                customer_order_line_id="RL-CO-DEMO-2",
                customer_id="RL-CUST-DEMO-2",
                product_id="RL-PROD-00000",
                plant_id="RL-PLANT-CHI",
                production_order_id="RL-MO-DEMO-2",
                quantity=2900,
                due_date=date(2026, 9, 8),
                unit_revenue=Decimal("200"),
                unit_margin=Decimal("70"),
            ),
        )
        return cls(
            case_id=case_id,
            runtime_mode=runtime_mode,
            scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
            analysis_horizon_start=SCENARIO_EFFECTIVE_TIME,
            analysis_horizon_end=max(
                *(order.due_date for order in production_orders),
                *(order.due_date for order in customer_orders),
            ),
            inventory_positions=(
                InventoryPosition(
                    inventory_id="RL-INV-DEMO-CHI",
                    part_id="RL-MAT-10247",
                    plant_id="RL-PLANT-CHI",
                    on_hand=4500,
                    quality_hold=200,
                    protected_allocation=300,
                ),
                InventoryPosition(
                    inventory_id="RL-INV-DEMO-DAL",
                    part_id="RL-MAT-10247",
                    plant_id="RL-PLANT-DAL",
                    on_hand=1800,
                    quality_hold=0,
                    protected_allocation=300,
                ),
            ),
            production_orders=production_orders,
            customer_orders=customer_orders,
            disruption=Disruption(
                disruption_id="RL-DISRUPTION-001",
                supplier_id="RL-SUP-ALPHA",
                po_line_id="RL-PO-000001",
                part_id="RL-MAT-10247",
                plant_id="RL-PLANT-CHI",
                original_quantity=8000,
                original_due_date=date(2026, 9, 3),
                partial_quantity=0,
                partial_due_date=None,
                recovery_date=None,
                source_ref="RL-001",
            ),
            alpha_expedite=SupplyReceiptOption(
                receipt_id="RL-ALPHA-OPTIONAL-3000",
                supplier_id="RL-SUP-ALPHA",
                part_id="RL-MAT-10247",
                plant_id="RL-PLANT-CHI",
                quantity=3000,
                due_date=date(2026, 9, 6),
                incremental_cost_per_unit=Decimal("7.50"),
            ),
            transfer=InventoryTransfer(
                transfer_id="RL-TRANSFER-DAL-CHI-1500",
                part_id="RL-MAT-10247",
                source_plant_id="RL-PLANT-DAL",
                destination_plant_id="RL-PLANT-CHI",
                quantity=1500,
                dispatch_date=date(2026, 9, 4),
                arrival_date=date(2026, 9, 5),
                incremental_cost_per_unit=Decimal("1.50"),
            ),
            beta_qualification=QualityQualification(
                qualification_id="RL-QUAL-BETA",
                supplier_id="RL-SUP-BETA",
                part_id="RL-MAT-10247",
                status=QualificationStatus.PENDING,
                evidence_ref="RL-QUALITY-001",
                audit_complete=False,
                first_article_complete=False,
                expected_decision_date=date(2026, 9, 15),
            ),
        )


def build_rl001_template() -> DemoTemplate:
    return DemoTemplate(
        template_id="RL-001",
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
    )


def instantiate_rl001(
    *, case_id: str, purpose: CasePurpose, runtime_mode: RuntimeMode
) -> tuple[CaseInstance, OperationalSnapshot]:
    case = CaseInstance(
        case_id=case_id,
        template_id="RL-001",
        purpose=purpose,
        runtime_mode=runtime_mode,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
    )
    return case, OperationalSnapshot.rl001(
        case_id=case_id,
        runtime_mode=runtime_mode,
    )
