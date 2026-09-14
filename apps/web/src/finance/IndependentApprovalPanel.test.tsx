// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import {api} from "../api";
import {IndependentApprovalPanel} from "./IndependentApprovalPanel";

vi.mock("../api", async importOriginal => ({...(await importOriginal<typeof import("../api")>()), api: {
  proposal: vi.fn(), submitProposal: vi.fn(), finalizeProposal: vi.fn(),
}}));
const empty = {token: {generation: 0, analysis_id: "analysis-1", analysis_material_hash: "a".repeat(64), selection_id: null}, selection: null, review: null, review_revision: null};
const high: any = {option_id: "combined", name: "Combined response", executable: true, predicted: {response_cost: "24750.00"}, assumptions: [], evidence_ids: [], blocking_codes: []};
const low = {...high, option_id: "transfer", name: "Transfer inventory", predicted: {response_cost: "2250.00"}} as never;
afterEach(() => {cleanup(); vi.clearAllMocks();});

it("submits the selected response then reads current state separately", async () => {
  vi.mocked(api.proposal).mockResolvedValueOnce(empty as never).mockResolvedValueOnce({...empty, token: {...empty.token, generation: 1, selection_id: "selection-1"}, selection: {selection_id: "selection-1", proposal: {option_id: "combined", response_cost: "24750.00"}, finance_review_id: "review-1", submitted_at: "2026-09-13T10:00:00Z"}, review: {review_id: "review-1", status: "pending"}, review_revision: 1} as never);
  vi.mocked(api.submitProposal).mockResolvedValue({selection: {selection_id: "selection-1"}, review: {review_id: "review-1", status: "pending"}, review_revision: 1} as never);
  render(<IndependentApprovalPanel caseId="case-1" selectedOption={high} finalDecision={null} onFinalDecision={vi.fn()} />);
  await userEvent.click(await screen.findByRole("button", {name: "Submit for Finance review"}));
  await waitFor(() => expect(api.submitProposal).toHaveBeenCalledWith("case-1", {option_id: "combined", expected: empty.token}, expect.any(String)));
  expect(api.proposal).toHaveBeenCalledTimes(2);
  expect(await screen.findByText(/waiting for Taylor/i)).toBeVisible();
  expect(screen.getByRole("link", {name: /open Taylor review/i})).toHaveAttribute("href", expect.stringContaining("financeReviewId=review-1"));
});

it("does not reuse approval for a changed selection and explains low-cost review", async () => {
  vi.mocked(api.proposal).mockResolvedValue({...empty, token: {...empty.token, selection_id: "selection-1"}, selection: {selection_id: "selection-1", proposal: {option_id: "combined", response_cost: "24750.00"}, finance_review_id: "review-1"}, review: {review_id: "review-1", status: "approved"}, review_revision: 2} as never);
  render(<IndependentApprovalPanel caseId="case-1" selectedOption={low} finalDecision={null} onFinalDecision={vi.fn()} />);
  expect(await screen.findByText("Finance review not required—within the spending threshold")).toBeVisible();
  expect(screen.getByText(/fresh submission/i)).toBeVisible();
  expect(screen.queryByRole("button", {name: /final approval/i})).not.toBeInTheDocument();
});

it("keeps Alex final approval distinct and reports execution as unavailable", async () => {
  const current = {...empty, token: {...empty.token, generation: 2, selection_id: "selection-1"}, selection: {selection_id: "selection-1", proposal: {option_id: "combined", response_cost: "24750.00"}, finance_review_id: "review-1"}, review: {review_id: "review-1", status: "approved", reviewed_at: "2026-09-13T11:00:00Z"}, review_revision: 2};
  vi.mocked(api.proposal).mockResolvedValue(current as never);
  vi.mocked(api.finalizeProposal).mockResolvedValue({decision_id: "decision-1", kind: "approved", selected_option_id: "combined", action_planning_status: "failed"} as never);
  render(<IndependentApprovalPanel caseId="case-1" selectedOption={high} finalDecision={null} onFinalDecision={vi.fn()} />);
  await userEvent.click(await screen.findByRole("button", {name: "Give final Alex approval"}));
  expect(api.finalizeProposal).toHaveBeenCalledWith("case-1", {expected: current.token, kind: "approved"}, expect.any(String));
  expect(await screen.findByText(/execution is not available in this milestone/i)).toBeVisible();
});

it("retries a timed-out submission with the original body and key", async () => {
  vi.mocked(api.proposal).mockResolvedValue(empty as never);
  vi.mocked(api.submitProposal).mockRejectedValue(new Error("timeout"));
  render(<IndependentApprovalPanel caseId="case-1" selectedOption={high} finalDecision={null} onFinalDecision={vi.fn()} />);
  const button = await screen.findByRole("button", {name: "Submit for Finance review"});
  await userEvent.click(button); await screen.findByRole("alert"); await userEvent.click(button);
  expect(api.submitProposal).toHaveBeenCalledTimes(2);
  expect(vi.mocked(api.submitProposal).mock.calls[1]).toEqual(vi.mocked(api.submitProposal).mock.calls[0]);
});
