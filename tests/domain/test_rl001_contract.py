from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

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
    assert template.scenario_effective_time == datetime.fromisoformat(
        "2026-09-01T09:00:00-05:00"
    )
    assert template.scenario_timezone == "America/Chicago"
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
    assert [order.customer_revenue for order in snapshot.production_orders] == [
        Decimal("375000"),
        Decimal("580000"),
    ]
    assert [order.customer_margin for order in snapshot.production_orders] == [
        Decimal("125000"),
        Decimal("203000"),
    ]
    assert snapshot.scenario_timezone == "America/Chicago"
    assert snapshot.analysis_horizon_start == case.scenario_effective_time
    assert snapshot.analysis_horizon_end.isoformat() == "2026-09-08"
    assert snapshot.disruption.partial_quantity == 0
    assert snapshot.disruption.partial_due_date is None
    assert snapshot.disruption.recovery_date is None
    assert snapshot.alpha_expedite.quantity == 3000
    assert snapshot.alpha_expedite.due_date.isoformat() == "2026-09-06"
    assert snapshot.transfer.incremental_cost_per_unit == Decimal("1.50")
    assert snapshot.transfer.quantity == 1500
    assert snapshot.transfer.dispatch_date.isoformat() == "2026-09-04"
    assert snapshot.transfer.arrival_date.isoformat() == "2026-09-05"
    assert snapshot.alpha_expedite.incremental_cost_per_unit == Decimal("7.50")
    assert snapshot.beta_qualification.status.value == "pending"
    assert snapshot.beta_qualification.audit_complete is False
    assert snapshot.beta_qualification.first_article_complete is False
    assert (
        snapshot.model_dump(mode="json")["production_orders"][0]["customer_revenue"]
        == "375000.00"
    )
    assert (
        snapshot.model_dump(mode="json")["transfer"]["incremental_cost_per_unit"]
        == "1.50"
    )


def test_runtime_mode_is_immutable_on_a_case_instance():
    case, _ = instantiate_rl001(
        case_id="RL-CASE-TEST-002",
        purpose=CasePurpose.REHEARSAL,
        runtime_mode=RuntimeMode.LIVE,
    )
    with pytest.raises(ValidationError):
        case.runtime_mode = RuntimeMode.FALLBACK

    with pytest.raises(ValueError, match="different case_id"):
        case.model_copy(update={"runtime_mode": RuntimeMode.FALLBACK})

    with pytest.raises(ValidationError):
        case.model_copy(
            update={
                "case_id": "RL-CASE-TEST-INVALID",
                "runtime_mode": "invalid",
            }
        )

    changed = case.model_copy(
        update={
            "case_id": "RL-CASE-TEST-003",
            "runtime_mode": "fallback",
        }
    )
    assert changed.runtime_mode is RuntimeMode.FALLBACK
    assert case.runtime_mode is RuntimeMode.LIVE
    assert changed.case_id != case.case_id


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

    from data.domain import (
        BomComponent as CanonicalBomComponent,
        CalculationMetadata as CanonicalCalculationMetadata,
        Customer as CanonicalCustomer,
        CustomerOrder as CanonicalCustomerOrder,
        InventoryPosition as CanonicalInventoryPosition,
        Part as CanonicalPart,
        ProductionOrder as CanonicalProductionOrder,
        ProjectionPoint as CanonicalProjectionPoint,
        PurchaseOrder as CanonicalPurchaseOrder,
        QualificationStatus as CanonicalQualificationStatus,
        QualityQualification as CanonicalQualityQualification,
        Supplier as CanonicalSupplier,
        SupplierPart as CanonicalSupplierPart,
        TimedQuantity as CanonicalTimedQuantity,
        TransportOption as CanonicalTransportOption,
    )

    assert (
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
    ) == (
        CanonicalBomComponent,
        CanonicalCalculationMetadata,
        CanonicalCustomer,
        CanonicalCustomerOrder,
        CanonicalInventoryPosition,
        CanonicalPart,
        CanonicalProductionOrder,
        CanonicalProjectionPoint,
        CanonicalPurchaseOrder,
        CanonicalQualificationStatus,
        CanonicalQualityQualification,
        CanonicalSupplier,
        CanonicalSupplierPart,
        CanonicalTimedQuantity,
        CanonicalTransportOption,
    )
