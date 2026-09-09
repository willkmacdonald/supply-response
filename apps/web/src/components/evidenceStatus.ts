import type {AnalysisVersion, EvidenceItem, EvidenceItemValidation} from "../types";
import {validInstant} from "./snapshotValidation";

export type StatusItem = Pick<EvidenceItem,
  "evidence_id" | "case_id" | "source_system" | "runtime_mode" | "synthetic" |
  "retrieval_health" | "retrieved_for_analysis_id" | "retrieved_at">;
export type StatusContext = Pick<AnalysisVersion,
  "case_id" | "analysis_id" | "runtime_mode" | "analysis_started_at" |
  "retrieval_window_ends_at" | "created_at"> & {results: EvidenceItemValidation[]};
export interface EvidenceStatus {
  platform: string;
  retrieval: string;
  recordedAt: string | null;
  validation: string;
  warning: string | null;
}

function instant(value: string | null): number {
  return validInstant(value) ? Date.parse(value) : NaN;
}

export function evidenceStatus(item: StatusItem, context: StatusContext): EvidenceStatus {
  const fixture = item.synthetic;
  const platform = fixture ? "Demo data" :
    item.source_system === "work_iq" ? "Work IQ" :
    item.source_system === "fabric" ? "Microsoft Fabric" : "Other source";
  const bound = item.case_id === context.case_id &&
    item.runtime_mode === context.runtime_mode &&
    item.retrieved_for_analysis_id === context.analysis_id;
  const at = instant(item.retrieved_at);
  const inWindow = Number.isFinite(at) && at >= instant(context.analysis_started_at) &&
    at <= instant(context.retrieval_window_ends_at) && at <= instant(context.created_at);
  const retrieved = bound && inWindow && item.retrieval_health === "healthy";
  const matches = context.results.filter(result => result.evidence_id === item.evidence_id);
  const check = bound && matches.length === 1 ? matches[0] : undefined;
  const passed = retrieved && check !== undefined &&
    (check.requirement === "contextual" || check.authoritative === true) &&
    check.freshness === "current" && check.business_validity === "valid" &&
    check.uncertainty_state !== "conflicted" && check.retrieval_health === "healthy" &&
    check.blocking_codes.length === 0;
  const warning = !bound ? "Source does not belong to this analysis" :
    item.retrieval_health !== "healthy" ? "Source could not be retrieved for this analysis" :
    !inWindow ? "Retrieval time is unavailable or does not match this analysis" :
    !check ? "Check result unavailable for this source" :
    check.retrieval_health !== "healthy" ? "Source checks could not be completed" :
    check.uncertainty_state === "conflicted" ? "Sources conflict and need review" :
    check.freshness !== "current" ? "Source is not current for this analysis" :
    check.business_validity !== "valid" ? "Source does not apply to this scenario date" :
    check.requirement === "required_authoritative" && !check.authoritative ?
      "Source cannot support this analysis requirement" :
    check.blocking_codes.length > 0 ? "Source checks need attention" : null;
  return {
    platform,
    retrieval: fixture ? "Sample data — not a live retrieval" :
      retrieved ? (context.runtime_mode === "fallback" ? "Recorded for this analysis (fallback)" :
        "Retrieved for this analysis") : "Retrieval not verified for this analysis",
    recordedAt: retrieved && !fixture ? item.retrieved_at : null,
    validation: passed ? (check?.requirement === "contextual" ?
      "Context only — not authoritative evidence" : "Required checks passed") :
      !check ? "Check result unavailable" : check.requirement === "contextual" ?
        "Context checks did not pass" : "Required checks did not pass",
    warning,
  };
}
