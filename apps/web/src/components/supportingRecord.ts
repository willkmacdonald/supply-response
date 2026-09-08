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
