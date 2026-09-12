import type {PredictedOutcome} from "../types";
import {customerLineBasis, type PlannerSnapshot} from "./plannerSnapshot";
import {validMoney} from "./snapshotValidation";
import {number, wholeUsd} from "./plannerFormatting";

export function PredictionSummary({predicted: p, snapshot, basis, compact = false}: {
  predicted: PredictedOutcome | null; snapshot: PlannerSnapshot | null; basis: "baseline" | "response"; compact?: boolean;
}) {
  const valid = p && Number.isSafeInteger(p.uncovered_part_demand) && p.uncovered_part_demand >= 0
    && Number.isInteger(p.otif_loss_percentage) && p.otif_loss_percentage >= 0 && p.otif_loss_percentage <= 100
    && [p.revenue_at_risk, p.margin_at_risk, p.response_cost].every(validMoney)
    && Array.isArray(p.protected_customer_order_ids) && p.protected_customer_order_ids.every(id => typeof id === "string");
  const lineBasis = valid && p ? customerLineBasis(snapshot, p.protected_customer_order_ids) : null;
  const consistent = lineBasis && p && Math.floor(100 * lineBasis.missed / lineBasis.total) === p.otif_loss_percentage
    ? lineBasis : null;
  const part = snapshot?.disruption?.part_id;
  return <div className="prediction-summary">
    <p>{basis === "baseline" ? "Expected if we do nothing — baseline" : "Expected if we take this option"}</p>
    {!valid || !p ? <p>Prediction unavailable for this analysis</p> : <>
      <dl className="compact-list">
        <div><dt>Parts still needed</dt><dd>{number(p.uncovered_part_demand)} {part ? `${part} component units` : "component units (part unavailable)"}</dd></div>
        <div><dt>{consistent ? "Customer order lines expected to miss the on-time, in-full target"
          : "Production orders expected to miss the on-time, in-full target"}</dt><dd>{p.otif_loss_percentage}%{consistent && ` (${consistent.missed} of ${consistent.total} lines)`}</dd></div>
        {!compact && <><div><dt>Revenue at risk</dt><dd>{wholeUsd(p.revenue_at_risk)}</dd></div>
          <div><dt>Margin at risk</dt><dd>{wholeUsd(p.margin_at_risk)}</dd></div></>}
        <div><dt>Response cost</dt><dd>{wholeUsd(p.response_cost)}</dd></div>
      </dl>
      {!compact && <p>{consistent ? "Revenue at risk is the value of customer order lines expected to miss the service target."
        : "Customer-order-line interpretation unavailable. Revenue and service exposure retain the production-order calculation basis."}</p>}
    </>}
  </div>;
}
