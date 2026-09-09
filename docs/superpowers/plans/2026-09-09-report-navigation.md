# Exact report navigation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the tested, fail-closed URL contract that connects planner cards to their exact saved analysis and supporting record.

**Architecture:** A pure frontend builder accepts only the verified reporting contract and a canonical report base URL. It creates new page URLs with explicit identity filters; UTF-16LE hexadecimal identity keys prevent Power BI's case-insensitive string filtering from aliasing distinct source IDs. This independently testable navigation subproject does not activate links; model/pages and coordinated runtime activation are separate implementation tasks in stage 4.

**Tech Stack:** TypeScript, Vitest, existing React application; Power BI URL filters.

## Global Constraints

- Preserve the existing report and semantic-model item identities.
- A record link must include the exact case, immutable analysis, record family and source record identity.
- Invalid or unavailable selection must not silently select another record or the newest case.
- A fallback fixture must not be presented as a live Fabric record.
- Preserve original supplier email and Quality Teams citations.
- No live deployment, permission or license changes, analysis runs, approvals or playback in this implementation stage.
- The new report links must remain inactive until the matching report contract is verified by the API.
- Query filters are navigation context, not access control; Microsoft authorization remains required.

## File map

- `apps/web/src/reporting/reportNavigation.ts`: one pure, typed URL constructor; no network or lifecycle actions.
- `apps/web/src/reporting/reportNavigation.test.ts`: exact URL protocol, identity preservation, rejection and availability tests.

## Protocol shared with the report stage

Contract string: `saved-analysis-v1` in `RuntimeStatus.deployment_contract.power_bi_reporting_contract`.
The API must emit it only after verifying the new artifact-bound reporting receipt; the existing URL-only receipt is insufficient.
Model keys are SQL `CONVERT(varchar(max), CONVERT(varbinary(max), CONVERT(nvarchar(max), identity)), 2)`.
No URL links are mounted by this task; existing inline supporting-record details remain available.

Microsoft reference: https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-url-filters
The documented URL-filter limit is 2,000 characters, with at most ten expressions. This builder uses at most five expressions and checks the encoded query length conservatively.

### Task 1: Exact, release-gated report URLs

**Files:**
- Create: `apps/web/src/reporting/reportNavigation.ts`
- Test: `apps/web/src/reporting/reportNavigation.test.ts`

**Interfaces:**
- Consumes: existing `RuntimeStatus` from `../types`.
- Produces: `REPORTING_CONTRACT`, `ReportTarget`, `reportIdentityKey(value: string): string`, `buildReportUrl(runtime: RuntimeStatus, target: ReportTarget): string | null`.
- Caller must independently validate the supporting record and saved-Fabric provenance before constructing a record target. The builder validates navigation identity, release availability and runtime; it does not infer provenance from an ID.

- [x] **Step 1: Add failing contract tests**

```typescript
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
```

The runtime fixture uses the existing declared `RuntimeStatus` fields. Do not cast the fixture to bypass type checking.

- [x] **Step 2: Run RED**

```sh
cd apps/web
npm test -- src/reporting/reportNavigation.test.ts
```

Expected: module import failure before `reportNavigation.ts` exists.

- [x] **Step 3: Implement the builder**

```typescript
import type { RuntimeStatus } from "../types";

export const REPORTING_CONTRACT = "saved-analysis-v1";

type Context = { caseId: string; runtimeMode: "live" | "fallback" };
export type ReportTarget = Context & (
  | { page: "command-center"; analysisId?: string }
  | { page: "supplier-shipment" | "plant-transfer" | "supplier-qualification"; analysisId: string; recordId: string }
  | { page: "available-stock" | "customer-orders"; analysisId: string }
  | { page: "response-options"; analysisId: string; optionId?: string }
);

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
```

- [x] **Step 4: Verify focused tests, full frontend suite and production build**

```sh
cd apps/web
npm test -- src/reporting/reportNavigation.test.ts
npm test
npm run build
```

Expected: new navigation tests and all existing tests pass; TypeScript and Vite build succeed. No source citation, approval, model or runtime behavior changed.

- [x] **Step 5: Commit and independent review**

```sh
git add apps/web/src/reporting/reportNavigation.ts apps/web/src/reporting/reportNavigation.test.ts
git commit -m "feat: define exact saved-analysis report navigation"
```

## Controller self-review

This subproject covers navigation identity/encoding/availability only; it intentionally does not claim stage 4 complete. Model tables must use the names and encoding above; report pages must exist before the API reports `saved-analysis-v1`. Inline details, plain-language cards, source footers and Work IQ citations are already implemented and untouched. Remaining stage 4 work is model/pages, runtime release receipt and visible link integration, followed by actual Power BI acceptance during coordinated release. Traditional walkthrough remains stage 5.
