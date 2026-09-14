// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, waitFor, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import {FinanceWorkspace} from "./FinanceWorkspace";
import {api} from "../api";

vi.mock("../api", async importOriginal => ({...(await importOriginal<typeof import("../api")>()), api: {
  financeReviews: vi.fn(), financeReview: vi.fn(), resolveFinanceReview: vi.fn(),
}}));

const token = {generation: 1, analysis_id: "analysis-1", analysis_material_hash: "a".repeat(64), selection_id: "selection-1"};
const identity = {persona_id: "RL-PERSONA-ALEX", effective_roles: ["material_planner", "response_approver"], identity_source: "entra", source_id: "RL-ENTRA-ALEX", tenant_id: "tenant", object_id: "alex", display_name: "Alex", user_principal_name: "alex@example.com"};
const option = {option_id: "option-1", option_kind: "combined", name: "Combined response", executable: true, active_mitigation: true,
  predicted: {uncovered_part_demand: 2, otif_loss_percentage: 10, revenue_at_risk: "100.00", margin_at_risk: "50.00", response_cost: "24750.00", protected_customer_order_ids: []}, assumptions: ["Recovery date remains unconfirmed"], evidence_ids: ["evidence-1"], evidence_requirements: [], blocking_codes: [], prerequisite_roles: ["finance_approver"], source_data_lineage: ["evidence-1"], approval_burden: 1, execution_risk: 1, requested_side_effects: []};
const detail: any = {selection: {selection_id: "selection-1", proposal: {case_id: "case-1", analysis_id: "analysis-1", analysis_material_hash: "a".repeat(64), option_id: "option-1", response_cost: "24750.00"}, workflow_version: "independent-finance-v1", submitted_by: identity, submitted_at: "2026-09-13T10:00:00Z", finance_review_id: "review-1"}, review: {review_id: "review-1", proposal: {case_id: "case-1", analysis_id: "analysis-1", analysis_material_hash: "a".repeat(64), option_id: "option-1", response_cost: "24750.00"}, submitted_by: identity, submitted_at: "2026-09-13T10:00:00Z", status: "pending", reviewed_by: null, reviewed_at: null, reason: null, superseded_at: null}, review_revision: 1, analysis: {analysis_id: "analysis-1", evidence_items: [{evidence_id: "evidence-1", claim: "Supplier recovery evidence", source_system: "work_iq"}]}, option, is_current: true, current_token: token};

afterEach(() => {cleanup(); vi.clearAllMocks(); window.history.replaceState(null, "", "/");});

it("shows Taylor the pending detail and requires a reason to reject", async () => {
  vi.mocked(api.financeReviews).mockResolvedValue([detail]); vi.mocked(api.financeReview).mockResolvedValue(detail);
  window.history.replaceState(null, "", "/?financeReviewId=review-1");
  render(<FinanceWorkspace displayName="Taylor" onSwitchAccount={vi.fn()} />);
  expect(await screen.findByRole("heading", {name: "Combined response"})).toBeVisible();
  expect(screen.getByText("$24,750")).toBeVisible();
  expect(screen.getByText("Supplier recovery evidence")).toBeVisible();
  expect(screen.getByRole("button", {name: "Reject spending"})).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Reduce expedite cost");
  vi.mocked(api.resolveFinanceReview).mockResolvedValue({review: {...detail.review, status: "rejected", reason: "Reduce expedite cost"}, review_revision: 2} as never);
  await userEvent.click(screen.getByRole("button", {name: "Reject spending"}));
  await waitFor(() => expect(api.resolveFinanceReview).toHaveBeenCalledWith("review-1", {expected: token, expected_review_revision: 1, approved: false, reason: "Reduce expedite cost"}, expect.any(String)));
  expect(api.financeReview).toHaveBeenCalledTimes(2);
});

it("keeps resolved and superseded reviews readable but not actionable", async () => {
  const resolved = {...detail, is_current: false, review: {...detail.review, status: "superseded", superseded_at: "2026-09-13T11:00:00Z"}} as never;
  vi.mocked(api.financeReviews).mockResolvedValue([resolved]); vi.mocked(api.financeReview).mockResolvedValue(resolved);
  render(<FinanceWorkspace displayName="Taylor" onSwitchAccount={vi.fn()} />);
  const row = await screen.findByRole("button", {name: /combined response/i}); await userEvent.click(row);
  expect(screen.getAllByText(/superseded/i)).not.toHaveLength(0);
  expect(screen.queryByRole("button", {name: "Approve spending"})).not.toBeInTheDocument();
  expect(within(screen.getByRole("main")).getAllByText(/historical/i)).not.toHaveLength(0);
});
