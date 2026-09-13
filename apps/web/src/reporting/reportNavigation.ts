import type { RuntimeStatus } from "../types";

export const REPORTING_CONTRACT = "saved-analysis-v1";

type Context = { caseId: string; runtimeMode: "live" | "fallback" };
export type ReportTarget = Context & (
  | { page: "command-center"; analysisId?: string }
  | { page: "supplier-shipment" | "plant-transfer" | "supplier-qualification"; analysisId: string; recordId: string }
  | { page: "available-stock" | "customer-orders"; analysisId: string }
  | { page: "response-options"; analysisId: string; optionId?: string }
);
export type ReportAnalysisContext = Pick<
  Extract<ReportTarget, {page: "response-options"}>,
  "caseId" | "analysisId" | "runtimeMode"
>;

const uuid = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
const reportPath = new RegExp(`^/groups/${uuid}/reports/${uuid}$`);

function usableIdentity(value: string): boolean {
  return typeof value === "string" && value.trim().length > 0 && value.length <= 256
    && !/[\u0000-\u001f\u007f-\u009f]/.test(value);
}

/** SQL nvarchar -> varbinary -> hexadecimal, preserving case and UTF-16 code units. */
export function reportIdentityKey(value: string): string {
  let encoded = "";
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    encoded += (unit & 255).toString(16).padStart(2, "0");
    encoded += (unit >>> 8).toString(16).padStart(2, "0");
  }
  return encoded.toUpperCase();
}

export function buildReportUrl(runtime: RuntimeStatus, target: ReportTarget): string | null {
  if (runtime.runtime_mode !== "live" || target.runtimeMode !== "live"
    || !runtime.power_bi_available
    || runtime.deployment_contract?.power_bi_reporting_contract !== REPORTING_CONTRACT
    || !runtime.power_bi_url || !usableIdentity(target.caseId)) return null;
  let url: URL;
  try { url = new URL(runtime.power_bi_url); } catch { return null; }
  if (url.protocol !== "https:" || url.hostname !== "app.powerbi.com"
    || url.username || url.password || url.port || url.search || url.hash
    || !reportPath.test(url.pathname)
    || runtime.power_bi_url !== url.origin + url.pathname) return null;

  const filters = [`CaseCommandCenter/case_key eq '${reportIdentityKey(target.caseId)}'`];
  if (target.page !== "command-center" || target.analysisId !== undefined) {
    if (target.analysisId === undefined || !usableIdentity(target.analysisId)) return null;
    filters.push(`SavedAnalyses/analysis_key eq '${reportIdentityKey(target.analysisId)}'`);
  }
  switch (target.page) {
    case "supplier-shipment":
    case "plant-transfer":
    case "supplier-qualification": {
      if (!usableIdentity(target.recordId)) return null;
      const family = { "supplier-shipment": "shipment", "plant-transfer": "transfer", "supplier-qualification": "qualification" }[target.page];
      filters.push(`SavedRecords/record_family eq '${family}'`);
      filters.push(`SavedRecords/record_key eq '${reportIdentityKey(target.recordId)}'`);
      break;
    }
    case "response-options":
      if (target.optionId !== undefined) {
        if (!usableIdentity(target.optionId)) return null;
        filters.push(`SavedOptions/option_key eq '${reportIdentityKey(target.optionId)}'`);
      }
      break;
    case "command-center":
    case "available-stock":
    case "customer-orders":
      break;
    default:
      return null;
  }
  url.pathname += "/" + target.page;
  url.searchParams.set("filter", filters.join(" and "));
  return url.search.length <= 2000 ? url.href : null;
}

export function buildTraditionalReportUrl(
  runtime: RuntimeStatus,
  target: { caseId: string; analysisId: string; runtimeMode: "live" | "fallback" },
): string | null {
  const base = buildReportUrl(runtime, { ...target, page: "command-center" });
  if (!base || !usableIdentity(target.analysisId)) return null;
  const url = new URL(base);
  url.pathname = url.pathname.slice(0, -"/command-center".length) + "/operations-overview";
  url.searchParams.set("filter", "OperationalRecords/dataset_id eq 'TRADITIONAL-OPS-2026-09-V1'");
  return url.search.length <= 2000 ? url.href : null;
}
