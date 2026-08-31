import json
from datetime import timedelta
from pathlib import Path

from data.domain import CasePurpose, RuntimeMode
from data.domain.common import serialize_money
from data.domain.decisions import CorpusScope
from data.synthetic.rl001 import OperationalSnapshot, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case


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
        test_path, node_id = case["test"].split("::", maxsplit=1)
        test_name = node_id.split("[", maxsplit=1)[0]
        source = (ROOT / test_path).read_text(encoding="utf-8")
        assert f"def {test_name}(" in source, case["id"]
        if "[" in node_id:
            assert node_id.endswith(f"[{case['id']}]")


def _canonical_no_mitigation_result() -> dict[str, object]:
    snapshot = OperationalSnapshot.rl001()
    projected_balance = snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-CHI")
    projected_balances = []
    for order in snapshot.production_orders:
        projected_balance -= order.component_demand
        projected_balances.append(
            {"date": order.due_date.isoformat(), "balance": projected_balance}
        )

    revenue_at_risk = sum(
        order.customer_revenue for order in snapshot.production_orders
    )
    margin_at_risk = sum(order.customer_margin for order in snapshot.production_orders)
    return {
        "disruption_id": snapshot.disruption.disruption_id,
        "plant_id": snapshot.disruption.plant_id,
        "calculation_version": "rl001-no-mitigation-v1",
        "usable_inventory": snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-CHI"),
        "projected_balances": projected_balances,
        "first_stockout_date": "2026-09-05",
        "maximum_shortage_quantity": abs(projected_balance),
        "affected_production_order_ids": [
            order.production_order_id for order in snapshot.production_orders
        ],
        "affected_customer_order_line_ids": [
            order.customer_order_id for order in snapshot.production_orders
        ],
        "revenue_at_risk": serialize_money(revenue_at_risk),
        "margin_at_risk": serialize_money(margin_at_risk),
        "otif_lines_at_risk": len(snapshot.production_orders),
        "response_cost": serialize_money(0),
        "revenue_protected": serialize_money(0),
        "remaining_uncertainty": ["Remaining supplier recovery date is unconfirmed"],
        "source_data_lineage": [
            "RL-001",
            "RL-INV-DEMO-CHI",
            "RL-MO-DEMO-1",
            "RL-MO-DEMO-2",
        ],
    }


def test_rl_001_matches_the_frozen_no_mitigation_baseline():
    expected = json.loads(EXPECTED_RL_001.read_text(encoding="utf-8"))
    baseline = _canonical_no_mitigation_result()
    assert {key: expected[key] for key in baseline} == baseline


def test_rl_001_expected_result_freezes_real_options_and_ranking():
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-1",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    analysis = analyze_case(
        AnalyzeCaseCommand(
            analysis_id="RL-ANALYSIS-RL-001",
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            analysis_started_at=case.scenario_effective_time,
            created_at=case.scenario_effective_time + timedelta(minutes=2),
            calculation_version="rl001-options-v1",
        )
    )
    expected = json.loads(EXPECTED_RL_001.read_text(encoding="utf-8"))
    actual_options = {
        option.option_id: {
            "executable": option.executable,
            "blocking_codes": list(option.blocking_codes),
            "approval_burden": option.approval_burden,
            "execution_risk": option.execution_risk,
            "predicted": (
                option.predicted.model_dump(mode="json")
                if option.predicted is not None
                else None
            ),
        }
        for option in analysis.response_options
    }

    assert expected["response_options"] == actual_options
    assert expected["ranking"] == analysis.ranking.model_dump(mode="json")
