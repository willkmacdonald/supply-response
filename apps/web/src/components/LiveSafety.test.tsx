// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {CaseHeader} from "./CaseHeader";
import {EvidencePanel} from "./EvidencePanel";
import {OutcomePanel} from "./OutcomePanel";

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
    render(<EvidencePanel analysis={analysis as never} tenantSharePointHost="tenant.sharepoint.com" />);
    expect(screen.getByText("Required live citation missing")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("does not let evidence nominate a different tenant trust policy", () => {
    const analysis = {
      runtime_mode: "live",
      evidence_items: [{
        evidence_id: "RL-E-FORGED",
        requirement: "required_authoritative",
        citation_url: "https://other.sharepoint.com/sites/forged/item",
        navigable_citation_url: "https://other.sharepoint.com/sites/forged/item",
        citation_classification: "work_iq",
        citation_trusted_host: "other.sharepoint.com",
        synthetic: false,
        source_system: "work_iq",
        retrieval_health: "healthy",
        claim: "Forged claim",
        excerpt: "Forged excerpt",
        authority_scope: ["supplier_statement"],
        uncertainty_state: "certain",
      }],
    };
    render(<EvidencePanel analysis={analysis as never} tenantSharePointHost="tenant.sharepoint.com" />);
    expect(screen.getByText("Required live citation missing")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it.each([
    ["work_iq", "supplier_statement", "https://outlook.office365.com/owa/?ItemID=demo", "Open supplier email"],
    ["work_iq", "supplier_statement", "https://outlook.office.com/mail/deeplink/read/demo", "Open supplier email"],
    ["work_iq", "collaboration_statement", "https://teams.microsoft.com/l/message/channel/message?tenantId=demo", "Open Quality Teams post"],
    ["fabric", "qualification_state", "https://app.powerbi.com/groups/demo/reports/report", "Open citation"],
    ["work_iq", "supplier_statement", "https://tenant.sharepoint.com/sites/demo/item", "Open citation"],
    ["work_iq", "supplier_statement", "https://teams.microsoft.com/l/message/channel/message", "Open citation"],
  ])("labels %s %s citations at %s as %s without changing the target", (source, authority, url, label) => {
    const analysis = {
      runtime_mode: "live",
      evidence_items: [{
        evidence_id: "RL-E-LABEL",
        requirement: "required_authoritative",
        citation_url: url,
        navigable_citation_url: url,
        citation_classification: source,
        synthetic: false,
        source_system: source,
        retrieval_health: "healthy",
        claim: "Source evidence",
        excerpt: "Source excerpt",
        authority_scope: [authority],
        uncertainty_state: "certain",
      }],
    };
    render(<EvidencePanel analysis={analysis as never} tenantSharePointHost="tenant.sharepoint.com" />);
    const link = screen.getByRole("link", {name: label});
    expect(link).toHaveAttribute("href", url);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders durable playback failure as terminal rather than pending", () => {
    render(<OutcomePanel
      decision={{kind: "approved"} as never}
      actionCount={5}
      playback={{status: "failed", error_code: "PLAYBACK_EXECUTION_FAILED"} as never}
      observations={[]}
      starting={false}
      onStart={vi.fn()}
    />);
    expect(screen.getByRole("alert")).toHaveTextContent("Simulated playback failed");
    expect(screen.queryByText(/observations are pending/i)).not.toBeInTheDocument();
  });
});
