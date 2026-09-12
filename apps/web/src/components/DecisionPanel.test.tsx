// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, describe, expect, it, vi} from "vitest";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {DecisionPanel} from "./DecisionPanel";

afterEach(cleanup);

const combined = {
  option_id: "RL-OPTION-COMBINED",
  option_kind: "combined",
  name: "Internal combined option",
  executable: true,
  prerequisite_roles: ["material_planner", "finance_approver"],
};
const expedite = {
  option_id: "RL-OPTION-EXPEDITE",
  option_kind: "expedite",
  name: "Internal expedite option",
  executable: true,
  prerequisite_roles: ["material_planner"],
};

function state(overrides: Record<string, unknown> = {}): CaseWorkspaceState {
  return {
    analysis: {
      analysis_id: "RL-ANALYSIS-1",
      evidence_validation: {item_results: [], global_blocking_codes: [], blocking_codes: []},
      response_options: [combined, expedite],
      approval_satisfactions: [
        {analysis_id: "RL-ANALYSIS-1", option_id: combined.option_id, role: "material_planner", satisfied: true},
        {analysis_id: "RL-ANALYSIS-1", option_id: combined.option_id, role: "finance_approver", satisfied: false},
      ],
    },
    caseInstance: {controls: {decide: true}},
    selectedOption: combined,
    decision: null,
    operation: null,
    decisionBlocked: false,
    ...overrides,
  } as unknown as CaseWorkspaceState;
}

describe("DecisionPanel", () => {
  it("keeps blocked approval disabled while allowing a valid rejection when unblocked", async () => {
    const onReject = vi.fn();
    const {rerender} = render(<DecisionPanel state={state({decisionBlocked: true})} onApprove={vi.fn()} onReject={onReject} />);

    expect(screen.getByRole("button", {name: "Approve combined response"})).toBeDisabled();
    expect(screen.getByText("Material planner: Authorization recorded")).toBeVisible();
    expect(screen.getByText("Finance approver: Authorization still required")).toBeVisible();

    rerender(<DecisionPanel state={state()} onApprove={vi.fn()} onReject={onReject} />);
    await userEvent.type(screen.getByLabelText("Rejection reason"), "Wait for confirmed supply.");
    await userEvent.click(screen.getByRole("button", {name: "Reject recommendation"}));
    expect(onReject).toHaveBeenCalledWith("Wait for confirmed supply.");
  });

  it("keeps inherited and unknown requirement identifiers out of the main decision copy", () => {
    const unsafeOption = {...combined, prerequisite_roles: ["constructor", "custom_approver"]};
    const unsafeState = state({selectedOption: unsafeOption, decisionBlocked: true});
    unsafeState.analysis = {
      ...unsafeState.analysis!,
      evidence_validation: {
        ...unsafeState.analysis!.evidence_validation,
        global_blocking_codes: ["toString"],
        blocking_codes: ["CUSTOM_BLOCKER"],
      },
      approval_satisfactions: [],
    };

    render(<DecisionPanel state={unsafeState} onApprove={vi.fn()} onReject={vi.fn()} />);

    const blockerList = document.querySelector<HTMLElement>(".blocking-codes")!;
    expect(within(blockerList).getAllByText("A planning requirement is unresolved")).toHaveLength(2);
    expect(blockerList).not.toHaveTextContent("toString");
    expect(blockerList).not.toHaveTextContent("CUSTOM_BLOCKER");
    const roles = screen.getByRole("list", {name: "Required approval roles"});
    expect(within(roles).getAllByText(/Additional authorization role: Authorization still required/)).toHaveLength(2);
    expect(roles).not.toHaveTextContent("constructor");
    expect(roles).not.toHaveTextContent("custom_approver");
    const details = screen.getByText("Decision details").closest("details");
    expect(details).toHaveTextContent("toString");
    expect(details).toHaveTextContent("CUSTOM_BLOCKER");
    expect(details).toHaveTextContent("constructor");
    expect(details).toHaveTextContent("custom_approver");
  });

  it("shows the recorded approved response and roles instead of the mutable selection", () => {
    render(<DecisionPanel state={state({
      selectedOption: expedite,
      decision: {
        decision_id: "RL-DECISION-1",
        analysis_id: "RL-ANALYSIS-1",
        kind: "approved",
        selected_option_id: combined.option_id,
        prerequisite_roles: ["material_planner", "finance_approver"],
        runtime_mode: "fallback",
      },
    })} onApprove={vi.fn()} onReject={vi.fn()} />);

    const receipt = screen.getByTestId("decision-receipt");
    expect(within(receipt).getByRole("heading", {name: "Approved response"})).toBeVisible();
    expect(within(receipt).getByText("Combined response")).toBeVisible();
    expect(within(receipt).getByText("Material planner, Finance approver")).toBeVisible();
    expect(within(receipt).queryByText("Expedite the partial shipment")).not.toBeInTheDocument();
    const details = within(receipt).getByText("Decision details").closest("details");
    expect(details).toHaveTextContent("RL-DECISION-1");
    expect(details).toHaveTextContent("RL-OPTION-COMBINED");
    expect(details).toHaveTextContent("fallback");
  });

  it("does not resolve an older decision through the current analysis options", () => {
    render(<DecisionPanel state={state({
      decision: {
        decision_id: "RL-DECISION-OLD",
        analysis_id: "RL-ANALYSIS-OLD",
        kind: "approved",
        selected_option_id: combined.option_id,
        prerequisite_roles: ["material_planner"],
        runtime_mode: "fallback",
      },
    })} onApprove={vi.fn()} onReject={vi.fn()} />);

    const receipt = screen.getByTestId("decision-receipt");
    expect(within(receipt).getByText("Recorded response details unavailable")).toBeVisible();
    expect(within(receipt).queryByText("Combined response")).not.toBeInTheDocument();
  });

  it("describes a rejection without presenting the mutable selection as approved", () => {
    render(<DecisionPanel state={state({
      selectedOption: combined,
      decision: {
        decision_id: "RL-DECISION-REJECTED",
        analysis_id: "RL-ANALYSIS-1",
        kind: "rejected",
        selected_option_id: null,
        rejection_reason: "Wait for confirmed supply.",
        prerequisite_roles: ["material_planner"],
        runtime_mode: "fallback",
      },
    })} onApprove={vi.fn()} onReject={vi.fn()} />);

    const receipt = screen.getByTestId("decision-receipt");
    expect(within(receipt).getByRole("heading", {name: "Recommendation rejected"})).toBeVisible();
    expect(within(receipt).getByText("Wait for confirmed supply.")).toBeVisible();
    expect(within(receipt).queryByText("Combined response")).not.toBeInTheDocument();
  });
});
