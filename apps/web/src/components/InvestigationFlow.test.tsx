// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import type {ResponseOption} from "../types";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {InvestigationFlow} from "./InvestigationFlow";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function state(): CaseWorkspaceState {
  const at = "2026-09-01T09:00:00-05:00";
  const ranking = {policy_version: "v1", eligible_option_ids: [], infeasible_option_ids: [],
    excluded_baseline_ids: [], stages: [], recommended_option_id: null, no_feasible_mitigation: true};
  const validation = {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: []};
  return {runtime: null, selectedOption: null, decision: null, actions: [], drafts: [], playback: null,
    observations: [], operation: null, error: null, existingCases: null, existingCasesError: null, decisionBlocked: true,
    create: vi.fn(), loadExistingCases: vi.fn(), reopen: vi.fn(), analyze: vi.fn(), selectOption: vi.fn(), approve: vi.fn(), reject: vi.fn(),
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
async function selectDecisionStage() {
  await userEvent.click(screen.getByRole("tab", {name: "3. Make the decision"}));
}
it("shows one approved three-card stage at a time", async () => {
  const user = userEvent.setup();
  render(<InvestigationFlow state={state()} />);
  expect(screen.getAllByRole("tab").map(tab => tab.textContent)).toEqual([
    "1. Understand the disruption", "2. Investigate responses", "3. Make the decision",
  ]);
  expect(screen.getAllByRole("heading", {level: 3}).map(h => h.textContent)).toEqual([
    "What changed?", "What do we have available?", "What does that put at risk?",
  ]);
  expect(screen.getByText("Disruption details aren't available for this analysis")).toBeVisible();
  await user.click(screen.getByRole("tab", {name: "2. Investigate responses"}));
  expect(screen.getAllByRole("heading", {level: 3}).map(h => h.textContent)).toEqual([
    "What can Supplier Alpha still supply?", "Can another plant help?", "Can we use the alternate supplier?",
  ]);
  expect(screen.getByText("Shipment details aren't available for this analysis")).toBeVisible();
  expect(screen.getByText("Plant transfer details aren't available for this analysis")).toBeVisible();
  expect(screen.getByText("Supplier qualification details aren't available for this analysis")).toBeVisible();
  await user.click(screen.getByRole("tab", {name: "3. Make the decision"}));
  expect(screen.getAllByRole("heading", {level: 3}).map(h => h.textContent)).toEqual([
    "Compare the options.", "Recommended response—and why.", "Review and approve.",
  ]);
  expect(screen.getByRole("button", {name: "Approve selected response"})).toBeDisabled();
  expect(screen.getByText("No option meets the planning requirements")).toBeVisible();
  expect(screen.getByText("Sample data — not a live retrieval")).toBeVisible();
  const comparison = screen.getByRole("region", {name: "Compare the options."});
  expect(within(comparison).getByText("Do-nothing comparison unavailable for this analysis")).toBeVisible();
  expect(within(comparison).getByText("How the options were compared")).toBeVisible();
  expect(comparison.lastElementChild).toHaveTextContent("Comparison from this analysis; selection is not approval or execution.");
});
it("uses manual keyboard activation with wrapping and stable panel associations", async () => {
  const user = userEvent.setup(); const input = state(); const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  const location = window.location.href; render(<InvestigationFlow state={input} />);
  const tabs = screen.getAllByRole("tab");
  expect(tabs[0]).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tabpanel")).toHaveAccessibleName("1. Understand the disruption");
  tabs[0].focus(); await user.keyboard("{ArrowLeft}");
  expect(tabs[2]).toHaveFocus(); expect(tabs[0]).toHaveAttribute("aria-selected", "true");
  expect(tabs.map(tab => tab.tabIndex)).toEqual([-1, -1, 0]);
  expect(tabs.filter(tab => tab.tabIndex === 0)).toHaveLength(1);
  await user.keyboard("{Enter}"); expect(tabs[2]).toHaveAttribute("aria-selected", "true");
  await user.keyboard("{Home}"); expect(tabs[0]).toHaveFocus();
  expect(tabs[2]).toHaveAttribute("aria-selected", "true");
  await user.keyboard(" "); expect(tabs[0]).toHaveAttribute("aria-selected", "true");
  await user.keyboard("{End}"); expect(tabs[2]).toHaveFocus();
  await user.keyboard("{ArrowRight}"); expect(tabs[0]).toHaveFocus();
  expect(fetch).not.toHaveBeenCalled(); expect(window.location.href).toBe(location);
  expect(input.selectOption).not.toHaveBeenCalled(); expect(input.approve).not.toHaveBeenCalled();
  expect(input.reject).not.toHaveBeenCalled(); expect(input.analyze).not.toHaveBeenCalled();
});

it("preserves the selected stage on same-case rerenders and resets for a different case", async () => {
  const user = userEvent.setup(); const input = state();
  const {rerender} = render(<InvestigationFlow state={input} />);
  await user.click(screen.getByRole("tab", {name: "2. Investigate responses"}));
  input.operation = "analyzing"; rerender(<InvestigationFlow state={input} />);
  expect(screen.getByRole("tab", {name: "2. Investigate responses"})).toHaveAttribute("aria-selected", "true");
  input.operation = null; input.caseInstance = {...input.caseInstance!, case_id: "another-case"};
  input.analysis = {...input.analysis!, case_id: "another-case"};
  rerender(<InvestigationFlow state={input} />);
  expect(screen.getByRole("tab", {name: "1. Understand the disruption"})).toHaveAttribute("aria-selected", "true");
});
it("keeps rejection explicit and respects the existing blocked state", async () => {
  const user = userEvent.setup(); const input = state(); render(<InvestigationFlow state={input} />);
  await user.click(screen.getByRole("tab", {name: "3. Make the decision"}));
  const decision = screen.getByRole("region", {name: "Review and approve."});
  expect(within(decision).getByLabelText("Rejection reason")).toBeDisabled();
  expect(input.approve).not.toHaveBeenCalled(); expect(input.reject).not.toHaveBeenCalled();
  cleanup(); input.decisionBlocked = false; input.caseInstance!.controls.decide = true; render(<InvestigationFlow state={input} />);
  await user.click(screen.getByRole("tab", {name: "3. Make the decision"}));
  await user.type(screen.getByLabelText("Rejection reason"), "Wait for evidence");
  await user.click(screen.getByRole("tab", {name: "1. Understand the disruption"}));
  await user.click(screen.getByRole("tab", {name: "3. Make the decision"}));
  expect(screen.getByLabelText("Rejection reason")).toHaveValue("Wait for evidence");
  await user.click(screen.getByRole("button", {name: "Reject recommendation"}));
  expect(input.reject).toHaveBeenCalledWith("Wait for evidence");
  expect(input.approve).not.toHaveBeenCalled();
});
it("reports historical and closed case state without inventing an awaiting decision", async () => {
  const input = state(); input.caseInstance!.status = "closed";
  input.caseInstance!.current_analysis_id = "newer";
  render(<InvestigationFlow state={input} />);
  await selectDecisionStage();
  expect(screen.getByText("Historical saved analysis. Case closed; no decision is shown for this analysis.")).toBeVisible();
  expect(screen.queryByText("Awaiting your explicit decision")).not.toBeInTheDocument();
});
it("shows recommended actions and predictions before keeping raw ranking rules in calculation details", async () => {
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
  const baseline: ResponseOption = {
    ...option, option_id: "baseline", option_kind: "no_mitigation", name: "No-Mitigation Baseline",
    executable: false, active_mitigation: false,
    predicted: {uncovered_part_demand: 6800, otif_loss_percentage: 100, revenue_at_risk: "955000.00",
      margin_at_risk: "328000.00", response_cost: "0.00", protected_customer_order_ids: []},
  };
  input.analysis!.material.operational_snapshot_json = JSON.stringify({
    case_id: "c", runtime_mode: "fallback", scenario_effective_time: "2026-09-01T09:00:00-05:00",
    scenario_timezone: "America/Chicago", analysis_horizon_start: "2026-09-01T09:00:00-05:00",
    analysis_horizon_end: "2026-09-30", disruption: {disruption_id: "d", supplier_id: "RL-SUP-ALPHA",
      po_line_id: "po", part_id: "RL-MAT-10247", plant_id: "RL-PLANT-CHI", original_quantity: 8000,
      original_due_date: "2026-09-03", partial_quantity: 0, partial_due_date: null, recovery_date: null,
      source_ref: "source-1"}, inventory_positions: [],
    production_orders: [
      {production_order_id: "mo1", product_id: "product", plant_id: "RL-PLANT-CHI", quantity: 1,
        due_date: "2026-09-03", component_demand: 1, customer_order_id: "co1", customer_revenue: "500000.00"},
      {production_order_id: "mo2", product_id: "product", plant_id: "RL-PLANT-CHI", quantity: 1,
        due_date: "2026-09-04", component_demand: 1, customer_order_id: "co2", customer_revenue: "455000.00"},
    ], customer_orders: [
      {customer_order_line_id: "co1", production_order_id: "mo1", customer_id: "customer-1", product_id: "product",
        plant_id: "RL-PLANT-CHI", quantity: 1, due_date: "2026-09-03", unit_revenue: "500000.00"},
      {customer_order_line_id: "co2", production_order_id: "mo2", customer_id: "customer-2", product_id: "product",
        plant_id: "RL-PLANT-CHI", quantity: 1, due_date: "2026-09-04", unit_revenue: "455000.00"},
    ],
  });
  option.predicted!.protected_customer_order_ids = ["co2"];
  input.analysis!.response_options = [baseline, option]; input.analysis!.recommendation = option;
  input.analysis!.ranking = {...input.analysis!.ranking, recommended_option_id: option.option_id,
    no_feasible_mitigation: false, stages: [{comparator: "uncovered_part_demand", threshold: "500",
      lower_is_better: true, input_option_ids: ["combined", "transfer"], values: [],
      retained_option_ids: ["combined"], eliminated_option_ids: ["transfer"]}]};
  render(<InvestigationFlow state={input} />);
  await selectDecisionStage();
  const recommendation = screen.getByRole("region", {name: "Recommended response—and why."});
  const details = within(recommendation).getByText("How the options were compared").closest("details")!;
  const mainText = Array.from(recommendation.children)
    .filter(node => node !== details).map(node => node.textContent).join(" ");
  expect(mainText).toContain("Recommended actions");
  expect(mainText).toContain("Expedite the proposed shipment from the current supplier, transfer stock from another plant, and prioritize production for customer needs.");
  const comparisonSummary = within(recommendation).getByRole("group", {name: "Compared with doing nothing"});
  expect(comparisonSummary).toHaveTextContent("Doing nothing → taking this response. These results are predictions.");
  expect(comparisonSummary).toHaveTextContent("Parts still needed6,800 → 2,300 RL-MAT-10247 component units");
  expect(comparisonSummary).toHaveTextContent("Customer order lines expected to miss the on-time, in-full target100% (2 of 2 lines) → 50% (1 of 2 lines)");
  expect(comparisonSummary).toHaveTextContent("Revenue at risk$955,000 → $375,000");
  expect(comparisonSummary).toHaveTextContent("Margin at risk$328,000 → $125,000");
  expect(comparisonSummary).toHaveTextContent("Response cost$0 → $24,750");
  expect(comparisonSummary).toHaveTextContent("Revenue at risk is the value of customer order lines expected to miss the service target.");
  expect(within(recommendation).queryByText("Expected if we take this option")).not.toBeInTheDocument();
  expect(mainText).not.toMatch(/threshold|option_id|stable option identifier/i);
  expect(mainText).not.toMatch(/persisted prediction/i);
  expect(within(details).getByText(/threshold 500/)).toBeInTheDocument();
  expect(comparisonSummary.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(within(recommendation).getByText("Assumptions and unresolved questions")).toBeVisible();
  const optionCard = within(screen.getByRole("region", {name: "Compare the options."}))
    .getByRole("article", {name: "Combined response"});
  expect(optionCard).toHaveTextContent("Execution coordination comparison score: 2");
  expect(optionCard).toHaveTextContent("Each unconfirmed external commitment counts 2 points");
  expect(optionCard).toHaveTextContent("Lower scores mean fewer or lower-weighted coordination factors");
  expect(optionCard).toHaveTextContent("This score is not a probability of failure");
});

it("explains when the persisted do-nothing comparison is missing or ambiguous", async () => {
  const input = state();
  const recommendation: ResponseOption = {
    option_id: "combined", option_kind: "combined", name: "Combined response", executable: true,
    active_mitigation: true, predicted: {uncovered_part_demand: 2300, otif_loss_percentage: 50,
      revenue_at_risk: "375000.00", margin_at_risk: "125000.00", response_cost: "24750.00",
      protected_customer_order_ids: []}, assumptions: [], evidence_ids: [], evidence_requirements: [],
    blocking_codes: [], prerequisite_roles: [], source_data_lineage: [], approval_burden: 0,
    execution_risk: 6, requested_side_effects: [],
  };
  input.analysis!.response_options = [recommendation]; input.analysis!.recommendation = recommendation;
  input.analysis!.ranking = {...input.analysis!.ranking, recommended_option_id: recommendation.option_id,
    no_feasible_mitigation: false};
  const {rerender} = render(<InvestigationFlow state={input} />);
  await selectDecisionStage();
  let card = screen.getByRole("region", {name: "Recommended response—and why."});
  expect(within(card).getByText("Do-nothing comparison unavailable: no baseline option is recorded.")).toBeVisible();
  expect(within(card).getByText("Expected if we take this option")).toBeVisible();
  const baseline = {...recommendation, option_id: "baseline-1", option_kind: "no_mitigation" as const,
    name: "No-Mitigation Baseline", active_mitigation: false};
  input.analysis!.response_options = [baseline, {...baseline, option_id: "baseline-2"}, recommendation];
  rerender(<InvestigationFlow state={input} />);
  card = screen.getByRole("region", {name: "Recommended response—and why."});
  expect(within(card).getByText("Do-nothing comparison unavailable: more than one baseline option is recorded.")).toBeVisible();
  expect(within(card).getByText("Expected if we take this option")).toBeVisible();
});

it("does not compare a missing persisted prediction", async () => {
  const input = state();
  const predicted = {uncovered_part_demand: 2300, otif_loss_percentage: 50,
    revenue_at_risk: "375000.00", margin_at_risk: "125000.00", response_cost: "24750.00",
    protected_customer_order_ids: []};
  const baseline: ResponseOption = {option_id: "baseline", option_kind: "no_mitigation",
    name: "No-Mitigation Baseline", executable: false, active_mitigation: false, predicted: null,
    assumptions: [], evidence_ids: [], evidence_requirements: [], blocking_codes: [], prerequisite_roles: [],
    source_data_lineage: [], approval_burden: 0, execution_risk: 0, requested_side_effects: []};
  const recommendation: ResponseOption = {...baseline, option_id: "combined", option_kind: "combined",
    name: "Combined response", executable: true, active_mitigation: true, predicted};
  input.analysis!.response_options = [baseline, recommendation]; input.analysis!.recommendation = recommendation;
  input.analysis!.ranking = {...input.analysis!.ranking, recommended_option_id: recommendation.option_id,
    no_feasible_mitigation: false};
  const {rerender} = render(<InvestigationFlow state={input} />);
  await selectDecisionStage();
  let card = screen.getByRole("region", {name: "Recommended response—and why."});
  expect(within(card).getByText("Do-nothing comparison unavailable: the baseline prediction is missing or invalid.")).toBeVisible();
  expect(within(card).getByText("Expected if we take this option")).toBeVisible();
  baseline.predicted = undefined as unknown as null;
  rerender(<InvestigationFlow state={input} />);
  card = screen.getByRole("region", {name: "Recommended response—and why."});
  expect(within(card).getByText("Do-nothing comparison unavailable: the baseline prediction is missing or invalid.")).toBeVisible();
  baseline.predicted = predicted; recommendation.predicted = null;
  rerender(<InvestigationFlow state={input} />);
  card = screen.getByRole("region", {name: "Recommended response—and why."});
  expect(within(card).getByText("Comparison unavailable: the recommended prediction is missing or invalid.")).toBeVisible();
});

it("does not claim a benefit when the persisted recommended and baseline predictions tie", async () => {
  const input = state();
  const predicted = {uncovered_part_demand: 6800, otif_loss_percentage: 100,
    revenue_at_risk: "955000.00", margin_at_risk: "328000.00", response_cost: "0.00",
    protected_customer_order_ids: []};
  const baseline: ResponseOption = {option_id: "baseline", option_kind: "no_mitigation",
    name: "No-Mitigation Baseline", executable: false, active_mitigation: false, predicted,
    assumptions: [], evidence_ids: [], evidence_requirements: [], blocking_codes: [], prerequisite_roles: [],
    source_data_lineage: [], approval_burden: 0, execution_risk: 0, requested_side_effects: []};
  const recommendation: ResponseOption = {...baseline, option_id: "combined", option_kind: "combined",
    name: "Combined response", executable: true, active_mitigation: true};
  input.analysis!.response_options = [baseline, recommendation]; input.analysis!.recommendation = recommendation;
  input.analysis!.ranking = {...input.analysis!.ranking, recommended_option_id: recommendation.option_id,
    no_feasible_mitigation: false};
  render(<InvestigationFlow state={input} />);
  await selectDecisionStage();
  const comparison = within(screen.getByRole("region", {name: "Recommended response—and why."}))
    .getByRole("group", {name: "Compared with doing nothing"});
  expect(comparison).toHaveTextContent("The values shown here are unchanged from doing nothing; no benefit is shown in these measures.");
  expect(comparison).toHaveTextContent("6,800 → 6,800 component units (part unavailable) (unchanged)");
  expect(comparison).toHaveTextContent("Production orders expected to miss the on-time, in-full target100% → 100% (unchanged)");
  expect(comparison).not.toHaveTextContent("Customer order lines expected");
  expect(comparison).toHaveTextContent("Customer-order-line interpretation unavailable. Revenue and service exposure retain the production-order calculation basis.");
});
