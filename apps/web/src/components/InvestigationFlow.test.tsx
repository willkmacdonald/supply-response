// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import type {ResponseOption} from "../types";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {InvestigationFlow} from "./InvestigationFlow";
afterEach(cleanup);

function state(): CaseWorkspaceState {
  const at = "2026-09-01T09:00:00-05:00";
  const ranking = {policy_version: "v1", eligible_option_ids: [], infeasible_option_ids: [],
    excluded_baseline_ids: [], stages: [], recommended_option_id: null, no_feasible_mitigation: true};
  const validation = {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: []};
  return {runtime: null, selectedOption: null, decision: null, actions: [], drafts: [], playback: null,
    observations: [], operation: null, error: null, decisionBlocked: true,
    create: vi.fn(), analyze: vi.fn(), selectOption: vi.fn(), approve: vi.fn(), reject: vi.fn(),
    retryPlanning: vi.fn(), retryAction: vi.fn(), startPlayback: vi.fn(),
    caseInstance: {case_id: "c", template_id: "RL-001", purpose: "showcase", runtime_mode: "fallback",
      scenario_effective_time: at, scenario_timezone: "America/Chicago", status: "awaiting_decision",
      current_analysis_id: "a", current_decision_id: null, display_status: null, recorded_at: at, projection_updated_at: at,
      controls: {new_analysis: false, decide: false, retry_action_planning: false, start_playback: false}},
    analysis: {analysis_id: "a", case_id: "c", runtime_mode: "fallback", scenario_effective_time: at,
      analysis_started_at: at, retrieval_window_ends_at: at, created_at: at, material_hash: "hash", evidence_items: [],
      evidence_validation: validation, response_options: [], approval_satisfactions: [], ranking, recommendation: null,
      material: {case_id: "c", template_id: "RL-001", case_purpose: "showcase", runtime_mode: "fallback", corpus: "demo_corpus",
        scenario_effective_time: at, operational_snapshot_json: "{}", required_authority_scope: [], evidence: [],
        conflicts: [], conflict_resolutions: [], evidence_validation: validation, response_options: [], standing_authorizations: [],
        approval_satisfactions: [], ranking, calculation_version: "v1", evidence_policy_version: "v1", approval_policy_version: "v1"}}};
}
it("keeps all nine cards in the exact approved row and DOM reading order", () => {
  render(<InvestigationFlow state={state()} />);
  expect(screen.getAllByRole("heading", {level: 2}).map(h => h.textContent)).toEqual([
    "1. Understand the disruption", "2. Investigate responses", "3. Make the decision",
  ]);
  expect(screen.getAllByRole("heading", {level: 3}).map(h => h.textContent)).toEqual([
    "What changed?", "What do we have available?", "What does that put at risk?",
    "What can Supplier Alpha still supply?", "Can another plant help?", "Can we use the alternate supplier?",
    "Compare the options.", "Recommended response—and why.", "Review and approve.",
  ]);
  expect(screen.getByRole("button", {name: "Approve selected response"})).toBeDisabled();
  expect(screen.getByText("No option meets the planning requirements")).toBeVisible();
  expect(screen.getByText("Disruption details aren't available for this analysis")).toBeVisible();
  expect(screen.getByText("Shipment details aren't available for this analysis")).toBeVisible();
  expect(screen.getByText("Plant transfer details aren't available for this analysis")).toBeVisible();
  expect(screen.getByText("Supplier qualification details aren't available for this analysis")).toBeVisible();
  expect(screen.getByText("Sample data — not a live retrieval")).toBeVisible();
  const comparison = screen.getByRole("region", {name: "Compare the options."});
  expect(within(comparison).getByText("Do-nothing comparison unavailable for this analysis")).toBeVisible();
  expect(within(comparison).getByText("How the options were compared")).toBeVisible();
  expect(comparison.lastElementChild).toHaveTextContent("Comparison from this analysis; selection is not approval or execution.");
});
it("keeps rejection explicit and respects the existing blocked state", async () => {
  const input = state(); render(<InvestigationFlow state={input} />);
  const decision = screen.getByRole("region", {name: "Review and approve."});
  expect(within(decision).getByLabelText("Rejection reason")).toBeDisabled();
  expect(input.approve).not.toHaveBeenCalled(); expect(input.reject).not.toHaveBeenCalled();
  cleanup(); input.decisionBlocked = false; render(<InvestigationFlow state={input} />);
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Wait for evidence");
  await userEvent.click(screen.getByRole("button", {name: "Reject recommendation"}));
  expect(input.reject).toHaveBeenCalledWith("Wait for evidence");
  expect(input.approve).not.toHaveBeenCalled();
});
it("reports historical and closed case state without inventing an awaiting decision", () => {
  const input = state(); input.caseInstance!.status = "closed";
  input.caseInstance!.current_analysis_id = "newer";
  render(<InvestigationFlow state={input} />);
  expect(screen.getByText("Historical saved analysis. Case closed; no decision is shown for this analysis.")).toBeVisible();
  expect(screen.queryByText("Awaiting your explicit decision")).not.toBeInTheDocument();
});
it("shows recommended actions and predictions before keeping raw ranking rules in calculation details", () => {
  const input = state();
  const option: ResponseOption = {
    option_id: "combined", option_kind: "combined", name: "Combine expedite, transfer, and resequencing",
    executable: true, active_mitigation: true,
    predicted: {uncovered_part_demand: 2300, otif_loss_percentage: 50, revenue_at_risk: "375000.00",
      margin_at_risk: "125000.00", response_cost: "24750.00", protected_customer_order_ids: []},
    assumptions: ["Remaining supplier recovery date is unconfirmed."], evidence_ids: [],
    evidence_requirements: [], blocking_codes: [], prerequisite_roles: ["material_planner"],
    source_data_lineage: ["source-1"], approval_burden: 1, execution_risk: 2,
    requested_side_effects: [],
  };
  input.analysis!.response_options = [option]; input.analysis!.recommendation = option;
  input.analysis!.ranking = {...input.analysis!.ranking, recommended_option_id: option.option_id,
    no_feasible_mitigation: false, stages: [{comparator: "uncovered_part_demand", threshold: "500",
      lower_is_better: true, input_option_ids: ["combined", "transfer"], values: [],
      retained_option_ids: ["combined"], eliminated_option_ids: ["transfer"]}]};
  render(<InvestigationFlow state={input} />);
  const recommendation = screen.getByRole("region", {name: "Recommended response—and why."});
  const details = within(recommendation).getByText("How the options were compared").closest("details")!;
  const mainText = Array.from(recommendation.children)
    .filter(node => node !== details).map(node => node.textContent).join(" ");
  expect(mainText).toContain("Recommended actions");
  expect(mainText).toContain("Expedite the proposed shipment from the current supplier, transfer stock from another plant, and prioritize production for customer needs.");
  expect(mainText).toContain("Expected if we take this option");
  expect(mainText).not.toMatch(/threshold|option_id|stable option identifier/i);
  expect(within(details).getByText(/threshold 500/)).toBeInTheDocument();
  const prediction = within(recommendation).getByText("Expected if we take this option").closest("div")!;
  expect(prediction.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(within(recommendation).getByText("Assumptions and unresolved questions")).toBeVisible();
});
