"""Golden-file regression test for the RL-001 evaluation case.

``evaluations/expected-results/rl-001.json`` is the committed expected output of
the deterministic services. If a calculation changes, this test fails and the
golden file must be reviewed and updated deliberately.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data.fixtures.demo import (
    DEMO_DISRUPTION_ID,
    HORIZON_END,
    HORIZON_START,
    demo_dataset,
)
from services.scenarios.evaluator import (
    EvaluationContext,
    calculate_baseline,
    evaluate_scenarios,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PATH = REPO_ROOT / "evaluations" / "expected-results" / "rl-001.json"
CASES_PATH = REPO_ROOT / "evaluations" / "datasets" / "evaluation_cases.json"
CALCULATED_AT = datetime(2025, 9, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def expected() -> dict:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def actual():
    dataset = demo_dataset()
    context = EvaluationContext(
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
    baseline = calculate_baseline(context, CALCULATED_AT)
    evaluations = evaluate_scenarios(
        dataset.response_scenarios, context, CALCULATED_AT
    )
    return baseline, evaluations


def test_baseline_matches_expected_results(expected, actual):
    baseline, _ = actual
    want = expected["baseline"]
    assert baseline.usable_inventory == want["usable_inventory"]
    assert baseline.first_stockout_date.isoformat() == want["first_stockout_date"]
    assert baseline.max_shortage_qty == want["max_shortage_qty"]
    assert baseline.total_shortage_qty == want["total_shortage_qty"]
    assert baseline.revenue_at_risk == want["revenue_at_risk"]
    assert baseline.margin_at_risk == want["margin_at_risk"]
    assert baseline.otif_lines_at_risk == want["otif_lines_at_risk"]
    assert [
        order.production_order_id for order in baseline.affected_production_orders
    ] == want["affected_production_orders"]
    assert [
        order.customer_order_id for order in baseline.affected_customer_orders
    ] == want["affected_customer_orders"]


def test_scenarios_match_expected_results(expected, actual):
    _, evaluations = actual
    assert len(evaluations) == len(expected["scenarios"])
    for evaluation, want in zip(evaluations, expected["scenarios"]):
        assert evaluation.scenario_id == want["scenario_id"]
        assert evaluation.rank == want["rank"]
        assert evaluation.executable == want["executable"]
        assert evaluation.recommended == want["recommended"]
        assert evaluation.response_cost == want["response_cost"]
        assert evaluation.revenue_protected == want["revenue_protected"]
        assert evaluation.revenue_at_risk == want["revenue_at_risk"]
        assert evaluation.otif_lines_at_risk == want["otif_lines_at_risk"]
        assert evaluation.max_shortage_qty == want["max_shortage_qty"]
        assert evaluation.approver_roles == want["approver_roles"]
        if want["blocking_constraint"] is None:
            assert evaluation.blocking_constraint is None
        else:
            assert evaluation.blocking_constraint == want["blocking_constraint"]


def test_every_documented_evaluation_case_has_a_test():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 10
    for case in cases:
        module, _, test_name = case["test"].partition("::")
        source = (REPO_ROOT / module).read_text(encoding="utf-8")
        assert f"def {test_name}(" in source, case["id"]


def test_generated_dataset_reproduces_the_demo_results(expected):
    """The RL-001 case must be identical in the fixtures and in a full dataset."""
    from data.synthetic.generator import generate_dataset

    dataset = generate_dataset(42)
    context = EvaluationContext(
        disruption=next(
            d for d in dataset.disruptions if d.disruption_id == DEMO_DISRUPTION_ID
        ),
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
    baseline = calculate_baseline(context, CALCULATED_AT)
    assert baseline.revenue_at_risk == expected["baseline"]["revenue_at_risk"]
    assert baseline.max_shortage_qty == expected["baseline"]["max_shortage_qty"]

    scenarios = [
        s for s in dataset.response_scenarios if s.disruption_id == DEMO_DISRUPTION_ID
    ]
    evaluations = evaluate_scenarios(scenarios, context, CALCULATED_AT)
    assert [e.scenario_id for e in evaluations] == [
        s["scenario_id"] for s in expected["scenarios"]
    ]
    for evaluation, want in zip(evaluations, expected["scenarios"]):
        assert evaluation.response_cost == want["response_cost"]
        assert evaluation.revenue_protected == want["revenue_protected"]
