// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import type {AnalysisVersion, CaseInstance, EvidenceItem} from "../types";
import {editSnapshot, recordFixture} from "./supportingRecord.fixture";
import {InvestigationEvidence} from "./InvestigationEvidence";
afterEach(() => {cleanup(); vi.unstubAllGlobals();});

function fixture(): {caseInstance: CaseInstance; analysis: AnalysisVersion} {
  const input = recordFixture(); const a = input.analysis; const at = a.created_at;
  const ranking = {policy_version: "v1", eligible_option_ids: [], infeasible_option_ids: [],
    excluded_baseline_ids: [], stages: [], recommended_option_id: null, no_feasible_mitigation: true};
  const validation = {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: []};
  const items: EvidenceItem[] = a.evidence_items.map(item => ({...item, authority_scope: ["operational_quantity"],
    effective_at: null, expires_at: null, claim: "Record statement", excerpt: null,
    citation_url: "https://app.powerbi.com/groups/demo/reports/report", citation_classification: "fabric",
    navigable_citation_url: "https://app.powerbi.com/groups/demo/reports/report", retrieval_health: "healthy",
    requirement: "required_authoritative", uncertainty_state: "certain"}));
  items.push({...items[0], evidence_id: "email", kind: "source_statement", source_system: "work_iq",
    source_id: "mail-id", authority_scope: ["supplier_statement"], claim: "Supplier statement",
    excerpt: "Original Alpha words, including $7.50 and unconfirmed timing.",
    citation_url: "https://outlook.office.com/mail/deeplink/read/mail-id",
    navigable_citation_url: "https://outlook.office.com/mail/deeplink/read/mail-id", citation_classification: "work_iq"});
  return {caseInstance: {...input.caseInstance, purpose: "showcase", scenario_timezone: "America/Chicago",
    status: "awaiting_decision", current_analysis_id: "newer", current_decision_id: null, display_status: null,
    recorded_at: at, projection_updated_at: at,
    controls: {new_analysis: false, decide: true, retry_action_planning: false, start_playback: false}},
    analysis: {...a, analysis_started_at: at, retrieval_window_ends_at: at, material_hash: "hash",
      evidence_items: items, evidence_validation: validation, response_options: [], approval_satisfactions: [], ranking, recommendation: null,
      material: {...a.material, case_purpose: "showcase", required_authority_scope: [], conflicts: [], conflict_resolutions: [],
        evidence: items.map(item => ({...item, citation_present: true, source_metadata_complete: true,
          validation: {evidence_id: item.evidence_id, requirement: item.requirement, validated_authority_scope: item.authority_scope,
            freshness: "current", business_validity: "valid", uncertainty_state: "certain", retrieval_health: "healthy",
            authoritative: true, blocking_codes: []}})), evidence_validation: validation, response_options: [], standing_authorizations: [],
        approval_satisfactions: [], ranking, calculation_version: "v1", evidence_policy_version: "v1", approval_policy_version: "v1"}}};
}

it("keeps the supplier delay first when snapshot fields are unavailable", () => {
  const input = fixture(); render(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getAllByRole("heading", {level: 3}).map(h => h.textContent)).toEqual(["What changed?", "What do we have available?", "What does that put at risk?"]);
  const first = screen.getAllByRole("article")[0];
  expect(within(first).getByText("Original Alpha words, including $7.50 and unconfirmed timing.")).toBeInTheDocument();
  expect(within(first).getByRole("link", {name: "Open supplier email"})).toHaveAttribute("href", input.analysis.evidence_items[1].citation_url);
  expect(within(first).getByText("Saved disruption details unavailable")).toBeVisible();
});
it("combines inline shipment inspection and the original supplier email without external Fabric navigation", async () => {
  const input = fixture(); const before = JSON.stringify(input); const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  render(<InvestigationEvidence {...input} row="responses" />); const alpha = screen.getAllByRole("article")[0];
  expect(within(alpha).getByText("Scheduled receipt: 3,000 component units on September 6, 2026.")).toBeVisible();
  await userEvent.click(within(alpha).getByText("View shipment record"));
  expect(within(alpha).getByText("Snapshot used for this analysis")).toBeVisible();
  expect(within(alpha).getByRole("link", {name: "Open supplier email"})).toBeVisible();
  expect(screen.queryByRole("link", {name: "Open citation"})).not.toBeInTheDocument();
  expect(screen.getAllByRole("link").every(link => !link.getAttribute("href")?.includes("powerbi"))).toBe(true);
  const footerGroup = alpha.querySelector(".source-footers")!; expect(alpha.lastElementChild).toBe(footerGroup);
  expect(fetch).not.toHaveBeenCalled(); expect(JSON.stringify(input)).toBe(before);
});
it("shows unmatched source warnings rather than hiding failed or unsupported evidence", () => {
  const input = fixture(); input.analysis.evidence_items[1].authority_scope = []; input.analysis.evidence_items[1].retrieval_health = "unhealthy";
  render(<InvestigationEvidence {...input} row="responses" />);
  expect(screen.getByText("Additional source context")).toBeVisible();
  expect(screen.getByText("Original Alpha words, including $7.50 and unconfirmed timing.")).toBeInTheDocument();
});
it("shows stock after holds including zero and uses baseline exposure instead of recommendation exposure", () => {
  const input = fixture(); editSnapshot(input, s => {
    s.disruption = {disruption_id: "d", supplier_id: "RL-SUP-ALPHA", po_line_id: "po", part_id: "p", plant_id: "RL-PLANT-CHI", original_quantity: 8000, original_due_date: "2026-09-03", partial_quantity: 0, partial_due_date: null, recovery_date: null, source_ref: "RL-001"};
    s.inventory_positions = [{inventory_id: "i", part_id: "p", plant_id: "RL-PLANT-CHI", on_hand: 4500, quality_hold: 200, protected_allocation: 300}];
  });
  const baseline: NonNullable<AnalysisVersion["recommendation"]> = {option_id: "baseline", option_kind: "no_mitigation", name: "Baseline", executable: false, active_mitigation: false,
    predicted: {uncovered_part_demand: 6800, otif_loss_percentage: 100, revenue_at_risk: "955000.00", margin_at_risk: "328000.00", response_cost: "0.00", protected_customer_order_ids: []},
    assumptions: [], evidence_ids: [], evidence_requirements: [], blocking_codes: [], prerequisite_roles: [], source_data_lineage: [], approval_burden: 0, execution_risk: 0, requested_side_effects: []};
  input.analysis.response_options = [baseline]; input.analysis.recommendation = {...baseline, option_id: "combined", option_kind: "combined", predicted: {...baseline.predicted!, uncovered_part_demand: 2300}};
  const {rerender} = render(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getByText("4,000 component units available after holds and protected allocations.")).toBeVisible();
  expect(screen.getByText("6,800 p component units")).toBeVisible(); expect(screen.queryByText("2,300 p component units")).not.toBeInTheDocument();
  editSnapshot(input, s => { s.inventory_positions[0].on_hand = 500; }); rerender(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getByText("0 component units available after holds and protected allocations.")).toBeVisible();
  editSnapshot(input, s => { s.inventory_positions[0].on_hand = 0; }); rerender(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getByText("Holds and protected allocations exceed on-hand stock in this snapshot.")).toBeVisible();
});
it("does not subtract a late partial delivery from the original affected delivery", () => {
  const input = fixture(); editSnapshot(input, s => { s.disruption = {disruption_id: "d", supplier_id: "RL-SUP-ALPHA", po_line_id: "po", part_id: "RL-MAT-10247", plant_id: "RL-PLANT-CHI", original_quantity: 8000, original_due_date: "2026-09-03", partial_quantity: 3000, partial_due_date: "2026-09-06", recovery_date: null, source_ref: "RL-001"}; });
  render(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getByText(/Original delivery affected: 8,000 component units/)).toBeVisible();
  expect(screen.getByText(/Recorded partial supply: 3,000 units; date: September 6, 2026/)).toBeVisible();
  expect(screen.queryByText(/Missed quantity.*5,000/)).not.toBeInTheDocument();
});
it("does not place a different supplier's saved shipment under the Supplier Alpha mapping", () => {
  const input = fixture(); editSnapshot(input, s => { s.alpha_expedite.supplier_id = "OTHER-SUPPLIER"; });
  render(<InvestigationEvidence {...input} row="responses" />);
  expect(screen.queryByText("View shipment record")).not.toBeInTheDocument(); expect(screen.queryByText(/Scheduled receipt: 3,000/)).not.toBeInTheDocument(); expect(screen.getByText("Additional source context")).toBeVisible();
});
it("does not place a transfer from a different plant under the Dallas plant mapping", () => {
  const input = fixture(); const record = input.analysis.evidence_items[0]; record.evidence_id = "RL-TRANSFER-DAL-CHI-1500"; record.source_id = "fabric.inventory_transfer/RL-TRANSFER-DAL-CHI-1500";
  input.analysis.material.evidence[0] = {...input.analysis.material.evidence[0], evidence_id: record.evidence_id, source_id: record.source_id}; editSnapshot(input, s => { s.transfer.source_plant_id = "OTHER-PLANT"; });
  render(<InvestigationEvidence {...input} row="responses" />); expect(screen.queryByText("View transfer record")).not.toBeInTheDocument(); expect(screen.queryByText("Dallas plant to Chicago plant")).not.toBeInTheDocument();
});
it("does not attribute an out-of-scenario authority-scoped source to Supplier Alpha", () => {
  const input = fixture(); input.analysis.material.corpus = "real_business"; render(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.queryByText("Supplier email — RL-Supplier Alpha — Current supplier")).not.toBeInTheDocument(); expect(screen.getByText("Supplier email unavailable for this analysis")).toBeVisible();
});
