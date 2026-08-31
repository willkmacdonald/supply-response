from data.synthetic.rl001 import OperationalSnapshot
from services.analysis.options import (
    calculate_approval_burden,
    calculate_execution_risk,
    evaluate_response_options,
)


EXPECTED = {
    "RL-OPTION-NO-MITIGATION": (False, 6800, 100, "955000", "328000", "0"),
    "RL-OPTION-EXPEDITE": (True, 3800, 100, "955000", "328000", "22500"),
    "RL-OPTION-TRANSFER": (True, 5300, 50, "580000", "203000", "2250"),
    "RL-OPTION-RESEQUENCE": (True, 6800, 100, "955000", "328000", "0"),
    "RL-OPTION-COMBINED": (True, 2300, 50, "375000", "125000", "24750"),
}


def test_rl001_response_options_match_the_frozen_contract():
    options = {
        item.option_id: item
        for item in evaluate_response_options(OperationalSnapshot.rl001())
    }
    assert set(options) == {*EXPECTED, "RL-OPTION-BETA"}
    for option_id, expected in EXPECTED.items():
        item = options[option_id]
        assert (
            item.executable,
            item.predicted.uncovered_part_demand,
            item.predicted.otif_loss_percentage,
            str(item.predicted.revenue_at_risk),
            str(item.predicted.margin_at_risk),
            str(item.predicted.response_cost),
        ) == expected

    beta = options["RL-OPTION-BETA"]
    assert beta.executable is False
    assert beta.blocking_codes == ("QUALITY_QUALIFICATION_PENDING",)
    assert beta.predicted is None


def test_no_mitigation_excludes_the_optional_alpha_receipt():
    baseline = next(
        item
        for item in evaluate_response_options(OperationalSnapshot.rl001())
        if item.option_id == "RL-OPTION-NO-MITIGATION"
    )
    assert "RL-ALPHA-OPTIONAL-3000" not in baseline.source_data_lineage


def test_rl001_options_derive_approval_burden_and_execution_risk():
    options = {
        item.option_id: item
        for item in evaluate_response_options(OperationalSnapshot.rl001())
    }

    assert {
        option_id: (item.prerequisite_roles, item.approval_burden, item.execution_risk)
        for option_id, item in options.items()
    } == {
        "RL-OPTION-NO-MITIGATION": ((), 0, 0),
        "RL-OPTION-EXPEDITE": (("material_planner", "finance_approver"), 2, 2),
        "RL-OPTION-TRANSFER": (("material_planner",), 1, 1),
        "RL-OPTION-RESEQUENCE": (("material_planner",), 1, 1),
        "RL-OPTION-BETA": (("material_planner", "quality_approver"), 2, 2),
        "RL-OPTION-COMBINED": (("material_planner", "finance_approver"), 2, 6),
    }


def test_score_helpers_count_each_policy_factor_without_score_literals():
    assert (
        calculate_approval_burden(
            ("material_planner", "response_approver", "material_planner")
        )
        == 1
    )
    assert (
        calculate_execution_risk(
            unconfirmed_external_commitments=1,
            cross_plant_movements=1,
            schedule_changes=1,
            coordinated_action_count=3,
        )
        == 6
    )
    assert calculate_execution_risk(unconfirmed_external_commitments=1) == 2
    assert calculate_execution_risk(cross_plant_movements=1) == 1
    assert calculate_execution_risk(schedule_changes=1) == 1
    assert calculate_execution_risk(coordinated_action_count=3) == 2
