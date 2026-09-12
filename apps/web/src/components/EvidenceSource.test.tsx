// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it} from "vitest";
import type {AnalysisVersion, EvidenceItem} from "../types";
import {EvidenceSource} from "./EvidenceSource";

afterEach(cleanup);

const baseItem: EvidenceItem = {
  evidence_id: "E-1",
  case_id: "CASE-1",
  kind: "source_statement",
  authority_scope: ["supplier_statement"],
  source_system: "work_iq",
  source_id: "message-1",
  source_timestamp: "2026-09-08T14:59:59Z",
  retrieved_at: "2026-09-08T15:00:00Z",
  retrieved_for_analysis_id: "ANALYSIS-1",
  retrieval_health: "healthy",
  effective_at: "2026-09-08T15:00:00Z",
  expires_at: null,
  claim: "Supplier confirmed the available quantity.",
  excerpt: "Two thousand units are available.",
  citation_url: "https://outlook.office.com/mail/deeplink/read/message-1",
  navigable_citation_url: "https://outlook.office.com/mail/deeplink/read/message-1",
  citation_classification: "work_iq",
  runtime_mode: "live",
  synthetic: false,
  requirement: "required_authoritative",
  uncertainty_state: "certain",
};

const analysis: AnalysisVersion = {
  analysis_id: "ANALYSIS-1",
  case_id: "CASE-1",
  runtime_mode: "live",
  scenario_effective_time: "2026-09-08T15:00:00Z",
  analysis_started_at: "2026-09-08T15:00:00Z",
  retrieval_window_ends_at: "2026-09-08T15:00:01Z",
  created_at: "2026-09-08T15:00:01Z",
  material_hash: "a".repeat(64),
  material: {
    case_id: "CASE-1", template_id: "TEMPLATE-1", case_purpose: "showcase",
    runtime_mode: "live", corpus: "real_business", scenario_effective_time: "2026-09-08T15:00:00Z",
    operational_snapshot_json: "{}", required_authority_scope: [], evidence: [], conflicts: [],
    conflict_resolutions: [], evidence_validation: {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: []},
    response_options: [], standing_authorizations: [], approval_satisfactions: [],
    ranking: {policy_version: "v1", eligible_option_ids: [], infeasible_option_ids: [], excluded_baseline_ids: [], stages: [], recommended_option_id: null, no_feasible_mitigation: true},
    calculation_version: "v1", evidence_policy_version: "v1", approval_policy_version: "v1",
  },
  evidence_items: [baseItem],
  evidence_validation: {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: []},
  response_options: [], approval_satisfactions: [],
  ranking: {policy_version: "v1", eligible_option_ids: [], infeasible_option_ids: [], excluded_baseline_ids: [], stages: [], recommended_option_id: null, no_feasible_mitigation: true},
  recommendation: null,
};

function renderSource(item: EvidenceItem, runtimeMode: AnalysisVersion["runtime_mode"] = "live") {
  return render(<EvidenceSource item={item} analysis={{...analysis, runtime_mode: runtimeMode, evidence_items: [item]}} label="Supplier email — Current supplier" />);
}

it("adds a decorative Outlook icon without changing the trusted supplier-email action", () => {
  const {container} = renderSource(baseItem);
  const action = screen.getByRole("link", {name: "Open supplier email"});
  expect(action).toHaveAttribute("href", baseItem.navigable_citation_url);
  expect(action).toHaveAttribute("target", "_blank");
  expect(action).toHaveAttribute("rel", "noopener noreferrer");
  const icon = action.querySelector("img.source-action-icon");
  expect(icon).toHaveAttribute("src", expect.stringContaining("outlook_32x1.svg"));
  expect(icon).toHaveAttribute("alt", "");
  expect(icon).toHaveAttribute("aria-hidden", "true");
  expect(container).toHaveTextContent("Two thousand units are available.");
  expect(screen.getByText("Source details")).toBeInTheDocument();
});

it("adds a decorative Teams icon only for a trusted collaboration action", () => {
  const teams = {...baseItem, authority_scope: ["collaboration_statement" as const],
    navigable_citation_url: "https://teams.microsoft.com/l/message/channel/message-1",
    citation_url: "https://teams.microsoft.com/l/message/channel/message-1"};
  renderSource(teams);
  const action = screen.getByRole("link", {name: "Open Quality Teams post"});
  expect(action).toHaveAttribute("href", teams.navigable_citation_url);
  expect(action.querySelector("img.source-action-icon")).toHaveAttribute("src", expect.stringContaining("teams_32x1.svg"));
});

it("does not render a link or product icon for absent and untrusted destinations", () => {
  const {container, rerender} = renderSource({...baseItem, navigable_citation_url: null, citation_url: null});
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  expect(container.querySelector("img.source-action-icon")).toBeNull();
  expect(screen.getByText("Source details")).toBeInTheDocument();
  rerender(<EvidenceSource item={{...baseItem, navigable_citation_url: "https://evil.example/mail", citation_url: "https://evil.example/mail"}} analysis={analysis} />);
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  expect(container.querySelector("img.source-action-icon")).toBeNull();
});

it("keeps fallback evidence non-live and generic validated destinations unlabeled", () => {
  const {container, rerender} = renderSource({...baseItem, runtime_mode: "fallback"}, "fallback");
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  expect(container.querySelector("img.source-action-icon")).toBeNull();

  const generic = {...baseItem, authority_scope: ["operational_quantity" as const],
    navigable_citation_url: "https://outlook.office.com/mail/deeplink/read/message-1"};
  rerender(<EvidenceSource item={generic} analysis={{...analysis, evidence_items: [generic]}} />);
  expect(screen.getByRole("link", {name: "Open citation"})).toBeInTheDocument();
  expect(screen.queryByRole("link", {name: /supplier email|Teams post/})).not.toBeInTheDocument();
  expect(container.querySelector("img.source-action-icon")).toBeNull();
});
