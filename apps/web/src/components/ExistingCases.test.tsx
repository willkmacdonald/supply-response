// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import {ExistingCases} from "./ExistingCases";
import type {CaseInstance} from "../types";
afterEach(cleanup);
const saved: CaseInstance = {case_id: "old-case", template_id: "RL-001", purpose: "showcase", runtime_mode: "live",
  scenario_effective_time: "2026-09-01T09:00:00Z", scenario_timezone: "America/Chicago", status: "open",
  current_analysis_id: null, current_decision_id: null, display_status: null, recorded_at: "2026-09-01T09:00:00Z",
  projection_updated_at: "2026-09-01T09:00:00Z",
  controls: {new_analysis: false, decide: false, retry_action_planning: false, start_playback: false}};
const props = {cases: [saved], loading: false, reopening: false, error: null, onLoad: vi.fn(), onReopen: vi.fn()};
it("offers the designated demo without loading or exposing the older case list", async () => {
  const onReopen = vi.fn(), onLoad = vi.fn();
  render(<ExistingCases {...props} featuredCaseId="verified-case" onReopen={onReopen} onLoad={onLoad} />);
  expect(screen.getByText(/supplier email and analysis are already saved/i)).toBeVisible();
  expect(screen.getByRole("button", {name: "Reopen case old-case"})).not.toBeVisible();
  expect(screen.getByText("Other saved cases").closest("details")).not.toHaveAttribute("open");
  await userEvent.click(screen.getByRole("button", {name: "Resume the analyzed disruption"}));
  expect(onReopen).toHaveBeenCalledExactlyOnceWith("verified-case");
  expect(onLoad).not.toHaveBeenCalled();
});
it("keeps all other cases recoverable behind a collapsed disclosure", async () => {
  render(<ExistingCases {...props} featuredCaseId="verified-case" cases={[saved, {...saved, case_id: "verified-case"}]} />);
  await userEvent.click(screen.getByText("Other saved cases"));
  expect(screen.getByRole("button", {name: "Reopen case old-case"})).toBeVisible();
  expect(screen.queryByRole("button", {name: "Reopen case verified-case"})).not.toBeInTheDocument();
});
it("does not invent a featured case when none is configured and preserves error and busy handling", async () => {
  const {rerender} = render(<ExistingCases {...props} />);
  expect(screen.queryByRole("button", {name: "Resume the analyzed disruption"})).not.toBeInTheDocument();
  rerender(<ExistingCases {...props} featuredCaseId="verified-case" busy error="Could not load cases" />);
  expect(screen.getByRole("button", {name: "Resume the analyzed disruption"})).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("Could not load cases");
  await userEvent.click(screen.getByText("Other saved cases"));
  expect(screen.getByRole("button", {name: "Try finding cases again"})).toBeDisabled();
});
