// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RuntimeStatus } from "../types";
import { reportIdentityKey } from "../reporting/reportNavigation";
import { PlanningRoutes } from "./PlanningRoutes";

const runtime: RuntimeStatus = {
  runtime_mode: "live", work_iq: "work_iq", operational_store: "fabric_sql",
  agent_runtime: "foundry", power_bi_available: true,
  power_bi_url: "https://app.powerbi.com/groups/dc3ac590-d892-40a7-9388-65dec120d67a/reports/e7611c8c-c887-443f-858a-13b1044bb4b9",
  deployment_contract: { power_bi_reporting_contract: "saved-analysis-v1" },
};
const caseInstance = { case_id: "Case-A", runtime_mode: "live" as const };
const analysis = { case_id: "Case-A", analysis_id: "Historical-A1", runtime_mode: "live" as const };
const props = { runtime, caseInstance, analysis };

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("planning routes", () => {
  it("names both routes and opens an exact unselected traditional context", () => {
    render(<PlanningRoutes {...props} />);
    expect(screen.getByRole("navigation", { name: "Planning routes" })).toBeVisible();
    const report = screen.getByRole("link", { name: "Explore in Power BI" });
    expect(report).toHaveAttribute("target", "_blank");
    expect(report).toHaveAttribute("rel", "noopener noreferrer");
    const href = new URL(report.getAttribute("href")!);
    expect(href.searchParams.get("filter")).toBe([
      `CaseCommandCenter/case_key eq '${reportIdentityKey(caseInstance.case_id)}'`,
      `SavedAnalyses/analysis_key eq '${reportIdentityKey(analysis.analysis_id)}'`,
      "CaseCommandCenter/walkthrough_route eq 'traditional'",
    ].join(" and "));
    expect(screen.getByRole("link", { name: "Review with AI assistance" }))
      .toHaveAttribute("href", "#assisted-review");
    expect(screen.getByText("Showing saved evidence; no new source retrieval is running.")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Return to demo" })).not.toBeInTheDocument();
  });

  it("keeps assisted review local and makes no request", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    render(<><PlanningRoutes {...props} /><div id="assisted-review">Existing analysis</div></>);
    const before = structuredClone(props);
    await userEvent.click(screen.getByRole("link", { name: "Review with AI assistance" }));
    expect(fetch).not.toHaveBeenCalled();
    expect(props).toEqual(before);
    expect(screen.getByText("Existing analysis")).toBeVisible();
  });

  it("does not offer Power BI for fallback", () => {
    render(<PlanningRoutes runtime={{ ...runtime, runtime_mode: "fallback" }}
      caseInstance={{ ...caseInstance, runtime_mode: "fallback" }}
      analysis={{ ...analysis, runtime_mode: "fallback" }} />);
    expect(screen.queryByRole("link", { name: "Explore in Power BI" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review with AI assistance" })).toBeVisible();
    expect(screen.getByText(/The Power BI comparison is not available/)).toBeVisible();
    expect(screen.queryByText(/Both routes use this saved analysis/)).not.toBeInTheDocument();
  });

  it.each([
    { ...props, runtime: null },
    { ...props, caseInstance: null },
    { ...props, analysis: null },
    { ...props, analysis: { ...analysis, case_id: "Case-B" } },
    { ...props, analysis: { ...analysis, runtime_mode: "fallback" as const } },
  ])("hides routes without a matching loaded context", invalid => {
    render(<PlanningRoutes {...invalid} />);
    expect(screen.queryByRole("navigation", { name: "Planning routes" })).not.toBeInTheDocument();
  });

  it("keeps assistance available when report activation or URL is invalid", () => {
    const { rerender } = render(<PlanningRoutes {...props}
      runtime={{ ...runtime, deployment_contract: null }} />);
    expect(screen.queryByRole("link", { name: "Explore in Power BI" })).not.toBeInTheDocument();
    expect(screen.getByText(/The Power BI comparison is not available/)).toBeVisible();
    rerender(<PlanningRoutes {...props} runtime={{ ...runtime, power_bi_url: "https://evil.example" }} />);
    expect(screen.queryByRole("link", { name: "Explore in Power BI" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review with AI assistance" })).toBeVisible();
    expect(screen.getByText(/The Power BI comparison is not available/)).toBeVisible();
  });
});
