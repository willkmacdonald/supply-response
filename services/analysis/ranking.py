from dataclasses import dataclass
from decimal import Decimal

from data.domain import ResponseOption
from data.domain.analysis import ComparatorValue, RankingResult, RankingStage


RANKING_POLICY_VERSION = "thresholded-lexicographic-v1"


@dataclass(frozen=True)
class Comparator:
    name: str
    threshold: Decimal
    lower_is_better: bool


COMPARATORS = (
    Comparator("uncovered_part_demand", Decimal("500"), lower_is_better=True),
    Comparator("otif_loss_percentage", Decimal("10"), lower_is_better=True),
    Comparator("revenue_at_risk", Decimal("50000"), lower_is_better=True),
    Comparator("margin_at_risk", Decimal("25000"), lower_is_better=True),
    Comparator("response_cost", Decimal("10000"), lower_is_better=True),
    Comparator("approval_burden", Decimal("0"), lower_is_better=True),
    Comparator("execution_risk", Decimal("0"), lower_is_better=True),
    Comparator("option_id", Decimal("0"), lower_is_better=True),
)


def _numeric_value(option: ResponseOption, comparator: Comparator) -> Decimal:
    if comparator.name in {"approval_burden", "execution_risk"}:
        return Decimal(getattr(option, comparator.name))
    if option.predicted is None:
        raise ValueError(f"Response option {option.option_id} has no predicted outcome")
    return Decimal(getattr(option.predicted, comparator.name))


def rank_options(options: tuple[ResponseOption, ...]) -> RankingResult:
    """Apply hard feasibility, then the frozen thresholded comparator policy."""
    option_ids = tuple(option.option_id for option in options)
    if len(option_ids) != len(set(option_ids)):
        raise ValueError("duplicate response option stable ID")

    excluded_baselines = tuple(
        sorted(option.option_id for option in options if not option.active_mitigation)
    )
    infeasible = tuple(
        sorted(
            option.option_id
            for option in options
            if option.active_mitigation
            and (
                not option.executable
                or option.predicted is None
                or bool(option.blocking_codes)
            )
        )
    )
    remaining = tuple(
        sorted(
            (
                option
                for option in options
                if option.active_mitigation
                and option.executable
                and option.predicted is not None
                and not option.blocking_codes
            ),
            key=lambda option: option.option_id,
        )
    )
    eligible_ids = tuple(option.option_id for option in remaining)
    if not remaining:
        return RankingResult(
            policy_version=RANKING_POLICY_VERSION,
            eligible_option_ids=(),
            infeasible_option_ids=infeasible,
            excluded_baseline_ids=excluded_baselines,
            stages=(),
            recommended_option_id=None,
            no_feasible_mitigation=True,
        )

    stages: list[RankingStage] = []
    for comparator in COMPARATORS:
        input_ids = tuple(option.option_id for option in remaining)
        if comparator.name == "option_id":
            values = tuple(
                ComparatorValue(option_id=option.option_id, value=option.option_id)
                for option in remaining
            )
            retained = (min(remaining, key=lambda option: option.option_id),)
        else:
            numeric_values = tuple(
                (option, _numeric_value(option, comparator)) for option in remaining
            )
            best = min(value for _, value in numeric_values)
            retained = tuple(
                option
                for option, value in numeric_values
                if value <= best + comparator.threshold
            )
            values = tuple(
                ComparatorValue(option_id=option.option_id, value=value)
                for option, value in numeric_values
            )
        retained_ids = tuple(option.option_id for option in retained)
        stages.append(
            RankingStage(
                comparator=comparator.name,
                threshold=comparator.threshold,
                lower_is_better=comparator.lower_is_better,
                input_option_ids=input_ids,
                values=values,
                retained_option_ids=retained_ids,
                eliminated_option_ids=tuple(
                    option_id
                    for option_id in input_ids
                    if option_id not in retained_ids
                ),
            )
        )
        remaining = retained
        if len(remaining) == 1:
            break

    return RankingResult(
        policy_version=RANKING_POLICY_VERSION,
        eligible_option_ids=eligible_ids,
        infeasible_option_ids=infeasible,
        excluded_baseline_ids=excluded_baselines,
        stages=tuple(stages),
        recommended_option_id=remaining[0].option_id,
        no_feasible_mitigation=False,
    )
