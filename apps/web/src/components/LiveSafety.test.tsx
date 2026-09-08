// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {CaseHeader} from "./CaseHeader";
import {EvidencePanel} from "./EvidencePanel";
import {OutcomePanel} from "./OutcomePanel";
import type {AnalysisVersion, EvidenceItem} from "../types";

function liveAnalysis(overrides: Partial<EvidenceItem>): AnalysisVersion {
  const item: EvidenceItem = {
    evidence_id: "RL-E-LIVE",
    case_id: "RL-CASE-LIVE",
    kind: "source_statement",
    authority_scope: ["supplier_statement"],
    source_system: "work_iq",
    source_id: "RL-SOURCE-LIVE",
    source_timestamp: "2026-09-08T14:59:00Z",
    retrieved_at: "2026-09-08T15:00:00Z",
    retrieved_for_analysis_id: "RL-ANALYSIS-LIVE",
    retrieval_health: "healthy",
    effective_at: "2026-09-08T15:00:00Z",
    expires_at: null,
    claim: "Required claim",
    excerpt: "Required excerpt",
    citation_url: null,
    runtime_mode: "live",
    synthetic: false,
    requirement: "required_authoritative",
    uncertainty_state: "certain",
    ...overrides,
  };
  const result = {
    evidence_id: item.evidence_id,
    requirement: item.requirement,
    validated_authority_scope: item.authority_scope,
    freshness: "current" as const,
    business_validity: "valid" as const,
    uncertainty_state: item.uncertainty_state,
    retrieval_health: item.retrieval_health,
    authoritative: true,
    blocking_codes: [],
  };
  const evidenceValidation = {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: [result]};
  const ranking = {policy_version: "v1", eligible_option_ids: [], infeasible_option_ids: [], excluded_baseline_ids: [], stages: [], recommended_option_id: null, no_feasible_mitigation: true};
  return {
    analysis_id: "RL-ANALYSIS-LIVE", case_id: "RL-CASE-LIVE", runtime_mode: "live",
    scenario_effective_time: "2026-09-08T15:00:00Z", analysis_started_at: "2026-09-08T14:59:59Z",
    retrieval_window_ends_at: "2026-09-08T15:00:01Z", created_at: "2026-09-08T15:00:01Z",
    material_hash: "a".repeat(64),
    material: {
      case_id: "RL-CASE-LIVE", template_id: "RL-001", case_purpose: "showcase", runtime_mode: "live",
      corpus: "real_business", scenario_effective_time: "2026-09-08T15:00:00Z", operational_snapshot_json: "{}",
      required_authority_scope: item.authority_scope, evidence: [], conflicts: [], conflict_resolutions: [],
      evidence_validation: evidenceValidation, response_options: [], standing_authorizations: [], approval_satisfactions: [],
      ranking, calculation_version: "v1", evidence_policy_version: "v1", approval_policy_version: "v1",
    },
    evidence_items: [item], evidence_validation: evidenceValidation, response_options: [], approval_satisfactions: [], ranking, recommendation: null,
  };
}

const citationCases: Array<[
  "fabric" | "work_iq",
  EvidenceItem["authority_scope"][number],
  string,
  string,
]> = [
  ["work_iq", "supplier_statement", "https://outlook.office365.com/owa/?ItemID=demo", "Open supplier email"],
  ["work_iq", "supplier_statement", "https://outlook.office.com/mail/deeplink/read/demo", "Open supplier email"],
  ["work_iq", "collaboration_statement", "https://teams.microsoft.com/l/message/channel/message?tenantId=demo", "Open Quality Teams post"],
  ["fabric", "qualification_state", "https://app.powerbi.com/groups/demo/reports/report", "Open citation"],
  ["work_iq", "supplier_statement", "https://tenant.sharepoint.com/sites/demo/item", "Open citation"],
  ["work_iq", "supplier_statement", "https://teams.microsoft.com/l/message/channel/message", "Open citation"],
];

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
    const analysis = liveAnalysis({
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
    });
    render(<EvidencePanel analysis={analysis} tenantSharePointHost="tenant.sharepoint.com" />);
    expect(screen.getByText("Required live citation missing")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("does not let evidence nominate a different tenant trust policy", () => {
    const analysis = liveAnalysis({
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
    });
    render(<EvidencePanel analysis={analysis} tenantSharePointHost="tenant.sharepoint.com" />);
    expect(screen.getByText("Required live citation missing")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it.each(citationCases)("labels %s %s citations at %s as %s without changing the target", (source, authority, url, label) => {
    const analysis = liveAnalysis({
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
    });
    render(<EvidencePanel analysis={analysis} tenantSharePointHost="tenant.sharepoint.com" />);
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
