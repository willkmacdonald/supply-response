# Evidence Status Footer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. The user selected delegated implementation with Codex's review between tasks, not user approval between tasks. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve visible evidence-processing transparency with bottom-of-card platform labels, truthful timestamps and validation summaries, and prominent warnings.

**Architecture:** Add a pure evidence-status presenter and a small React footer. Consume existing analysis identity and item-validation results; never infer fine-grained runtime events from configuration or `certain`. Integrate without changing source links, evidence content, decision gates, or backend behavior.

**Tech Stack:** Existing TypeScript, React, Vitest, Testing Library, CSS and Vite. No new dependencies.

## Global Constraints

- Approved spec: `docs/superpowers/specs/2026-09-08-evidence-records-and-case-dashboard-design.md`.
- **Retrieved for this analysis**, not an unqualified **Live** indicator suggesting ongoing monitoring.
- Separate **business status** from **evidence-processing status**.
- Keep **live service access** and **fictional scenario content** distinct.
- Badges belong at the bottom; critical failures remain near the claim.
- No source-message, immutable-analysis, permission, licensing, or approval-policy changes.
- No production create/analyze/approve/playback calls, deployment, or push in this stage.
- Run all commands from `/Users/willmacdonald/Documents/Code/m365/supply-response/.worktrees/planner-experience`.

## File structure

- Create `apps/web/src/components/evidenceStatus.ts`: pure conservative display model.
- Create `apps/web/src/components/evidenceStatus.test.ts`: table-driven status tests.
- Create `apps/web/src/components/EvidenceFooter.tsx`: bottom status presentation.
- Create `apps/web/src/components/EvidenceFooter.test.tsx`: timestamp and placement tests.
- Modify `apps/web/src/components/EvidencePanel.tsx`: separate warning and footer from business content.
- Modify `apps/web/src/styles.css`: bottom placement without mobile overflow.
- Modify `apps/web/src/App.tsx`: honest analysis-pending text.

## Task 1: Conservative evidence-status presenter

**Interfaces:**
- Consumes `EvidenceItem`, `AnalysisVersion`, and `EvidenceItemValidation` from `../types`.
- Produces `evidenceStatus(item, context): EvidenceStatus`, with explicit footer text and a separate warning.

- [x] Add the following failing tests to `evidenceStatus.test.ts`:

```ts
import {describe, expect, it} from "vitest";
import type {EvidenceItemValidation} from "../types";
import {evidenceStatus, type StatusItem, type StatusContext} from "./evidenceStatus";

const item: StatusItem = {
  evidence_id: "e1", case_id: "c1", source_system: "work_iq",
  runtime_mode: "live", synthetic: false, retrieval_health: "healthy",
  retrieved_for_analysis_id: "a1", retrieved_at: "2026-09-08T15:00:00Z",
};
const validation: EvidenceItemValidation = {
  evidence_id: "e1", requirement: "required_authoritative",
  validated_authority_scope: ["supplier_statement"], freshness: "current",
  business_validity: "valid", uncertainty_state: "certain",
  retrieval_health: "healthy", authoritative: true, blocking_codes: [],
};
const context: StatusContext = {
  case_id: "c1", analysis_id: "a1", runtime_mode: "live",
  analysis_started_at: "2026-09-08T14:59:00Z",
  retrieval_window_ends_at: "2026-09-08T15:01:00Z",
  created_at: "2026-09-08T15:00:01Z", results: [validation],
};

describe("evidence status", () => {
  it("uses recorded retrieval and policy results, not a confidence promise", () => {
    expect(evidenceStatus(item, context)).toMatchObject({
      platform: "Work IQ", retrieval: "Retrieved for this analysis",
      recordedAt: item.retrieved_at, validation: "Evidence policy checks passed",
      warning: null,
    });
  });
  it("does not infer validation from successful retrieval", () => {
    expect(evidenceStatus(item, {...context, results: []}).validation)
      .toBe("Validation result unavailable");
  });
  it("does not treat fixture provenance as a live retrieval", () => {
    expect(evidenceStatus({...item, synthetic: true}, context)).toMatchObject({
      platform: "Synthetic fixture", retrieval: "Demo fixture — not a live retrieval",
      recordedAt: null,
    });
  });
  it.each([
    {...item, case_id: "other"}, {...item, retrieved_for_analysis_id: "old"},
    {...item, runtime_mode: "fallback" as const},
    {...item, retrieval_health: "unhealthy" as const},
    {...item, retrieved_at: null}, {...item, retrieved_at: "bad"},
    {...item, retrieved_at: "2026-09-08T16:00:00Z"},
  ])("does not claim a valid current retrieval for %j", (changed) => {
    const result = evidenceStatus(changed, context);
    expect(result.retrieval).not.toBe("Retrieved for this analysis");
    expect(result.warning).not.toBeNull();
  });
  it.each([
    {...validation, freshness: "stale" as const},
    {...validation, business_validity: "expired" as const},
    {...validation, uncertainty_state: "conflicted" as const},
    {...validation, blocking_codes: ["EVIDENCE_TIMESTAMP_STALE"]},
  ])("exposes failed checks independently from retrieval", (changed) => {
    const result = evidenceStatus(item, {...context, results: [changed]});
    expect(result.validation).not.toBe("Evidence policy checks passed");
    expect(result.warning).not.toBeNull();
  });
  it("does not select arbitrarily between duplicate validation results", () => {
    expect(evidenceStatus(item, {...context, results: [validation, validation]}).validation)
      .toBe("Validation result unavailable");
  });
});
```

- [x] Run `npm --prefix apps/web test -- src/components/evidenceStatus.test.ts`; expect an import failure because the presenter does not exist yet.
- [x] Create `evidenceStatus.ts` with this implementation:

```ts
import type {AnalysisVersion, EvidenceItem, EvidenceItemValidation} from "../types";

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
  return value && /(Z|[+-]\d{2}:\d{2})$/.test(value) ? Date.parse(value) : NaN;
}
export function evidenceStatus(item: StatusItem, context: StatusContext): EvidenceStatus {
  const fixture = item.synthetic;
  const platform = fixture ? "Synthetic fixture" :
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
  const warning = !bound ? "Source does not match this analysis" :
    item.retrieval_health !== "healthy" ? "Source retrieval failed" :
    !inWindow ? "Retrieval time unavailable or outside this analysis" :
    !check ? "Validation result unavailable" :
    check.uncertainty_state === "conflicted" ? "Conflicting evidence needs review" :
    check.freshness !== "current" ? "Evidence freshness check failed" :
    check.business_validity !== "valid" ? "Evidence is not valid for this scenario date" :
    check.blocking_codes.length > 0 ? "Evidence checks need attention" : null;
  return {
    platform,
    retrieval: fixture ? "Demo fixture — not a live retrieval" :
      retrieved ? (context.runtime_mode === "fallback" ? "Recorded for this analysis (fallback)" :
        "Retrieved for this analysis") : "Retrieval not verified for this analysis",
    recordedAt: retrieved && !fixture ? item.retrieved_at : null,
    validation: passed ? (check?.requirement === "contextual" ?
      "Supporting context — not authoritative evidence" : "Evidence policy checks passed") :
      !check ? "Validation result unavailable" : "Not accepted as authoritative evidence",
    warning,
  };
}
```

- [x] Extend the tests before final implementation verification: synthetic evidence with wrong binding, stale validation, unhealthy retrieval and missing/duplicate results must still warn; a valid fallback server source must not be labeled Synthetic fixture; valid contextual results with `authoritative: false` must say **Supporting context — not authoritative evidence** without a failure warning. Required-authoritative evidence with `authoritative: false` must not pass. These corrections preserve the approved distinction between provenance and validity, and between supporting context and authoritative facts.
- [x] Run the same test command; expect all cases to pass.
- [x] Run `git diff --check`, then commit only the two presenter files with message `feat: describe evidence retrieval and validation conservatively`.

Task 1 verification: commits `676b6c0` and `bac0a40`; independent review approved.
Final focused suite: 23 tests. Full frontend suite: 81 tests. Build passed.
Review additionally required a warning for unhealthy retrieval in the validation
result itself, implemented test-first in `bac0a40`.

## Task 2: Bottom footer and prominent warnings

**Interfaces:**
- Consumes `EvidenceStatus` from Task 1.
- Produces `<EvidenceFooter status={status} />`; parent places `status.warning` beside the affected claim.

- [x] Create `EvidenceFooter.test.tsx`:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it} from "vitest";
import {EvidenceFooter} from "./EvidenceFooter";
afterEach(cleanup);
it("shows recorded UTC time without claiming ongoing monitoring", () => {
  const {container, rerender} = render(<EvidenceFooter status={{
    platform: "Work IQ", retrieval: "Retrieved for this analysis",
    recordedAt: "2026-09-08T15:00:00Z", validation: "Evidence policy checks passed",
    warning: null,
  }} />);
  expect(screen.getByText("Work IQ")).toBeInTheDocument();
  expect(container.querySelector("time")).toHaveAttribute("datetime", "2026-09-08T15:00:00Z");
  expect(container.textContent).toContain("UTC");
  expect(container.textContent).not.toMatch(/Checking now|certain|healthy/);
  rerender(<EvidenceFooter status={{platform: "Synthetic fixture",
    retrieval: "Demo fixture — not a live retrieval", recordedAt: null,
    validation: "Fixture evidence", warning: null}} />);
  expect(container.querySelector("time")).toBeNull();
});
```

- [x] Run `npm --prefix apps/web test -- src/components/EvidenceFooter.test.tsx`; expect missing-module failure.
- [x] Create `EvidenceFooter.tsx`:

```tsx
import type {EvidenceStatus} from "./evidenceStatus";
export function EvidenceFooter({status}: {status: EvidenceStatus}) {
  return <footer className="evidence-footer" aria-label="Source and evidence status">
    <span className="badge">{status.platform}</span>
    <p>{status.retrieval}{status.recordedAt && <> · <time dateTime={status.recordedAt}>
      {new Intl.DateTimeFormat("en-US", {
        year: "numeric", month: "short", day: "numeric", hour: "numeric",
        minute: "2-digit", timeZone: "UTC", timeZoneName: "short",
      }).format(new Date(status.recordedAt))}
    </time></>}</p>
    <p>{status.validation}</p>
  </footer>;
}
```

- [x] In `EvidencePanel.tsx`, import `EvidenceFooter` and `evidenceStatus`. Inside the existing evidence `map`, immediately before `return`, add:

```tsx
const status = evidenceStatus(item, {
  ...analysis, results: analysis.evidence_validation?.item_results ?? [],
});
```

- [x] Remove the existing top `<div className="card-labels">` containing source-system and retrieval-health badges. Immediately after `<h3>{item.claim}</h3>`, insert:

```tsx
{status.warning && <p className="warning" role="alert">{status.warning}</p>}
```

- [x] Replace the existing technical `<dl>` with an expandable section. Preserve raw historical values only inside this section; do not reinterpret them as probabilities:

```tsx
<details>
  <summary>Source details</summary>
  <dl className="compact-list">
    <div><dt>Source record ID</dt><dd>{item.source_id?.trim() || "Unavailable"}</dd></div>
    <div><dt>Evidence ID</dt><dd>{item.evidence_id}</dd></div>
    <div><dt>Technical authority scopes</dt><dd>{item.authority_scope.join(", ")}</dd></div>
    <div><dt>Internal evidence classification</dt><dd>{item.uncertainty_state}</dd></div>
  </dl>
  <p>The internal classification is not a probability or a guarantee of supplier performance.</p>
</details>
```

- [x] Insert `<EvidenceFooter status={status} />` after the existing citation link and immediately before `</article>`. Do not change `citationLabel`, trusted URL validation, or the required-citation warning in this stage.
- [x] Append this CSS to `styles.css`:

```css
.evidence-card { display: flex; flex-direction: column; gap: 0.5rem; }
.evidence-card > details { margin: 0.25rem 0; }
.evidence-card summary { cursor: pointer; font-weight: 600; }
.evidence-card summary:focus-visible { outline: 3px solid #e69c37; outline-offset: 3px; }
.evidence-footer { margin-top: auto; padding-top: 0.9rem; border-top: 1px solid #dde4dd; }
.evidence-footer p { margin: 0.35rem 0 0; font-size: 0.8rem; color: #52645e; overflow-wrap: anywhere; }
```

- [x] In `App.tsx`, insert this immediately after the existing initialization/creation status block:

```tsx
{workspace.operation === "analyzing" && (
  <p role="status" aria-live="polite">Analysis in progress. Source retrieval and evidence checks will be shown when the analysis completes.</p>
)}
```

- [x] Run `npm --prefix apps/web test` and `npm --prefix apps/web run build`. Existing `LiveSafety.test.tsx` uses incomplete analysis casts; update those fixtures with explicit analysis IDs, matching evidence IDs/case/runtime, timestamps and a matching validation result where the test expects no warning. Do not disable new warnings or remove assertions to satisfy incomplete fixtures. Tests about unsafe URLs must continue rejecting the same targets.
- [x] Extend `EvidenceFooter.test.tsx` with a render of the integrated `EvidencePanel` using a complete matching fixture; assert `article.lastElementChild` is the footer and that the citation precedes it. Rerender with an old retrieval ID and assert the mismatch warning is before the footer; rerender the same completed analysis and assert the timestamp has not changed. This integration fixture must include all the analysis fields consumed by the presenter, not `as never` partial objects.
- [x] Verify with local fixture rendering at 1280px and 390px that the footer is readable, at the bottom, and warnings remain adjacent to the claim. No real service calls are necessary. Use the webapp-testing skill for local browser verification.
- [x] Run `git diff --check`; commit only Task 2 files and relevant fixture updates with message `feat: move evidence provenance into readable card footers`.

## Stage completion and next boundary

Task 2 completed in `4986eb7`; all steps above implemented and independently
reviewed for specification compliance and code quality. Controller post-commit
checks passed: 86 frontend tests, production build, and local mocked browser
verification at 1280px and 390px (footer placement, warning prominence, stable
timestamp, no overflow or browser errors). The live deployment is unchanged.

Passing this plan delivers only the evidence-status foundation. It does not
implement the three-row investigation layout, typed shipment/transfer/qualification
views, case restoration, Power BI redesign, or walkthrough. Those remain required
in `2026-09-08-planner-experience-delivery.md`. Do not deploy this stage as the
completed redesign or claim that current generic Fabric links are corrected.
