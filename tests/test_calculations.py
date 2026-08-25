"""Deterministic calculation tests.

These cover the core formulas from the project brief and the evaluation cases
listed in the acceptance criteria.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from data.fixtures.demo import (
    ALTERNATE_PLANT_ID,
    DEMO_DISRUPTION_ID,
    DEMO_PART_ID,
    DEMO_PLANT_ID,
    HORIZON_END,
    HORIZON_START,
    QUALITY_CONSTRAINT_ID,
    SUPPLIER_ALPHA_ID,
    SUPPLIER_BETA_ID,
    demo_dataset,
)
from data.schemas.models import (
    InventoryPosition,
    POStatus,
    ProductionOrderStatus,
    PurchaseOrder,
    ScenarioType,
)
from services.exposure.calculator import (
    CALCULATION_VERSION,
    DemandEvent,
    SupplyEvent,
    Transfer,
    component_demand,
    confirmed_receipts,
    first_stockout_date,
    max_shortage_qty,
    project_balance,
    response_cost,
    revenue_protected,
    total_usable_inventory,
    usable_inventory,
)
from services.policy.checker import (
    PREMIUM_FREIGHT_APPROVAL_THRESHOLD,
    check_spend_approval,
    check_supplier_qualification,
)
from services.scenarios.evaluator import (
    EvaluationContext,
    calculate_baseline,
    evaluate_scenarios,
)

CALCULATED_AT = datetime(2025, 9, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def dataset():
    return demo_dataset()


@pytest.fixture(scope="module")
def context(dataset) -> EvaluationContext:
    return EvaluationContext(
        disruption=dataset.disruptions[0],
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        inventory_positions=dataset.inventory_positions,
        purchase_orders=dataset.purchase_orders,
        production_orders=dataset.production_orders,
        bom_components=dataset.bom_components,
        customer_orders=dataset.customer_orders,
        customers=dataset.customers,
        transport_options=dataset.transport_options,
        quality_qualifications=dataset.quality_qualifications,
    )


@pytest.fixture(scope="module")
def baseline(context):
    return calculate_baseline(context, CALCULATED_AT)


@pytest.fixture(scope="module")
def evaluations(context):
    return evaluate_scenarios(demo_dataset().response_scenarios, context, CALCULATED_AT)


# --------------------------------------------------------------------------- #
# usable inventory
# --------------------------------------------------------------------------- #
def test_usable_inventory_formula():
    position = InventoryPosition(
        inventory_id="RL-INV-999999",
        part_id=DEMO_PART_ID,
        plant_id=DEMO_PLANT_ID,
        location_id="RL-LOC-9999",
        on_hand=5200,
        quality_hold=400,
        protected_allocation=800,
        as_of_date=HORIZON_START,
    )
    assert usable_inventory(position) == 4000


def test_usable_inventory_never_negative():
    position = InventoryPosition(
        inventory_id="RL-INV-999998",
        part_id=DEMO_PART_ID,
        plant_id=DEMO_PLANT_ID,
        location_id="RL-LOC-9998",
        on_hand=100,
        quality_hold=80,
        protected_allocation=90,
        as_of_date=HORIZON_START,
    )
    assert usable_inventory(position) == 0


def test_total_usable_inventory_by_plant(dataset):
    assert total_usable_inventory(dataset.inventory_positions, DEMO_PART_ID, DEMO_PLANT_ID) == 4000
    assert (
        total_usable_inventory(dataset.inventory_positions, DEMO_PART_ID, ALTERNATE_PLANT_ID)
        == 2500
    )


# --------------------------------------------------------------------------- #
# projected balance
# --------------------------------------------------------------------------- #
def test_project_balance_formula():
    rows = project_balance(
        opening_balance=100,
        receipts=[SupplyEvent(date=date(2025, 9, 2), quantity=50, source_type="purchase_order", source_id="RL-PO-000001:1")],
        transfers=[Transfer(part_id=DEMO_PART_ID, to_plant_id=DEMO_PLANT_ID, quantity=25, available_date=date(2025, 9, 3))],
        demand=[
            DemandEvent(date=date(2025, 9, 1), quantity=40, production_order_id="RL-PRD-000001", part_id=DEMO_PART_ID, plant_id=DEMO_PLANT_ID),
            DemandEvent(date=date(2025, 9, 3), quantity=200, production_order_id="RL-PRD-000002", part_id=DEMO_PART_ID, plant_id=DEMO_PLANT_ID),
        ],
        horizon_start=date(2025, 9, 1),
        horizon_end=date(2025, 9, 4),
    )
    assert [row.projected_balance for row in rows] == [60, 110, -65, -65]
    assert [row.shortage for row in rows] == [0, 0, 65, 65]
    assert first_stockout_date(rows) == date(2025, 9, 3)
    assert max_shortage_qty(rows) == 65


def test_project_balance_rejects_inverted_horizon():
    with pytest.raises(ValueError):
        project_balance(0, [], [], [], date(2025, 9, 10), date(2025, 9, 1))


def test_no_stockout_returns_none():
    rows = project_balance(500, [], [], [], HORIZON_START, HORIZON_START)
    assert first_stockout_date(rows) is None
    assert max_shortage_qty(rows) == 0


# --------------------------------------------------------------------------- #
# receipts and demand
# --------------------------------------------------------------------------- #
def test_delayed_po_without_revised_date_is_not_counted(dataset):
    receipts = confirmed_receipts(
        dataset.purchase_orders, DEMO_PART_ID, DEMO_PLANT_ID, HORIZON_START, HORIZON_END
    )
    assert [event.source_id for event in receipts] == ["RL-PO-000102:1"]
    assert receipts[0].quantity == 2000
    assert receipts[0].date == date(2025, 9, 18)


def test_confirmed_recovery_date_is_counted(dataset):
    """Evaluation case: confirmed supplier recovery date."""
    delayed = dataset.purchase_orders[0].model_copy(
        update={"revised_date": date(2025, 9, 12), "status": POStatus.DELAYED}
    )
    receipts = confirmed_receipts(
        [delayed], DEMO_PART_ID, DEMO_PLANT_ID, HORIZON_START, HORIZON_END
    )
    assert len(receipts) == 1
    assert receipts[0].date == date(2025, 9, 12)
    assert receipts[0].quantity == 8000


def test_component_demand_explodes_bom(dataset):
    demand = component_demand(
        dataset.production_orders,
        dataset.bom_components,
        DEMO_PART_ID,
        DEMO_PLANT_ID,
        HORIZON_START,
        HORIZON_END,
    )
    assert [event.quantity for event in demand] == [3000, 2400, 2000, 1800, 1600]
    assert sum(event.quantity for event in demand) == 10800


def test_component_demand_applies_scrap_factor(dataset):
    scrapped = [
        dataset.bom_components[0].model_copy(update={"scrap_factor": 0.05})
    ]
    demand = component_demand(
        dataset.production_orders[:1],
        scrapped,
        DEMO_PART_ID,
        DEMO_PLANT_ID,
        HORIZON_START,
        HORIZON_END,
    )
    assert demand[0].quantity == 3158  # ceil(1500 * 2 / 0.95)


def test_closed_production_orders_are_ignored(dataset):
    closed = [
        order.model_copy(update={"status": ProductionOrderStatus.COMPLETE})
        for order in dataset.production_orders
    ]
    demand = component_demand(
        closed, dataset.bom_components, DEMO_PART_ID, DEMO_PLANT_ID, HORIZON_START, HORIZON_END
    )
    assert demand == []


# --------------------------------------------------------------------------- #
# baseline exposure for RL-001
# --------------------------------------------------------------------------- #
def test_baseline_exposure_is_reproducible(context, baseline):
    repeat = calculate_baseline(context, CALCULATED_AT)
    assert repeat.model_dump() == baseline.model_dump()


def test_baseline_exposure_numbers(baseline):
    assert baseline.calculation_version == CALCULATION_VERSION
    assert baseline.usable_inventory == 4000
    assert baseline.first_stockout_date == date(2025, 9, 5)
    assert baseline.max_shortage_qty == 6800
    assert baseline.total_shortage_qty == 6800
    assert [o.production_order_id for o in baseline.affected_production_orders] == [
        "RL-PRD-000102",
        "RL-PRD-000103",
        "RL-PRD-000104",
        "RL-PRD-000105",
    ]
    assert baseline.revenue_at_risk == 1_071_000.0
    assert baseline.margin_at_risk == 408_000.0
    assert baseline.otif_lines_at_risk == 4


def test_baseline_lineage_and_uncertainty(baseline):
    assert baseline.lineage["purchase_orders"] == ["RL-PO-000102:1"]
    assert "RL-INV-000101" in baseline.lineage["inventory_positions"]
    assert baseline.open_questions  # unconfirmed recovery date
    assert baseline.assumptions


def test_inventory_at_another_plant_removes_the_stockout(context):
    """Evaluation case: inventory available at another plant."""
    from services.exposure.calculator import calculate_exposure

    result = calculate_exposure(
        scenario_id="RL-SCN-TEST",
        part_id=DEMO_PART_ID,
        plant_id=DEMO_PLANT_ID,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        inventory_positions=context.inventory_positions,
        purchase_orders=context.purchase_orders,
        production_orders=context.production_orders,
        bom_components=context.bom_components,
        customer_orders=context.customer_orders,
        transfers=[
            Transfer(
                part_id=DEMO_PART_ID,
                to_plant_id=DEMO_PLANT_ID,
                from_plant_id=ALTERNATE_PLANT_ID,
                quantity=9000,
                available_date=date(2025, 9, 3),
            )
        ],
        calculated_at=CALCULATED_AT,
    )
    assert result.first_stockout_date is None
    assert result.affected_production_orders == []
    assert result.revenue_at_risk == 0.0


# --------------------------------------------------------------------------- #
# cost helpers
# --------------------------------------------------------------------------- #
def test_response_cost_components():
    assert response_cost(
        expedite_qty=3000, expedite_cost_per_unit=8.0, expedite_fixed_cost=4000.0
    ) == 28_000.0
    assert response_cost(
        transfer_qty=2500, transfer_cost_per_unit=1.2, transfer_fixed_cost=1800.0
    ) == 4_800.0
    assert response_cost() == 0.0


def test_revenue_protected_is_never_negative():
    assert revenue_protected(1_000_000.0, 400_000.0) == 600_000.0
    assert revenue_protected(100.0, 500.0) == 0.0


# --------------------------------------------------------------------------- #
# policy
# --------------------------------------------------------------------------- #
def test_supplier_beta_is_not_approved(dataset):
    """Evaluation case: alternate supplier not approved."""
    decision = check_supplier_qualification(
        dataset.quality_qualifications, SUPPLIER_BETA_ID, DEMO_PART_ID
    )
    assert decision.executable is False
    assert QUALITY_CONSTRAINT_ID in decision.blocking_constraint
    assert decision.violations[0].expected_resolution_date == date(2025, 9, 15)


def test_supplier_alpha_is_approved(dataset):
    """Evaluation case: alternate supplier approved."""
    decision = check_supplier_qualification(
        dataset.quality_qualifications, SUPPLIER_ALPHA_ID, DEMO_PART_ID
    )
    assert decision.executable is True
    assert decision.blocking_constraint is None


def test_missing_qualification_record_blocks(dataset):
    """Evaluation case: missing or stale collaboration evidence."""
    decision = check_supplier_qualification(
        dataset.quality_qualifications, "RL-SUP-0049", DEMO_PART_ID
    )
    assert decision.executable is False
    assert decision.violations[0].code == "QUALITY_NO_RECORD"


def test_premium_freight_above_threshold_requires_finance():
    """Evaluation case: premium freight above approval threshold."""
    decision = check_spend_approval(
        cost=28_000.0, premium_freight_cost=PREMIUM_FREIGHT_APPROVAL_THRESHOLD + 3_000.0
    )
    assert decision.requires_approval is True
    assert "finance_approver" in decision.approver_roles


def test_small_spend_requires_planner_only():
    decision = check_spend_approval(cost=4_800.0, premium_freight_cost=0.0)
    assert decision.approver_roles == ["material_planner"]


# --------------------------------------------------------------------------- #
# scenario evaluation
# --------------------------------------------------------------------------- #
def test_six_scenarios_are_evaluated(evaluations):
    assert len(evaluations) == 6
    assert {e.scenario_id for e in evaluations} == {
        f"RL-SCN-{i:03d}" for i in range(1, 7)
    }


def test_beta_scenario_is_not_executable_and_ranked_last(evaluations):
    beta = next(e for e in evaluations if e.scenario_id == "RL-SCN-005")
    assert beta.executable is False
    assert QUALITY_CONSTRAINT_ID in beta.blocking_constraint
    assert beta.rank == len(evaluations)
    assert beta.recommended is False
    assert beta.conditional is True


def test_at_least_three_executable_scenarios(evaluations):
    """Acceptance criterion 6."""
    executable = [e for e in evaluations if e.executable]
    assert len(executable) >= 3


def test_combined_scenario_is_recommended(evaluations):
    top = evaluations[0]
    assert top.scenario_id == "RL-SCN-006"
    assert top.scenario_type == ScenarioType.COMBINED
    assert top.recommended is True
    assert top.response_cost == 35_800.0
    assert top.revenue_protected == 777_000.0
    assert top.otif_lines_at_risk == 2


def test_expedite_scenario_numbers(evaluations):
    """Evaluation case: partial shipment."""
    expedite = next(e for e in evaluations if e.scenario_id == "RL-SCN-002")
    assert expedite.executable is True
    assert expedite.response_cost == 28_000.0
    assert expedite.revenue_protected == 273_000.0
    assert "finance_approver" in expedite.approver_roles


def test_transfer_scenario_numbers(evaluations):
    transfer = next(e for e in evaluations if e.scenario_id == "RL-SCN-003")
    assert transfer.response_cost == 4_800.0
    assert transfer.revenue_protected == 168_000.0
    assert transfer.first_stockout_date == date(2025, 9, 5)


def test_accept_delay_protects_no_revenue(evaluations, baseline):
    """Evaluation case: no feasible mitigation / do nothing."""
    accept = next(e for e in evaluations if e.scenario_id == "RL-SCN-001")
    assert accept.revenue_protected == 0.0
    assert accept.revenue_at_risk == baseline.revenue_at_risk
    assert accept.response_cost == 17_000.0


def test_ranking_is_deterministic(context):
    first = evaluate_scenarios(demo_dataset().response_scenarios, context, CALCULATED_AT)
    second = evaluate_scenarios(demo_dataset().response_scenarios, context, CALCULATED_AT)
    assert [e.scenario_id for e in first] == [e.scenario_id for e in second]
    assert [e.score for e in first] == [e.score for e in second]


def test_every_evaluation_carries_lineage(evaluations):
    """Acceptance criterion 7: evidence and assumptions on every recommendation."""
    for evaluation in evaluations:
        assert evaluation.scenario_id
        assert evaluation.calculation_version == CALCULATION_VERSION
        assert evaluation.evaluated_at == CALCULATED_AT
        assert evaluation.assumptions
        assert evaluation.evidence
        assert evaluation.exposure is not None
        assert evaluation.exposure.lineage


def test_conflicting_email_and_erp_dates_prefers_erp_revision(dataset):
    """Evaluation case: conflicting email and ERP dates.

    The ERP revised date is a commitment; it is used and the conflict is
    surfaced rather than silently resolved.
    """
    erp_revised = PurchaseOrder(
        po_id="RL-PO-000101",
        po_line=1,
        supplier_id=SUPPLIER_ALPHA_ID,
        part_id=DEMO_PART_ID,
        plant_id=DEMO_PLANT_ID,
        order_qty=8000,
        promised_date=date(2025, 9, 3),
        revised_date=date(2025, 9, 20),
        status=POStatus.DELAYED,
        unit_price=18.40,
    )
    receipts = confirmed_receipts(
        [erp_revised], DEMO_PART_ID, DEMO_PLANT_ID, HORIZON_START, HORIZON_END
    )
    assert receipts[0].date == date(2025, 9, 20)
    assert erp_revised.effective_date == date(2025, 9, 20)
    assert erp_revised.open_qty == 8000


def test_demo_disruption_identifiers(dataset):
    disruption = dataset.disruptions[0]
    assert disruption.disruption_id == DEMO_DISRUPTION_ID
    assert disruption.delayed_qty == 8000
    assert disruption.partial_qty == 3000
    assert disruption.partial_date == date(2025, 9, 6)
    assert disruption.recovery_date_confirmed is False
