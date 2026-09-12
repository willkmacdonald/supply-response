// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import type {RuntimeStatus} from "../types";
import {CaseHeader} from "./CaseHeader";

afterEach(cleanup);

const liveRuntime = {
  runtime_mode: "live", work_iq: "work_iq", operational_store: "fabric_sql",
  agent_runtime: "foundry", power_bi_available: false, power_bi_url: null,
  deployment_contract: null,
} as RuntimeStatus;

function renderHeader(runtime: RuntimeStatus | null) {
  render(<CaseHeader runtime={runtime} caseInstance={null} analysis={null}
    createPurpose="showcase" creating={false} analyzing={false}
    onCreate={vi.fn()} onAnalyze={vi.fn()} />);
}

it.each([
  [liveRuntime, "Fictional scenario · Uses live Microsoft services"],
  [{...liveRuntime, runtime_mode: "fallback"} as RuntimeStatus, "Fictional scenario · Uses predefined sample data"],
  [null, "Fictional scenario · Service mode not yet available"],
])("presents the approved story and mode copy", (runtime, modeCopy) => {
  renderHeader(runtime);
  expect(screen.getByText("RL-001 · Supply Disruption Response")).toBeVisible();
  expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("Respond to supply disruptions with AI");
  expect(screen.getByText("AI brings together supplier messages, inventory, and customer orders to assess the impact of a delay, compare recovery options, and support the planner's decision.")).toBeVisible();
  expect(screen.getByText(modeCopy)).toBeVisible();
});
