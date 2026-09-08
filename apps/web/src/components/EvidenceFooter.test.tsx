// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it} from "vitest";
import type {AnalysisVersion, EvidenceItem} from "../types";
import {EvidenceFooter} from "./EvidenceFooter";
import {EvidencePanel} from "./EvidencePanel";

afterEach(cleanup);

const validationResult = {
  evidence_id: "E-1",
  requirement: "required_authoritative" as const,
  validated_authority_scope: ["supplier_statement" as const],
  freshness: "current" as const,
  business_validity: "valid" as const,
  uncertainty_state: "certain" as const,
  retrieval_health: "healthy" as const,
  authoritative: true,
  blocking_codes: [],
};

const evidence: EvidenceItem = {
  evidence_id: "E-1",
  case_id: "CASE-1",
  kind: "operational_fact",
  authority_scope: ["supplier_statement"],
  source_system: "work_iq",
  source_id: "SOURCE-1",
  source_timestamp: "2026-09-08T14:59:59Z",
  retrieved_at: "2026-09-08T15:00:00.125Z",
  retrieved_for_analysis_id: "ANALYSIS-1",
  retrieval_health: "healthy",
  effective_at: "2026-09-08T15:00:00Z",
  expires_at: null,
  claim: "Supplier confirmed the available quantity.",
  excerpt: "Two thousand units are available.",
  citation_url: "https://outlook.office.com/mail/deeplink/read/demo",
  navigable_citation_url: "https://outlook.office.com/mail/deeplink/read/demo",
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
    case_id: "CASE-1",
    template_id: "TEMPLATE-1",
    case_purpose: "showcase",
    runtime_mode: "live",
    corpus: "real_business",
    scenario_effective_time: "2026-09-08T15:00:00Z",
    operational_snapshot_json: "{}",
    required_authority_scope: ["supplier_statement"],
    evidence: [],
    conflicts: [],
    conflict_resolutions: [],
    evidence_validation: {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: [validationResult]},
    response_options: [],
    standing_authorizations: [],
    approval_satisfactions: [],
    ranking: {policy_version: "v1", eligible_option_ids: [], infeasible_option_ids: [], excluded_baseline_ids: [], stages: [], recommended_option_id: null, no_feasible_mitigation: true},
    calculation_version: "v1",
    evidence_policy_version: "v1",
    approval_policy_version: "v1",
  },
  evidence_items: [evidence],
  evidence_validation: {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: [validationResult]},
  response_options: [],
  approval_satisfactions: [],
  ranking: {policy_version: "v1", eligible_option_ids: [], infeasible_option_ids: [], excluded_baseline_ids: [], stages: [], recommended_option_id: null, no_feasible_mitigation: true},
  recommendation: null,
};

it("shows recorded UTC time without claiming ongoing monitoring", () => {
  const {container, rerender} = render(<EvidenceFooter status={{
    platform: "Work IQ", retrieval: "Retrieved for this analysis",
    recordedAt: "2026-09-08T15:00:00Z", validation: "Evidence policy checks passed",
    warning: null,
  }} />);
  expect(screen.getByText("Work IQ")).toBeInTheDocument();
  expect(container.querySelector("time")).toHaveAttribute("datetime", "2026-09-08T15:00:00Z");
  expect(container.textContent).toContain("UTC");
  expect(container.textContent).not.toMatch(/Checking now|certain|healthy/);
  rerender(<EvidenceFooter status={{platform: "Synthetic fixture",
    retrieval: "Demo fixture — not a live retrieval", recordedAt: null,
    validation: "Fixture evidence", warning: null}} />);
  expect(container.querySelector("time")).toBeNull();
});

it("renders fractional UTC timestamps and omits a missing timestamp", () => {
  const {container, rerender} = render(<EvidenceFooter status={{
    platform: "Work IQ", retrieval: "Retrieved for this analysis",
    recordedAt: "2026-09-08T15:00:00.125Z", validation: "Evidence policy checks passed", warning: null,
  }} />);
  expect(container.querySelector("time")).toHaveAttribute("datetime", "2026-09-08T15:00:00.125Z");
  expect(container.querySelector("time")).toHaveTextContent("Sep 8, 2026, 3:00 PM UTC");
  rerender(<EvidenceFooter status={{platform: "Work IQ", retrieval: "Retrieval not verified for this analysis", recordedAt: null, validation: "Validation result unavailable", warning: "Retrieval time unavailable or outside this analysis"}} />);
  expect(container.querySelector("time")).toBeNull();
});

it("places the citation before the footer and keeps warnings beside the claim", () => {
  const {container, rerender} = render(<EvidencePanel analysis={analysis} tenantSharePointHost="tenant.sharepoint.com" />);
  const article = container.querySelector("article");
  const citation = screen.getByRole("link", {name: "Open supplier email"});
  const footer = screen.getByRole("contentinfo", {name: "Source and evidence status"});
  expect(article?.lastElementChild).toBe(footer);
  expect(citation.compareDocumentPosition(footer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  const recorded = container.querySelector("time")?.getAttribute("datetime");

  rerender(<EvidencePanel analysis={{...analysis, evidence_items: [{...evidence, retrieved_for_analysis_id: "OLD-ANALYSIS"}]}} tenantSharePointHost="tenant.sharepoint.com" />);
  const warning = screen.getByRole("alert", {name: ""});
  expect(warning).toHaveTextContent("Source does not match this analysis");
  expect(screen.getByRole("heading", {name: evidence.claim}).nextElementSibling).toContainElement(warning);
  expect(warning).toBeVisible();
  const mismatchFooter = screen.getByRole("contentinfo", {name: "Source and evidence status"});
  expect(warning.compareDocumentPosition(mismatchFooter) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  rerender(<EvidencePanel analysis={analysis} tenantSharePointHost="tenant.sharepoint.com" />);
  expect(container.querySelector("time")).toHaveAttribute("datetime", recorded);
});

it("does not substitute the evidence ID when the source record ID is blank", () => {
  render(<EvidencePanel analysis={{...analysis, evidence_items: [{...evidence, source_id: "  "}]}} tenantSharePointHost="tenant.sharepoint.com" />);
  expect(screen.getByText("Source record ID").nextElementSibling).toHaveTextContent("Unavailable");
  expect(screen.getByText("Evidence ID").nextElementSibling).toHaveTextContent("E-1");
});
