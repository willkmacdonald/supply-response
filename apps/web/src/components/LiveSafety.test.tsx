// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {CaseHeader} from "./CaseHeader";
import {EvidencePanel} from "./EvidencePanel";
import {OutcomePanel} from "./OutcomePanel";
import type {AnalysisVersion, CaseInstance, EvidenceItem} from "../types";
import {reportIdentityKey} from "../reporting/reportNavigation";

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
  ["work_iq", "supplier_statement", "https://tenant.sharepoint.com/sites/demo/item", "Open citation"],
  ["work_iq", "supplier_statement", "https://teams.microsoft.com/l/message/channel/message", "Open citation"],
];

describe("live journey safety", () => {
  afterEach(cleanup);
  it("does not present a generic Fabric report as a record citation", () => {
    const analysis = liveAnalysis({source_system: "fabric", authority_scope: ["qualification_state"],
      citation_url: "https://app.powerbi.com/groups/demo/reports/report",
      navigable_citation_url: "https://app.powerbi.com/groups/demo/reports/report", citation_classification: "fabric"});
    render(<EvidencePanel analysis={analysis} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText("Required live citation missing")).not.toBeInTheDocument();
  });
  it("shows a safe Power BI action only for an available live report", () => {
    const runtime = {
      runtime_mode: "live" as const,
      work_iq: "work_iq" as const,
      operational_store: "fabric_sql" as const,
      agent_runtime: "foundry" as const,
      power_bi_available: true,
      power_bi_url: "https://app.powerbi.com/groups/dc3ac590-d892-40a7-9388-65dec120d67a/reports/e7611c8c-c887-443f-858a-13b1044bb4b9",
      deployment_contract: {power_bi_reporting_contract: "saved-analysis-v1"},
      capability_health: {
        operational_store: "ready" as const,
        work_iq: "ready" as const,
        agent_runtime: "ready" as const,
        power_bi: "ready" as const,
      },
    };
    const caseInstance: CaseInstance = {
      case_id: "RL-CASE-LIVE", template_id: "RL-001", purpose: "showcase", runtime_mode: "live",
      scenario_effective_time: "2026-09-08T15:00:00Z", scenario_timezone: "America/Chicago",
      status: "open", current_analysis_id: null, current_decision_id: null, display_status: null,
      recorded_at: "2026-09-08T15:00:00Z", projection_updated_at: "2026-09-08T15:00:00Z",
      controls: {new_analysis: false, decide: false, retry_action_planning: false, start_playback: false},
    };
    const view = <CaseHeader runtime={runtime} caseInstance={caseInstance} analysis={null} createPurpose="showcase" creating={false} analyzing={false} onCreate={vi.fn()} onAnalyze={vi.fn()} />;
    const {rerender} = render(view);
    expect(screen.getByText("Fictional scenario · Uses live Microsoft services")).toBeVisible();
    const link = screen.getByRole("link", {name: "Open case dashboard"});
    const url = new URL(link.getAttribute("href")!);
    expect(url.origin + url.pathname).toBe(`${runtime.power_bi_url}/command-center`);
    expect(url.searchParams.get("filter")).toBe(`CaseCommandCenter/case_key eq '${reportIdentityKey(caseInstance.case_id)}'`);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    const caseDetails = screen.getByText("Case details").closest("details");
    expect(caseDetails).toHaveTextContent("RL-CASE-LIVE");
    expect(document.querySelector(".case-id")).not.toBeInTheDocument();
    rerender(<CaseHeader runtime={runtime} caseInstance={null} analysis={null} createPurpose="showcase" creating={false} analyzing={false} onCreate={vi.fn()} onAnalyze={vi.fn()} />);
    expect(screen.queryByRole("link", {name: "Open case dashboard"})).not.toBeInTheDocument();
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
    expect(screen.getByRole("alert")).toHaveTextContent("Simulation failed. Another simulation cannot be started for this Case.");
    expect(screen.getByRole("alert")).not.toHaveTextContent("new Case");
    expect(screen.queryByText(/observations are pending/i)).not.toBeInTheDocument();
  });

  it("labels supported playback states as simulation without relabeling actual observations", () => {
    const observation = {
      observation_id: "OBS-1",
      metric: "units_recovered",
      observed_value: "12",
      predicted_value: "10",
      unit: "units",
      source_reference: "source-1",
      synthetic: false,
      display_label: "Observed",
    };
    const {rerender} = render(<OutcomePanel
      decision={{kind: "approved"} as never}
      actionCount={5}
      playback={{status: "in_progress"} as never}
      observations={[]}
      starting={false}
      onStart={vi.fn()}
    />);
    expect(screen.getByRole("heading", {name: "Simulated results"})).toBeVisible();
    expect(screen.getByText("Simulation in progress")).toBeVisible();
    expect(screen.getByText("Review outcomes")).toBeVisible();

    rerender(<OutcomePanel
      decision={{kind: "approved"} as never}
      actionCount={5}
      playback={null}
      observations={[observation] as never}
      starting={false}
      onStart={vi.fn()}
    />);
    expect(screen.getByRole("heading", {name: "Recorded results"})).toBeVisible();
    expect(screen.getByText("Observed")).toBeVisible();
    expect(screen.queryByText("Simulated")).not.toBeInTheDocument();

    for (const metric of ["response_cost", "revenue_protected", "margin_protected"]) {
      rerender(<OutcomePanel decision={{kind: "approved"} as never} actionCount={5} playback={null}
        observations={[{...observation, metric, observed_value: "328000.50", predicted_value: "0", unit: "USD"}] as never}
        starting={false} onStart={vi.fn()} />);
      expect(screen.getByText("$328,001")).toBeVisible();
      expect(screen.getByText(/Predicted: \$0 · source-1/)).toBeVisible();
      expect(screen.getByTestId("outcome-observation")).not.toHaveTextContent("USD");
    }

    rerender(<OutcomePanel
      decision={{kind: "approved"} as never}
      actionCount={5}
      playback={null}
      observations={[{...observation, metric: "toString"}] as never}
      starting={false}
      onStart={vi.fn()}
    />);
    expect(screen.getByRole("heading", {name: "Result metric not recognized"})).toBeVisible();
  });
});
