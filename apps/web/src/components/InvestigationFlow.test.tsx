// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
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
