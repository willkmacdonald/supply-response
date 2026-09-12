import type {PredictedOutcome, ResponseOption} from "../types";
import {number, wholeUsd} from "./plannerFormatting";
import {customerLineBasis, type PlannerSnapshot} from "./plannerSnapshot";
import {PredictionSummary} from "./PredictionSummary";
import {validMoney} from "./snapshotValidation";

function validPrediction(value: PredictedOutcome | null | undefined): value is PredictedOutcome {
  return value != null
    && Number.isSafeInteger(value.uncovered_part_demand) && value.uncovered_part_demand >= 0
    && Number.isInteger(value.otif_loss_percentage) && value.otif_loss_percentage >= 0
    && value.otif_loss_percentage <= 100
    && [value.revenue_at_risk, value.margin_at_risk, value.response_cost].every(validMoney)
    && Array.isArray(value.protected_customer_order_ids)
    && value.protected_customer_order_ids.every(id => typeof id === "string");
}

function sameMoney(left: string, right: string) {
  return BigInt(left.replace(".", "")) === BigInt(right.replace(".", ""));
}

function sameShownValues(left: PredictedOutcome, right: PredictedOutcome) {
  return left.uncovered_part_demand === right.uncovered_part_demand
    && left.otif_loss_percentage === right.otif_loss_percentage
    && sameMoney(left.revenue_at_risk, right.revenue_at_risk)
    && sameMoney(left.margin_at_risk, right.margin_at_risk)
    && sameMoney(left.response_cost, right.response_cost);
}

function lineBasis(predicted: PredictedOutcome, snapshot: PlannerSnapshot | null) {
  const basis = customerLineBasis(snapshot, predicted.protected_customer_order_ids);
  return basis && Math.floor(100 * basis.missed / basis.total) === predicted.otif_loss_percentage
    ? basis : null;
}

const unchanged = (same: boolean) => same ? " (unchanged)" : "";

export function PredictionComparison({recommended, options, snapshot}: {
  recommended: ResponseOption;
  options: ResponseOption[];
  snapshot: PlannerSnapshot | null;
}) {
  const baselines = options.filter(option => option.option_kind === "no_mitigation");
  let unavailable: string | null = null;
  if (baselines.length === 0) unavailable = "Do-nothing comparison unavailable: no baseline option is recorded.";
  else if (baselines.length > 1) unavailable = "Do-nothing comparison unavailable: more than one baseline option is recorded.";
  else if (!validPrediction(baselines[0].predicted)) unavailable = "Do-nothing comparison unavailable: the baseline prediction is missing or invalid.";
  else if (!validPrediction(recommended.predicted)) unavailable = "Comparison unavailable: the recommended prediction is missing or invalid.";
  const baseline = baselines.length === 1 && validPrediction(baselines[0].predicted)
    ? baselines[0].predicted : null;
  const prediction = validPrediction(recommended.predicted) ? recommended.predicted : null;
  const baselineLines = baseline ? lineBasis(baseline, snapshot) : null;
  const recommendedLines = prediction ? lineBasis(prediction, snapshot) : null;
  const customerLines = baselineLines && recommendedLines && baselineLines.total === recommendedLines.total
    ? {baseline: baselineLines, recommended: recommendedLines} : null;
  const part = snapshot?.disruption?.part_id;
  return <div role="group" aria-labelledby="recommended-comparison-heading">
    <h4 id="recommended-comparison-heading">Compared with doing nothing</h4>
    {unavailable ? <><p>{unavailable}</p>
      <PredictionSummary predicted={recommended.predicted} snapshot={snapshot} basis="response" />
    </> : baseline && prediction && <>
      {sameShownValues(baseline, prediction)
        ? <p>The values shown here are unchanged from doing nothing; no benefit is shown in these measures.</p>
        : <p>Doing nothing → taking this response. These results are predictions.</p>}
      <dl className="compact-list">
        <div><dt>Parts still needed</dt><dd>{number(baseline.uncovered_part_demand)} → {number(prediction.uncovered_part_demand)} {part ? `${part} component units` : "component units (part unavailable)"}{unchanged(baseline.uncovered_part_demand === prediction.uncovered_part_demand)}</dd></div>
        <div><dt>{customerLines ? "Customer order lines expected to miss the on-time, in-full target" : "Production orders expected to miss the on-time, in-full target"}</dt><dd>
          {customerLines ? `${baseline.otif_loss_percentage}% (${customerLines.baseline.missed} of ${customerLines.baseline.total} lines)` : `${baseline.otif_loss_percentage}%`}
          {" → "}
          {customerLines ? `${prediction.otif_loss_percentage}% (${customerLines.recommended.missed} of ${customerLines.recommended.total} lines)` : `${prediction.otif_loss_percentage}%`}
          {unchanged(baseline.otif_loss_percentage === prediction.otif_loss_percentage)}
        </dd></div>
        <div><dt>Revenue at risk</dt><dd>{wholeUsd(baseline.revenue_at_risk)} → {wholeUsd(prediction.revenue_at_risk)}{unchanged(sameMoney(baseline.revenue_at_risk, prediction.revenue_at_risk))}</dd></div>
        <div><dt>Margin at risk</dt><dd>{wholeUsd(baseline.margin_at_risk)} → {wholeUsd(prediction.margin_at_risk)}{unchanged(sameMoney(baseline.margin_at_risk, prediction.margin_at_risk))}</dd></div>
        <div><dt>Response cost</dt><dd>{wholeUsd(baseline.response_cost)} → {wholeUsd(prediction.response_cost)}{unchanged(sameMoney(baseline.response_cost, prediction.response_cost))}</dd></div>
      </dl>
      <p>{customerLines
        ? "Revenue at risk is the value of customer order lines expected to miss the service target."
        : "Customer-order-line interpretation unavailable. Revenue and service exposure retain the production-order calculation basis."}</p>
    </>}
  </div>;
}
