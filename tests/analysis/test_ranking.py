from decimal import Decimal

from data.domain import PredictedOutcome, ResponseOption
from data.domain.common import ResponseOptionKind
from data.synthetic.rl001 import OperationalSnapshot
from services.analysis.options import evaluate_response_options
from services.analysis.ranking import COMPARATORS, rank_options


def rl001_options() -> tuple[ResponseOption, ...]:
    return evaluate_response_options(OperationalSnapshot.rl001())


def option_pair(
    *,
    uncovered: tuple[int, int],
    otif: tuple[int, int],
    revenue: tuple[Decimal, Decimal] = (Decimal("200000"), Decimal("100000")),
) -> tuple[ResponseOption, ...]:
    return tuple(
        ResponseOption(
            option_id=option_id,
            option_kind=ResponseOptionKind.RESEQUENCE,
            name=option_id,
            executable=True,
            active_mitigation=True,
            predicted=PredictedOutcome(
                uncovered_part_demand=uncovered[index],
                otif_loss_percentage=otif[index],
                revenue_at_risk=revenue[index],
                margin_at_risk=Decimal("50000"),
                response_cost=Decimal("0"),
            ),
        )
        for index, option_id in enumerate(("RL-A", "RL-B"))
    )


def test_thresholded_lexicographic_ranking_selects_combined():
    result = rank_options(rl001_options())
    assert result.recommended_option_id == "RL-OPTION-COMBINED"
    assert result.policy_version == "thresholded-lexicographic-v1"
    assert result.stages[0].comparator == "uncovered_part_demand"
    assert result.stages[0].threshold == Decimal("500")
    assert result.stages[0].retained_option_ids == ("RL-OPTION-COMBINED",)
    assert "RL-OPTION-BETA" in result.infeasible_option_ids
    assert "RL-OPTION-NO-MITIGATION" in result.excluded_baseline_ids


def test_comparator_policy_names_and_thresholds_are_exact():
    assert tuple((item.name, item.threshold) for item in COMPARATORS) == (
        ("uncovered_part_demand", Decimal("500")),
        ("otif_loss_percentage", Decimal("10")),
        ("revenue_at_risk", Decimal("50000")),
        ("margin_at_risk", Decimal("25000")),
        ("response_cost", Decimal("10000")),
        ("approval_burden", Decimal("0")),
        ("execution_risk", Decimal("0")),
        ("option_id", Decimal("0")),
    )


def test_threshold_keeps_immaterial_difference_for_next_comparator():
    options = option_pair(uncovered=(2300, 2600), otif=(50, 40))
    result = rank_options(options)
    assert result.stages[0].retained_option_ids == ("RL-A", "RL-B")
    assert result.stages[1].comparator == "otif_loss_percentage"
    assert result.stages[1].retained_option_ids == ("RL-A", "RL-B")
    assert result.stages[2].comparator == "revenue_at_risk"
    assert result.recommended_option_id == "RL-B"


def test_ranking_is_input_order_independent_and_records_each_executed_stage():
    tied = option_pair(
        uncovered=(2300, 2600),
        otif=(40, 40),
        revenue=(Decimal("100000"), Decimal("100000")),
    )
    forward = rank_options(tied)
    reverse = rank_options(tuple(reversed(tied)))

    assert reverse == forward
    assert forward.stages[-1].comparator == "option_id"
    assert forward.stages[-1].retained_option_ids == ("RL-A",)
    for stage in forward.stages:
        assert (
            tuple(value.option_id for value in stage.values) == stage.input_option_ids
        )
        assert set(stage.retained_option_ids).isdisjoint(stage.eliminated_option_ids)
        assert set(stage.retained_option_ids) | set(stage.eliminated_option_ids) == set(
            stage.input_option_ids
        )


def test_no_feasible_mitigation_has_no_recommendation_or_stages():
    options = tuple(
        option.model_copy(update={"executable": False})
        for option in option_pair(uncovered=(2300, 2600), otif=(50, 40))
    )

    result = rank_options(options)

    assert result.recommended_option_id is None
    assert result.stages == ()
    assert result.infeasible_option_ids == ("RL-A", "RL-B")


def test_duplicate_option_ids_are_rejected():
    option = option_pair(uncovered=(2300, 2600), otif=(50, 40))[0]

    try:
        rank_options((option, option))
    except ValueError as error:
        assert str(error) == "duplicate response option stable ID"
    else:
        raise AssertionError("duplicate response option IDs must be rejected")
