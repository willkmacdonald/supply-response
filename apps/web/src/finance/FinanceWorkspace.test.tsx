// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
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
detail.analysis = {
  case_id: "case-1", analysis_id: "analysis-1", runtime_mode: "fallback", analysis_started_at: "2026-09-13T09:00:00Z", retrieval_window_ends_at: "2026-09-13T09:02:00Z", created_at: "2026-09-13T09:02:00Z", material: {corpus: "demo_corpus"},
  evidence_validation: {blocking_codes: [], global_blocking_codes: [], item_results: [{evidence_id: "evidence-1", requirement: "required_authoritative", validated_authority_scope: ["supplier_statement"], freshness: "current", business_validity: "valid", uncertainty_state: "certain", retrieval_health: "healthy", authoritative: true, blocking_codes: []}]},
  evidence_items: [{evidence_id: "evidence-1", case_id: "case-1", kind: "source_statement", authority_scope: ["supplier_statement"], source_system: "work_iq", source_id: "outlook.message/recovery", source_timestamp: "2026-09-13T09:00:00Z", retrieved_at: "2026-09-13T09:01:00Z", retrieved_for_analysis_id: "analysis-1", retrieval_health: "healthy", effective_at: null, expires_at: null, claim: "Supplier recovery evidence", excerpt: "Recovery remains unconfirmed.", citation_url: null, runtime_mode: "fallback", synthetic: true, requirement: "required_authoritative", uncertainty_state: "certain"}],
};

afterEach(() => {cleanup(); vi.clearAllMocks(); window.history.replaceState(null, "", "/");});

it("shows Taylor the pending detail and requires a reason to reject", async () => {
  vi.mocked(api.financeReviews).mockResolvedValue([detail]); vi.mocked(api.financeReview).mockResolvedValue(detail);
  window.history.replaceState(null, "", "/?financeReviewId=review-1");
  render(<FinanceWorkspace displayName="Taylor" onSwitchAccount={vi.fn()} independentFinanceEnabled />);
  expect(await screen.findByRole("heading", {name: "Combined response"})).toBeVisible();
  expect(screen.getByText("$24,750")).toBeVisible();
  expect(screen.getByText(/saved source claim/i)).toHaveTextContent("Supplier recovery evidence");
  expect(screen.getByRole("button", {name: "Reject spending"})).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Reduce expedite cost");
  vi.mocked(api.resolveFinanceReview).mockResolvedValue({review: {...detail.review, status: "rejected", reason: "Reduce expedite cost"}, review_revision: 2} as never);
  await userEvent.click(screen.getByRole("button", {name: "Reject spending"}));
  await waitFor(() => expect(api.resolveFinanceReview).toHaveBeenCalledWith("review-1", {expected: token, expected_review_revision: 1, approved: false, reason: "Reduce expedite cost"}, expect.any(String)));
  expect(api.financeReview).toHaveBeenCalledTimes(2);
});

it("keeps superseded reviews readable with their state-specific explanation", async () => {
  const resolved = {...detail, is_current: false, review: {...detail.review, status: "superseded", superseded_at: "2026-09-13T11:00:00Z"}} as never;
  vi.mocked(api.financeReviews).mockResolvedValue([resolved]); vi.mocked(api.financeReview).mockResolvedValue(resolved);
  render(<FinanceWorkspace displayName="Taylor" onSwitchAccount={vi.fn()} independentFinanceEnabled />);
  const row = await screen.findByRole("button", {name: /combined response/i}); await userEvent.click(row);
  expect(screen.getAllByText(/superseded/i)).not.toHaveLength(0);
  expect(screen.queryByRole("button", {name: "Approve spending"})).not.toBeInTheDocument();
  expect(screen.getByText("This request was superseded by a newer proposal and remains readable but not actionable.")).toBeVisible();
});

it("keeps a rejected request readable without implying a next action", async () => {
  const rejected = {...detail, review: {...detail.review, status: "rejected", reviewed_at: "2026-09-13T10:30:00Z", reason: "Reduce expedite cost"}} as never;
  vi.mocked(api.financeReviews).mockResolvedValue([rejected]); vi.mocked(api.financeReview).mockResolvedValue(rejected);
  render(<FinanceWorkspace displayName="Taylor" onSwitchAccount={vi.fn()} independentFinanceEnabled />);
  await userEvent.click(await screen.findByRole("button", {name: /combined response/i}));
  expect(screen.getByText("This request was rejected and remains readable but not actionable.")).toBeVisible();
  expect(screen.queryByRole("button", {name: /approve spending|reject spending|return to alex/i})).not.toBeInTheDocument();
});

it("returns a current approved live review to Alex using the reviewed analysis", async () => {
  const approvedLive = {...detail,
    review: {...detail.review, status: "approved", reviewed_by: {...identity, persona_id: "RL-PERSONA-TAYLOR", display_name: "Taylor Brooks"}, reviewed_at: "2026-09-13T10:30:00Z"},
    analysis: {...detail.analysis, runtime_mode: "live", material: {...detail.analysis.material, corpus: "real_business", runtime_mode: "live"},
      evidence_items: [{...detail.analysis.evidence_items[0], runtime_mode: "live", synthetic: false}],
    },
  } as never;
  let switchLocation: string | null = null;
  const onSwitchAccount = vi.fn(async () => { switchLocation = window.location.href; });
  vi.mocked(api.financeReviews).mockResolvedValue([approvedLive]); vi.mocked(api.financeReview).mockResolvedValue(approvedLive);
  window.history.replaceState(null, "", "/?financeReviewId=review-1&caseId=stale-case&analysisId=stale-analysis&stage=understand");
  render(<FinanceWorkspace displayName="Taylor" onSwitchAccount={onSwitchAccount} independentFinanceEnabled />);
  const approvalMessage = await screen.findByText(/Taylor Brooks approved the spending/i);
  expect(approvalMessage).toHaveTextContent("Sep 13, 2026, 5:30 AM");
  expect(screen.getByText(/Retrieved for this analysis/)).toBeVisible();
  expect(screen.getByText("Required checks passed")).toBeVisible();
  for (const warning of ["Source does not belong to this analysis", "Retrieval not verified for this analysis", "Check result unavailable"]) {
    expect(screen.queryByText(warning)).not.toBeInTheDocument();
  }
  await userEvent.click(screen.getByRole("button", {name: "Return to Alex for final approval"}));
  expect(switchLocation).not.toBeNull();
  const parameters = new URL(switchLocation!).searchParams;
  expect(parameters.get("caseId")).toBe("case-1");
  expect(parameters.get("analysisId")).toBe("analysis-1");
  expect(parameters.get("optionId")).toBe("option-1");
  expect(parameters.get("stage")).toBe("approval");
  expect(parameters.has("financeReviewId")).toBe(false);
  expect(onSwitchAccount).toHaveBeenCalledOnce();
});

it("keeps a current approved review factual when Finance commands are disabled", async () => {
  const approved = {...detail, review: {...detail.review, status: "approved", reviewed_by: {...identity, persona_id: "RL-PERSONA-TAYLOR", display_name: "Taylor Brooks"}, reviewed_at: "2026-09-13T10:30:00Z"}} as never;
  vi.mocked(api.financeReviews).mockResolvedValue([approved]); vi.mocked(api.financeReview).mockResolvedValue(approved);
  render(<FinanceWorkspace displayName="Taylor" onSwitchAccount={vi.fn()} independentFinanceEnabled={false} />);
  await userEvent.click(await screen.findByRole("button", {name: /combined response/i}));
  expect(screen.getByText("Taylor Brooks approved the spending on Sep 13, 2026, 5:30 AM. Independent Finance commands are disabled; this request remains readable and does not provide a handoff.")).toBeVisible();
  expect(screen.queryByText(/Alex can now complete final approval/i)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", {name: "Return to Alex for final approval"})).not.toBeInTheDocument();
});

it("creates a new retry intent when Taylor moves from review A to review B", async () => {
  const reviewB = {...detail, selection: {...detail.selection, selection_id: "selection-2", finance_review_id: "review-2", proposal: {...detail.selection.proposal, option_id: "option-2"}}, review: {...detail.review, review_id: "review-2", proposal: {...detail.review.proposal, option_id: "option-2"}}, option: {...detail.option, option_id: "option-2", name: "Expedite response"}, current_token: {...token, selection_id: "selection-2"}};
  vi.mocked(api.financeReviews).mockResolvedValue([detail, reviewB]);
  vi.mocked(api.financeReview).mockImplementation(async id => id === "review-1" ? detail : reviewB);
  vi.mocked(api.resolveFinanceReview).mockRejectedValue(new Error("timeout"));
  window.history.replaceState(null, "", "/?financeReviewId=review-1");
  render(<FinanceWorkspace displayName="Taylor" onSwitchAccount={vi.fn()} independentFinanceEnabled />);
  await userEvent.click(await screen.findByRole("button", {name: "Approve spending"}));
  await screen.findByText(/Finance decision was not completed/i);
  await userEvent.click(screen.getByRole("button", {name: /expedite response/i}));
  await userEvent.click(await screen.findByRole("button", {name: "Approve spending"}));
  const calls = vi.mocked(api.resolveFinanceReview).mock.calls;
  expect(calls[0][0]).toBe("review-1"); expect(calls[1][0]).toBe("review-2");
  expect(calls[1][2]).not.toBe(calls[0][2]);
});

it("qualifies fictional data and preserves saved evidence provenance", async () => {
  vi.mocked(api.financeReviews).mockResolvedValue([detail]); vi.mocked(api.financeReview).mockResolvedValue(detail);
  window.history.replaceState(null, "", "/?financeReviewId=review-1");
  render(<FinanceWorkspace displayName="Taylor" onSwitchAccount={vi.fn()} independentFinanceEnabled />);
  expect(await screen.findByText(/demo corpus.*fictional/i)).toBeVisible();
  expect(screen.getAllByText(/sample data.*not a live retrieval/i)).not.toHaveLength(0);
  expect(screen.getAllByText(/source record/i)).not.toHaveLength(0);
});
