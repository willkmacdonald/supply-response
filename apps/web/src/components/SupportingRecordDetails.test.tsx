// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, describe, expect, it, vi} from "vitest";
import {SupportingRecordDetails} from "./SupportingRecordDetails";
import {resolveSupportingRecord} from "./supportingRecord";
import {editSnapshot, recordFixture, selectRecord} from "./supportingRecord.fixture";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe("supporting record disclosure", () => {
  it("expands and collapses with native disclosure activation without fetching or altering input", async () => {
    const user = userEvent.setup();
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    const input = recordFixture(); const before = JSON.stringify(input);
    render(<SupportingRecordDetails result={resolveSupportingRecord(input, input.analysis.evidence_items[0].evidence_id)} />);
    const summary = screen.getByText("View shipment record");
    const details = summary.closest("details")!;
    expect(details).not.toHaveAttribute("open");
    await user.tab(); expect(summary).toHaveFocus();
    // jsdom does not implement native Enter activation for <summary>; the browser gate covers keyboard activation.
    await user.click(summary); expect(details).toHaveAttribute("open");
    expect(screen.getByText("Snapshot used for this analysis")).toBeVisible();
    expect(screen.getByText("Demo corpus — fictional")).toBeVisible();
    expect(screen.getByText("RL-Supplier Alpha — Current supplier")).toBeVisible();
    expect(screen.getByText("September 6, 2026")).toBeVisible();
    expect(screen.getByText("7.50 per unit (currency not specified)")).toBeVisible();
    const scenarioTime = screen.getByText(/In this scenario, as of/).querySelector("time")!;
    expect(scenarioTime).toHaveAttribute("datetime", "2026-09-01T09:00:00-05:00");
    expect(scenarioTime).toHaveTextContent(/Sep 1, 2026/);
    expect(scenarioTime).toHaveTextContent(/UTC/);
    expect(scenarioTime).not.toHaveTextContent("2026-09-01T");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    await user.click(summary); expect(details).not.toHaveAttribute("open");
    expect(fetch).not.toHaveBeenCalled(); expect(JSON.stringify(input)).toBe(before);
  });

  it("keeps qualification false flags and unknown dates distinct", () => {
    const input = recordFixture(); const id = selectRecord(input, "qualification");
    render(<SupportingRecordDetails result={resolveSupportingRecord(input, id)} />);
    expect(screen.getByText("View qualification record")).toBeInTheDocument();
    expect(screen.getByText("RL-Supplier Beta — Alternate supplier")).toBeInTheDocument();
    expect(screen.getByText("Supplier qualification pending")).toBeInTheDocument();
    expect(screen.getAllByText("Incomplete")).toHaveLength(2);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("Expected qualification decision date")).toBeInTheDocument();
  });

  it("labels transfer plants and renders source-controlled text as text", () => {
    const input = recordFixture(); const id = selectRecord(input, "transfer");
    editSnapshot(input, s => { s.transfer.part_id = "<img src=x onerror=alert(1)>"; });
    const {container} = render(<SupportingRecordDetails result={resolveSupportingRecord(input, id)} />);
    expect(screen.getByText("View transfer record")).toBeInTheDocument();
    expect(screen.getByText("Dallas plant")).toBeInTheDocument();
    expect(screen.getByText("Chicago plant")).toBeInTheDocument();
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
  });

  it("makes unavailability explicit without offering a substitute destination", () => {
    render(<SupportingRecordDetails result={{status: "unavailable", message: "Supporting record unavailable"}} />);
    expect(screen.getByText("Supporting record unavailable")).toBeVisible();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText(/View .* record/)).not.toBeInTheDocument();
  });
});
