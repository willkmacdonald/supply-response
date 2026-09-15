// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {ExecutionPanel} from "./ExecutionPanel";

const decision = {kind: "approved", action_planning_status: "complete"} as never;

afterEach(cleanup);

describe("ExecutionPanel", () => {
  it("keeps simulated coordination visually separate from actual supplier mail state", () => {
    render(<ExecutionPanel decision={decision} actions={[
      {action_id: "A-1", kind: "coordinate_alpha_expedited_partial", status: "planned", owner_kind: "persona",
        execution_mode: "simulation"},
    ] as never} drafts={[
      {artifact_id: "D-1", artifact_kind: "supplier_recovery_request", subject: "Recovery request", body: null},
    ] as never} retrying={false} onRetry={vi.fn()} onRetryAction={vi.fn()}
    supplierEmail={{email_id: "email-1", decision_id: "decision-1", action_id: "A-2", revision: 1,
      subject: "Recovery request", body: "Please confirm timing.", from_address: "agent@willmacdonald.com",
      to_address: "will@willmacdonald.com", reviewed_revision: null, reviewed_at: null, reviewed_by: null,
      send_status: "draft"}}
    onSaveSupplierEmail={vi.fn()} onReviewSupplierEmail={vi.fn()} onSendSupplierEmail={vi.fn()}
    onCheckSupplierEmail={vi.fn()} />);

    const simulation = screen.getByRole("region", {name: "Simulated actions and prepared drafts"});
    const mail = screen.getByRole("region", {name: "Review the supplier email"});
    expect(simulation).toHaveTextContent("What happens here: Simulated coordination");
    expect(simulation).toHaveTextContent("Prepared draft");
    expect(simulation).not.toHaveTextContent("Not sent");
    expect(mail).toHaveTextContent("Not sent");
    expect(simulation).not.toContainElement(mail);
  });

  it("uses business labels for known action kinds and an honest fallback for unknown kinds", () => {
    render(<ExecutionPanel decision={decision} actions={[
      {action_id: "A-1", kind: "prepare_alpha_recovery_draft", status: "planned", owner_kind: "persona",
        purpose: "Prepare a supplier communication for review.", expected_result: "An unsent draft is ready.",
        execution_mode: "communication_preparation"},
      {action_id: "A-2", kind: "mystery_email_action", status: "planned"},
      {action_id: "A-3", kind: "constructor", status: "toString"},
    ] as never} drafts={[]} retrying={false} onRetry={vi.fn()} onRetryAction={vi.fn()} />);

    expect(screen.getByText("Prepare supplier recovery draft")).toBeVisible();
    expect(screen.getByText("Prepare a supplier communication for review.")).toBeVisible();
    expect(screen.getByText("Owner: Alex")).toBeVisible();
    expect(screen.getByText("Expected result: An unsent draft is ready.")).toBeVisible();
    expect(screen.getByText("What happens here: Draft prepared for Alex to review")).toBeVisible();
    expect(screen.getAllByText("Action type not recognized")).toHaveLength(2);
    expect(screen.getByText("Status not recognized")).toBeVisible();
    expect(screen.queryByText("mystery email action")).not.toBeInTheDocument();
    expect(screen.getByText("5. Execute mitigation plan")).toBeVisible();
  });

  it("keeps drafts unsent and labels only proven draft kinds specifically", () => {
    render(<ExecutionPanel decision={decision} actions={[]} drafts={[
      {artifact_id: "D-1", artifact_kind: "alpha_recovery_request", subject: "Recovery request", body: null},
      {artifact_id: "D-2", artifact_kind: "unknown_artifact", subject: null, body: null},
    ] as never} retrying={false} onRetry={vi.fn()} onRetryAction={vi.fn()} />);

    expect(screen.getAllByText("Not sent")).toHaveLength(2);
    expect(screen.getByRole("heading", {name: "Supplier recovery request draft"})).toBeVisible();
    expect(screen.getByRole("heading", {name: "Draft for review"})).toBeVisible();
    expect(screen.getByText("No draft subject recorded.")).toBeVisible();
    expect(screen.queryByText(/will be filled during simulated execution/i)).not.toBeInTheDocument();
  });

  it("labels a legacy draft action truthfully when execution mode was not stored", () => {
    render(<ExecutionPanel decision={decision} actions={[
      {action_id: "A-LEGACY-DRAFT", kind: "prepare_alpha_recovery_draft", status: "planned",
        owner_kind: "persona", execution_mode: null},
      {action_id: "A-LEGACY-UNKNOWN", kind: "mystery_action", status: "planned",
        owner_kind: "system", execution_mode: null},
    ] as never} drafts={[]} retrying={false} onRetry={vi.fn()} onRetryAction={vi.fn()} />);

    expect(screen.getByText("What happens here: Draft prepared for Alex to review")).toBeVisible();
    expect(screen.getByText("What happens here: Execution details not recorded")).toBeVisible();
    expect(screen.queryByText("What happens here: Simulated coordination")).not.toBeInTheDocument();
  });
});
