import type {CaseInstance, RankingStage} from "../types";
import {validDate, validInstant, validMoney} from "./snapshotValidation";

export const number = (value: number) => value.toLocaleString("en-US");
export const calendar = (value: string | null) => validDate(value)
  ? new Intl.DateTimeFormat("en-US", {year: "numeric", month: "long", day: "numeric", timeZone: "UTC"})
    .format(new Date(`${value}T00:00:00Z`)) : "Unavailable";
export const instant = (value: string | null) => validInstant(value)
  ? new Intl.DateTimeFormat("en-US", {year: "numeric", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit", timeZone: "UTC", timeZoneName: "short"}).format(new Date(value)) : "Unavailable";
// Policy thresholds and observations can arrive as integer decimal strings.
export function usdDecimal(value: string): string {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) return "";
  const [whole, cents = ""] = value.split(".");
  return `${whole}.${cents.padEnd(2, "0")}`;
}
export function wholeUsd(value: string) {
  if (!validMoney(value)) return "Unavailable";
  const cents = BigInt(value.replace(".", ""));
  return `$${((cents + 50n) / 100n).toLocaleString("en-US")}`;
}
export function usd(value: string) {
  if (!validMoney(value)) return "Unavailable";
  const [whole, cents] = value.split(".");
  return `$${BigInt(whole).toLocaleString("en-US")}.${cents}`;
}
export const supplier = (id: string) => id === "RL-SUP-ALPHA" ? "RL-Supplier Alpha — Current supplier"
  : id === "RL-SUP-BETA" ? "RL-Supplier Beta — Alternate supplier" : `Supplier ${id}`;
export const plant = (id: string) => id === "RL-PLANT-DAL" ? "Dallas plant"
  : id === "RL-PLANT-CHI" ? "Chicago plant" : `Plant ${id}`;
const blockers = new Map<string, string>([
  ["QUALITY_QUALIFICATION_PENDING", "Cannot use Supplier Beta yet: supplier qualification is incomplete"],
  ["ALPHA_PARTIAL_SHIPMENT_UNAVAILABLE", "No partial shipment from Supplier Alpha is available"],
  ["TRANSFER_INVENTORY_UNAVAILABLE", "The source plant does not have enough available inventory for this transfer"],
  ["RESEQUENCE_NOT_APPLICABLE", "Changing the production sequence does not provide a response for this plan"],
]);
export const blocker = (code: string) => blockers.get(code) ?? "A planning requirement is unresolved";
const roles = new Map<string, string>([
  ["material_planner", "Material planner"],
  ["finance_approver", "Finance approver"],
  ["quality_approver", "Quality approver"],
  ["response_approver", "Response approver"],
]);
export const role = (value: string) => roles.get(value) ?? "Additional authorization role";
const comparators = new Map<string, {label: string; unit: string}>([
  ["uncovered_part_demand", {label: "parts still needed", unit: "component units"}],
  ["otif_loss_percentage", {label: "service-target exposure", unit: "percentage points"}],
  ["revenue_at_risk", {label: "revenue at risk", unit: ""}],
  ["margin_at_risk", {label: "margin at risk", unit: ""}],
  ["response_cost", {label: "response cost", unit: ""}],
  ["approval_burden", {label: "required approval burden", unit: "roles"}],
  ["execution_risk", {label: "execution risk", unit: "score points"}],
]);
export function rankingThreshold(stage: RankingStage): string {
  if (!["revenue_at_risk", "margin_at_risk", "response_cost"].includes(stage.comparator)) return stage.threshold;
  const decimal = usdDecimal(stage.threshold);
  // Preserve exact policy precision; rounding applies only to displayed totals.
  return decimal.endsWith(".00") ? wholeUsd(decimal) : usd(decimal);
}
export function rankingReason(stage: RankingStage, optionId: string): string {
  if (!stage.retained_option_ids.includes(optionId)) return "This saved comparison stage did not retain the displayed option.";
  if (stage.comparator === "option_id") return "The saved comparison used its stable option identifier to resolve the remaining tie.";
  const known = comparators.get(stage.comparator);
  if (!known) return "The option was retained by an additional saved comparison rule; technical details are available below.";
  const count = stage.eliminated_option_ids.length;
  const outcome = count > 0
    ? `${count} other ${count === 1 ? "option was" : "options were"} ruled out in this comparison.`
    : "All remaining options stayed in consideration.";
  return `This option stayed in consideration after comparing ${known.label}, allowing a difference of ${rankingThreshold(stage)}${known.unit ? ` ${known.unit}` : ""} under the saved planning policy. ${outcome}`;
}
const states: Record<CaseInstance["status"], string> = {
  open: "Case open; no decision recorded", analyzing: "Case analysis in progress", awaiting_decision: "Case awaiting a decision",
  decision_rejected: "Case recommendation rejected", action_planning: "Case action planning in progress",
  executing: "Case execution in progress", monitoring: "Case monitoring in progress",
  reanalysis_required: "Case requires a new analysis", closed: "Case closed",
};
export function decisionContext(c: CaseInstance | null, analysisId: string, hasDecision: boolean): string {
  if (hasDecision) return "Recorded decision shown below";
  if (!c) return "Case context unavailable; no decision is shown";
  if (c.current_analysis_id !== analysisId) return `Historical saved analysis. ${states[c.status]}; no decision is shown for this analysis.`;
  return `${states[c.status]}. No decision is recorded in this view.`;
}
