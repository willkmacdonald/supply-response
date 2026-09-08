# Supporting Record Inspection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve and inspect the exact saved shipment, transfer, or qualification record behind an analysis evidence item in an accessible, reusable inline component.

**Architecture:** A pure resolver validates the selected snapshot branch and its identity across the displayed case, analysis, material, and evidence before returning a typed record and immutable navigation context. A standalone React disclosure displays that result without network requests or application state changes. Integration into the investigation layout and Power BI navigation belongs to subsequent plans.

**Tech Stack:** Existing TypeScript, React, Vitest, Testing Library, and Vite; no added dependencies or backend changes.

## Global Constraints

- “Use `analysis.material.operational_snapshot_json` already returned by the API.”
- “Never render arbitrary HTML or unvalidated URLs.”
- “Preserve zero values and explicit false flags.”
- “Dates and currency must be formatted without timezone-related day shifts or invented units.”
- “Fallback data remains explicitly synthetic and is not relabeled as a Fabric record.”
- “Do not mutate immutable analysis material, source bundles, hashes, or stored citations, and do not weaken existing trusted-URL validation or approval rules.”
- “Snapshot used for this analysis” and “Demo corpus — fictional” remain visible in expanded details.
- “These are display clarifications, not source-data renames. Preserve original message text, source identifiers, citations, and immutable analysis records.”
- No production/network work, SQL/report changes, full three-row layout, or edits to the concurrently changing evidence footer and panel. No live queries or generic-report substitution.

---

## Boundaries and evidence for the design

Read the approved `docs/superpowers/specs/2026-09-08-evidence-records-and-case-dashboard-design.md`, especially Part 1 Data and validation, naming, and transparency. `data/domain/operations.py` defines positive receipt/transfer quantities, nonnegative decimal costs, calendar dates, and nullable qualification booleans/dates. `data/domain/common.py` serializes Money to two decimal places but supplies **no currency code**. Show the exact amount with “currency not specified”; do not add `$`, USD, or infer currency from the Chicago plant.

`data/synthetic/rl001.py` defines the snapshot envelope and fixture lineage. `integrations/fabric/demo_source.py` uses the three allowlisted source families. Qualification evidence ID is `evidence_ref` (`RL-QUALITY-001`), while source record ID is `qualification_id` (`RL-QUAL-BETA`); these must never be conflated. `integrations/fabric/operational.py` rebinds retrieved evidence to the case and analysis. Live demo evidence currently has `synthetic: false`; fictional content comes from `material.corpus === "demo_corpus"`, while service/fixture provenance comes from runtime and source system.

This increment supports RL-001 demo corpus explicitly. The resolver rejects other templates/corpora rather than falsely labeling real business records fictional. It validates the snapshot envelope and every displayed field of the selected record, not unrelated inventory/order business fields that this component never reads. An absent optional receipt is an unavailable shipment; it must not prevent a valid transfer from being inspected.

The exact-record context contains case ID, immutable analysis ID, runtime, evidence ID, record kind, actual record ID, and source ID. Future report routing consumes this context only after successful resolution, and must separately validate/encode allowlisted report destinations. No URL is emitted here. Historical displayed analyses remain inspectable: do not require `case.current_analysis_id` to equal the displayed saved analysis.

## File map

Create only:

- `apps/web/src/components/supportingRecord.ts`: narrow typed input, snapshot validation, identity resolution, immutable result.
- `apps/web/src/components/supportingRecord.fixture.ts`: deterministic test inputs, no application imports of this fixture.
- `apps/web/src/components/supportingRecord.test.ts`: resolver contract and negative cases.
- `apps/web/src/components/SupportingRecordDetails.tsx`: standalone accessible disclosure; no source-link behavior.
- `apps/web/src/components/SupportingRecordDetails.test.tsx`: DOM behavior and text safety.

Do not modify `types.ts`, `EvidencePanel.tsx`, `evidenceStatus.ts`, citation helpers, or existing footer tests. Full API objects structurally satisfy the new narrow inputs. No callers are added in this increment. The later layout task passes the displayed case, saved analysis, and evidence ID to `resolveSupportingRecord`, then passes its result to `SupportingRecordDetails` inside the originating card.

## Task 1: Validate and resolve exact saved supporting records

**Files:** Create the first three files in the file map.

**Interfaces:** Consumes existing `CaseInstance`, `AnalysisVersion`, `AnalysisMaterial`, `EvidenceItem`, `AnalysisEvidenceMaterial`, and `RuntimeMode` from `../types`. Produces `resolveSupportingRecord(input: SupportingRecordInput, evidenceId: string): SupportingRecordResult`, `SupportingRecord`, and `ExactRecordContext`. All exported result fields are readonly; the parsed record and result are frozen copies, never references into API material.

- [ ] **Step 1: Add the complete fixture and failing resolver tests below.**

`apps/web/src/components/supportingRecord.fixture.ts`:

```ts
import type {SupportingRecordInput} from "./supportingRecord";

export function recordFixture(): SupportingRecordInput {
  const at = "2026-09-01T09:00:00-05:00";
  const evidence = {
    evidence_id: "RL-ALPHA-OPTIONAL-3000", case_id: "case-1",
    kind: "operational_fact" as const, source_system: "fabric" as const,
    source_id: "fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000",
    runtime_mode: "live" as const, synthetic: false,
    source_timestamp: at, retrieved_at: at, retrieved_for_analysis_id: "analysis-1",
  };
  return {
    caseInstance: {case_id: "case-1", runtime_mode: "live", template_id: "RL-001", scenario_effective_time: at},
    analysis: {
      analysis_id: "analysis-1", case_id: "case-1", runtime_mode: "live",
      scenario_effective_time: at, created_at: at,
      evidence_items: [evidence],
      material: {
        case_id: "case-1", runtime_mode: "live", template_id: "RL-001",
        corpus: "demo_corpus", scenario_effective_time: at, evidence: [{...evidence}],
        operational_snapshot_json: JSON.stringify({
          case_id: "case-1", runtime_mode: "live", scenario_effective_time: at,
          scenario_timezone: "America/Chicago", analysis_horizon_start: at,
          analysis_horizon_end: "2026-09-08", inventory_positions: [],
          production_orders: [], customer_orders: [], disruption: {},
          alpha_expedite: {
            receipt_id: "RL-ALPHA-OPTIONAL-3000", supplier_id: "RL-SUP-ALPHA",
            part_id: "RL-MAT-10247", plant_id: "RL-PLANT-CHI", quantity: 3000,
            due_date: "2026-09-06", incremental_cost_per_unit: "7.50",
          },
          transfer: {
            transfer_id: "RL-TRANSFER-DAL-CHI-1500", part_id: "RL-MAT-10247",
            source_plant_id: "RL-PLANT-DAL", destination_plant_id: "RL-PLANT-CHI",
            quantity: 1500, dispatch_date: "2026-09-04", arrival_date: "2026-09-05",
            incremental_cost_per_unit: "1.50",
          },
          beta_qualification: {
            qualification_id: "RL-QUAL-BETA", supplier_id: "RL-SUP-BETA",
            part_id: "RL-MAT-10247", evidence_ref: "RL-QUALITY-001", status: "pending",
            effective_date: null, audit_complete: false, first_article_complete: false,
            expected_decision_date: "2026-09-15",
          },
        }),
      },
    },
  };
}

export function editSnapshot(input: SupportingRecordInput, edit: (snapshot: Record<string, any>) => void) {
  const snapshot = JSON.parse(input.analysis.material.operational_snapshot_json);
  edit(snapshot);
  input.analysis.material.operational_snapshot_json = JSON.stringify(snapshot);
}

export function selectRecord(input: SupportingRecordInput, kind: "transfer" | "qualification") {
  const item = input.analysis.evidence_items[0];
  item.evidence_id = kind === "transfer" ? "RL-TRANSFER-DAL-CHI-1500" : "RL-QUALITY-001";
  item.source_id = kind === "transfer"
    ? "fabric.inventory_transfer/RL-TRANSFER-DAL-CHI-1500"
    : "fabric.qualification/RL-QUAL-BETA";
  input.analysis.material.evidence = [{...item}];
  return item.evidence_id;
}
```

The fixture's `any` is confined to deliberately corrupting decoded JSON in negative tests. Production parsing below starts from `unknown`.

`apps/web/src/components/supportingRecord.test.ts`:

```ts
import {describe, expect, it} from "vitest";
import {resolveSupportingRecord, type SupportingRecordInput} from "./supportingRecord";
import {editSnapshot, recordFixture, selectRecord} from "./supportingRecord.fixture";

const resolve = (input: SupportingRecordInput) =>
  resolveSupportingRecord(input, input.analysis.evidence_items[0].evidence_id);

describe("exact saved supporting records", () => {
  it("resolves a frozen receipt and exact report context without changing its input", () => {
    const input = recordFixture();
    const before = JSON.stringify(input);
    const result = resolve(input);
    expect(result.status).toBe("available");
    if (result.status !== "available") throw new Error("Expected record");
    expect(result.context).toEqual({caseId: "case-1", analysisId: "analysis-1", runtimeMode: "live",
      evidenceId: "RL-ALPHA-OPTIONAL-3000", recordKind: "shipment",
      recordId: "RL-ALPHA-OPTIONAL-3000", sourceId: "fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000"});
    expect(result.record).toMatchObject({kind: "shipment", quantity: 3000, due_date: "2026-09-06"});
    expect(Object.isFrozen(result.record)).toBe(true);
    expect(Object.isFrozen(result.context)).toBe(true);
    expect(JSON.stringify(input)).toBe(before);
  });

  it.each(["transfer", "qualification"] as const)("resolves %s using its own identity", kind => {
    const input = recordFixture();
    selectRecord(input, kind);
    const result = resolve(input);
    expect(result.status).toBe("available");
    if (result.status !== "available") throw new Error("Expected record");
    expect(result.record.kind).toBe(kind);
    expect(result.context.recordId).toBe(kind === "transfer" ? "RL-TRANSFER-DAL-CHI-1500" : "RL-QUAL-BETA");
  });

  it("preserves zero cost, false flags, and nullable dates", () => {
    const input = recordFixture();
    editSnapshot(input, s => { s.alpha_expedite.incremental_cost_per_unit = "0.00"; });
    expect(resolve(input)).toMatchObject({record: {incremental_cost_per_unit: "0.00"}});
    selectRecord(input, "qualification");
    expect(resolve(input)).toMatchObject({record: {audit_complete: false, first_article_complete: false, effective_date: null}});
  });

  it("resolves a valid transfer when the optional shipment is absent", () => {
    const input = recordFixture();
    selectRecord(input, "transfer");
    editSnapshot(input, s => { s.alpha_expedite = null; });
    expect(resolve(input)).toMatchObject({status: "available", record: {kind: "transfer", transfer_id: "RL-TRANSFER-DAL-CHI-1500"}});
  });

  it.each(["shipment", "transfer", "qualification"] as const)("resolves explicit %s fixture lineage without claiming Fabric", kind => {
    const input = recordFixture();
    if (kind !== "shipment") selectRecord(input, kind);
    input.caseInstance.runtime_mode = "fallback";
    input.analysis.runtime_mode = "fallback";
    input.analysis.material.runtime_mode = "fallback";
    editSnapshot(input, s => { s.runtime_mode = "fallback"; });
    const item = input.analysis.evidence_items[0];
    Object.assign(item, {runtime_mode: "fallback", source_system: "synthetic_fixture", synthetic: true,
      source_id: `RL-SOURCE-${item.evidence_id}`});
    input.analysis.material.evidence = [{...item}];
    expect(resolve(input)).toMatchObject({status: "available", provenance: "Demo fixture — not a live retrieval"});
  });

  const invalid: [string, (input: SupportingRecordInput) => void][] = [
    ["malformed JSON", i => { i.analysis.material.operational_snapshot_json = "{"; }],
    ["array root", i => { i.analysis.material.operational_snapshot_json = "[]"; }],
    ["case", i => { i.caseInstance.case_id = "other"; }],
    ["material case", i => { i.analysis.material.case_id = "other"; }],
    ["snapshot case", i => editSnapshot(i, s => { s.case_id = "other"; })],
    ["runtime", i => { i.caseInstance.runtime_mode = "fallback"; }],
    ["snapshot runtime", i => editSnapshot(i, s => { s.runtime_mode = "fallback"; })],
    ["retrieval analysis", i => { i.analysis.evidence_items[0].retrieved_for_analysis_id = "old"; }],
    ["missing material membership", i => { i.analysis.material.evidence = []; }],
    ["duplicate evidence", i => { i.analysis.evidence_items.push({...i.analysis.evidence_items[0]}); }],
    ["duplicate material", i => { i.analysis.material.evidence.push({...i.analysis.material.evidence[0]}); }],
    ["kind", i => { i.analysis.evidence_items[0].kind = "source_statement"; }],
    ["synthetic live Fabric evidence", i => { i.analysis.evidence_items[0].synthetic = true; i.analysis.material.evidence[0].synthetic = true; }],
    ["source mismatch", i => { i.analysis.material.evidence[0].source_id = "other"; }],
    ["unsupported family", i => { i.analysis.evidence_items[0].source_id = "fabric.inventory/other"; }],
    ["missing receipt", i => editSnapshot(i, s => { s.alpha_expedite = null; })],
    ["record identity", i => editSnapshot(i, s => { s.alpha_expedite.receipt_id = "other"; })],
    ["quantity string", i => editSnapshot(i, s => { s.alpha_expedite.quantity = "3000"; })],
    ["zero positive quantity", i => editSnapshot(i, s => { s.alpha_expedite.quantity = 0; })],
    ["fractional quantity", i => editSnapshot(i, s => { s.alpha_expedite.quantity = 1.5; })],
    ["impossible date", i => editSnapshot(i, s => { s.alpha_expedite.due_date = "2026-02-30"; })],
    ["timestamp as date", i => editSnapshot(i, s => { s.alpha_expedite.due_date = "2026-09-06T00:00:00Z"; })],
    ["numeric money", i => editSnapshot(i, s => { s.alpha_expedite.incremental_cost_per_unit = 7.5; })],
    ["negative money", i => editSnapshot(i, s => { s.alpha_expedite.incremental_cost_per_unit = "-1.00"; })],
    ["currency text", i => editSnapshot(i, s => { s.alpha_expedite.incremental_cost_per_unit = "$7.50"; })],
    ["scenario mismatch", i => editSnapshot(i, s => { s.scenario_effective_time = "2026-09-02T09:00:00-05:00"; })],
    ["invalid timestamp", i => { i.analysis.evidence_items[0].retrieved_at = "2026-02-30T09:00:00Z"; }],
    ["no timestamp offset", i => { i.analysis.evidence_items[0].retrieved_at = "2026-09-01T09:00:00"; }],
    ["non-demo corpus", i => { i.analysis.material.corpus = "real_business"; }],
    ["qualification reference", i => { selectRecord(i, "qualification"); editSnapshot(i, s => { s.beta_qualification.evidence_ref = "other"; }); }],
    ["qualification string false", i => { selectRecord(i, "qualification"); editSnapshot(i, s => { s.beta_qualification.audit_complete = "false"; }); }],
    ["qualification unknown status", i => { selectRecord(i, "qualification"); editSnapshot(i, s => { s.beta_qualification.status = "ready"; }); }],
    ["transfer arrival date", i => { selectRecord(i, "transfer"); editSnapshot(i, s => { s.transfer.arrival_date = "bad"; }); }],
  ];
  it.each(invalid)("rejects %s without another record", (_name, corrupt) => {
    const input = recordFixture(); corrupt(input);
    expect(resolve(input)).toEqual({status: "unavailable", message: "Supporting record unavailable"});
  });

  it("requires requested evidence membership and leaves nullable timestamps unavailable", () => {
    const input = recordFixture();
    expect(resolveSupportingRecord(input, "missing").status).toBe("unavailable");
    input.analysis.evidence_items[0].retrieved_at = null;
    input.analysis.evidence_items[0].source_timestamp = null;
    input.analysis.material.evidence[0].source_timestamp = null;
    expect(resolve(input)).toMatchObject({status: "available", retrievedAt: null, sourceTimestamp: null});
  });
});
```

- [ ] **Step 2: Run the red test.** From `apps/web`, run `npx vitest run src/components/supportingRecord.test.ts`. Expected: FAIL because `./supportingRecord` does not exist.
- [ ] **Step 3: Create the complete resolver implementation.**

`apps/web/src/components/supportingRecord.ts`:

```ts
import type {AnalysisEvidenceMaterial, AnalysisMaterial, AnalysisVersion, CaseInstance, EvidenceItem, RuntimeMode} from "../types";

type IdentityKeys = "evidence_id" | "case_id" | "kind" | "source_system" | "source_id" | "runtime_mode" | "synthetic" | "source_timestamp";
type SavedEvidence = Pick<EvidenceItem, IdentityKeys | "retrieved_at" | "retrieved_for_analysis_id">;
export interface SupportingRecordInput {
  caseInstance: Pick<CaseInstance, "case_id" | "runtime_mode" | "template_id" | "scenario_effective_time">;
  analysis: Pick<AnalysisVersion, "analysis_id" | "case_id" | "runtime_mode" | "scenario_effective_time" | "created_at"> & {
    evidence_items: SavedEvidence[];
    material: Pick<AnalysisMaterial, "case_id" | "runtime_mode" | "template_id" | "corpus" | "scenario_effective_time" | "operational_snapshot_json"> & {
      evidence: Pick<AnalysisEvidenceMaterial, IdentityKeys>[];
    };
  };
}
type Shipment = Readonly<{kind: "shipment"; receipt_id: string; supplier_id: string; part_id: string;
  plant_id: string; quantity: number; due_date: string; incremental_cost_per_unit: string}>;
type Transfer = Readonly<{kind: "transfer"; transfer_id: string; part_id: string; source_plant_id: string;
  destination_plant_id: string; quantity: number; dispatch_date: string; arrival_date: string; incremental_cost_per_unit: string}>;
type Qualification = Readonly<{kind: "qualification"; qualification_id: string; supplier_id: string; part_id: string;
  evidence_ref: string; status: "approved" | "pending" | "not_approved" | "conditional";
  effective_date: string | null; audit_complete: boolean | null; first_article_complete: boolean | null;
  expected_decision_date: string | null}>;
export type SupportingRecord = Shipment | Transfer | Qualification;
export type ExactRecordContext = Readonly<{caseId: string; analysisId: string; runtimeMode: RuntimeMode;
  evidenceId: string; recordKind: SupportingRecord["kind"]; recordId: string; sourceId: string}>;
export type SupportingRecordResult = Readonly<{status: "unavailable"; message: "Supporting record unavailable"}> |
  Readonly<{status: "available"; context: ExactRecordContext; record: SupportingRecord;
    scenarioEffectiveTime: string; analysisCreatedAt: string; sourceTimestamp: string | null;
    retrievedAt: string | null; provenance: "Saved Microsoft Fabric record" | "Demo fixture — not a live retrieval"}>;

const unavailable = Object.freeze({status: "unavailable", message: "Supporting record unavailable"} as const);
const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === "string" && v.trim().length > 0;
const date = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)
  && Number.isFinite(Date.parse(`${v}T00:00:00Z`)) && new Date(`${v}T00:00:00Z`).toISOString().slice(0, 10) === v;
const timestamp = (v: unknown): v is string => typeof v === "string"
  && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.test(v)
  && date(v.slice(0, 10)) && Number.isFinite(Date.parse(v));
const sameTime = (a: unknown, b: unknown) => timestamp(a) && timestamp(b) && Date.parse(a) === Date.parse(b);
const nullableDate = (v: unknown): v is string | null => v === null || date(v);
const nullableFlag = (v: unknown): v is boolean | null => v === null || typeof v === "boolean";
const positive = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v > 0;
const money = (v: unknown): v is string => typeof v === "string" && /^\d+\.\d{2}$/.test(v);

function parseRecord(kind: SupportingRecord["kind"], v: unknown): SupportingRecord | null {
  if (!object(v) || !text(v.part_id)) return null;
  if (kind === "shipment" && text(v.receipt_id) && text(v.supplier_id) && text(v.plant_id)
      && positive(v.quantity) && date(v.due_date) && money(v.incremental_cost_per_unit)) {
    return Object.freeze({kind, receipt_id: v.receipt_id, supplier_id: v.supplier_id, part_id: v.part_id,
      plant_id: v.plant_id, quantity: v.quantity, due_date: v.due_date, incremental_cost_per_unit: v.incremental_cost_per_unit});
  }
  if (kind === "transfer" && text(v.transfer_id) && text(v.source_plant_id) && text(v.destination_plant_id)
      && positive(v.quantity) && date(v.dispatch_date) && date(v.arrival_date) && money(v.incremental_cost_per_unit)) {
    return Object.freeze({kind, transfer_id: v.transfer_id, part_id: v.part_id, source_plant_id: v.source_plant_id,
      destination_plant_id: v.destination_plant_id, quantity: v.quantity, dispatch_date: v.dispatch_date,
      arrival_date: v.arrival_date, incremental_cost_per_unit: v.incremental_cost_per_unit});
  }
  if (kind === "qualification" && text(v.qualification_id) && text(v.supplier_id) && text(v.evidence_ref)
      && (v.status === "approved" || v.status === "pending" || v.status === "not_approved" || v.status === "conditional")
      && nullableDate(v.effective_date) && nullableDate(v.expected_decision_date)
      && nullableFlag(v.audit_complete) && nullableFlag(v.first_article_complete)) {
    return Object.freeze({kind, qualification_id: v.qualification_id, supplier_id: v.supplier_id, part_id: v.part_id,
      evidence_ref: v.evidence_ref, status: v.status, effective_date: v.effective_date,
      expected_decision_date: v.expected_decision_date, audit_complete: v.audit_complete, first_article_complete: v.first_article_complete});
  }
  return null;
}

export function resolveSupportingRecord(input: SupportingRecordInput, evidenceId: string): SupportingRecordResult {
  try {
    const {caseInstance: c, analysis: a} = input;
    const m = a.material;
    const s: unknown = JSON.parse(m.operational_snapshot_json);
    if (!object(s) || !text(a.analysis_id) || !text(a.case_id) || !text(evidenceId)
        || c.template_id !== "RL-001" || m.template_id !== c.template_id || m.corpus !== "demo_corpus"
        || ![c.case_id, m.case_id, s.case_id].every(id => id === a.case_id)
        || (a.runtime_mode !== "live" && a.runtime_mode !== "fallback")
        || ![c.runtime_mode, m.runtime_mode, s.runtime_mode].every(mode => mode === a.runtime_mode)
        || ![c.scenario_effective_time, m.scenario_effective_time, s.scenario_effective_time].every(at => sameTime(at, a.scenario_effective_time))
        || s.scenario_timezone !== "America/Chicago" || !timestamp(s.analysis_horizon_start) || !date(s.analysis_horizon_end)
        || !Array.isArray(s.inventory_positions) || !Array.isArray(s.production_orders) || !Array.isArray(s.customer_orders)
        || !object(s.disruption) || !timestamp(a.created_at)) return unavailable;
    const items = a.evidence_items.filter(e => e.evidence_id === evidenceId);
    const materialItems = m.evidence.filter(e => e.evidence_id === evidenceId);
    if (items.length !== 1 || materialItems.length !== 1) return unavailable;
    const e = items[0];
    const identityKeys: IdentityKeys[] = ["evidence_id", "case_id", "kind", "source_system", "source_id", "runtime_mode", "synthetic", "source_timestamp"];
    if (!identityKeys.every(key => e[key] === materialItems[0][key]) || e.kind !== "operational_fact"
        || e.case_id !== a.case_id || e.runtime_mode !== a.runtime_mode || e.retrieved_for_analysis_id !== a.analysis_id
        || typeof e.synthetic !== "boolean" || !text(e.source_id)
        || (e.retrieved_at !== null && !timestamp(e.retrieved_at))
        || (e.source_timestamp !== null && !timestamp(e.source_timestamp))) return unavailable;
    const fixture = a.runtime_mode === "fallback" && e.source_system === "synthetic_fixture" && e.synthetic === true;
    const fabric = a.runtime_mode === "live" && e.source_system === "fabric" && e.synthetic === false;
    if (!fixture && !fabric) return unavailable;
    const families = [
      ["shipment", "alpha_expedite", "fabric.supply_receipt/"],
      ["transfer", "transfer", "fabric.inventory_transfer/"],
      ["qualification", "beta_qualification", "fabric.qualification/"],
    ] as const;
    const matches: {record: SupportingRecord; recordId: string}[] = [];
    for (const [kind, member, prefix] of families) {
      const record = parseRecord(kind, s[member]);
      if (!record) continue;
      const recordId = record.kind === "shipment" ? record.receipt_id
        : record.kind === "transfer" ? record.transfer_id : record.qualification_id;
      const expectedEvidence = record.kind === "qualification" ? record.evidence_ref : recordId;
      if (e.evidence_id !== expectedEvidence) continue;
      if (fabric ? e.source_id !== `${prefix}${recordId}` : e.source_id !== `RL-SOURCE-${expectedEvidence}`) continue;
      matches.push({record, recordId});
    }
    if (matches.length !== 1) return unavailable;
    const {record, recordId} = matches[0];
    return Object.freeze({status: "available", record,
      context: Object.freeze({caseId: a.case_id, analysisId: a.analysis_id, runtimeMode: a.runtime_mode,
        evidenceId, recordKind: record.kind, recordId, sourceId: e.source_id}),
      scenarioEffectiveTime: a.scenario_effective_time, analysisCreatedAt: a.created_at,
      sourceTimestamp: e.source_timestamp, retrievedAt: e.retrieved_at,
      provenance: fixture ? "Demo fixture — not a live retrieval" : "Saved Microsoft Fabric record"});
  } catch {
    return unavailable;
  }
}
```

- [ ] **Step 4: Run `npx vitest run src/components/supportingRecord.test.ts` and `npm run build` from `apps/web`.** Expected: resolver tests and strict TypeScript compilation pass. Fix failures within these new files before proceeding.
- [ ] **Step 5: Review the diff, then commit only the three Task 1 files if the parent authorizes committing in the shared worktree.** The current planning assignment expressly prohibits commits; the parent controls Git while other agents work. Suggested eventual commit message: `feat: resolve exact saved supporting records`.

## Task 2: Provide accessible inline details without coupling to the current panel

**Files:** Create `apps/web/src/components/SupportingRecordDetails.tsx` and `apps/web/src/components/SupportingRecordDetails.test.tsx`.

**Interfaces:** Consumes `SupportingRecordResult` from Task 1. Produces `SupportingRecordDetails({result}: {result: SupportingRecordResult})`. Native `<details>/<summary>` provides keyboard expansion without IDs derived from arbitrary source identifiers. No network, effects, router, callbacks, URLs, or application mutation. The unavailable message stays visible even before expansion.

- [ ] **Step 1: Add the complete failing component tests.**

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, describe, expect, it, vi} from "vitest";
import {SupportingRecordDetails} from "./SupportingRecordDetails";
import {resolveSupportingRecord} from "./supportingRecord";
import {editSnapshot, recordFixture, selectRecord} from "./supportingRecord.fixture";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe("supporting record disclosure", () => {
  it("expands and collapses with the keyboard without fetching or altering input", async () => {
    const user = userEvent.setup();
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    const input = recordFixture(); const before = JSON.stringify(input);
    render(<SupportingRecordDetails result={resolveSupportingRecord(input, input.analysis.evidence_items[0].evidence_id)} />);
    const summary = screen.getByText("View shipment record");
    const details = summary.closest("details")!;
    expect(details).not.toHaveAttribute("open");
    await user.tab(); expect(summary).toHaveFocus();
    await user.keyboard("{Enter}"); expect(details).toHaveAttribute("open");
    expect(screen.getByText("Snapshot used for this analysis")).toBeVisible();
    expect(screen.getByText("Demo corpus — fictional")).toBeVisible();
    expect(screen.getByText("RL-Supplier Alpha — Current supplier")).toBeVisible();
    expect(screen.getByText("September 6, 2026")).toBeVisible();
    expect(screen.getByText("7.50 per unit (currency not specified)")).toBeVisible();
    const scenarioTime = screen.getByText(/In this scenario, as of/).querySelector("time")!;
    expect(scenarioTime).toHaveAttribute("datetime", "2026-09-01T09:00:00-05:00");
    expect(scenarioTime).toHaveTextContent(/Sep 1, 2026/);
    expect(scenarioTime).toHaveTextContent(/UTC/);
    expect(scenarioTime).not.toHaveTextContent("2026-09-01T");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    await user.keyboard("{Enter}"); expect(details).not.toHaveAttribute("open");
    expect(fetch).not.toHaveBeenCalled(); expect(JSON.stringify(input)).toBe(before);
  });

  it("keeps qualification false flags and unknown dates distinct", () => {
    const input = recordFixture(); const id = selectRecord(input, "qualification");
    render(<SupportingRecordDetails result={resolveSupportingRecord(input, id)} />);
    expect(screen.getByText("View qualification record")).toBeInTheDocument();
    expect(screen.getByText("RL-Supplier Beta — Alternate supplier")).toBeInTheDocument();
    expect(screen.getByText("Supplier qualification pending")).toBeInTheDocument();
    expect(screen.getAllByText("Incomplete")).toHaveLength(2);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("Expected qualification decision date")).toBeInTheDocument();
  });

  it("labels transfer plants and renders source-controlled text as text", () => {
    const input = recordFixture(); const id = selectRecord(input, "transfer");
    editSnapshot(input, s => { s.transfer.part_id = "<img src=x onerror=alert(1)>"; });
    const {container} = render(<SupportingRecordDetails result={resolveSupportingRecord(input, id)} />);
    expect(screen.getByText("View transfer record")).toBeInTheDocument();
    expect(screen.getByText("Dallas plant")).toBeInTheDocument();
    expect(screen.getByText("Chicago plant")).toBeInTheDocument();
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
  });

  it("makes unavailability explicit without offering a substitute destination", () => {
    render(<SupportingRecordDetails result={{status: "unavailable", message: "Supporting record unavailable"}} />);
    expect(screen.getByText("Supporting record unavailable")).toBeVisible();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText(/View .* record/)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run `npx vitest run src/components/SupportingRecordDetails.test.tsx` from `apps/web`.** Expected: FAIL because the component does not exist.
- [ ] **Step 3: Create the complete component below.**

```tsx
import type {ReactNode} from "react";
import type {SupportingRecordResult} from "./supportingRecord";

const calendar = (value: string | null) => value === null ? "Unavailable" : new Intl.DateTimeFormat("en-US", {
  year: "numeric", month: "long", day: "numeric", timeZone: "UTC",
}).format(new Date(`${value}T00:00:00Z`));
const instantFormat = new Intl.DateTimeFormat("en-US", {
  year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  second: "2-digit", timeZone: "UTC", timeZoneName: "short",
});
const instant = (value: string | null): ReactNode => value === null ? "Unavailable"
  : <time dateTime={value}>{instantFormat.format(new Date(value))}</time>;
const flag = (value: boolean | null) => value === null ? "Unavailable" : value ? "Complete" : "Incomplete";
const supplier = (id: string) => id === "RL-SUP-ALPHA" ? "RL-Supplier Alpha — Current supplier"
  : id === "RL-SUP-BETA" ? "RL-Supplier Beta — Alternate supplier" : `Supplier ${id}`;
const plant = (id: string) => id === "RL-PLANT-DAL" ? "Dallas plant" : id === "RL-PLANT-CHI" ? "Chicago plant" : `Plant ${id}`;
const qualification = {approved: "Supplier qualification approved", pending: "Supplier qualification pending",
  not_approved: "Supplier qualification not approved", conditional: "Supplier qualification conditional"};

export function SupportingRecordDetails({result}: {result: SupportingRecordResult}) {
  if (result.status === "unavailable") return <p>{result.message}</p>;
  const r = result.record;
  const rows: [string, string][] = [["Component part", r.part_id]];
  if (r.kind === "shipment") rows.push(
    ["Supplier", supplier(r.supplier_id)], ["Receiving plant", plant(r.plant_id)],
    ["Scheduled receipt quantity", `${r.quantity.toLocaleString("en-US")} units`],
    ["Scheduled receipt date", calendar(r.due_date)],
    ["Incremental cost", `${r.incremental_cost_per_unit} per unit (currency not specified)`],
  );
  if (r.kind === "transfer") rows.push(
    ["From", plant(r.source_plant_id)], ["To", plant(r.destination_plant_id)],
    ["Transfer quantity", `${r.quantity.toLocaleString("en-US")} units`],
    ["Dispatch date", calendar(r.dispatch_date)], ["Arrival date", calendar(r.arrival_date)],
    ["Incremental cost", `${r.incremental_cost_per_unit} per unit (currency not specified)`],
  );
  if (r.kind === "qualification") rows.push(
    ["Supplier", supplier(r.supplier_id)], ["Qualification status", qualification[r.status]],
    ["Audit", flag(r.audit_complete)], ["First article", flag(r.first_article_complete)],
    ["Qualification effective date", calendar(r.effective_date)],
    ["Expected qualification decision date", calendar(r.expected_decision_date)],
  );
  const sourceRows: [string, ReactNode][] = [
    ["Case ID", result.context.caseId], ["Analysis ID", result.context.analysisId],
    ["Source record ID", result.context.recordId], ["Evidence reference", result.context.evidenceId],
    ["Source identifier", result.context.sourceId], ["Runtime mode", result.context.runtimeMode],
    ["Analysis saved at", instant(result.analysisCreatedAt)], ["Source time", instant(result.sourceTimestamp)],
    [result.context.runtimeMode === "fallback" ? "Fixture recorded for analysis at" : "Retrieved for this analysis at", instant(result.retrievedAt)],
  ];
  const list = (values: [string, ReactNode][]) => <dl>{values.map(([label, value]) =>
    <div key={label}><dt>{label}</dt><dd style={{overflowWrap: "anywhere"}}>{value}</dd></div>)}</dl>;
  return <details>
    <summary>View {r.kind} record</summary>
    <p>Snapshot used for this analysis</p>
    <p>Demo corpus — fictional</p>
    <p>{result.provenance}</p>
    <p>In this scenario, as of {instant(result.scenarioEffectiveTime)}</p>
    {list(rows)}
    {r.kind === "qualification" && <p>A review date is not an approval or delivery date.</p>}
    <details><summary>Source details</summary>{list(sourceRows)}</details>
  </details>;
}
```

This component uses natural document flow and wraps long values; no fixed widths or new design system. The current card's platform/activity footer remains its own responsibility. Fixture provenance is visible in the record body and cannot be mistaken for a fresh service call. Original email/Teams quotations and source links remain untouched because this increment does not render or modify them. The component derives no extra supplier statement from a scheduled receipt.

- [ ] **Step 4: Run `npx vitest run src/components/SupportingRecordDetails.test.tsx` and `npm run build` from `apps/web`.** Expected: four component tests and TypeScript/build pass. Keyboard disclosure verification uses the platform's native summary behavior; if the installed jsdom cannot simulate Enter activation, preserve a real keyboard browser check and test click toggling in jsdom with `await user.click(summary)` instead of adding redundant custom keyboard handlers.
- [ ] **Step 5: Run bounded final regression verification from `apps/web`: `npm test`, `TZ=America/Los_Angeles npx vitest run src/components/SupportingRecordDetails.test.tsx`, and `npm run build`.** Expected: all existing/new unit tests pass, September 6 stays September 6 in the alternate timezone, build passes. From the worktree root run `git diff --check`. Do not broaden to deployment, credentials, live retrieval, approval, or execution workflows.
- [ ] **Step 6: Review only the two Task 2 files, then let the parent commit when shared-worktree work is settled.** Suggested eventual commit message: `feat: add inline supporting record disclosure`.

## Review gates and subsequent integration

Success for this bounded increment is a typed resolver with negative identity/type tests, a compiled standalone disclosure with accessible keyboard behavior and no fetch/navigation, unchanged existing citation safety tests, and no edits outside the five implementation/test files. It intentionally does not change what the current evidence panel renders. The subsequent layout integration must wire this component to the selected case and displayed analysis, remove the generic Fabric citation action from that rendered path, preserve supplier-email and Quality Teams-post actions, and arrange the three investigation rows. Those are separate reviewable changes; this plan does not assume the concurrent footer's uncommitted interface.

Before that integration is released, visually review populated shipment, transfer, pending qualification, null timestamps, explicit fixtures, malformed snapshot, and long identifiers on desktop and narrow mobile widths. This increment's unit tests establish behavior but are not a claim of completed end-to-end visual review. Power BI exact-record routes, page allowlists, encoded filters, SQL projection, and report data availability remain separate work.

Self-review against the approved specification: Task 1 covers the saved snapshot, case/runtime/material/evidence/retrieval identity, source family and actual record ID (including qualification reference), relevant runtime types, invalid dates, zero cost, false flags, nullable fields, and fixture lineage. Task 2 covers safe text rendering, native inline disclosure, record fields, identity/source details, fictional provenance, truthful timestamps, role-qualified display names, and unavailability. No new source validations, source freshness, supplier agreements, approval status, or currency denomination are inferred. No unresolved contract conflict blocks this bounded plan; the absent currency code is displayed explicitly rather than invented.
