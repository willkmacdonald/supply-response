import type {AnalysisVersion, PredictedOutcome, ResponseOption} from "../types";
import {validMoney} from "./snapshotValidation";

export function validPrediction(value: PredictedOutcome | null | undefined): value is PredictedOutcome {
  return value != null
    && Number.isSafeInteger(value.uncovered_part_demand) && value.uncovered_part_demand >= 0
    && Number.isInteger(value.otif_loss_percentage) && value.otif_loss_percentage >= 0
    && value.otif_loss_percentage <= 100
    && [value.revenue_at_risk, value.margin_at_risk, value.response_cost].every(validMoney)
    && Array.isArray(value.protected_customer_order_ids)
    && value.protected_customer_order_ids.every(id => typeof id === "string");
}

export function recommendedOption(analysis: AnalysisVersion): ResponseOption | null {
  const rankedId = analysis.ranking.recommended_option_id;
  if (!rankedId || !analysis.recommendation || analysis.recommendation.option_id !== rankedId) return null;
  if (analysis.ranking.no_feasible_mitigation || analysis.ranking.infeasible_option_ids.includes(rankedId)) return null;
  const matches = analysis.response_options.filter(option => option.option_id === rankedId);
  if (matches.length !== 1) return null;
  const option = matches[0];
  return option.active_mitigation && option.executable && option.blocking_codes.length === 0
    && validPrediction(option.predicted) ? option : null;
}
