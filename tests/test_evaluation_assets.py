import json
from pathlib import Path

from data.schemas.models import TimedQuantity
from data.synthetic.generator import generate_dataset
from services.exposure.calculator import calculate_exposure


ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "Supply-Response-Project-Brief.md"
EVALUATION_CASES = ROOT / "evaluations/datasets/evaluation_cases.json"
EXPECTED_RL_001 = ROOT / "evaluations/expected-results/rl-001.json"


def test_project_brief_preserves_core_requirements():
    text = BRIEF.read_text(encoding="utf-8")
    assert "## Acceptance criteria" in text
    assert "## Evaluation cases" in text
    assert "Scenario 5 must be marked **not executable**" in text
    assert "The prototype must not create a real PO or financial commitment." in text


def test_evaluation_catalog_is_complete_and_linked_to_tests():
    payload = json.loads(EVALUATION_CASES.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert payload["version"] == "1.0.0"
    assert [case["id"] for case in cases] == [
        f"RL-EVAL-{index:03d}" for index in range(1, 11)
    ]

    required_keys = {"id", "name", "input", "expected", "test"}
    for case in cases:
        assert set(case) == required_keys
        test_path, test_name = case["test"].split("::", maxsplit=1)
        source = (ROOT / test_path).read_text(encoding="utf-8")
        assert f"def {test_name}(" in source, case["id"]


def _baseline_result() -> dict[str, object]:
    dataset = generate_dataset(seed=42)
    disruption = dataset.disruptions[0]
    receipts = [
        TimedQuantity(
            date=disruption.partial_due_date,
            quantity=disruption.partial_quantity,
            source_id=disruption.source_ref,
        )
    ]
    exposure = calculate_exposure(
        scenario_id="RL-SCENARIO-BASELINE",
        part_id=disruption.part_id,
        plant_id=disruption.plant_id,
        inventory_positions=dataset.inventory_positions,
        receipts=receipts,
        transfers=[],
        bom_components=dataset.bom_components,
        production_orders=dataset.production_orders,
        customer_orders=dataset.customer_orders,
        assumptions=("Only confirmed receipts are included",),
        remaining_uncertainty=("Remaining supplier recovery date is unconfirmed",),
    )
    return {
        "disruption_id": disruption.disruption_id,
        "plant_id": disruption.plant_id,
        "calculation_version": exposure.metadata.calculation_version,
        "usable_inventory": exposure.usable_inventory,
        "projected_balances": [
            {
                "date": point.date.isoformat(),
                "balance": point.projected_balance,
            }
            for point in exposure.projected_inventory
        ],
        "first_stockout_date": exposure.first_stockout_date.isoformat()
        if exposure.first_stockout_date
        else None,
        "maximum_shortage_quantity": exposure.maximum_shortage_quantity,
        "affected_production_order_ids": list(exposure.affected_production_order_ids),
        "affected_customer_order_line_ids": list(
            exposure.affected_customer_order_line_ids
        ),
        "revenue_at_risk": str(exposure.revenue_at_risk),
        "margin_at_risk": str(exposure.margin_at_risk),
        "otif_lines_at_risk": exposure.otif_lines_at_risk,
        "response_cost": str(exposure.response_cost),
        "revenue_protected": str(exposure.revenue_protected),
        "remaining_uncertainty": list(exposure.remaining_uncertainty),
        "source_data_lineage": list(exposure.metadata.source_data_lineage),
    }


def test_rl_001_matches_exact_2026_baseline():
    expected = json.loads(EXPECTED_RL_001.read_text(encoding="utf-8"))
    assert _baseline_result() == expected
