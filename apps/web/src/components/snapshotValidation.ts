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
