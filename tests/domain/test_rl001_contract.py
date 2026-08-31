from datetime import datetime
from decimal import Decimal

from data.domain import CasePurpose, RuntimeMode
from data.synthetic.rl001 import build_rl001_template, instantiate_rl001


def test_rl001_template_freezes_the_approved_business_facts():
    template = build_rl001_template()
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-TEST-001",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )

    assert template.template_id == "RL-001"
    assert case.scenario_effective_time == datetime.fromisoformat(
        "2026-09-01T09:00:00-05:00"
    )
    assert case.runtime_mode is RuntimeMode.FALLBACK
    assert snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-CHI") == 4000
    assert snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-DAL") == 1500
    assert [order.component_demand for order in snapshot.production_orders] == [
        5000,
        5800,
    ]
    assert [order.customer_priority for order in snapshot.production_orders] == [3, 1]
    assert snapshot.transfer.incremental_cost_per_unit == Decimal("1.50")
    assert snapshot.alpha_expedite.incremental_cost_per_unit == Decimal("7.50")
    assert snapshot.beta_qualification.status.value == "pending"


def test_runtime_mode_is_immutable_on_a_case_instance():
    case, _ = instantiate_rl001(
        case_id="RL-CASE-TEST-002",
        purpose=CasePurpose.REHEARSAL,
        runtime_mode=RuntimeMode.LIVE,
    )
    changed = case.model_copy(update={"runtime_mode": RuntimeMode.FALLBACK})
    assert changed.runtime_mode is RuntimeMode.FALLBACK
    assert case.runtime_mode is RuntimeMode.LIVE
    assert changed.case_id == case.case_id
    # The application service added in Task 5 must reject persisting `changed`.


def test_legacy_schema_path_reexports_operational_and_analysis_contracts():
    from data.schemas.models import (
        BomComponent,
        CalculationMetadata,
        Customer,
        CustomerOrder,
        InventoryPosition,
        Part,
        ProductionOrder,
        ProjectionPoint,
        PurchaseOrder,
        QualificationStatus,
        QualityQualification,
        Supplier,
        SupplierPart,
        TimedQuantity,
        TransportOption,
    )

    assert all(
        item is not None
        for item in (
            BomComponent,
            CalculationMetadata,
            Customer,
            CustomerOrder,
            InventoryPosition,
            Part,
            ProductionOrder,
            ProjectionPoint,
            PurchaseOrder,
            QualificationStatus,
            QualityQualification,
            Supplier,
            SupplierPart,
            TimedQuantity,
            TransportOption,
        )
    )
