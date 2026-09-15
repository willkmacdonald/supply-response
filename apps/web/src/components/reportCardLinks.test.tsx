// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import type {AnalysisVersion, CaseInstance, EvidenceItem, ResponseOption, RuntimeStatus} from "../types";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {recordFixture, editSnapshot} from "./supportingRecord.fixture";
import {CaseHeader} from "./CaseHeader";
import {InvestigationFlow} from "./InvestigationFlow";
import {reportIdentityKey} from "../reporting/reportNavigation";

afterEach(() => {cleanup(); vi.unstubAllGlobals();});
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {configurable: true, value: function () { this.setAttribute("open", ""); }});
  Object.defineProperty(HTMLDialogElement.prototype, "close", {configurable: true, value: function () { this.removeAttribute("open"); }});
});
const base = "https://app.powerbi.com/groups/dc3ac590-d892-40a7-9388-65dec120d67a/reports/e7611c8c-c887-443f-858a-13b1044bb4b9";
const runtime: RuntimeStatus = {
  runtime_mode: "live", work_iq: "work_iq", operational_store: "fabric_sql",
  agent_runtime: "foundry", power_bi_available: true, power_bi_url: base,
  deployment_contract: {power_bi_reporting_contract: "saved-analysis-v1"},
};
const caseFilter = "CaseCommandCenter/case_key eq '63006100730065002D003100'";
const analysisFilter = "SavedAnalyses/analysis_key eq '61006E0061006C0079007300690073002D003100'";
const exact = `${caseFilter} and ${analysisFilter}`;
const emailUrl = "https://outlook.office.com/mail/deeplink/read/mail-id";
const teamsUrl = "https://teams.microsoft.com/l/message/19%3Ademo%40thread.tacv2/1788577543694?groupId=11111111-2222-3333-4444-555555555555&tenantId=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee&createdTime=1788577543694&parentMessageId=1788577543694";
function option(option_id: string, baseline = false): ResponseOption {
  return {option_id, option_kind: baseline ? "no_mitigation" : "combined", name: option_id,
    executable: !baseline, active_mitigation: !baseline,
    predicted: {uncovered_part_demand: 0, otif_loss_percentage: 0, revenue_at_risk: "0.00",
      margin_at_risk: "0.00", response_cost: "0.00", protected_customer_order_ids: ["line-1"]},
    assumptions: [], evidence_ids: [], evidence_requirements: [], blocking_codes: [],
    prerequisite_roles: [], source_data_lineage: [], approval_burden: 0, execution_risk: 0,
    requested_side_effects: []};
}
function fixture(): CaseWorkspaceState {
  const input = recordFixture(); const at = input.analysis.created_at;
  const seed = input.analysis.evidence_items[0];
  const items: EvidenceItem[] = [
    ["RL-ALPHA-OPTIONAL-3000", "fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000"],
    ["RL-TRANSFER-DAL-CHI-1500", "fabric.inventory_transfer/RL-TRANSFER-DAL-CHI-1500"],
    ["RL-QUALITY-001", "fabric.qualification/RL-QUAL-BETA"],
  ].map(([evidence_id, source_id]) => ({...seed, evidence_id, source_id,
    authority_scope: ["operational_quantity"], effective_at: null, expires_at: null,
    claim: "Saved record", excerpt: null, citation_url: base, navigable_citation_url: base,
    citation_classification: "fabric", retrieval_health: "healthy",
    requirement: "required_authoritative", uncertainty_state: "certain"}));
  items.push({...items[0], evidence_id: "email", source_system: "work_iq", kind: "source_statement",
    source_id: "mail-id", authority_scope: ["supplier_statement"], claim: "Supplier statement",
    excerpt: "Original supplier words", citation_url: emailUrl, navigable_citation_url: emailUrl,
    citation_classification: "work_iq"});
  items.push({...items[3], evidence_id: "teams", source_id: "teams-id",
    authority_scope: ["collaboration_statement"], claim: "Quality statement",
    excerpt: "Original Quality words", citation_url: teamsUrl, navigable_citation_url: teamsUrl});
  editSnapshot(input, s => {
    s.disruption = {disruption_id: "d", supplier_id: "RL-SUP-ALPHA", po_line_id: "po",
      part_id: "RL-MAT-10247", plant_id: "RL-PLANT-CHI", original_quantity: 8000,
      original_due_date: "2026-09-03", partial_quantity: 3000, partial_due_date: "2026-09-06",
      recovery_date: null, source_ref: "RL-001"};
    s.inventory_positions = [{inventory_id: "i", part_id: "RL-MAT-10247", plant_id: "RL-PLANT-CHI",
      on_hand: 500, quality_hold: 200, protected_allocation: 300}];
    s.production_orders = [{production_order_id: "production-1", product_id: "product-1",
      plant_id: "RL-PLANT-CHI", quantity: 1, due_date: "2026-09-03", component_demand: 1,
      customer_order_id: "line-1", customer_revenue: "100.00"}];
    s.customer_orders = [{customer_order_line_id: "line-1", production_order_id: "production-1",
      customer_id: "customer-1", product_id: "product-1", plant_id: "RL-PLANT-CHI", quantity: 1,
      due_date: "2026-09-03", unit_revenue: "100.00"}];
  });
  const options = [option("baseline", true), option("Option-A"), option("Option-B")];
  const ranking = {policy_version: "v1", eligible_option_ids: ["Option-A", "Option-B"],
    infeasible_option_ids: [], excluded_baseline_ids: ["baseline"], stages: [],
    recommended_option_id: "Option-A", no_feasible_mitigation: false};
  const validation = {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: []};
  const caseInstance: CaseInstance = {...input.caseInstance, purpose: "showcase",
    scenario_timezone: "America/Chicago", status: "awaiting_decision", current_analysis_id: "newer",
    current_decision_id: null, display_status: null, recorded_at: at, projection_updated_at: at,
    controls: {new_analysis: false, decide: true, retry_action_planning: false, start_playback: false}};
  const analysis: AnalysisVersion = {...input.analysis, analysis_started_at: at, retrieval_window_ends_at: at,
    material_hash: "hash", evidence_items: items, evidence_validation: validation,
    response_options: options, approval_satisfactions: [], ranking, recommendation: options[1],
    material: {...input.analysis.material, case_purpose: "showcase", required_authority_scope: [],
      evidence: items.map(item => ({...item, citation_present: true, source_metadata_complete: true,
        validation: {evidence_id: item.evidence_id, requirement: item.requirement,
          validated_authority_scope: item.authority_scope, freshness: "current", business_validity: "valid",
          uncertainty_state: "certain", retrieval_health: "healthy", authoritative: true, blocking_codes: []}})),
      conflicts: [], conflict_resolutions: [], evidence_validation: validation, response_options: options,
      standing_authorizations: [], approval_satisfactions: [], ranking, calculation_version: "v1",
      evidence_policy_version: "v1", approval_policy_version: "v1"}};
  return {runtime, caseInstance, analysis, selectedOption: null, decision: null, actions: [], drafts: [], supplierEmail: null,
    playback: null, observations: [], operation: null, error: null, existingCases: null, existingCasesError: null, decisionBlocked: true,
    create: vi.fn(), loadExistingCases: vi.fn(), reopen: vi.fn(), analyze: vi.fn(), selectOption: vi.fn(), approve: vi.fn(), reject: vi.fn(),
    retryPlanning: vi.fn(), retryAction: vi.fn(), startPlayback: vi.fn(), saveSupplierEmail: vi.fn(),
    reviewSupplierEmail: vi.fn(), sendSupplierEmail: vi.fn(), checkSupplierEmail: vi.fn()};
}
function expectDestination(label: string, page: string, filter: string) {
  const link = screen.getByRole("link", {name: label});
  const url = new URL(link.getAttribute("href")!);
  expect(url.origin + url.pathname).toBe(base + "/" + page);
  expect(url.searchParams.get("filter")).toBe(filter);
  expect([...url.searchParams.keys()]).toEqual(["filter"]);
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
}
function header(s: CaseWorkspaceState) {
  return <CaseHeader runtime={s.runtime} caseInstance={s.caseInstance} analysis={s.analysis}
    createPurpose="showcase" creating={false} analyzing={false} onCreate={s.create} onAnalyze={s.analyze} />;
}
async function selectStage(name: "2. Investigate responses" | "3. Choose a response") {
  await userEvent.click(screen.getByRole("tab", {name}));
}
it("never mounts the redundant exact-case dashboard link in the header", () => {
  const s = fixture(); const {rerender} = render(header(s));
  expect(screen.queryByRole("link", {name: "Open case dashboard"})).not.toBeInTheDocument();
  s.analysis = null; rerender(header(s));
  expect(screen.queryByRole("link", {name: "Open case dashboard"})).not.toBeInTheDocument();
  s.analysis = fixture().analysis; s.analysis!.case_id = "other"; rerender(header(s));
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  s.caseInstance = null; rerender(header(s));
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
it.each([
  {...runtime, deployment_contract: null},
  {...runtime, deployment_contract: {power_bi_reporting_contract: "old"}},
  {...runtime, power_bi_available: false},
  {...runtime, runtime_mode: "fallback" as const},
  {...runtime, power_bi_url: base + "?filter=old"},
  {...runtime, power_bi_url: "https://app.powerbi.com/groups/demo/reports/report"},
])("suppresses every report anchor without a usable release and base: %j", async unavailableRuntime => {
  const s = fixture(); s.runtime = unavailableRuntime;
  render(<>{header(s)}<InvestigationFlow state={s} /></>);
  expect(screen.queryByRole("link", {name: /Power BI|case dashboard/})).not.toBeInTheDocument();
  expect(screen.getByRole("link", {name: "Open supplier email"})).toBeVisible();
  await selectStage("2. Investigate responses");
  expect(screen.getByRole("link", {name: "Open supplier email"})).toBeVisible();
});
it("mounts all three exact records and retains original sources, inline inspection and footer order", async () => {
  const s = fixture(); const before = JSON.stringify(s.analysis); const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  render(<InvestigationFlow state={s} />);
  const firstEmail = screen.getByRole("link", {name: "Open supplier email"});
  expect(firstEmail).toHaveAttribute("href", emailUrl);
  await selectStage("2. Investigate responses");
  for (const [kind, page, id] of [
    ["shipment", "supplier-shipment", "RL-ALPHA-OPTIONAL-3000"],
    ["transfer", "plant-transfer", "RL-TRANSFER-DAL-CHI-1500"],
    ["qualification", "supplier-qualification", "RL-QUAL-BETA"],
  ]) {
    expectDestination(`Explore ${kind} in Power BI`, page,
      `${exact} and SavedRecords/record_family eq '${kind}' and SavedRecords/record_key eq '${reportIdentityKey(id)}'`);
    const link = screen.getByRole("link", {name: `Explore ${kind} in Power BI`});
    expect(link.closest("details")).toBeNull();
    const card = link.closest("article")!;
    expect(card.lastElementChild).toHaveClass("source-footers");
    await userEvent.click(within(card).getByText(`View ${kind} record`));
    expect(within(card).getByText("Snapshot used for this analysis")).toBeVisible();
  }
  expect(screen.getByRole("link", {name: "Open supplier email"})).toHaveAttribute("href", emailUrl);
  expect(screen.getByRole("link", {name: "Open Quality Teams post"})).toHaveAttribute("href", teamsUrl);
  expect(fetch).not.toHaveBeenCalled(); expect(JSON.stringify(s.analysis)).toBe(before);
  expect(s.approve).not.toHaveBeenCalled(); expect(s.reject).not.toHaveBeenCalled();
});
it("requires linked saved orders and preserves valid zero stock", () => {
  const s = fixture(); const {rerender} = render(<InvestigationFlow state={s} />);
  expectDestination("Explore available stock in Power BI", "available-stock", exact);
  expectDestination("Explore affected customer orders in Power BI", "customer-orders", exact);
  expect(screen.getByText("0 component units available after holds and protected allocations.")).toBeVisible();
  const input = {caseInstance: s.caseInstance!, analysis: s.analysis!};
  editSnapshot(input, snapshot => {
    snapshot.customer_orders[0].plant_id = "RL-PLANT-DAL";
    snapshot.production_orders[0].plant_id = "RL-PLANT-DAL";
  });
  rerender(<InvestigationFlow state={s} />);
  expectDestination("Explore affected customer orders in Power BI", "customer-orders", exact);
  editSnapshot(input, snapshot => {snapshot.customer_orders[0].production_order_id = "unlinked";});
  rerender(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: "Explore affected customer orders in Power BI"})).not.toBeInTheDocument();
  editSnapshot(input, snapshot => {snapshot.customer_orders[0].production_order_id = "production-1"; snapshot.production_orders = [];});
  rerender(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: "Explore affected customer orders in Power BI"})).not.toBeInTheDocument();
  editSnapshot(input, snapshot => {snapshot.inventory_positions[0].plant_id = "OTHER";});
  rerender(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: "Explore available stock in Power BI"})).not.toBeInTheDocument();
});
it("preserves selected and recommended option identities independently", async () => {
  const s = fixture(); const {rerender} = render(<InvestigationFlow state={s} />);
  await selectStage("3. Choose a response");
  const optionA = `${exact} and SavedOptions/option_key eq '4F007000740069006F006E002D004100'`;
  const optionB = `${exact} and SavedOptions/option_key eq '4F007000740069006F006E002D004200'`;
  expectDestination("Explore response options in Power BI", "response-options", exact);
  await userEvent.click(screen.getByRole("button", {name: "Click here to understand why"}));
  expectDestination("Explore recommended response in Power BI", "response-options", optionA);
  s.selectedOption = s.analysis!.response_options[2]; rerender(<InvestigationFlow state={s} />);
  expectDestination("Explore response options in Power BI", "response-options", optionB);
  expectDestination("Explore recommended response in Power BI", "response-options", optionA);
  s.selectedOption = option("foreign"); rerender(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: "Explore response options in Power BI"})).not.toBeInTheDocument();
  s.analysis!.recommendation = s.analysis!.response_options[2]; rerender(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: "Explore recommended response in Power BI"})).not.toBeInTheDocument();
});
it("hides record links for wrong retrieval identity and all links for malformed envelope", async () => {
  const s = fixture(); s.analysis!.evidence_items[0].retrieved_for_analysis_id = "other";
  const {rerender} = render(<InvestigationFlow state={s} />);
  await selectStage("2. Investigate responses");
  expect(screen.queryByRole("link", {name: "Explore shipment in Power BI"})).not.toBeInTheDocument();
  expect(screen.getByRole("link", {name: "Explore transfer in Power BI"})).toBeVisible();
  s.analysis!.material.operational_snapshot_json = "{"; rerender(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: /Power BI/})).not.toBeInTheDocument();
  expect(screen.getAllByRole("heading", {level: 3})).toHaveLength(3);
  await selectStage("3. Choose a response");
  await userEvent.click(screen.getByRole("tab", {name: "4. Review and approve"}));
  expect(screen.getByRole("button", {name: "Approve selected response"})).toBeDisabled();
});
it("does not describe unavailable live reporting as fallback mode", () => {
  const s = fixture();
  s.runtime = {...runtime, power_bi_available: false};
  const {rerender} = render(header(s));
  expect(screen.getByText("Power BI report is not available")).toBeVisible();
  expect(screen.queryByText("Power BI unavailable in fallback")).not.toBeInTheDocument();
  s.runtime = {...s.runtime, runtime_mode: "fallback"};
  rerender(header(s));
  expect(screen.getByText("Power BI unavailable in fallback")).toBeVisible();
});
