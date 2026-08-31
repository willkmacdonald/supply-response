// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {CaseHeader} from "./CaseHeader";
import {EvidencePanel} from "./EvidencePanel";

describe("live journey safety", () => {
  afterEach(cleanup);
  it("shows a safe Power BI action only for an available live report", () => {
    const runtime = {
      runtime_mode: "live" as const,
      work_iq: "work_iq" as const,
      operational_store: "fabric_sql" as const,
      agent_runtime: "foundry" as const,
      power_bi_available: true,
      power_bi_url: "https://app.powerbi.com/groups/demo/reports/report",
      capability_health: {
        operational_store: "ready" as const,
        work_iq: "ready" as const,
        agent_runtime: "ready" as const,
        power_bi: "ready" as const,
      },
    };
    render(<CaseHeader runtime={runtime} caseInstance={null} createPurpose="showcase" creating={false} analyzing={false} onCreate={vi.fn()} onAnalyze={vi.fn()} />);
    const link = screen.getByRole("link", {name: "Open Power BI command center"});
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("exposes missing required live citations instead of rendering an unsafe link", () => {
    const analysis = {
      runtime_mode: "live",
      evidence_items: [{
        evidence_id: "RL-E-LIVE",
        requirement: "required_authoritative",
        citation_url: "https://evil.example/token=secret",
        synthetic: false,
        source_system: "work_iq",
        retrieval_health: "healthy",
        claim: "Required claim",
        excerpt: "Required excerpt",
        authority_scope: ["supplier_statement"],
        uncertainty_state: "certain",
      }],
    };
    render(<EvidencePanel analysis={analysis as never} />);
    expect(screen.getByText("Required live citation missing")).toBeInTheDocument();
    expect(screen.queryByRole("link", {name: "Open citation"})).not.toBeInTheDocument();
  });
});
