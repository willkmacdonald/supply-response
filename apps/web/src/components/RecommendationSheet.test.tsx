// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import type {AnalysisVersion, ResponseOption} from "../types";
import {OptionComparison} from "./OptionComparison";
import {RecommendationSheet} from "./RecommendationSheet";
import {recommendedOption} from "./recommendationState";

const predicted = {uncovered_part_demand: 10, otif_loss_percentage: 20, revenue_at_risk: "100.00",
  margin_at_risk: "50.00", response_cost: "12.34", protected_customer_order_ids: []};
function option(id: string, kind: ResponseOption["option_kind"] = "transfer"): ResponseOption {
  return {option_id: id, option_kind: kind, name: id, executable: true, active_mitigation: true,
    predicted, assumptions: ["Transfer timing is unconfirmed."], evidence_ids: [], evidence_requirements: [],
    blocking_codes: [], prerequisite_roles: ["material_planner"], source_data_lineage: ["record-1"],
    approval_burden: 0, execution_risk: 1, requested_side_effects: []};
}
function analysis(recommended = "transfer", recommendation: string | null = recommended): AnalysisVersion {
  const transfer = option("transfer"); const combined = option("combined", "combined");
  const baseline = {...option("baseline", "no_mitigation"), executable: false, active_mitigation: false,
    predicted: {...predicted, uncovered_part_demand: 20, response_cost: "0.00"}};
  const value: AnalysisVersion = {analysis_id: "a", case_id: "c", runtime_mode: "fallback", scenario_effective_time: "2026-09-01",
    analysis_started_at: "2026-09-01", retrieval_window_ends_at: "2026-09-01", created_at: "2026-09-01",
    material_hash: "hash", evidence_items: [], response_options: [baseline, transfer, combined],
    approval_satisfactions: [], recommendation: recommendation === null ? null : [transfer, combined].find(o => o.option_id === recommendation) ?? option(recommendation),
    ranking: {policy_version: "v1", eligible_option_ids: ["transfer", "combined"], infeasible_option_ids: [], excluded_baseline_ids: ["baseline"],
      stages: [{comparator: "uncovered_part_demand", threshold: "10", lower_is_better: true, input_option_ids: ["transfer", "combined"], values: [], retained_option_ids: [recommended], eliminated_option_ids: [recommended === "transfer" ? "combined" : "transfer"]}],
      recommended_option_id: recommended, no_feasible_mitigation: false},
    evidence_validation: {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: []},
    material: {} as AnalysisVersion["material"]};
  return value;
}

beforeEach(() => {
  vi.stubGlobal("PointerEvent", MouseEvent);
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {configurable: true, value: function () { this.setAttribute("open", ""); }});
  Object.defineProperty(HTMLDialogElement.prototype, "close", {configurable: true, value: function () { this.removeAttribute("open"); }});
});
afterEach(() => {cleanup(); document.body.style.overflow = ""; vi.unstubAllGlobals();});

it("opens one explanation from the non-combined recommended option without selecting it", async () => {
  const user = userEvent.setup(); const onSelect = vi.fn();
  render(<OptionComparison analysis={analysis()} selectedOption={null} onSelect={onSelect} />);
  const transfer = screen.getByRole("article", {name: "Transfer from another plant"});
  expect(within(transfer).getByText("Recommended for review")).toBeVisible();
  expect(screen.getAllByRole("button", {name: "Click here to understand why"})).toHaveLength(1);
  expect(screen.queryByRole("region", {name: "Recommended response—and why."})).not.toBeInTheDocument();
  const trigger = within(transfer).getByRole("button", {name: "Click here to understand why"});
  await user.click(trigger);
  const dialog = screen.getByRole("dialog", {name: "Why this response is recommended"});
  expect(within(dialog).getByText("Recommended for review: Transfer from another plant.")).toBeVisible();
  expect(within(dialog).getByText(/planning policy recorded for this saved analysis/)).toBeVisible();
  expect(onSelect).not.toHaveBeenCalled();
  await user.click(within(dialog).getByRole("button", {name: "Close"}));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

it("dismisses with Escape and backdrop, but not an inside click", async () => {
  const user = userEvent.setup(); render(<OptionComparison analysis={analysis()} selectedOption={null} onSelect={vi.fn()} />);
  const open = () => user.click(screen.getByRole("button", {name: "Click here to understand why"}));
  await open(); let dialog = screen.getByRole("dialog");
  fireEvent.click(dialog); expect(dialog).toBeVisible();
  fireEvent(dialog, new Event("cancel", {cancelable: true})); expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await open(); dialog = screen.getByRole("dialog");
  vi.spyOn(dialog, "getBoundingClientRect").mockReturnValue({left: 100, right: 500, top: 0, bottom: 500, width: 400, height: 500, x: 100, y: 0, toJSON: () => ({})});
  fireEvent.pointerDown(dialog, {clientX: 50, clientY: 100}); fireEvent.click(dialog, {clientX: 50, clientY: 100});
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("resets an open explanation when the analysis or case identity changes", async () => {
  const user = userEvent.setup(); const first = analysis(); const {rerender} = render(<OptionComparison analysis={first} selectedOption={null} onSelect={vi.fn()} />);
  await user.click(screen.getByRole("button", {name: "Click here to understand why"}));
  rerender(<OptionComparison analysis={{...first, analysis_id: "b"}} selectedOption={null} onSelect={vi.fn()} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", {name: "Click here to understand why"}));
  rerender(<OptionComparison analysis={{...first, case_id: "other"}} selectedOption={null} onSelect={vi.fn()} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("fails closed for absent, conflicting, duplicate, blocked, and missing-prediction recommendations", () => {
  const absent = analysis("transfer", null); expect(recommendedOption(absent)).toBeNull();
  expect(recommendedOption(analysis("transfer", "combined"))).toBeNull();
  const duplicate = analysis(); duplicate.response_options.push({...duplicate.response_options[1]}); expect(recommendedOption(duplicate)).toBeNull();
  const blocked = analysis(); blocked.response_options[1].blocking_codes = ["approval_missing"]; expect(recommendedOption(blocked)).toBeNull();
  const missing = analysis(); missing.response_options[1].predicted = null; expect(recommendedOption(missing)).toBeNull();
  const infeasible = analysis(); infeasible.ranking.infeasible_option_ids = ["transfer"]; expect(recommendedOption(infeasible)).toBeNull();
  const contradictory = analysis(); contradictory.ranking.no_feasible_mitigation = true; expect(recommendedOption(contradictory)).toBeNull();
  render(<OptionComparison analysis={missing} selectedOption={null} onSelect={vi.fn()} />);
  expect(screen.getByText("Recommendation unavailable for this analysis")).toBeVisible();
  expect(screen.queryByText("Recommended for review")).not.toBeInTheDocument();
});

it("wraps keyboard focus at both boundaries", async () => {
  const user = userEvent.setup();
  render(<RecommendationSheet onClose={vi.fn()}><a href="https://example.test">Last sheet control</a></RecommendationSheet>);
  const close = screen.getByRole("button", {name: "Close"}); const link = screen.getByRole("link");
  expect(close).toHaveFocus();
  await user.keyboard("{Shift>}{Tab}{/Shift}"); expect(link).toHaveFocus();
  await user.keyboard("{Tab}"); expect(close).toHaveFocus();
});
