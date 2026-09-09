import { describe, expect, it } from "vitest";
import type { RuntimeStatus } from "../types";
import { buildReportUrl, reportIdentityKey, REPORTING_CONTRACT } from "./reportNavigation";

const base = "https://app.powerbi.com/groups/dc3ac590-d892-40a7-9388-65dec120d67a/reports/e7611c8c-c887-443f-858a-13b1044bb4b9";
const runtime: RuntimeStatus = {
  runtime_mode: "live", work_iq: "work_iq", operational_store: "fabric_sql",
  agent_runtime: "foundry", power_bi_available: true, power_bi_url: base,
  deployment_contract: { power_bi_reporting_contract: "saved-analysis-v1" },
};
const shipment = {
  page: "supplier-shipment", caseId: "case-1", analysisId: "analysis-1",
  recordId: "RL-ALPHA-OPTIONAL-3000", runtimeMode: "live",
} as const;

describe("exact report navigation", () => {
  it("uses a versioned page and all exact identity filters", () => {
    const result = new URL(buildReportUrl(runtime, shipment)!);
    expect(result.origin + result.pathname).toBe(base + "/supplier-shipment");
    expect(result.searchParams.get("filter")).toBe([
      `CaseCommandCenter/case_key eq '${reportIdentityKey("case-1")}'`,
      `SavedAnalyses/analysis_key eq '${reportIdentityKey("analysis-1")}'`,
      "SavedRecords/record_family eq 'shipment'",
      `SavedRecords/record_key eq '${reportIdentityKey(shipment.recordId)}'`,
    ].join(" and "));
    expect([...result.searchParams.keys()]).toEqual(["filter"]);
  });
  it("encodes SQL-compatible UTF16LE identity without case folding", () => {
    expect(reportIdentityKey("RL")).toBe("52004C00");
    expect(reportIdentityKey("A'😀")).toBe("410027003DD800DE");
    expect(reportIdentityKey("A")).not.toBe(reportIdentityKey("a"));
    const result = new URL(buildReportUrl(runtime, { ...shipment, recordId: "A'&filter=x" })!);
    expect(result.searchParams.size).toBe(1);
    expect(result.searchParams.get("filter")).toContain(reportIdentityKey("A'&filter=x"));
  });
  it.each([
    ["plant-transfer", "transfer"],
    ["supplier-qualification", "qualification"],
  ] as const)("maps %s to its own record family", (page, family) => {
    const result = new URL(buildReportUrl(runtime, { ...shipment, page })!);
    expect(result.searchParams.get("filter")).toContain(`SavedRecords/record_family eq '${family}'`);
  });
  it.each(["available-stock", "customer-orders", "response-options"] as const)("keeps %s on the exact saved analysis", page => {
    const result = new URL(buildReportUrl(runtime, {
      page, caseId: "case-1", analysisId: "analysis-1", runtimeMode: "live",
    })!);
    expect(result.pathname).toBe(new URL(base).pathname + "/" + page);
    expect(result.searchParams.get("filter")).toContain("SavedAnalyses/analysis_key");
    expect(result.searchParams.get("filter")).not.toContain("SavedRecords/");
  });
  it("supports case-only overview and explicitly selected historical overview", () => {
    const target = { page: "command-center", caseId: "case-1", runtimeMode: "live" } as const;
    const current = new URL(buildReportUrl(runtime, target)!);
    expect(current.searchParams.get("filter")).not.toContain("SavedAnalyses");
    const historical = new URL(buildReportUrl(runtime, { ...target, analysisId: "older" })!);
    expect(historical.searchParams.get("filter")).toContain(reportIdentityKey("older"));
    expect(buildReportUrl(runtime, { ...target, analysisId: "" })).toBeNull();
  });
  it("adds an exact option only when requested", () => {
    const target = { page: "response-options", caseId: "case-1", analysisId: "analysis-1", runtimeMode: "live" } as const;
    expect(new URL(buildReportUrl(runtime, target)!).searchParams.get("filter")).not.toContain("SavedOptions");
    expect(new URL(buildReportUrl(runtime, { ...target, optionId: "Option-A" })!).searchParams.get("filter"))
      .toContain(`SavedOptions/option_key eq '${reportIdentityKey("Option-A")}'`);
    expect(buildReportUrl(runtime, { ...target, optionId: "" })).toBeNull();
  });
  it("requires the new reporting release rather than only the old report URL receipt", () => {
    expect(REPORTING_CONTRACT).toBe("saved-analysis-v1");
    expect(buildReportUrl({ ...runtime, deployment_contract: null }, shipment)).toBeNull();
    expect(buildReportUrl({ ...runtime, deployment_contract: { power_bi_reporting_contract: "old" } }, shipment)).toBeNull();
    expect(buildReportUrl({ ...runtime, power_bi_available: false }, shipment)).toBeNull();
    expect(buildReportUrl({ ...runtime, runtime_mode: "fallback" }, shipment)).toBeNull();
    expect(buildReportUrl(runtime, { ...shipment, runtimeMode: "fallback" })).toBeNull();
  });
  it.each([
    "http://app.powerbi.com/groups/x/reports/y", "https://evil.example/groups/x/reports/y",
    base + "?filter=old", base + "#fragment", base + "/command-center",
    base.replace("https://", "https://user:pass@"), base.replace(".com/", ".com:8443/"),
    base.replace("dc3ac590-d892-40a7-9388-65dec120d67a", "me"),
  ])("rejects noncanonical report bases: %s", power_bi_url => {
    expect(buildReportUrl({ ...runtime, power_bi_url }, shipment)).toBeNull();
  });
  it.each(["", " ", "bad\nidentity", "x".repeat(1000)])("rejects unusable record identities", recordId => {
    expect(buildReportUrl(runtime, { ...shipment, recordId })).toBeNull();
  });
  it("rejects missing case and analysis without creating a generic link", () => {
    expect(buildReportUrl(runtime, { ...shipment, caseId: "" })).toBeNull();
    expect(buildReportUrl(runtime, { ...shipment, analysisId: "" })).toBeNull();
  });
});
