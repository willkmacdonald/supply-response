# Mounted exact report card links implementation plan

> For agentic workers: Implement this one reviewed task using superpowers:subagent-driven-development and test-driven-development. No deployment, walkthrough or return-to-app behavior is authorized by this task.

**Goal:** Mount exact, fail-closed Power BI links on the approved investigation cards and case header without changing source inspection or decision behavior.

**Architecture:** Reuse `reporting/reportNavigation.ts` as the sole URL builder. Reuse `readPlannerSnapshot`, `parseSnapshotEnvelope`, and `SupportingRecordResult.context` as existing validation boundaries. Pass the mounted runtime and exact displayed analysis through existing components; do not infer record identities from labels, citation URLs, or current-analysis pointers.

**Tech stack:** React, TypeScript, Vitest, Testing Library, jsdom.

## Global constraints

Execution: implemented in `5a6ca60`; independently approved with no findings.
The obsolete header safety test was migrated as authorized below. Full web suite:
204 passed; production build passed. Controller browser checks passed all twelve
desktop/mobile variants, checking exact destinations, header contrast/focus,
source preservation, keyboard disclosures, no extra requests and no overflow.
Desktop/mobile response-row screenshots were inspected. Index-only `cecc1ef`
keeps the local scratch report ignored. Native Power BI/DAX/access acceptance
is still a coordinated release gate; no live changes were made.

- Scope is stage 4 frontend mounting only, from `docs/superpowers/specs/2026-09-08-evidence-records-and-case-dashboard-design.md`.
- Every external anchor uses `target="_blank" rel="noopener noreferrer"`.
- The separately verified API release may expose `deployment_contract.power_bi_reporting_contract = "saved-analysis-v1"`. Absent/other contract means no report links, even with a valid legacy report URL. Do not add a frontend default or activate the contract here.
- Preserve original supplier email and Quality Teams URLs, excerpts, inline details, footers as the last card child, warning messages, selection, approval, rejection, and execution callbacks.
- Preserve immutable snapshots and stored legacy citation metadata. Do not expose the generic report as a fallback.
- No new fetch, refresh, approval, execution, or report availability probe. Report refresh readiness is not inferable from this runtime contract; do not claim a specific analysis is already loaded into Power BI.
- `RuntimeStatus.deployment_contract` already supports the optional contract string. No API/type-model changes are necessary.

## Files and precise responsibilities

| File | Change |
| --- | --- |
| `apps/web/src/App.tsx` | Pass `analysis={workspace.analysis}` into the mounted header. |
| `apps/web/src/components/CaseHeader.tsx` | Replace generic trusted-URL report link with exact builder; accept displayed analysis. |
| `apps/web/src/components/InvestigationFlow.tsx` | Pass runtime to evidence cards; derive a matching analysis report context from the validated snapshot and pass it with runtime into comparison/recommendation. |
| `apps/web/src/components/InvestigationEvidence.tsx` | Accept optional runtime; mount stock/orders links and pass runtime to existing supporting-record details. |
| `apps/web/src/components/SupportingRecordDetails.tsx` | Append distinct external record anchor after existing inline details, using available live result context. |
| `apps/web/src/components/OptionComparison.tsx` | Mount exact analysis comparison link, including selected option when validated in that analysis. |
| `apps/web/src/components/ExposurePanel.tsx` | Mount exact recommended-option link using the already unambiguous resolved option. |
| `apps/web/src/reporting/reportNavigation.ts` | Export the small shared context type below; builder behavior remains unchanged. |
| New `apps/web/src/components/reportCardLinks.test.tsx` | Complete shared offline fixture and mounted header/flow positive, negative, and regression coverage provided below. Existing tests remain unchanged. |

### Task 1: Mount exact report links

- [x] Create the complete `reportCardLinks.test.tsx` supplied below. Run `cd apps/web && npx vitest run src/components/reportCardLinks.test.tsx` and observe missing mounted-link assertions fail. Use this one test file throughout the task.

### Code step A: exact header navigation
- [x] Add required `analysis: AnalysisVersion | null` to `CaseHeaderProps` and its destructuring. Import `AnalysisVersion`, `buildReportUrl`, and `parseSnapshotEnvelope`; remove the unused `trustedMicrosoftUrl` import. Replace `powerBiUrl` initialization with:

```ts
const matchingAnalysis = caseInstance && analysis
  ? parseSnapshotEnvelope({caseInstance, analysis}) !== null
  : false;
const powerBiUrl = runtime && caseInstance && (!analysis || matchingAnalysis)
  ? buildReportUrl(runtime, {
      page: "command-center",
      caseId: caseInstance.case_id,
      runtimeMode: caseInstance.runtime_mode,
      ...(analysis ? {analysisId: analysis.analysis_id} : {}),
    })
  : null;
```

- [x] Change only anchor text to `Open case dashboard`; add `analysis={workspace.analysis}` in `App.tsx`.
Case-only overview is allowed when there is no displayed analysis; if an analysis is present but mismatched or malformed, hide the link rather than falling back to a case-only overview. Historical displayed analysis uses its ID even when `current_analysis_id` is newer.

### Code step B: card wiring and exact record anchors

- [x] Export this type in `reportNavigation.ts`, immediately following `ReportTarget`:

```ts
export type ReportAnalysisContext = Pick<
  Extract<ReportTarget, {page: "response-options"}>,
  "caseId" | "analysisId" | "runtimeMode"
>;
```

- [x] `InvestigationFlow`: include `runtime: state.runtime` in existing evidence `props`. After reading `snapshot`, derive:

```ts
const reportContext = snapshot ? {
  caseId: analysis.case_id,
  analysisId: analysis.analysis_id,
  runtimeMode: analysis.runtime_mode,
} : null;
```

Pass `runtime={state.runtime} reportContext={reportContext}` to `OptionComparison` and `ExposurePanel`. Keep their existing analysis, snapshot, selection, and callbacks unchanged.

- [x] `InvestigationEvidence`: add `runtime?: RuntimeStatus | null` (default `null`) to props/destructuring; import `buildReportUrl`. Add `runtime={runtime}` to all three existing `SupportingRecordDetails` invocations. Do not change the existing unique-selection and scenario-mapping logic.
- [x] `SupportingRecordDetails`: add optional `runtime?: RuntimeStatus | null` defaulting to null. Keep early unavailable return. Immediately after `const r = result.record`, add:

```ts
const page = r.kind === "shipment" ? "supplier-shipment"
  : r.kind === "transfer" ? "plant-transfer" : "supplier-qualification";
const reportUrl = runtime && result.context.runtimeMode === "live"
  && result.provenance === "Saved Microsoft Fabric record"
  ? buildReportUrl(runtime, {
      page,
      caseId: result.context.caseId,
      analysisId: result.context.analysisId,
      recordId: result.context.recordId,
      runtimeMode: result.context.runtimeMode,
    })
  : null;
```

Wrap the existing outer `<details>...</details>` return in a fragment and append this sibling before closing the fragment:

```tsx
{reportUrl && <a href={reportUrl} target="_blank" rel="noopener noreferrer">
  Explore {r.kind} in Power BI
</a>}
```

The anchor is visible with inline details collapsed, remains inside the originating card, and precedes the card footer. Qualification uses `RL-QUAL-BETA` from context, never its distinct evidence reference `RL-QUALITY-001`.

### Code step C: snapshot and response anchors

- [x] In the disruption branch of `InvestigationEvidence`, after existing `baselines`, derive:

```ts
const analysisTarget = {
  caseId: analysis.case_id, analysisId: analysis.analysis_id,
  runtimeMode: analysis.runtime_mode,
};
const stockUrl = runtime && snapshot && d && inventory?.length && safeTotals
  ? buildReportUrl(runtime, {...analysisTarget, page: "available-stock"}) : null;
const hasLinkedOrders = snapshot?.customers?.some(customer =>
  snapshot.production?.some(production =>
    customer.production_order_id === production.production_order_id));
const ordersUrl = runtime && snapshot && d && hasLinkedOrders
  && baselines.length === 1
  ? buildReportUrl(runtime, {...analysisTarget, page: "customer-orders"}) : null;
```

Append `Explore available stock in Power BI` and `Explore affected customer orders in Power BI` anchors to their respective card content fragments, with the standard external attributes and conditional URLs. Place orders anchor after its existing details, stock after existing record snapshot paragraph. Keep the existing baseline basis visible. The customer-orders report contract selects the baseline for this destination; do not append an option filter unsupported by its builder target. If report work changes that baseline contract, resolve that with the parent before mounting orders.

Stock uses the existing exact plant/part inventory subset, valid typed records, nonempty matching inventory, and safe totals, preserving valid zero availability. Orders require at least one validated customer/production pair joined by production ID across all saved production rows, plus a unique baseline in the matching saved analysis. This matches SQL `in_disruption_scope`: do not add a disruption-plant restriction. Empty production or unlinked customer rows do not yield a useful report destination. Neither gate uses `current_analysis_id` or unvalidated raw JSON.

- [x] Add optional `runtime?: RuntimeStatus | null` and `reportContext?: ReportAnalysisContext | null` defaulting to null to both decision display components, importing both types and `buildReportUrl`. Derive the following in `OptionComparison` after its early return:

```ts
const matchesSelection = selectedOption === null
  || analysis.response_options.filter(option => option.option_id === selectedOption.option_id).length === 1;
const matchingContext = reportContext?.caseId === analysis.case_id
  && reportContext?.analysisId === analysis.analysis_id
  && reportContext?.runtimeMode === analysis.runtime_mode;
const reportUrl = runtime && reportContext && matchingContext && matchesSelection
  ? buildReportUrl(runtime, {
      ...reportContext, page: "response-options",
      ...(selectedOption ? {optionId: selectedOption.option_id} : {}),
    }) : null;
```

Append the conditional anchor `Explore response options in Power BI` immediately before the existing footer. A selected ID absent from or duplicated in this analysis hides the link. An unselected comparison contains only case and analysis filters. Use no option name or ranking fallback to repair an invalid selection.

- [x] In `ExposurePanel`, use the same `matchingContext` expression and the already resolved local `option`:

```ts
const reportUrl = runtime && reportContext && matchingContext && option
  ? buildReportUrl(runtime, {...reportContext, page: "response-options", optionId: option.option_id})
  : null;
```

Append `Explore recommended response in Power BI` immediately before its existing footer. Preserve the existing unique-ranking/recommendation agreement gate. Changing the user's selected option does not change this recommendation destination.

### Supplemental acceptance review (not additional implementation tasks)

The supplied shared test file below is the complete new test deliverable. These additional considerations guide parent review; they are not unimplemented test-writing steps and are not claims of newly executed coverage:

- Existing `reportNavigation.test.ts` covers URL canonicalization, missing contract, unknown contract, invalid identities, exact encoding, and record-family mapping.
- Existing supporting-record and snapshot tests cover malformed field types, source/evidence/case/runtime agreement, duplicate IDs, and fixture provenance. Existing evidence tests cover wrong supplier/plant mapping and original email content.
- Existing flow/decision/lifecycle tests cover card order and explicit selection, rejection, and approval behavior. The new test checks unchanged disabled approval and no callback side effects during inspection.
- The new file directly covers mounted runtime suppression, exact historical header context, all three record destinations, preserved email/Teams URLs, inline details and footers, zero stock, linked orders across plants, empty/unlinked production suppression, selected versus recommended option context, wrong retrieval ID, and malformed snapshot suppression.
- The one-line `App.tsx` analysis prop is reviewed in the diff and typechecked by the production build. No separate mocked App lifecycle test is proposed in this bounded task.
- Extra variations such as null runtime, duplicate selected option IDs, and alternate malformed inventory fields may be added to this same file if parent review identifies a gap beyond the existing builder/resolver coverage. They are not dependencies hidden behind this plan.

### Test step: complete shared mounted test file

Create `apps/web/src/components/reportCardLinks.test.tsx` with the following complete code. This centralizes the new integration coverage while the pre-existing evidence, trusted-URL, lifecycle, and approval tests remain unchanged. Run `cd apps/web && npx vitest run src/components/reportCardLinks.test.tsx` before and after mounting; the positive-link tests fail before implementation.

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import type {AnalysisVersion, CaseInstance, EvidenceItem, ResponseOption, RuntimeStatus} from "../types";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {recordFixture, editSnapshot} from "./supportingRecord.fixture";
import {CaseHeader} from "./CaseHeader";
import {InvestigationFlow} from "./InvestigationFlow";
import {reportIdentityKey} from "../reporting/reportNavigation";

afterEach(() => {cleanup(); vi.unstubAllGlobals();});
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
  return {runtime, caseInstance, analysis, selectedOption: null, decision: null, actions: [], drafts: [],
    playback: null, observations: [], operation: null, error: null, decisionBlocked: true,
    create: vi.fn(), analyze: vi.fn(), selectOption: vi.fn(), approve: vi.fn(), reject: vi.fn(),
    retryPlanning: vi.fn(), retryAction: vi.fn(), startPlayback: vi.fn()};
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
it("mounts exact historical header context and hides missing or mismatched context", () => {
  const s = fixture(); const {rerender} = render(header(s));
  expectDestination("Open case dashboard", "command-center", exact);
  s.analysis = null; rerender(header(s));
  expectDestination("Open case dashboard", "command-center", caseFilter);
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
])("suppresses every report anchor without a usable release and base: %j", unavailableRuntime => {
  const s = fixture(); s.runtime = unavailableRuntime;
  render(<>{header(s)}<InvestigationFlow state={s} /></>);
  expect(screen.queryByRole("link", {name: /Power BI|case dashboard/})).not.toBeInTheDocument();
  expect(screen.getAllByRole("link", {name: "Open supplier email"})).toHaveLength(2);
});
it("mounts all three exact records and retains original sources, inline inspection and footer order", async () => {
  const s = fixture(); const before = JSON.stringify(s.analysis); const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  render(<InvestigationFlow state={s} />);
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
  for (const link of screen.getAllByRole("link", {name: "Open supplier email"})) expect(link).toHaveAttribute("href", emailUrl);
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
it("preserves selected and recommended option identities independently", () => {
  const s = fixture(); const {rerender} = render(<InvestigationFlow state={s} />);
  const optionA = `${exact} and SavedOptions/option_key eq '4F007000740069006F006E002D004100'`;
  const optionB = `${exact} and SavedOptions/option_key eq '4F007000740069006F006E002D004200'`;
  expectDestination("Explore response options in Power BI", "response-options", exact);
  expectDestination("Explore recommended response in Power BI", "response-options", optionA);
  s.selectedOption = s.analysis!.response_options[2]; rerender(<InvestigationFlow state={s} />);
  expectDestination("Explore response options in Power BI", "response-options", optionB);
  expectDestination("Explore recommended response in Power BI", "response-options", optionA);
  s.selectedOption = option("foreign"); rerender(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: "Explore response options in Power BI"})).not.toBeInTheDocument();
  s.analysis!.recommendation = s.analysis!.response_options[2]; rerender(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: "Explore recommended response in Power BI"})).not.toBeInTheDocument();
});
it("hides record links for wrong retrieval identity and all links for malformed envelope", () => {
  const s = fixture(); s.analysis!.evidence_items[0].retrieved_for_analysis_id = "other";
  const {rerender} = render(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: "Explore shipment in Power BI"})).not.toBeInTheDocument();
  expect(screen.getByRole("link", {name: "Explore transfer in Power BI"})).toBeVisible();
  s.analysis!.material.operational_snapshot_json = "{"; rerender(<InvestigationFlow state={s} />);
  expect(screen.queryByRole("link", {name: /Power BI/})).not.toBeInTheDocument();
  expect(screen.getAllByRole("heading", {level: 3})).toHaveLength(9);
  expect(screen.getByRole("button", {name: "Approve selected response"})).toBeDisabled();
});
```

### Verification and handoff step

- [x] Run `cd apps/web && npx vitest run src/components/reportCardLinks.test.tsx`; all shared mounted tests pass.
- [x] Run `cd apps/web && npm test` and `cd apps/web && npm run build`; preserve existing pure navigation, source trust, lifecycle, and approval checks.
- [x] Review the diff for this bounded file map, report exact command results, and hand off for parent review. Commit only this task's listed files after verification and write `.superpowers/sdd/report-card-links-task-1-report.md`, including RED/GREEN evidence and remaining live acceptance limits. Do not deploy, push or merge.

## Review notes

Controller integration amendment: the existing `LiveSafety.test.tsx` header
test expected a generic report link without a case and omitted the now-required
analysis prop. Update that one obsolete test and necessary fixture/imports to a
canonical activated report, exact live case, `analysis={null}`, and exact
case-filtered `Open case dashboard` link with safe external attributes. Rerender
without a case and assert no report link. Preserve every other trust/source/
playback test. This migration is required by the intended new behavior, not a
weakening of the safety gate.

This deliberately does not change supporting-record resolution or source attribution. The only exported type addition names an existing target context; URL validation stays in the tested builder. An absent release gate safely hides the stale generic header today and all new links. The report's exact saved-analysis filtering and baseline semantics are a prerequisite owned by the separate report/release work, not evidence of availability established by frontend rendering.

## Controller amendment: truthful unavailable header wording

Local browser reconnaissance also confirmed the existing dashboard link is dark
green on the dark header. Add `apps/web/src/styles.css` to this task's ownership
for this one scoped rule, preserving all other styles:

```css
.case-header a { color: #c8f2e2; }
```

Place it next to the existing case-header rules. Controller browser acceptance
will check actual computed colors, contrast, keyboard focus and mobile wrapping;
no global link-color change or unrelated restyling is authorized.

While replacing the header link, replace the existing availability span with the
following expression. Its current unconditional fallback wording is incorrect
when the live report is unavailable; preserve the existing fallback text.

```tsx
{runtime && !runtime.power_bi_available && <span>
  {runtime.runtime_mode === "fallback"
    ? "Power BI unavailable in fallback"
    : "Power BI report is not available"}
</span>}
```

Append this regression to the supplied shared test file before implementation:

```tsx
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
```
