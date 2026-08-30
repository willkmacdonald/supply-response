from datetime import date
from decimal import Decimal

from data.schemas.models import Disruption, QualificationStatus, QualityQualification
from services.policy.thresholds import requires_finance_approval
from services.scenarios.evaluator import build_initial_scenarios


def disruption(**overrides):
    values = dict(
        disruption_id="RL-D",
        supplier_id="RL-SUP-ALPHA",
        po_line_id="RL-PO",
        part_id="RL-MAT-10247",
        plant_id="RL-PLANT-CHI",
        original_quantity=8000,
        original_due_date=date(2026, 9, 3),
        partial_quantity=3000,
        partial_due_date=date(2026, 9, 6),
        recovery_date=None,
        source_ref="RL-001",
    )
    values.update(overrides)
    return Disruption(**values)


def qualification(status):
    return QualityQualification(
        qualification_id="RL-Q",
        supplier_id="RL-SUP-BETA",
        part_id="RL-MAT-10247",
        status=status,
        effective_date=date(2026, 9, 1)
        if status == QualificationStatus.APPROVED
        else None,
        evidence_ref="RL-QUALITY-001",
    )


def test_unconfirmed_recovery_date_is_preserved_as_uncertainty():
    scenarios = build_initial_scenarios(
        disruption(), [qualification(QualificationStatus.NOT_APPROVED)]
    )
    assert "unconfirmed" in scenarios[1].remaining_uncertainty[0]


def test_confirmed_recovery_date_removes_that_uncertainty():
    scenarios = build_initial_scenarios(
        disruption(recovery_date=date(2026, 9, 12)),
        [qualification(QualificationStatus.NOT_APPROVED)],
    )
    assert scenarios[1].remaining_uncertainty == ()


def test_partial_shipment_controls_expedite_feasibility():
    assert (
        build_initial_scenarios(
            disruption(partial_quantity=0, partial_due_date=None),
            [qualification(QualificationStatus.NOT_APPROVED)],
        )[1].executable
        is False
    )


def test_alternate_supplier_not_approved_is_not_executable():
    beta = build_initial_scenarios(
        disruption(), [qualification(QualificationStatus.NOT_APPROVED)]
    )[4]
    assert beta.executable is False
    assert "not approved" in beta.constraint_violations[0]


def test_alternate_supplier_approved_is_executable():
    beta = build_initial_scenarios(
        disruption(), [qualification(QualificationStatus.APPROVED)]
    )[4]
    assert beta.executable is True
    assert beta.constraint_violations == ()


def test_premium_freight_above_threshold_requires_approval():
    assert requires_finance_approval(Decimal("22500")) is True
    assert requires_finance_approval(Decimal("20000")) is False


def test_blocked_alternate_supplier_carries_stable_evidence_metadata():
    beta = build_initial_scenarios(
        disruption(), [qualification(QualificationStatus.NOT_APPROVED)]
    )[4]
    assert beta.constraint_codes == ("QUALITY_NOT_APPROVED",)
    assert beta.evidence_refs == ("RL-QUALITY-001",)
    assert beta.required_approver_roles == ("material_planner",)


def test_expedite_above_threshold_names_finance_approver():
    expedite = build_initial_scenarios(
        disruption(), [qualification(QualificationStatus.NOT_APPROVED)]
    )[1]
    assert expedite.response_cost == Decimal("22500.00")
    assert expedite.required_approver_roles == (
        "material_planner",
        "finance_approver",
    )


def test_combined_response_above_threshold_carries_expedite_cost_and_finance_role():
    combined = build_initial_scenarios(
        disruption(), [qualification(QualificationStatus.NOT_APPROVED)]
    )[5]
    assert combined.response_cost == Decimal("22500.00")
    assert combined.required_approver_roles == (
        "material_planner",
        "finance_approver",
    )


def test_combined_response_below_threshold_carries_cost_without_finance_role():
    combined = build_initial_scenarios(
        disruption(partial_quantity=2000),
        [qualification(QualificationStatus.NOT_APPROVED)],
    )[5]
    assert combined.response_cost == Decimal("15000.00")
    assert combined.required_approver_roles == ("material_planner",)
