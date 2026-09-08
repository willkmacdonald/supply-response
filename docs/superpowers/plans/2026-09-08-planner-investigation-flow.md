# Planner Investigation Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present the saved analysis in the approved three investigation rows, with business questions, attributable sources, inspectable records, clearly separated baseline and response predictions, and unchanged explicit decision controls.

**Architecture:** A narrow snapshot reader validates the additional disruption, inventory, and order fields. Focused read-only presentation components compose the existing supporting-record resolver/details and evidence footer; they consume persisted predictions without implementing supply allocation or ranking. The workspace hook, API contracts, decision gates, execution, and playback remain the existing implementations.

**Tech Stack:** Existing React, TypeScript, Vitest, Testing Library, Vite, and CSS; no dependencies.

## Global Constraints

- “The first card at the top left is always the supplier delay, not a platform record.”
- “Missing information leaves a clearly explained gap in its logical position; it does not silently reorder the investigation or invent a fact.”
- “Use `analysis.material.operational_snapshot_json` already returned by the API.”
- “Preserve zero values and explicit false flags.”
- “Dates and currency must be formatted without timezone-related day shifts or invented units.”
- “Never render arbitrary HTML or unvalidated URLs.”
- “These are display clarifications, not source-data renames. Preserve original message text, source identifiers, citations, and immutable analysis records.”
- “This is an inspection view of existing evidence, not a new authority or approval gate.”
- “Do not mutate immutable analysis material, source bundles, hashes, or stored citations, and do not weaken existing trusted-URL validation or approval rules.”
- No live calls, API/backend/report changes, or new Power BI links. The existing header report action belongs to the coordinated navigation stage; this increment removes generic Fabric citation actions from the evidence path.
- Do not commit during this planning assignment. During execution the parent coordinates scoped task commits for review packages; no next task starts before the preceding review gate passes.

---

## Prerequisites, boundaries, and resolved contract questions

Read Part 1 of `docs/superpowers/specs/2026-09-08-evidence-records-and-case-dashboard-design.md` and stage 2 of `docs/superpowers/plans/2026-09-08-planner-experience-delivery.md`. Execute only after the five files in `docs/superpowers/plans/2026-09-08-supporting-record-inspection.md` have passed their review. That plan owns `resolveSupportingRecord(input: SupportingRecordInput, evidenceId: string): SupportingRecordResult`, `SupportingRecord`, `ExactRecordContext`, and `SupportingRecordDetails({result}: {result: SupportingRecordResult})`; do not change those public interfaces. Task 1 narrowly extracts internal primitive/envelope validation from `supportingRecord.ts` for reuse, preserving its behavior and section checks. Full `CaseInstance` and `AnalysisVersion` structurally satisfy `SupportingRecordInput`. `EvidenceFooter({status})` and `evidenceStatus(item, {...analysis, results: analysis.evidence_validation.item_results})` are already committed.

`data/domain/operations.py` and `data/synthetic/rl001.py` define the additional saved fields. Inventory availability is precisely on hand minus quality holds minus protected allocations, summed over the affected part/plant. Showing that stock breakdown is presentation arithmetic, not a second planning engine. Do not clamp a negative result: retain it and explain that holds/allocations exceed stock. Empty inventory means unavailable, not known zero stock.

`services/analysis/options.py::_calculate_intervention_outcome` computes its service percentage over **production orders**, then persists their customer order IDs. Only describe the percentage as a customer-order-line measure if every production order in the calculation has a unique matching customer line, and every saved protected ID matches that set. Otherwise explicitly retain the server percentage as a production-order service projection with customer-line interpretation unavailable. No rounding a percentage into a count. The risk values come from persisted predictions, never from summing arbitrary displayed orders. The one-to-one validation also checks saved production customer revenue against line quantity × unit revenue using integer cents before explaining revenue as customer-line value.

Money has no currency code. Display `24,750.00 (currency not specified)` and `7.50 per unit (currency not specified)`, never manufacture USD or `$`. The excerpt can contain its original `$7.50` because it is a source quotation. Calendar dates format in UTC without moving a day. Actual timestamps retain timezone labels and remain distinct from the fictional scenario time.

The API exposes source text and authority scopes, not typed parsed supplier-email quantities. Quote the supplier excerpt verbatim under `Supplier email`; show the saved disruption and receipt summaries separately and label them as saved planning/record data. Do not derive an “air” offer, 5,000-unit remainder, or agreement between sources by parsing prose or subtracting an unrelated receipt. `recovery_date === null` supports the saved-plan statement that the remaining recovery date is unavailable; it does not establish what the supplier promised. RL-001 demo-corpus supplier and Quality source roles are defined by `integrations/workiq/prompts.py`; apply the specified Jordan display attribution only to that supported scenario and scope. Unsupported sources remain visible as additional source context with no invented author.

Historical saved analyses are inspectable even if `case.current_analysis_id` differs. The reader validates case, runtime, template/corpus, scenario time, and saved analysis identity, not “latest”. It neither enables nor disables approval: the existing workspace safety gate remains authoritative.

## File map

Create:

- `apps/web/src/components/snapshotValidation.ts`: shared strict value predicates and saved-envelope identity parsing; no section or evidence resolution.
- `apps/web/src/components/plannerSnapshot.ts`: only the additional saved business fields and section-specific type validation.
- `apps/web/src/components/plannerSnapshot.test.ts`: malformed/partial/historical/zero and linkage tests.
- `apps/web/src/components/plannerFormatting.ts`: safe units, dates, business names, and blocker copy.
- `apps/web/src/components/PredictionSummary.tsx`: persisted prediction display with verified metric basis.
- `apps/web/src/components/PredictionSummary.test.tsx`: baseline/response and unit tests.
- `apps/web/src/components/EvidenceSource.tsx`: reusable original source disclosure, source links/warnings, and bottom footers.
- `apps/web/src/components/InvestigationEvidence.tsx`: six business cards, attribution, and supporting-record integration.
- `apps/web/src/components/InvestigationEvidence.test.tsx`: source placement, links, gaps, and disclosures.
- `apps/web/src/components/InvestigationFlow.tsx`: three labeled rows and composition.
- `apps/web/src/components/InvestigationFlow.test.tsx`: semantic reading order and unchanged control behavior.

Modify:

- `apps/web/src/components/supportingRecord.ts`: replace only internal primitive/envelope validation with shared imports, retaining its existing branch/evidence validation and public interfaces.
- `apps/web/src/components/EvidencePanel.tsx`: keep its standalone compatibility wrapper for existing tests, consuming the production helpers from `EvidenceSource.tsx`.
- `apps/web/src/components/ExposurePanel.tsx`: recommendation card, persisted explanation and metrics.
- `apps/web/src/components/OptionComparison.tsx`: compact alternatives and baseline within the decision row.
- `apps/web/src/components/optionLabels.ts`: display names only.
- `apps/web/src/components/DecisionPanel.tsx`: heading and readable requirements; retain control logic.
- `apps/web/src/App.tsx`: replace four panel calls with the composed investigation flow.
- `apps/web/src/styles.css`: scoped three-row desktop/mobile layout.
- `apps/web/src/components/LiveSafety.test.tsx`: replace obsolete Fabric citation expectation with explicit absence.
- `apps/web/src/App.test.tsx`: update only changed heading/name queries, preserve lifecycle assertions.

No edits to `types.ts`, `useCaseWorkspace.ts`, `api.ts`, the trusted-URL functions, supporting-record component/fixtures/tests, evidence-status implementation, or post-decision panels. The sole supporting-record exception is the internal validation extraction in Task 1.

## Task 1: Validate the remaining immutable snapshot fields

**Files:** Create `snapshotValidation.ts`, `plannerSnapshot.ts`, and `plannerSnapshot.test.ts` in `apps/web/src/components/`; narrowly modify `supportingRecord.ts`.

**Interfaces:** Consumes `SupportingRecordInput`. Produces shared `parseSnapshotEnvelope(input: SnapshotEnvelopeInput): Record<string, unknown> | null` and strict predicates, plus `readPlannerSnapshot(input): PlannerSnapshot | null`, with independently nullable disruption/inventory/production/customer sections; `customerLineBasis(snapshot, protectedIds): {total: number; missed: number} | null`. Unknown and malformed sections fail closed locally, so a malformed customer array does not remove a valid disruption. The supporting-record resolver retains its existing requirement for all three arrays and an object disruption before resolving a branch. The shared envelope does not enforce those caller-specific rules.

- [ ] **Step 1: Create these failing tests.**

```ts
import {describe, expect, it} from "vitest";
import {editSnapshot, recordFixture} from "./supportingRecord.fixture";
import {customerLineBasis, readPlannerSnapshot} from "./plannerSnapshot";
import {resolveSupportingRecord} from "./supportingRecord";
import {parseSnapshotEnvelope, validDate, validInstant, validMoney} from "./snapshotValidation";

function fixture() {
  const input = recordFixture();
  editSnapshot(input, s => {
    s.disruption = {disruption_id: "d", supplier_id: "RL-SUP-ALPHA", po_line_id: "po",
      part_id: "p", plant_id: "RL-PLANT-CHI", original_quantity: 8000,
      original_due_date: "2026-09-03", partial_quantity: 0,
      partial_due_date: null, recovery_date: null, source_ref: "RL-001"};
    s.inventory_positions = [{inventory_id: "i", part_id: "p", plant_id: "RL-PLANT-CHI",
      on_hand: 4500, quality_hold: 200, protected_allocation: 300}];
    s.production_orders = [{production_order_id: "mo", product_id: "product", plant_id: "RL-PLANT-CHI",
      quantity: 2, due_date: "2026-09-05", component_demand: 4,
      customer_order_id: "co", customer_revenue: "10.00"}];
    s.customer_orders = [{customer_order_line_id: "co", production_order_id: "mo",
      customer_id: "customer", product_id: "product", plant_id: "RL-PLANT-CHI",
      quantity: 2, due_date: "2026-09-05", unit_revenue: "5.00"}];
  });
  return input;
}

describe("planner snapshot", () => {
  it("shares strict value checks and keeps caller-specific section rules separate", () => {
    expect(validDate("2026-02-30")).toBe(false);
    expect(validInstant("2026-09-01T09:00:00")).toBe(false);
    expect(validMoney("0.00")).toBe(true);
    expect(validMoney("0")).toBe(false);
    const input = fixture();
    editSnapshot(input, s => { s.customer_orders = "malformed"; });
    expect(parseSnapshotEnvelope(input)).not.toBeNull();
    expect(readPlannerSnapshot(input)?.disruption?.original_quantity).toBe(8000);
    expect(readPlannerSnapshot(input)?.customers).toBeNull();
    expect(resolveSupportingRecord(input, input.analysis.evidence_items[0].evidence_id).status).toBe("unavailable");
  });
  it("retains zero and null and accepts a historical analysis without mutation", () => {
    const input = fixture(); const before = JSON.stringify(input);
    const saved = readPlannerSnapshot(input)!;
    expect(saved.disruption?.partial_quantity).toBe(0);
    expect(saved.disruption?.recovery_date).toBeNull();
    expect(saved.inventory?.[0].on_hand).toBe(4500);
    expect(JSON.stringify(input)).toBe(before);
    expect(readPlannerSnapshot({...input, caseInstance: {...input.caseInstance,
      ...{current_analysis_id: "newer-analysis"}}})).not.toBeNull();
  });
  it.each(["case", "runtime", "scenario", "corpus", "json"])("rejects %s identity problems", kind => {
    const input = fixture();
    if (kind === "case") input.analysis.material.case_id = "other";
    if (kind === "runtime") input.caseInstance.runtime_mode = "fallback";
    if (kind === "scenario") input.analysis.material.scenario_effective_time = "2026-09-02T09:00:00-05:00";
    if (kind === "corpus") input.analysis.material.corpus = "real_business";
    if (kind === "json") input.analysis.material.operational_snapshot_json = "{";
    expect(readPlannerSnapshot(input)).toBeNull();
  });
  it("rejects malformed fields locally, including impossible calendar dates and duplicate IDs", () => {
    const input = fixture();
    editSnapshot(input, s => { s.customer_orders[0].due_date = "2026-02-30"; });
    expect(readPlannerSnapshot(input)?.customers).toBeNull();
    expect(readPlannerSnapshot(input)?.disruption).not.toBeNull();
    editSnapshot(input, s => { s.inventory_positions.push({...s.inventory_positions[0]}); });
    expect(readPlannerSnapshot(input)?.inventory).toBeNull();
    editSnapshot(input, s => { s.disruption.partial_quantity = "0"; });
    expect(readPlannerSnapshot(input)?.disruption).toBeNull();
  });
  it("distinguishes empty arrays, zero stock, and negative net availability inputs", () => {
    const input = fixture();
    editSnapshot(input, s => { s.inventory_positions[0].on_hand = 0; });
    expect(readPlannerSnapshot(input)?.inventory?.[0].on_hand).toBe(0);
    editSnapshot(input, s => { s.inventory_positions = []; });
    expect(readPlannerSnapshot(input)?.inventory).toEqual([]);
  });
  it("permits customer-line counts only for exact one-to-one metric lineage", () => {
    const input = fixture();
    expect(customerLineBasis(readPlannerSnapshot(input), [])).toEqual({total: 1, missed: 1});
    expect(customerLineBasis(readPlannerSnapshot(input), ["co"])).toEqual({total: 1, missed: 0});
    expect(customerLineBasis(readPlannerSnapshot(input), ["unknown"])).toBeNull();
    expect(customerLineBasis(readPlannerSnapshot(input), ["co", "co"])).toBeNull();
    editSnapshot(input, s => { s.production_orders[0].customer_revenue = "11.00"; });
    expect(customerLineBasis(readPlannerSnapshot(input), [])).toBeNull();
    editSnapshot(input, s => { s.production_orders[0].customer_order_id = null; });
    expect(customerLineBasis(readPlannerSnapshot(input), [])).toBeNull();
  });
});
```

- [ ] **Step 2: Run `cd apps/web && npx vitest run src/components/plannerSnapshot.test.ts`.** Expected: missing-module failure.
- [ ] **Step 3: Create `snapshotValidation.ts` with these shared strict predicates and envelope parser.** Its input type imports only API types, avoiding a runtime/type dependency cycle between the two readers. The parser catches malformed JSON and verifies saved identity; it deliberately leaves business sections unknown for each caller to validate.

```ts
import type {AnalysisMaterial, AnalysisVersion, CaseInstance} from "../types";
export type SnapshotEnvelopeInput = {
  caseInstance: Pick<CaseInstance, "case_id" | "runtime_mode" | "template_id" | "scenario_effective_time">;
  analysis: Pick<AnalysisVersion, "analysis_id" | "case_id" | "runtime_mode" | "scenario_effective_time" | "created_at"> & {
    material: Pick<AnalysisMaterial, "case_id" | "runtime_mode" | "template_id" | "corpus" | "scenario_effective_time" | "operational_snapshot_json">;
  };
};
export const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
export const text = (v: unknown): v is string => typeof v === "string" && v.trim().length > 0;
export const whole = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
export const positive = (v: unknown): v is number => whole(v) && v > 0;
export const validMoney = (v: unknown): v is string => typeof v === "string" && /^\d+\.\d{2}$/.test(v);
export const validDate = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)
  && Number.isFinite(Date.parse(`${v}T00:00:00Z`)) && new Date(`${v}T00:00:00Z`).toISOString().slice(0, 10) === v;
export const validInstant = (v: unknown): v is string => typeof v === "string"
  && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.test(v)
  && validDate(v.slice(0, 10)) && Number.isFinite(Date.parse(v));
export const nullableDate = (v: unknown): v is string | null => v === null || validDate(v);
export const nullableFlag = (v: unknown): v is boolean | null => v === null || typeof v === "boolean";
const sameTime = (a: unknown, b: unknown) => validInstant(a) && validInstant(b) && Date.parse(a) === Date.parse(b);
export function parseSnapshotEnvelope({caseInstance: c, analysis: a}: SnapshotEnvelopeInput): Record<string, unknown> | null {
  try {
    const m = a.material; const s: unknown = JSON.parse(m.operational_snapshot_json);
    if (!object(s) || !text(a.analysis_id) || !text(a.case_id) || !validInstant(a.created_at)
      || c.template_id !== "RL-001" || m.template_id !== c.template_id || m.corpus !== "demo_corpus"
      || ![c.case_id, m.case_id, s.case_id].every(id => id === a.case_id)
      || (a.runtime_mode !== "live" && a.runtime_mode !== "fallback")
      || ![c.runtime_mode, m.runtime_mode, s.runtime_mode].every(mode => mode === a.runtime_mode)
      || ![c.scenario_effective_time, m.scenario_effective_time, s.scenario_effective_time].every(at => sameTime(at, a.scenario_effective_time))
      || s.scenario_timezone !== "America/Chicago" || !validInstant(s.analysis_horizon_start)
      || !validDate(s.analysis_horizon_end)) return null;
    return s;
  } catch { return null; }
}
```

- [ ] **Step 4: Replace only internal validation in `supportingRecord.ts`.** Add the following import:

```ts
import {object, text, positive, validDate as date, validInstant as timestamp, validMoney as money,
  nullableDate, nullableFlag, parseSnapshotEnvelope} from "./snapshotValidation";
```

Remove its consecutive local definitions from `const object = ...` through `const money = ...`, leaving `const unavailable` and `parseRecord` unchanged. Inside `resolveSupportingRecord`, replace the initial destructure, material, JSON parse, and envelope `if` (up to immediately before `const items = ...`) with:

```ts
    const {analysis: a} = input;
    const m = a.material;
    const s = parseSnapshotEnvelope(input);
    if (!s || !text(evidenceId)
      || !Array.isArray(s.inventory_positions) || !Array.isArray(s.production_orders)
      || !Array.isArray(s.customer_orders) || !object(s.disruption)) return unavailable;
```

All remaining resolver code stays unchanged, including its outer try/catch, exact evidence membership/material checks, timestamps, fixture/live provenance, family resolution, and frozen copies. Run `cd apps/web && npx vitest run src/components/supportingRecord.test.ts` now. Expected: all 42 existing tests pass without changing those tests.

- [ ] **Step 5: Create the complete reader below.** Bounded typed parsers narrow every field before constructing explicit objects; no generic schema-to-type assertion is used. The only generic helper parses arrays using the caller's actual typed parser and identity accessor.

```ts
import type {SupportingRecordInput} from "./supportingRecord";
import type {Disruption} from "../types";
import {object, text, whole, positive, validDate, validMoney, nullableDate, parseSnapshotEnvelope} from "./snapshotValidation";

type Inventory = {inventory_id: string; part_id: string; plant_id: string;
  on_hand: number; quality_hold: number; protected_allocation: number};
type Production = {production_order_id: string; product_id: string; plant_id: string;
  quantity: number; due_date: string; component_demand: number | null;
  customer_order_id: string | null; customer_revenue: string | null};
type Customer = {customer_order_line_id: string; production_order_id: string | null;
  customer_id: string; product_id: string; plant_id: string; quantity: number;
  due_date: string; unit_revenue: string};
export type PlannerSnapshot = Readonly<{disruption: Disruption | null;
  inventory: Inventory[] | null; production: Production[] | null; customers: Customer[] | null}>;

function records<T>(v: unknown, parse: (value: unknown) => T | null, id: (value: T) => string): T[] | null {
  if (!Array.isArray(v)) return null;
  const result: T[] = [];
  for (const value of v) { const parsed = parse(value); if (parsed === null) return null; result.push(parsed); }
  return new Set(result.map(id)).size === result.length ? result : null;
}
function parseDisruption(v: unknown): Disruption | null {
  if (!object(v) || !text(v.disruption_id) || !text(v.supplier_id) || !text(v.po_line_id)
    || !text(v.part_id) || !text(v.plant_id) || !positive(v.original_quantity) || !validDate(v.original_due_date)
    || !whole(v.partial_quantity) || v.partial_quantity > v.original_quantity
    || !nullableDate(v.partial_due_date) || !nullableDate(v.recovery_date) || !text(v.source_ref)) return null;
  return {disruption_id: v.disruption_id, supplier_id: v.supplier_id, po_line_id: v.po_line_id,
    part_id: v.part_id, plant_id: v.plant_id, original_quantity: v.original_quantity, original_due_date: v.original_due_date,
    partial_quantity: v.partial_quantity, partial_due_date: v.partial_due_date, recovery_date: v.recovery_date, source_ref: v.source_ref};
}
function parseInventory(v: unknown): Inventory | null {
  if (!object(v) || !text(v.inventory_id) || !text(v.part_id) || !text(v.plant_id)
    || !whole(v.on_hand) || !whole(v.quality_hold) || !whole(v.protected_allocation)) return null;
  return {inventory_id: v.inventory_id, part_id: v.part_id, plant_id: v.plant_id,
    on_hand: v.on_hand, quality_hold: v.quality_hold, protected_allocation: v.protected_allocation};
}
function parseProduction(v: unknown): Production | null {
  if (!object(v) || !text(v.production_order_id) || !text(v.product_id) || !text(v.plant_id)
    || !positive(v.quantity) || !validDate(v.due_date)
    || !(v.component_demand === null || positive(v.component_demand))
    || !(v.customer_order_id === null || text(v.customer_order_id))
    || !(v.customer_revenue === null || validMoney(v.customer_revenue))) return null;
  return {production_order_id: v.production_order_id, product_id: v.product_id, plant_id: v.plant_id,
    quantity: v.quantity, due_date: v.due_date, component_demand: v.component_demand,
    customer_order_id: v.customer_order_id, customer_revenue: v.customer_revenue};
}
function parseCustomer(v: unknown): Customer | null {
  if (!object(v) || !text(v.customer_order_line_id) || !(v.production_order_id === null || text(v.production_order_id))
    || !text(v.customer_id) || !text(v.product_id) || !text(v.plant_id)
    || !positive(v.quantity) || !validDate(v.due_date) || !validMoney(v.unit_revenue)) return null;
  return {customer_order_line_id: v.customer_order_line_id, production_order_id: v.production_order_id,
    customer_id: v.customer_id, product_id: v.product_id, plant_id: v.plant_id,
    quantity: v.quantity, due_date: v.due_date, unit_revenue: v.unit_revenue};
}
export function readPlannerSnapshot(input: SupportingRecordInput): PlannerSnapshot | null {
  const s = parseSnapshotEnvelope(input);
  return s ? {disruption: parseDisruption(s.disruption),
    inventory: records(s.inventory_positions, parseInventory, value => value.inventory_id),
    production: records(s.production_orders, parseProduction, value => value.production_order_id),
    customers: records(s.customer_orders, parseCustomer, value => value.customer_order_line_id)} : null;
}

export function customerLineBasis(snapshot: PlannerSnapshot | null, protectedIds: string[]): {total: number; missed: number} | null {
  const production = snapshot?.production; const customers = snapshot?.customers;
  if (!production?.length || !customers || production.length !== customers.length
    || new Set(protectedIds).size !== protectedIds.length) return null;
  const ids = production.map(order => order.customer_order_id);
  if (new Set(ids).size !== ids.length || ids.some(id => id === null)
    || protectedIds.some(id => !ids.includes(id))) return null;
  const cents = (value: string) => BigInt(value.replace(".", ""));
  const linked = production.every(order => {
    const customer = customers.find(line => line.customer_order_line_id === order.customer_order_id);
    return customer && customer.production_order_id === order.production_order_id
      && customer.product_id === order.product_id && customer.plant_id === order.plant_id
      && customer.quantity === order.quantity && customer.due_date === order.due_date
      && order.customer_revenue !== null
      && cents(order.customer_revenue) === BigInt(customer.quantity) * cents(customer.unit_revenue);
  });
  return linked ? {total: production.length, missed: production.length - protectedIds.length} : null;
}
```

- [ ] **Step 6: Run `cd apps/web && npx vitest run src/components/plannerSnapshot.test.ts src/components/supportingRecord.test.ts src/components/SupportingRecordDetails.test.tsx && npm run build`.** Expected: all new tests, the existing 42 resolver tests, detail tests, and strict compilation pass without changing resolver expectations. `apps/web/tsconfig.json` already targets ES2022 and supports `BigInt`; no target change or floating-point substitute is needed.
- [ ] **Step 7: Review the four-file diff and give it to the parent for the eventual `feat: share snapshot validation and validate planner fields` commit.**

## Task 2: Display persisted predictions with explicit metric basis and units

**Files:** Create `plannerFormatting.ts`, `PredictionSummary.tsx`, `PredictionSummary.test.tsx`; modify `optionLabels.ts`.

**Interfaces:** `PredictionSummary({predicted, snapshot, basis, compact = false}: {predicted: PredictedOutcome | null; snapshot: PlannerSnapshot | null; basis: "baseline" | "response"; compact?: boolean})`; shared pure formatters shown below. Compact display retains parts, service, and response cost; full exposure/assumptions are available in native option details. No allocation, ranking, response-cost recomputation, or synthetic outcome creation.

- [ ] **Step 1: Add the complete tests below.**

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it} from "vitest";
import {PredictionSummary} from "./PredictionSummary";
import {calendar, money, blocker, rankingReason, decisionContext} from "./plannerFormatting";
afterEach(cleanup);
const predicted = {uncovered_part_demand: 0, otif_loss_percentage: 0,
  revenue_at_risk: "0.00", margin_at_risk: "0.00", response_cost: "24750.00",
  protected_customer_order_ids: []};
it("shows persisted zero, absent currency, and the baseline label without inventing line counts", () => {
  render(<PredictionSummary predicted={predicted} snapshot={null} basis="baseline" />);
  expect(screen.getByText("Expected if we do nothing — baseline")).toBeVisible();
  expect(screen.getByText("0 component units (part unavailable)")).toBeVisible();
  expect(screen.getByText("24,750.00 (currency not specified)")).toBeVisible();
  expect(screen.getByText("Production orders expected to miss the on-time, in-full target")).toBeVisible();
  expect(screen.getByText(/Customer-order-line interpretation unavailable/)).toBeVisible();
});
it("labels response predictions and does not invent missing outcomes", () => {
  render(<PredictionSummary predicted={null} snapshot={null} basis="response" />);
  expect(screen.getByText("Expected if we take this option")).toBeVisible();
  expect(screen.getByText("Saved prediction unavailable")).toBeVisible();
  expect(screen.queryByText(/0 component/)).not.toBeInTheDocument();
});
it("formats calendar dates without day shifts and keeps unsafe values unavailable", () => {
  expect(calendar("2026-09-06")).toBe("September 6, 2026");
  expect(calendar("2026-02-30")).toBe("Unavailable");
  expect(money("0.00")).toBe("0.00 (currency not specified)");
  expect(money("NaN")).toBe("Unavailable");
  expect(blocker("QUALITY_QUALIFICATION_PENDING")).toBe("Cannot use Supplier Beta yet: supplier qualification is incomplete");
  expect(blocker("NEW_POLICY_CODE")).toBe("Planning requirement unresolved (NEW_POLICY_CODE)");
});
it("describes recorded ranking with business meaning and units without asserting a new ranking", () => {
  const stage = {comparator: "uncovered_part_demand", threshold: "500", lower_is_better: true,
    input_option_ids: ["a", "b"], values: [], retained_option_ids: ["a"], eliminated_option_ids: ["b"]};
  expect(rankingReason(stage, "a")).toBe("This option stayed in consideration after comparing parts still needed, allowing a difference of 500 component units under the saved planning policy. 1 other option was ruled out in this comparison.");
  expect(rankingReason({...stage, comparator: "otif_loss_percentage", threshold: "10"}, "a")).toContain("10 percentage points");
  expect(rankingReason({...stage, comparator: "response_cost", threshold: "10000"}, "a")).toContain("currency not specified");
  expect(rankingReason({...stage, comparator: "unknown"}, "a")).toContain("additional saved comparison rule");
  expect(decisionContext(null, "a", false)).toBe("Case context unavailable; no decision is shown");
});
it("keeps the comparison summary compact with parts, service and response cost", () => {
  render(<PredictionSummary predicted={predicted} snapshot={null} basis="response" compact />);
  expect(screen.getByText("Parts still needed")).toBeVisible();
  expect(screen.getByText("Response cost")).toBeVisible();
  expect(screen.queryByText("Revenue at risk")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run `cd apps/web && npx vitest run src/components/PredictionSummary.test.tsx`.** Expected: missing-module failure.
- [ ] **Step 3: Create the formatting module.**

```ts
import type {CaseInstance, RankingStage} from "../types";
import {validDate, validInstant, validMoney} from "./snapshotValidation";
export const number = (value: number) => value.toLocaleString("en-US");
export const calendar = (value: string | null) => validDate(value)
  ? new Intl.DateTimeFormat("en-US", {year: "numeric", month: "long", day: "numeric", timeZone: "UTC"})
    .format(new Date(`${value}T00:00:00Z`)) : "Unavailable";
export const instant = (value: string | null) => validInstant(value)
  ? new Intl.DateTimeFormat("en-US", {year: "numeric", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit", timeZone: "UTC", timeZoneName: "short"}).format(new Date(value)) : "Unavailable";
export function money(value: string) {
  if (!validMoney(value)) return "Unavailable";
  const [whole, cents] = value.split(".");
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${cents} (currency not specified)`;
}
export const supplier = (id: string) => id === "RL-SUP-ALPHA" ? "RL-Supplier Alpha — Current supplier"
  : id === "RL-SUP-BETA" ? "RL-Supplier Beta — Alternate supplier" : `Supplier ${id}`;
export const plant = (id: string) => id === "RL-PLANT-DAL" ? "Dallas plant"
  : id === "RL-PLANT-CHI" ? "Chicago plant" : `Plant ${id}`;
const blockers: Record<string, string> = {
  QUALITY_QUALIFICATION_PENDING: "Cannot use Supplier Beta yet: supplier qualification is incomplete",
  ALPHA_PARTIAL_SHIPMENT_UNAVAILABLE: "No partial shipment from Supplier Alpha is available",
  TRANSFER_INVENTORY_UNAVAILABLE: "The source plant does not have enough available inventory for this transfer",
  RESEQUENCE_NOT_APPLICABLE: "Changing the production sequence does not provide a response for this plan",
};
export const blocker = (code: string) => blockers[code] ?? `Planning requirement unresolved (${code})`;
const roles: Record<string, string> = {material_planner: "Material planner", finance_approver: "Finance approver",
  quality_approver: "Quality approver", response_approver: "Response approver"};
export const role = (value: string) => roles[value] ?? `Required role: ${value}`;
const comparators: Record<string, {label: string; unit: string}> = {
  uncovered_part_demand: {label: "parts still needed", unit: "component units"},
  otif_loss_percentage: {label: "service-target exposure", unit: "percentage points"},
  revenue_at_risk: {label: "revenue at risk", unit: "currency units (currency not specified)"},
  margin_at_risk: {label: "margin at risk", unit: "currency units (currency not specified)"},
  response_cost: {label: "response cost", unit: "currency units (currency not specified)"},
  approval_burden: {label: "required approval burden", unit: "roles"},
  execution_risk: {label: "execution risk", unit: "score points"},
};
export function rankingReason(stage: RankingStage, optionId: string): string {
  if (!stage.retained_option_ids.includes(optionId)) return "This saved comparison stage did not retain the displayed option.";
  if (stage.comparator === "option_id") return "The saved comparison used its stable option identifier to resolve the remaining tie.";
  const known = comparators[stage.comparator];
  if (!known) return "The option was retained by an additional saved comparison rule; technical details are available below.";
  const count = stage.eliminated_option_ids.length;
  const outcome = count > 0
    ? `${count} other ${count === 1 ? "option was" : "options were"} ruled out in this comparison.`
    : "All remaining options stayed in consideration.";
  return `This option stayed in consideration after comparing ${known.label}, allowing a difference of ${stage.threshold} ${known.unit} under the saved planning policy. ${outcome}`;
}
const states: Record<CaseInstance["status"], string> = {
  open: "Case open; no decision recorded", analyzing: "Case analysis in progress", awaiting_decision: "Case awaiting a decision",
  decision_rejected: "Case recommendation rejected", action_planning: "Case action planning in progress",
  executing: "Case execution in progress", monitoring: "Case monitoring in progress",
  reanalysis_required: "Case requires a new analysis", closed: "Case closed",
};
export function decisionContext(c: CaseInstance | null, analysisId: string, hasDecision: boolean): string {
  if (hasDecision) return "Recorded decision shown below";
  if (!c) return "Case context unavailable; no decision is shown";
  if (c.current_analysis_id !== analysisId) return `Historical saved analysis. ${states[c.status]}; no decision is shown for this analysis.`;
  return `${states[c.status]}. No decision is recorded in this view.`;
}
```

Create `PredictionSummary.tsx`:

```tsx
import type {PredictedOutcome} from "../types";
import {customerLineBasis, type PlannerSnapshot} from "./plannerSnapshot";
import {validMoney} from "./snapshotValidation";
import {money, number} from "./plannerFormatting";

export function PredictionSummary({predicted: p, snapshot, basis, compact = false}: {
  predicted: PredictedOutcome | null; snapshot: PlannerSnapshot | null; basis: "baseline" | "response"; compact?: boolean;
}) {
  const valid = p && Number.isSafeInteger(p.uncovered_part_demand) && p.uncovered_part_demand >= 0
    && Number.isInteger(p.otif_loss_percentage) && p.otif_loss_percentage >= 0 && p.otif_loss_percentage <= 100
    && [p.revenue_at_risk, p.margin_at_risk, p.response_cost].every(validMoney)
    && Array.isArray(p.protected_customer_order_ids) && p.protected_customer_order_ids.every(id => typeof id === "string");
  const lineBasis = valid && p ? customerLineBasis(snapshot, p.protected_customer_order_ids) : null;
  const consistent = lineBasis && p && Math.floor(100 * lineBasis.missed / lineBasis.total) === p.otif_loss_percentage
    ? lineBasis : null;
  const part = snapshot?.disruption?.part_id;
  return <div className="prediction-summary">
    <p>{basis === "baseline" ? "Expected if we do nothing — baseline" : "Expected if we take this option"}</p>
    {!valid || !p ? <p>Saved prediction unavailable</p> : <>
      <dl className="compact-list">
        <div><dt>Parts still needed</dt><dd>{number(p.uncovered_part_demand)} {part ? `${part} component units` : "component units (part unavailable)"}</dd></div>
        <div><dt>{consistent ? "Customer order lines expected to miss the on-time, in-full target"
          : "Production orders expected to miss the on-time, in-full target"}</dt><dd>{p.otif_loss_percentage}%{consistent && ` (${consistent.missed} of ${consistent.total} lines)`}</dd></div>
        {!compact && <><div><dt>Revenue at risk</dt><dd>{money(p.revenue_at_risk)}</dd></div>
          <div><dt>Margin at risk</dt><dd>{money(p.margin_at_risk)}</dd></div></>}
        <div><dt>Response cost</dt><dd>{money(p.response_cost)}</dd></div>
      </dl>
      {!compact && <p>{consistent ? "Revenue at risk is the saved value of customer order lines expected to miss the service target."
        : "Customer-order-line interpretation unavailable. Revenue and service exposure retain the saved production-order calculation basis."}</p>}
    </>}
  </div>;
}
```

Replace `optionLabels.ts` with:

```ts
import type {ResponseOption} from "../types";
const labels: Record<ResponseOption["option_kind"], string> = {
  no_mitigation: "Do nothing — baseline", expedite: "Expedite the partial shipment",
  transfer: "Transfer from another plant", resequence: "Prioritize production for customer needs",
  alternate_source: "Use the alternate supplier", combined: "Combined response",
};
export function optionDisplayName(option: ResponseOption): string {
  return labels[option.option_kind] ?? option.name;
}
```

- [ ] **Step 4: Run `cd apps/web && npx vitest run src/components/PredictionSummary.test.tsx && npm run build`.** Expected: tests/build pass; `TZ=America/Los_Angeles npx vitest run src/components/PredictionSummary.test.tsx` also passes. Existing approval button labels for Combined response stay unchanged.
- [ ] **Step 5: Parent reviews this deliverable for `feat: explain saved prediction basis and planner units`.**

## Task 3: Reuse safe sources and build the first six investigation cards

**Files:** Modify `EvidencePanel.tsx`, `LiveSafety.test.tsx`; create `EvidenceSource.tsx`, `InvestigationEvidence.tsx`, `InvestigationEvidence.test.tsx`.

**Interfaces:** Existing `EvidencePanel` props remain compatible. `EvidenceSource.tsx` exports `EvidenceSource({item, analysis, tenantSharePointHost, label})`, `EvidenceFooters({items, analysis})`, `RequiredCitationWarning({analysis, tenantSharePointHost})`, and `statusFor(item: EvidenceItem, analysis: AnalysisVersion): EvidenceStatus`. Export `InvestigationEvidence({caseInstance, analysis, tenantSharePointHost, row}: {caseInstance: CaseInstance; analysis: AnalysisVersion; tenantSharePointHost?: string | null; row: "disruption" | "responses"})`; returns exactly three sibling cards for the selected row. Source role selection is separate from operational-record identity resolution.

- [ ] **Step 1: Add this integration test file.** It uses the existing narrow record fixture, then supplies the other required API fields explicitly.

```tsx
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
  const input = fixture();
  render(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getAllByRole("heading", {level: 3}).map(h => h.textContent)).toEqual([
    "What changed?", "What do we have available?", "What does that put at risk?",
  ]);
  const first = screen.getAllByRole("article")[0];
  expect(within(first).getByText("Original Alpha words, including $7.50 and unconfirmed timing.")).toBeInTheDocument();
  expect(within(first).getByRole("link", {name: "Open supplier email"})).toHaveAttribute("href", input.analysis.evidence_items[1].citation_url);
  expect(within(first).getByText("Saved disruption details unavailable")).toBeVisible();
});
it("combines inline shipment inspection and the original supplier email without external Fabric navigation", async () => {
  const input = fixture(); const before = JSON.stringify(input); const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  render(<InvestigationEvidence {...input} row="responses" />);
  const alpha = screen.getAllByRole("article")[0];
  expect(within(alpha).getByText("Scheduled receipt: 3,000 component units on September 6, 2026.")).toBeVisible();
  await userEvent.click(within(alpha).getByText("View shipment record"));
  expect(within(alpha).getByText("Snapshot used for this analysis")).toBeVisible();
  expect(within(alpha).getByRole("link", {name: "Open supplier email"})).toBeVisible();
  expect(screen.queryByRole("link", {name: "Open citation"})).not.toBeInTheDocument();
  expect(screen.getAllByRole("link").every(link => !link.getAttribute("href")?.includes("powerbi"))).toBe(true);
  const footerGroup = alpha.querySelector(".source-footers")!;
  expect(alpha.lastElementChild).toBe(footerGroup);
  expect(fetch).not.toHaveBeenCalled(); expect(JSON.stringify(input)).toBe(before);
});
it("shows unmatched source warnings rather than hiding failed or unsupported evidence", () => {
  const input = fixture(); input.analysis.evidence_items[1].authority_scope = [];
  input.analysis.evidence_items[1].retrieval_health = "unhealthy";
  render(<InvestigationEvidence {...input} row="responses" />);
  expect(screen.getByText("Additional source context")).toBeVisible();
  expect(screen.getByText("Original Alpha words, including $7.50 and unconfirmed timing.")).toBeInTheDocument();
});
it("shows stock after holds including zero and uses baseline exposure instead of recommendation exposure", () => {
  const input = fixture();
  editSnapshot(input, s => {
    s.disruption = {disruption_id: "d", supplier_id: "RL-SUP-ALPHA", po_line_id: "po", part_id: "p",
      plant_id: "RL-PLANT-CHI", original_quantity: 8000, original_due_date: "2026-09-03",
      partial_quantity: 0, partial_due_date: null, recovery_date: null, source_ref: "RL-001"};
    s.inventory_positions = [{inventory_id: "i", part_id: "p", plant_id: "RL-PLANT-CHI",
      on_hand: 4500, quality_hold: 200, protected_allocation: 300}];
  });
  const baseline: NonNullable<AnalysisVersion["recommendation"]> = {option_id: "baseline", option_kind: "no_mitigation",
    name: "Baseline", executable: false, active_mitigation: false,
    predicted: {uncovered_part_demand: 6800, otif_loss_percentage: 100, revenue_at_risk: "955000.00",
      margin_at_risk: "328000.00", response_cost: "0.00", protected_customer_order_ids: []},
    assumptions: [], evidence_ids: [], evidence_requirements: [], blocking_codes: [], prerequisite_roles: [],
    source_data_lineage: [], approval_burden: 0, execution_risk: 0, requested_side_effects: []};
  input.analysis.response_options = [baseline];
  input.analysis.recommendation = {...baseline, option_id: "combined", option_kind: "combined",
    predicted: {...baseline.predicted!, uncovered_part_demand: 2300}};
  const {rerender} = render(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getByText("4,000 component units available after holds and protected allocations.")).toBeVisible();
  expect(screen.getByText("6,800 p component units")).toBeVisible();
  expect(screen.queryByText("2,300 p component units")).not.toBeInTheDocument();
  editSnapshot(input, s => { s.inventory_positions[0].on_hand = 500; });
  rerender(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getByText("0 component units available after holds and protected allocations.")).toBeVisible();
  editSnapshot(input, s => { s.inventory_positions[0].on_hand = 0; });
  rerender(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getByText("Holds and protected allocations exceed on-hand stock in this snapshot.")).toBeVisible();
});
it("does not subtract a late partial delivery from the original affected delivery", () => {
  const input = fixture();
  editSnapshot(input, s => { s.disruption = {disruption_id: "d", supplier_id: "RL-SUP-ALPHA", po_line_id: "po",
    part_id: "RL-MAT-10247", plant_id: "RL-PLANT-CHI", original_quantity: 8000, original_due_date: "2026-09-03",
    partial_quantity: 3000, partial_due_date: "2026-09-06", recovery_date: null, source_ref: "RL-001"}; });
  render(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.getByText(/Original delivery affected: 8,000 component units/)).toBeVisible();
  expect(screen.getByText(/Recorded partial supply: 3,000 units; date: September 6, 2026/)).toBeVisible();
  expect(screen.queryByText(/Missed quantity.*5,000/)).not.toBeInTheDocument();
});
it("does not place a different supplier's saved shipment under the Supplier Alpha mapping", () => {
  const input = fixture(); editSnapshot(input, s => { s.alpha_expedite.supplier_id = "OTHER-SUPPLIER"; });
  render(<InvestigationEvidence {...input} row="responses" />);
  expect(screen.queryByText("View shipment record")).not.toBeInTheDocument();
  expect(screen.queryByText(/Scheduled receipt: 3,000/)).not.toBeInTheDocument();
  expect(screen.getByText("Additional source context")).toBeVisible();
});
it("does not place a transfer from a different plant under the Dallas plant mapping", () => {
  const input = fixture(); const record = input.analysis.evidence_items[0];
  record.evidence_id = "RL-TRANSFER-DAL-CHI-1500";
  record.source_id = "fabric.inventory_transfer/RL-TRANSFER-DAL-CHI-1500";
  input.analysis.material.evidence[0] = {...input.analysis.material.evidence[0], evidence_id: record.evidence_id, source_id: record.source_id};
  editSnapshot(input, s => { s.transfer.source_plant_id = "OTHER-PLANT"; });
  render(<InvestigationEvidence {...input} row="responses" />);
  expect(screen.queryByText("View transfer record")).not.toBeInTheDocument();
  expect(screen.queryByText("Dallas plant to Chicago plant")).not.toBeInTheDocument();
});
it("does not attribute an out-of-scenario authority-scoped source to Supplier Alpha", () => {
  const input = fixture(); input.analysis.material.corpus = "real_business";
  render(<InvestigationEvidence {...input} row="disruption" />);
  expect(screen.queryByText("Supplier email — RL-Supplier Alpha — Current supplier")).not.toBeInTheDocument();
  expect(screen.getByText("Supplier email unavailable for this analysis")).toBeVisible();
});
```

- [ ] **Step 2: Run `cd apps/web && npx vitest run src/components/InvestigationEvidence.test.tsx`.** Expected: missing-module failure.
- [ ] **Step 3: Create `EvidenceSource.tsx` with the reusable extraction below.** The live required-citation warning still examines all required items, including Fabric items; hiding a generic UI action does not remove the validation warning or change the hook's safety gate. Fallback arbitrary URLs are no longer emitted. No valid live email/Teams target changes. Original excerpts use a native disclosure while source role, warning, and source link remain visible.

```tsx
import type {AnalysisVersion, EvidenceItem} from "../types";
import {trustedServerCitation} from "../security/trustedUrls";
import {EvidenceFooter} from "./EvidenceFooter";
import {evidenceStatus} from "./evidenceStatus";

type SourceProps = {item: EvidenceItem; analysis: AnalysisVersion; tenantSharePointHost?: string | null; label?: string};
export const statusFor = (item: EvidenceItem, analysis: AnalysisVersion) => evidenceStatus(item, {
  ...analysis, results: analysis.evidence_validation?.item_results ?? [],
});
function citation(item: EvidenceItem, analysis: AnalysisVersion, host?: string | null) {
  if (analysis.runtime_mode !== "live" || item.source_system !== "work_iq" || item.citation_classification !== "work_iq") return null;
  return trustedServerCitation(item.navigable_citation_url, item.citation_classification, host);
}
function citationLabel(item: EvidenceItem, url: string) {
  const host = new URL(url).hostname;
  if (["outlook.office.com", "outlook.office365.com"].includes(host) && item.authority_scope.includes("supplier_statement")) return "Open supplier email";
  if (host === "teams.microsoft.com" && item.authority_scope.includes("collaboration_statement")) return "Open Quality Teams post";
  return "Open citation";
}
export function RequiredCitationWarning({analysis, tenantSharePointHost}: {analysis: AnalysisVersion; tenantSharePointHost?: string | null}) {
  const missing = analysis.runtime_mode === "live" && analysis.evidence_items.some(item =>
    item.requirement === "required_authoritative" && !trustedServerCitation(item.navigable_citation_url, item.citation_classification, tenantSharePointHost));
  return missing ? <p className="warning" role="alert">Required live citation missing</p> : null;
}
export function EvidenceSource({item, analysis, tenantSharePointHost, label = "Source statement"}: SourceProps) {
  const status = statusFor(item, analysis); const url = citation(item, analysis, tenantSharePointHost);
  return <div className="source-evidence">
    <p className="source-role">{label}</p>
    {status.warning && <p className="warning" role="alert">{status.warning}</p>}
    {item.excerpt ? <details><summary>Read original {label.toLowerCase()} excerpt</summary><blockquote>{item.excerpt}</blockquote></details>
      : <p>Source excerpt unavailable</p>}
    <details><summary>Source details</summary>
      <dl className="compact-list">
        <div><dt>Source record ID</dt><dd>{item.source_id?.trim() || "Unavailable"}</dd></div>
        <div><dt>Evidence ID</dt><dd>{item.evidence_id}</dd></div>
        <div><dt>Technical authority scopes</dt><dd>{item.authority_scope.join(", ")}</dd></div>
        <div><dt>Internal evidence classification</dt><dd>{item.uncertainty_state}</dd></div>
      </dl>
      <p>Saved source claim: {item.claim}</p>
      <p>The internal classification is not a probability or a guarantee of supplier performance.</p>
    </details>
    {url && <a href={url} target="_blank" rel="noopener noreferrer">{citationLabel(item, url)}</a>}
  </div>;
}
export function EvidenceFooters({items, analysis}: {items: EvidenceItem[]; analysis: AnalysisVersion}) {
  return <div className="source-footers">{items.map((item, index) => <div key={`${item.evidence_id}-${index}`}>
    <p className="footer-source">{item.kind === "operational_fact" ? "Supporting record" : "Source statement"}</p>
    <EvidenceFooter status={statusFor(item, analysis)} />
  </div>)}</div>;
}
```

Replace `EvidencePanel.tsx` with this compatibility wrapper. Production code imports the helpers directly from `EvidenceSource.tsx`, so the old wrapper does not own the new layout's behavior:

```tsx
import type {AnalysisVersion} from "../types";
import {EvidenceFooter} from "./EvidenceFooter";
import {EvidenceSource, RequiredCitationWarning, statusFor} from "./EvidenceSource";
export function EvidencePanel({analysis, tenantSharePointHost}: {analysis: AnalysisVersion | null; tenantSharePointHost?: string | null}) {
  if (!analysis) return null;
  return <section className="panel" aria-labelledby="evidence-heading">
    <h2 id="evidence-heading">Evidence items</h2>
    <RequiredCitationWarning analysis={analysis} tenantSharePointHost={tenantSharePointHost} />
    <div className="card-grid">{analysis.evidence_items.map((item, index) => <article className="evidence-card" key={`${item.evidence_id}-${index}`}>
      <h3>{item.claim}</h3><EvidenceSource item={item} analysis={analysis} tenantSharePointHost={tenantSharePointHost} />
      <EvidenceFooter status={statusFor(item, analysis)} />
    </article>)}</div>
  </section>;
}
```

In `LiveSafety.test.tsx`, remove this single tuple from `citationCases`:

```ts
  ["fabric", "qualification_state", "https://app.powerbi.com/groups/demo/reports/report", "Open citation"],
```

Add this test inside `describe("live journey safety", ...)`:

```tsx
  it("does not present a generic Fabric report as a record citation", () => {
    const analysis = liveAnalysis({source_system: "fabric", authority_scope: ["qualification_state"],
      citation_url: "https://app.powerbi.com/groups/demo/reports/report",
      navigable_citation_url: "https://app.powerbi.com/groups/demo/reports/report", citation_classification: "fabric"});
    render(<EvidencePanel analysis={analysis} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText("Required live citation missing")).not.toBeInTheDocument();
  });
```

Create `InvestigationEvidence.tsx`:

```tsx
import type {ReactNode} from "react";
import type {AnalysisVersion, CaseInstance, EvidenceItem} from "../types";
import {EvidenceSource, EvidenceFooters} from "./EvidenceSource";
import {resolveSupportingRecord, type SupportingRecordResult} from "./supportingRecord";
import {SupportingRecordDetails} from "./SupportingRecordDetails";
import {readPlannerSnapshot} from "./plannerSnapshot";
import {calendar, money, number, plant, supplier} from "./plannerFormatting";
import {PredictionSummary} from "./PredictionSummary";

type Props = {caseInstance: CaseInstance; analysis: AnalysisVersion; tenantSharePointHost?: string | null; row: "disruption" | "responses"};
const unavailable: SupportingRecordResult = {status: "unavailable", message: "Supporting record unavailable"};

export function InvestigationEvidence({caseInstance, analysis, tenantSharePointHost, row}: Props) {
  const input = {caseInstance, analysis}; const snapshot = readPlannerSnapshot(input); const d = snapshot?.disruption;
  const all = analysis.evidence_items;
  const supportedScenario = snapshot !== null;
  const currentSupplierMapped = supportedScenario && d?.supplier_id === "RL-SUP-ALPHA"
    && d.part_id === "RL-MAT-10247" && d.plant_id === "RL-PLANT-CHI";
  const belongs = (item: EvidenceItem) => item.case_id === analysis.case_id && item.runtime_mode === analysis.runtime_mode
    && item.retrieved_for_analysis_id === analysis.analysis_id;
  const supplierItems = supportedScenario ? all.filter(item => belongs(item) && item.kind === "source_statement"
    && item.authority_scope.includes("supplier_statement")) : [];
  const qualityItems = supportedScenario ? all.filter(item => belongs(item) && item.kind === "source_statement"
    && item.authority_scope.includes("collaboration_statement")) : [];
  const resolved = all.map(item => ({item, result: resolveSupportingRecord(input, item.evidence_id)}));
  const select = (kind: "shipment" | "transfer" | "qualification") => {
    const matches = resolved.filter(entry => entry.result.status === "available" && entry.result.record.kind === kind);
    if (matches.length !== 1) return null;
    const match = matches[0]; if (match.result.status !== "available") return null;
    const r = match.result.record;
    const mapped = r.part_id === "RL-MAT-10247" && (r.kind === "shipment"
      ? r.supplier_id === "RL-SUP-ALPHA" && r.plant_id === "RL-PLANT-CHI"
      : r.kind === "transfer" ? r.source_plant_id === "RL-PLANT-DAL" && r.destination_plant_id === "RL-PLANT-CHI"
      : r.supplier_id === "RL-SUP-BETA");
    return mapped ? match : null;
  };
  const shipment = select("shipment"); const transfer = select("transfer"); const qualification = select("qualification");
  const used = new Set([...supplierItems, ...qualityItems, ...[shipment, transfer, qualification].flatMap(entry => entry ? [entry.item] : [])]);
  const other = all.filter(item => !used.has(item));
  const sources = (items: EvidenceItem[], label: string) => items.map((item, index) =>
    <EvidenceSource key={`${item.evidence_id}-${index}`} item={item} analysis={analysis} tenantSharePointHost={tenantSharePointHost} label={label} />);
  const card = (title: string, content: ReactNode, items: EvidenceItem[]) => <article className="evidence-card">
    <h3>{title}</h3>{content}{items.length ? <EvidenceFooters items={items} analysis={analysis} />
      : <footer className="saved-analysis-footer">Saved analysis snapshot. Separate source retrieval and validation details unavailable.</footer>}
  </article>;
  if (row === "disruption") {
    const inventory = d && snapshot?.inventory?.filter(position => position.part_id === d.part_id && position.plant_id === d.plant_id);
    const total = (key: "on_hand" | "quality_hold" | "protected_allocation") => inventory?.reduce((sum, item) => sum + item[key], 0) ?? 0;
    const usable = total("on_hand") - total("quality_hold") - total("protected_allocation");
    const safeTotals = [total("on_hand"), total("quality_hold"), total("protected_allocation"), usable].every(Number.isSafeInteger);
    const baselines = analysis.response_options.filter(option => option.option_kind === "no_mitigation");
    return <>
      {card("What changed?", <>
        <p>{d ? supplier(d.supplier_id) : "Supplier identity unavailable in the saved disruption"}</p>
        {d ? <><p>Saved disruption: {number(d.original_quantity)} component units were due {calendar(d.original_due_date)} at {plant(d.plant_id)}.</p>
          <p>Component: {d.part_id}. Recorded partial supply: {number(d.partial_quantity)} units; date: {calendar(d.partial_due_date)}.</p>
          <p>Original delivery affected: {number(d.original_quantity)} component units.</p>
          <details><summary>Disruption source details</summary><p>A partial receipt dated after the original due date does not establish an on-time delivery.</p>
            <p>Source reference: {d.source_ref}. Purchase-order line: {d.po_line_id}.</p></details>
          <p>Saved recovery date: {calendar(d.recovery_date)}.</p></> : <p>Saved disruption details unavailable</p>}
        {supplierItems.length ? sources(supplierItems, currentSupplierMapped ? "Supplier email — RL-Supplier Alpha — Current supplier" : "Supplier email") : <p>Supplier email unavailable for this analysis</p>}
      </>, supplierItems)}
      {card("What do we have available?", <>
        {d && inventory?.length && safeTotals ? <><p>{plant(d.plant_id)} · {d.part_id}</p>
          <p>{number(usable)} component units available after holds and protected allocations.</p>
          <dl className="compact-list"><div><dt>On hand</dt><dd>{number(total("on_hand"))} component units</dd></div>
            <div><dt>Quality holds</dt><dd>{number(total("quality_hold"))} component units</dd></div>
            <div><dt>Protected allocations</dt><dd>{number(total("protected_allocation"))} component units</dd></div></dl>
          {usable < 0 && <p className="warning">Holds and protected allocations exceed on-hand stock in this snapshot.</p>}
          <details><summary>Source details</summary><p>Inventory records: {inventory.map(item => item.inventory_id).join(", ")}</p></details>
        </> : <p>Available stock unavailable in the saved snapshot</p>}
        <p>Inventory record snapshot used for this analysis; a separate record retrieval time is unavailable.</p>
      </>, [])}
      {card("What does that put at risk?", <>
        <PredictionSummary predicted={baselines.length === 1 ? baselines[0].predicted : null} snapshot={snapshot} basis="baseline" />
        <details><summary>Affected production and customer orders</summary>
          <p>Orders in this saved planning analysis; individual service outcomes are shown only by the saved prediction.</p>
          {snapshot?.production?.length ? <ul>{snapshot.production.map(order => <li key={order.production_order_id}>
            Production {order.production_order_id}: {number(order.quantity)} finished-product units of {order.product_id} at {plant(order.plant_id)}, due {calendar(order.due_date)}.
            {order.component_demand !== null && <> Component demand: {number(order.component_demand)} units.</>}
          </li>)}</ul> : <p>Production orders unavailable</p>}
          {snapshot?.customers?.length ? <ul>{snapshot.customers.map(order => <li key={order.customer_order_line_id}>
            Customer line {order.customer_order_line_id}: {number(order.quantity)} finished-product units of {order.product_id}, due {calendar(order.due_date)}; unit revenue {money(order.unit_revenue)}.
          </li>)}</ul> : <p>Customer order lines unavailable</p>}
        </details>
      </>, [])}
    </>;
  }
  const s = shipment?.result.status === "available" && shipment.result.record.kind === "shipment" ? shipment.result.record : null;
  const t = transfer?.result.status === "available" && transfer.result.record.kind === "transfer" ? transfer.result.record : null;
  const q = qualification?.result.status === "available" && qualification.result.record.kind === "qualification" ? qualification.result.record : null;
  const qName = q?.supplier_id === "RL-SUP-BETA" ? "Supplier Beta" : q ? supplier(q.supplier_id) : "Supplier";
  const qStatus = q?.status === "approved" ? `${qName} qualification is approved in this snapshot`
    : q?.status === "pending" ? `${qName} is not yet qualified`
    : q?.status === "conditional" ? `${qName} qualification is conditional`
    : `${qName} qualification is not approved`;
  const qFlag = (flag: boolean | null) => flag === null ? "Unavailable" : flag ? "Complete" : "Incomplete";
  return <>
    {card("What can Supplier Alpha still supply?", <>
      <p>{s ? supplier(s.supplier_id) : supportedScenario ? "RL-Supplier Alpha — Current supplier" : "Supplier identity unavailable"}</p>
      {s ? <><p>Scheduled receipt: {number(s.quantity)} component units on {calendar(s.due_date)}.</p>
        <p>{s.part_id} to {plant(s.plant_id)}; incremental cost {s.incremental_cost_per_unit} per unit (currency not specified).</p></> : <p>Saved partial shipment unavailable</p>}
      <p>The scheduled receipt and supplier statement have separate source roles; a receipt is not an approval.</p>
      {d && <p>Remaining recovery date in the saved plan: {calendar(d.recovery_date)}.</p>}
      {supplierItems.length ? sources(supplierItems, s ? "Supplier email — RL-Supplier Alpha — Current supplier (scenario role)" : "Supplier email") : <p>Supplier email unavailable for this analysis</p>}
      {shipment && sources([shipment.item], "Shipment record")}
      <SupportingRecordDetails result={shipment?.result ?? unavailable} />
    </>, [...supplierItems, ...(shipment ? [shipment.item] : [])])}
    {card("Can another plant help?", <>
      {t ? <><p>{plant(t.source_plant_id)} to {plant(t.destination_plant_id)}</p>
        <p>{number(t.quantity)} {t.part_id} component units; arrival {calendar(t.arrival_date)}.</p>
        <p>Dispatch {calendar(t.dispatch_date)}; incremental cost {t.incremental_cost_per_unit} per unit (currency not specified).</p></> : <p>Saved plant transfer unavailable</p>}
      {transfer && sources([transfer.item], "Transfer record")}
      <SupportingRecordDetails result={transfer?.result ?? unavailable} />
    </>, transfer ? [transfer.item] : [])}
    {card("Can we use the alternate supplier?", <>
      <p>{q ? supplier(q.supplier_id) : supportedScenario ? "RL-Supplier Beta — Alternate supplier" : "Supplier identity unavailable"}</p>
      {q ? <><p className={q.status === "approved" ? undefined : "warning"}>{qStatus}</p>
        <p>Audit: {qFlag(q.audit_complete)}. First article: {qFlag(q.first_article_complete)}.</p>
        <p>Expected qualification decision: {calendar(q.expected_decision_date)}. This is not an approval or delivery date.</p></> : <p>Saved supplier qualification unavailable</p>}
      {qualification && sources([qualification.item], "Qualification record")}
      {qualityItems.length ? <><p>Scenario role: Jordan Lee — Quality Manager. Author identity is not a separate verified field in this saved payload.</p>
        {sources(qualityItems, "Quality Teams post")}</> : <p>Quality Teams post unavailable for this analysis</p>}
      <SupportingRecordDetails result={qualification?.result ?? unavailable} />
      {other.length > 0 && <details><summary>Additional source context</summary>{sources(other, "Unmatched source context — role unavailable")}</details>}
    </>, [...qualityItems, ...(qualification ? [qualification.item] : []), ...other])}
  </>;
}
```

Missing/unmatched operational evidence retains its footer in the final card's additional-context collection. Its critical footer warning must also remain outside the collapsed context: add the following immediately before the `other.length > 0` disclosure above, and import `evidenceStatus` at the top. This makes failures visible without forcing unsupported records into a falsely matched response card.

```tsx
import {evidenceStatus} from "./evidenceStatus";
```

```tsx
      {other.map((item, index) => {
        const warning = evidenceStatus(item, {...analysis, results: analysis.evidence_validation.item_results}).warning;
        return warning ? <p className="warning" role="alert" key={`${item.evidence_id}-${index}`}>Additional source context: {warning}</p> : null;
      })}
```

- [ ] **Step 4: Run `cd apps/web && npx vitest run src/components/InvestigationEvidence.test.tsx src/components/LiveSafety.test.tsx src/components/EvidenceFooter.test.tsx src/components/evidenceStatus.test.ts && npm run build`.** Expected: new and preserved safety tests pass. The standalone compatibility wrapper retains its direct footer child, so the existing strict order assertions remain unchanged.
- [ ] **Step 5: Parent reviews the source linkage and warnings before an eventual `feat: organize disruption and response evidence cards` commit.**

## Task 4: Compose the third row and preserve explicit decisions

**Files:** Modify `OptionComparison.tsx`, `ExposurePanel.tsx`, `DecisionPanel.tsx`; create `InvestigationFlow.tsx`, `InvestigationFlow.test.tsx`; modify `App.tsx`, `App.test.tsx`, `styles.css`.

**Interfaces:** `InvestigationFlow({state}: {state: CaseWorkspaceState})`; `OptionComparison` gains optional `snapshot?: PlannerSnapshot | null`; `ExposurePanel` gains optional `snapshot?: PlannerSnapshot | null`. Existing callers with only analysis still compile. State callbacks pass straight through; no effect or fetch is added.

- [ ] **Step 1: Add this focused composition test.** The test intentionally uses empty malformed material to verify fixed empty-state positions without creating a second giant API fixture.

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {InvestigationFlow} from "./InvestigationFlow";
afterEach(cleanup);

function state(): CaseWorkspaceState {
  const at = "2026-09-01T09:00:00-05:00";
  const ranking = {policy_version: "v1", eligible_option_ids: [], infeasible_option_ids: [],
    excluded_baseline_ids: [], stages: [], recommended_option_id: null, no_feasible_mitigation: true};
  const validation = {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: []};
  return {runtime: null, selectedOption: null, decision: null, actions: [], drafts: [], playback: null,
    observations: [], operation: null, error: null, decisionBlocked: true,
    create: vi.fn(), analyze: vi.fn(), selectOption: vi.fn(), approve: vi.fn(), reject: vi.fn(),
    retryPlanning: vi.fn(), retryAction: vi.fn(), startPlayback: vi.fn(),
    caseInstance: {case_id: "c", template_id: "RL-001", purpose: "showcase", runtime_mode: "fallback",
      scenario_effective_time: at, scenario_timezone: "America/Chicago", status: "awaiting_decision",
      current_analysis_id: "a", current_decision_id: null, display_status: null, recorded_at: at, projection_updated_at: at,
      controls: {new_analysis: false, decide: false, retry_action_planning: false, start_playback: false}},
    analysis: {analysis_id: "a", case_id: "c", runtime_mode: "fallback", scenario_effective_time: at,
      analysis_started_at: at, retrieval_window_ends_at: at, created_at: at, material_hash: "hash", evidence_items: [],
      evidence_validation: validation, response_options: [], approval_satisfactions: [], ranking, recommendation: null,
      material: {case_id: "c", template_id: "RL-001", case_purpose: "showcase", runtime_mode: "fallback", corpus: "demo_corpus",
        scenario_effective_time: at, operational_snapshot_json: "{}", required_authority_scope: [], evidence: [],
        conflicts: [], conflict_resolutions: [], evidence_validation: validation, response_options: [], standing_authorizations: [],
        approval_satisfactions: [], ranking, calculation_version: "v1", evidence_policy_version: "v1", approval_policy_version: "v1"}}};
}
it("keeps all nine cards in the exact approved row and DOM reading order", () => {
  render(<InvestigationFlow state={state()} />);
  expect(screen.getAllByRole("heading", {level: 2}).map(h => h.textContent)).toEqual([
    "1. Understand the disruption", "2. Investigate responses", "3. Make the decision",
  ]);
  expect(screen.getAllByRole("heading", {level: 3}).map(h => h.textContent)).toEqual([
    "What changed?", "What do we have available?", "What does that put at risk?",
    "What can Supplier Alpha still supply?", "Can another plant help?", "Can we use the alternate supplier?",
    "Compare the options.", "Recommended response—and why.", "Review and approve.",
  ]);
  expect(screen.getByRole("button", {name: "Approve selected response"})).toBeDisabled();
});
it("keeps rejection explicit and respects the existing blocked state", async () => {
  const input = state(); render(<InvestigationFlow state={input} />);
  const decision = screen.getByRole("region", {name: "Review and approve."});
  expect(within(decision).getByLabelText("Rejection reason")).toBeDisabled();
  expect(input.approve).not.toHaveBeenCalled(); expect(input.reject).not.toHaveBeenCalled();
  cleanup(); input.decisionBlocked = false; render(<InvestigationFlow state={input} />);
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Wait for evidence");
  await userEvent.click(screen.getByRole("button", {name: "Reject recommendation"}));
  expect(input.reject).toHaveBeenCalledWith("Wait for evidence");
  expect(input.approve).not.toHaveBeenCalled();
});
it("reports historical and closed case state without inventing an awaiting decision", () => {
  const input = state(); input.caseInstance!.status = "closed";
  input.caseInstance!.current_analysis_id = "newer";
  render(<InvestigationFlow state={input} />);
  expect(screen.getByText("Historical saved analysis. Case closed; no decision is shown for this analysis.")).toBeVisible();
  expect(screen.queryByText("Awaiting your explicit decision")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run `cd apps/web && npx vitest run src/components/InvestigationFlow.test.tsx`.** Expected: missing-module failure.
- [ ] **Step 3: Replace `OptionComparison.tsx` with this compact card.** Selection button state and callbacks stay exactly executable-driven, baseline remains non-executable, ranking stays server-owned.

```tsx
import type {AnalysisVersion, ResponseOption} from "../types";
import type {PlannerSnapshot} from "./plannerSnapshot";
import {optionDisplayName} from "./optionLabels";
import {blocker} from "./plannerFormatting";
import {PredictionSummary} from "./PredictionSummary";
export function OptionComparison({analysis, selectedOption, onSelect, snapshot = null}: {
  analysis: AnalysisVersion | null; selectedOption: ResponseOption | null;
  onSelect: (option: ResponseOption) => void; snapshot?: PlannerSnapshot | null;
}) {
  if (!analysis) return null;
  const options = [...analysis.response_options].sort((a, b) => Number(b.option_kind === "no_mitigation") - Number(a.option_kind === "no_mitigation"));
  return <section className="panel investigation-card" aria-labelledby="options-heading">
    <h3 id="options-heading">Compare the options.</h3>
    {!options.some(option => option.option_kind === "no_mitigation") && <p>Do-nothing baseline unavailable in this saved analysis</p>}
    <div className="planner-options">{options.map(option => {
      const name = optionDisplayName(option); const baseline = option.option_kind === "no_mitigation";
      return <article aria-label={name} className={`option-card ${!option.executable ? "blocked" : ""}`} key={option.option_id}>
        <h4>{name}</h4>
        {option.option_id === analysis.ranking.recommended_option_id && <span className="badge accent">Recommended for review</span>}
        <p>{baseline ? "Comparison only" : option.executable ? "Meets the planning requirements" : "Does not meet the planning requirements"}</p>
        {option.blocking_codes.length > 0 && <ul>{option.blocking_codes.map(code => <li key={code}>{blocker(code)}</li>)}</ul>}
        <PredictionSummary predicted={option.predicted} snapshot={snapshot} basis={baseline ? "baseline" : "response"} compact />
        <details><summary>Full option metrics, assumptions, and calculation details</summary>
          <PredictionSummary predicted={option.predicted} snapshot={snapshot} basis={baseline ? "baseline" : "response"} />
          <ul>{option.assumptions.map((text, index) => <li key={index}>{text}</li>)}</ul>
          <p>Execution risk score: {option.execution_risk}</p>
          <p>Source records: {option.source_data_lineage.join(", ") || "Unavailable"}</p>
        </details>
        <button type="button" disabled={!option.executable} aria-pressed={selectedOption?.option_id === option.option_id}
          onClick={() => onSelect(option)}>Select {name}</button>
      </article>;
    })}</div>
    <details className="trace"><summary>How the saved analysis ranked the options</summary>
      {analysis.ranking.stages.length === 0 ? <p>No options were eliminated by ranking stages.</p> : <ol>
        {analysis.ranking.stages.map((stage, index) => <li key={`${stage.comparator}-${index}`}>
          {stage.comparator.replaceAll("_", " ")}: threshold {stage.threshold}; eliminated {stage.eliminated_option_ids.join(", ") || "none"}
        </li>)}
      </ol>}
    </details>
    <footer className="saved-analysis-footer">Saved analysis comparison; selection is not approval or execution.</footer>
  </section>;
}
```

Replace `ExposurePanel.tsx` with:

```tsx
import type {AnalysisVersion} from "../types";
import type {PlannerSnapshot} from "./plannerSnapshot";
import {optionDisplayName} from "./optionLabels";
import {PredictionSummary} from "./PredictionSummary";
import {blocker, role, rankingReason} from "./plannerFormatting";
export function ExposurePanel({analysis, snapshot = null}: {analysis: AnalysisVersion | null; snapshot?: PlannerSnapshot | null}) {
  if (!analysis) return null;
  const matches = analysis.response_options.filter(option => option.option_id === analysis.ranking.recommended_option_id);
  const option = matches.length === 1 && analysis.recommendation?.option_id === matches[0].option_id ? matches[0] : null;
  return <section className="panel investigation-card" aria-labelledby="exposure-heading">
    <h3 id="exposure-heading">Recommended response—and why.</h3>
    {option ? <>
      <p>Recommended for review: {optionDisplayName(option)}.</p>
      <p>Recommendation does not mean approval or execution.</p>
      {analysis.ranking.stages.some(stage => stage.retained_option_ids.includes(option.option_id))
        ? <ul aria-label="Reasons from the saved comparison">{analysis.ranking.stages.filter(stage => stage.retained_option_ids.includes(option.option_id))
          .map((stage, index) => <li key={index}>{rankingReason(stage, option.option_id)}</li>)}</ul>
        : <p>The saved analysis names this recommendation but contains no retained-stage explanation.</p>}
      <PredictionSummary predicted={option.predicted} snapshot={snapshot} basis="response" />
      {option.blocking_codes.length > 0 && <ul>{option.blocking_codes.map(code => <li key={code}>{blocker(code)}</li>)}</ul>}
      <p>Required roles: {option.prerequisite_roles.map(role).join(", ") || "No roles recorded"}.</p>
      {option.assumptions.length > 0 && <><h4>What remains uncertain</h4><ul>{option.assumptions.map((text, index) => <li key={index}>{text}</li>)}</ul></>}
      <details><summary>Why this option was retained</summary>
        <ol>{analysis.ranking.stages.map((stage, index) => <li key={index}>
          {stage.comparator.replaceAll("_", " ")}: {stage.retained_option_ids.includes(option.option_id) ? "recommended option retained" : "see saved ranking"}; threshold {stage.threshold}.
        </li>)}</ol>
        <p>Source records: {option.source_data_lineage.join(", ") || "Unavailable"}</p>
        <p>Calculation version: {analysis.material.calculation_version}</p>
      </details>
    </> : <p>No unambiguous recommendation is available in this saved analysis.</p>}
    <footer className="saved-analysis-footer">Saved analysis recommendation; benefits are predictions.</footer>
  </section>;
}
```

Make these exact localized edits in `DecisionPanel.tsx`; preserve all remaining code including `disabled`, `onApprove`, `onReject`, the receipt, and reason state:

```tsx
// Add import:
import {blocker, role, decisionContext} from "./plannerFormatting";

// Replace the opening section, step, and h2 with:
  return <section className="panel investigation-card" aria-labelledby="decision-heading">
    <h3 id="decision-heading">Review and approve.</h3>
    <p>{decisionContext(state.caseInstance, state.analysis.analysis_id, Boolean(state.decision))}</p>

// Replace the blocking-code map expression with:
        {blockingCodes.map((code, index) => <li key={`${code}-${index}`}>{blocker(code)}</li>)}

// Replace the Selected option paragraph with:
      <p>Selected option: {state.selectedOption ? optionDisplayName(state.selectedOption) : "None"}</p>
      {state.selectedOption && <ul aria-label="Required approval roles">{state.selectedOption.prerequisite_roles.map(required => {
        const satisfied = state.analysis!.approval_satisfactions.some(item => item.analysis_id === state.analysis!.analysis_id
          && item.option_id === state.selectedOption!.option_id && item.role === required && item.satisfied);
        return <li key={required}>{role(required)}: {satisfied ? "Recorded authorization satisfied" : "No satisfied authorization recorded"}</li>;
      })}</ul>}

// Insert immediately before the closing </section>:
    <footer className="saved-analysis-footer">Approval remains an explicit user action. Any execution shown afterward is separately labeled.</footer>
```

Create `InvestigationFlow.tsx`:

```tsx
import type {ReactNode} from "react";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {InvestigationEvidence} from "./InvestigationEvidence";
import {RequiredCitationWarning} from "./EvidenceSource";
import {ExposurePanel} from "./ExposurePanel";
import {OptionComparison} from "./OptionComparison";
import {DecisionPanel} from "./DecisionPanel";
import {readPlannerSnapshot} from "./plannerSnapshot";
import {instant} from "./plannerFormatting";

function Row({id, label, children}: {id: string; label: string; children: ReactNode}) {
  return <section className="investigation-row" aria-labelledby={id}>
    <h2 id={id}>{label}</h2><div className="investigation-cards">{children}</div>
  </section>;
}
export function InvestigationFlow({state}: {state: CaseWorkspaceState}) {
  const {caseInstance, analysis} = state;
  if (!analysis) return null;
  if (!caseInstance) return <p className="warning">Case context unavailable for this saved analysis</p>;
  const props = {caseInstance, analysis, tenantSharePointHost: state.runtime?.deployment_contract?.tenant_sharepoint_host};
  const snapshot = readPlannerSnapshot(props);
  return <div className="investigation-flow">
    <div className="analysis-context">
      <p>{analysis.material.corpus === "demo_corpus" ? "Demo corpus — fictional" : "Fictional provenance not established for this analysis"}</p>
      <p>Snapshot used for this analysis · In this scenario, as of {instant(analysis.scenario_effective_time)}</p>
      <p>Analysis saved at {instant(analysis.created_at)}. Saved records do not indicate ongoing monitoring.</p>
      {analysis.runtime_mode === "fallback" && <p>Demo fixture — not a live retrieval</p>}
      <details><summary>Analysis source details</summary><p>Case {analysis.case_id}</p><p>Analysis {analysis.analysis_id}</p></details>
    </div>
    <RequiredCitationWarning analysis={analysis} tenantSharePointHost={props.tenantSharePointHost} />
    <Row id="understand-row" label="1. Understand the disruption"><InvestigationEvidence {...props} row="disruption" /></Row>
    <Row id="responses-row" label="2. Investigate responses"><InvestigationEvidence {...props} row="responses" /></Row>
    <Row id="decision-row" label="3. Make the decision">
      <OptionComparison analysis={analysis} selectedOption={state.selectedOption} onSelect={state.selectOption} snapshot={snapshot} />
      <ExposurePanel analysis={analysis} snapshot={snapshot} />
      <DecisionPanel state={state} onApprove={state.approve} onReject={state.reject} />
    </Row>
  </div>;
}
```

In `App.tsx`, replace imports of `DecisionPanel`, `EvidencePanel`, `ExposurePanel`, and `OptionComparison` with:

```tsx
import {InvestigationFlow} from "./components/InvestigationFlow";
```

Replace the contiguous JSX from `<EvidencePanel ... />` through `<DecisionPanel ... />` with:

```tsx
    <InvestigationFlow state={workspace} />
```

Keep CaseHeader, honest analysis-progress text, ExecutionPanel, OutcomePanel, authentication, and all callbacks exactly as they are. No new initialization, fetching, approving, or playback effects.

Append this scoped CSS to `styles.css`:

```css
.investigation-flow { display: grid; gap: 1.5rem; margin-top: 1.5rem; }
.analysis-context { padding: 0 0.4rem; color: #52645e; font-size: 0.85rem; }
.analysis-context p { margin: 0.4rem 0; }
.investigation-row { display: grid; grid-template-columns: minmax(9rem, 0.6fr) minmax(0, 3fr); gap: 1rem; align-items: start; }
.investigation-row > h2 { font-size: 1.15rem; line-height: 1.4; margin: 1rem 0; color: #075d4b; }
.investigation-cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.9rem; align-items: stretch; }
.investigation-cards > * { min-width: 0; margin: 0; padding: 1rem; }
.investigation-card { display: flex; flex-direction: column; gap: 0.5rem; }
.investigation-cards h3 { font-size: 1.15rem; line-height: 1.35; }
.investigation-cards h4 { margin: 0.3rem 0; }
.investigation-cards p, .investigation-cards li, .investigation-cards blockquote { overflow-wrap: anywhere; }
.investigation-cards blockquote { margin: 0.4rem 0; border-left: 3px solid #99b6a9; padding-left: 0.65rem; }
.investigation-cards .compact-list div { display: grid; gap: 0.3rem; }
.investigation-cards .compact-list dd { text-align: left; }
.investigation-cards .decision-controls { grid-template-columns: 1fr; }
.source-role { color: #52645e; font-size: 0.85rem; font-weight: 700; }
.source-footers { margin-top: auto; padding-top: 0.75rem; }
.source-footers .footer-source { margin: 0.4rem 0; font-size: 0.75rem; color: #52645e; overflow-wrap: anywhere; }
.source-footers .evidence-footer { padding-top: 0.5rem; }
.saved-analysis-footer { margin-top: auto; border-top: 1px solid #dde4dd; padding-top: 0.9rem; font-size: 0.8rem; color: #52645e; }
.planner-options { display: grid; gap: 0.8rem; }
.planner-options .option-card { padding: 0.75rem; }
.investigation-flow summary { cursor: pointer; font-weight: 600; }
.investigation-flow summary:focus-visible { outline: 3px solid #e69c37; outline-offset: 3px; }
.investigation-cards details { margin: 0.4rem 0; }
.investigation-cards details dl { display: grid; gap: 0.75rem; margin: 1rem 0; }
.investigation-cards details dl > div { display: grid; gap: 0.25rem; padding-bottom: 0.5rem; border-bottom: 1px solid #e8ece7; }
.investigation-cards details dt { color: #52645e; font-size: 0.85rem; }
.investigation-cards details dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }
.investigation-cards details details { padding-top: 0.5rem; border-top: 1px solid #d8dfd8; }
@media (max-width: 1000px) {
  .investigation-row { grid-template-columns: minmax(0, 1fr); }
  .investigation-row > h2 { margin: 0; }
}
@media (max-width: 760px) {
  .investigation-cards { grid-template-columns: minmax(0, 1fr); }
}
```

In `App.test.tsx`, make only these exact query substitutions (all occurrences); the recommendation card uses a prefixed sentence so the standalone `Combined response` option heading remains unambiguous:

```tsx
// Old:
screen.getByRole("heading", {name: "Evidence items"})
// New:
screen.getByRole("heading", {name: "1. Understand the disruption"})

// Old:
screen.getByRole("heading", {name: "Exposure and lineage"})
// New:
screen.getByRole("heading", {name: "Recommended response—and why."})

// Old:
screen.getByRole("heading", {name: "Decision receipt"})
// New:
screen.getByRole("heading", {name: "Review and approve."})
```

Replace the exact three Beta assertions in `it("keeps blocked Beta visible and nonselectable with its exact code", ...)` with the following; rename that test to `keeps the alternate supplier blocker visible and nonselectable`. The displayed blocker now explains the same saved code:

```tsx
    const beta = await screen.findByRole("article", {name: "Use the alternate supplier"});
    expect(within(beta).getByText("Cannot use Supplier Beta yet: supplier qualification is incomplete")).toBeVisible();
    expect(within(beta).getByRole("button", {name: "Select Use the alternate supplier"})).toBeDisabled();
```

Keep `findByText("Combined response")` and all existing API request, approval, rejection, action-planning, child-action retry, playback concurrency, and synthetic-observation assertions intact. Generic option labels avoid falsely naming a supplier or plant when only an option kind is available; the associated response card owns the validated entity name.

In the `disables decision controls for stale or evidence-blocked analysis` test, replace the single exact-code visible-text query with the new explanatory copy while retaining both disabled assertions:

```tsx
    expect(await screen.findByText("Planning requirement unresolved (REQUIRED_EVIDENCE_STALE)")).toBeVisible();
```

- [ ] **Step 4: Run `cd apps/web && npx vitest run src/components/InvestigationFlow.test.tsx src/App.test.tsx && npm run build`.** Expected: new semantic-order/control tests and existing lifecycle tests pass. If an existing text assertion changes because of a specified display name, replace only that selector with the exact mapped business label; never delete the associated behavioral assertion.
- [ ] **Step 5: Parent reviews the final composition for the eventual `feat: present the approved three-row planner investigation` commit.**

## Task 5: Close coverage gaps and visually verify the integrated flow

**Files:** Modify only the four new test files if new evidence from review requires a correction. Existing test and build commands below are mandatory. This is a final acceptance gate, not permission to deploy or run live lifecycle scripts.

**Interfaces:** All contracts from Tasks 1–4. No production code interface additions in this gate.

- [ ] **Step 1: Add these negative field cases inside `describe("planner snapshot", ...)` in `plannerSnapshot.test.ts`.**

```ts
  it.each([
    ["inventory_positions", "on_hand", -1, "inventory"],
    ["inventory_positions", "quality_hold", false, "inventory"],
    ["production_orders", "quantity", 0, "production"],
    ["production_orders", "component_demand", "4", "production"],
    ["customer_orders", "unit_revenue", "5", "customers"],
    ["customer_orders", "production_order_id", false, "customers"],
  ] as const)("rejects malformed %s.%s", (member, key, value, result) => {
    const input = fixture(); editSnapshot(input, s => { s[member][0][key] = value; });
    expect(readPlannerSnapshot(input)?.[result]).toBeNull();
  });
```

- [ ] **Step 2: Add the following test to `PredictionSummary.test.tsx` to verify exact count/denominator and mismatch behavior.**

```tsx
it("renders customer-line semantics only when the exact saved one-to-one lineage and percentage agree", () => {
  const snapshot = {disruption: null, inventory: [],
    production: [{production_order_id: "mo", product_id: "p", plant_id: "plant", quantity: 2,
      due_date: "2026-09-06", component_demand: 4, customer_order_id: "co", customer_revenue: "10.00"}],
    customers: [{customer_order_line_id: "co", production_order_id: "mo", customer_id: "customer", product_id: "p",
      plant_id: "plant", quantity: 2, due_date: "2026-09-06", unit_revenue: "5.00"}]};
  const {rerender} = render(<PredictionSummary predicted={{...predicted, otif_loss_percentage: 100}} snapshot={snapshot} basis="response" />);
  expect(screen.getByText("100% (1 of 1 lines)")).toBeVisible();
  expect(screen.getByText("Customer order lines expected to miss the on-time, in-full target")).toBeVisible();
  rerender(<PredictionSummary predicted={{...predicted, otif_loss_percentage: 50}} snapshot={snapshot} basis="response" />);
  expect(screen.getByText("Production orders expected to miss the on-time, in-full target")).toBeVisible();
  expect(screen.queryByText(/of 1 lines/)).not.toBeInTheDocument();
});
```

- [ ] **Step 3: Run `cd apps/web && npm test && npm run build`.** Expected: full frontend suite and strict production build pass. Run `TZ=America/Los_Angeles npx vitest run src/components/PredictionSummary.test.tsx src/components/SupportingRecordDetails.test.tsx` from `apps/web` and `git diff --check` from the worktree root. Expected: no shifted dates, no test failures, no whitespace errors. Do not run `tests/fabric/test_power_bi_live.py` or any live API lifecycle script.
- [ ] **Step 4: Visually inspect the locally mocked application at 1440px and 390px widths.** Use the existing frontend mocked-test harness or locally intercepted API responses, without making real case, analysis, decision, or playback requests. Inspect one populated live-demo fixture, one explicit fallback fixture, and one malformed snapshot. The required observations are: row labels occupy the left at desktop; exactly three cards appear per row in order; mobile label then cards stack in the same DOM order; original supplier and Quality quotations remain unmodified; all amounts and dates wrap; footers sit at each card bottom; keyboard focus reaches source links/disclosures and explicit decision controls; opening every available record changes only disclosure state; zero inventory and false qualification flags remain visible; missing timestamps say unavailable; no evidence card navigates to Power BI. Capture populated and empty screenshots for parent visual review. Do not call this complete until that review is recorded.
- [ ] **Step 5: Parent reviews the bounded diff and recorded verification before committing acceptance corrections.** The plan is not release authorization. Deployment, reporting, case-dashboard URL changes, and cross-application navigation remain stages 3–6 of the delivery sequence.

## Self-review and handoff notes

Coverage: Task 1 covers remaining snapshot types, malformed members, empty arrays, zero, exact linkage, history, and no mutation. Task 2 covers units, currency, date safety, baseline versus recommendation, and no duplicate analytic engine. Task 3 covers the first six business positions, original source quotations and roles, exact supporting records, inline disclosure, source failures, safe unchanged live message destinations, and the removal of generic Fabric actions. Task 4 covers the exact three row labels/nine card headings, recommendation and roles, unchanged selection/approval/rejection/execution flow, and responsive reading order. Task 5 closes count/denominator and malformed-field regression coverage and requires real visual review before claiming completion.

Known scope/interface observations: there is no currency denomination, typed email fact payload, separate inventory retrieval event, or generally valid customer-line denominator in the existing API. The plan displays these limitations explicitly and does not expand API scope. Strict value and envelope validation is shared in `snapshotValidation.ts`. The supporting-record resolver retains its existing outer array/disruption requirements, then validates its selected record branch; the planner reader independently validates only its newly consumed sections. Thus an invalid business field within an array does not suppress a valid supporting transfer, while a non-array section continues to reject supporting-record resolution exactly as before. The supplied source-role mapping applies only to the approved RL-001 demo context; fixed response slots additionally require canonical supplier/plant/part mapping. Generic report removal changes the old Fabric-only citation expectation deliberately; tenant trust and missing-live-citation safety remain unchanged.

Controller preflight resolved the presentation choices: retain the standalone `EvidencePanel` compatibility wrapper for existing safety coverage, with production helpers in `EvidenceSource.tsx`; show compact cost/parts/service summaries initially and put full metrics/assumptions in native details. Original quotations can be expanded without hiding their source link or failure warning. These refinements stay within the approved design and require no additional authority.

Execution handoff: parent independently reviews this plan before task execution. It is saved as a standalone stage-2 plan, with supporting-record implementation as its explicit prerequisite. No implementation or commit is performed by this planning assignment.
