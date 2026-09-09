# Traditional and assisted walkthrough implementation plan

> For agentic workers: execute task by task in the current isolated worktree, with controller review. This scratch note is a design handoff, not permission to publish or perform live checks. The controller explicitly requested no subagents for this design task.

**Goal:** Present the same existing case and immutable analysis through Explore in Power BI and Review with AI assistance, without an answer preselected in the traditional route.

**Architecture:** Reuse the eight generated report pages. Add a constant presentation-mode column to the existing CaseCommandCenter query; a URL filter on that column selects traditional mode. That route supplies only case and analysis identity; each record page resolves exactly one validated record of its own family within that immutable analysis. Explicit card links retain their existing strict record-ID guard. Keep the existing app tab as the assisted route.

**Tech stack:** Existing Python PBIR/TMDL generators, SQL SELECT projections, TypeScript/Vitest/React. No new analytical engine, report, service, persisted data, relationships, dependencies, authentication, permissions, or licensing changes.

## Status and validation boundary

Local model checkpoint `fad02f4` implements Tasks 1–2 (presentation marker,
exact-analysis requirement, and explicit-versus-singleton record selection).
Its post-hook generator/project suite passes 126 tests with Microsoft TOM.
Independent spec and quality review passed with no findings. After explicit user
approval, the controller uploaded only `fabric/report_model.py` and
`fabric/reporting/queries/CaseCommandCenter.sql` to the existing private
`supply-response-test.exe.xyz` checkout. The updated SQL integration suite passed
126 tests in 13.13 seconds and removed its disposable synthetic database. This
tests SQL Server query behavior, not live Fabric or native Power BI execution.

Tasks 3 and 5 (native navigation and neutral pages) are implemented through
`e0387df` and independently reviewed. The page checkpoint passed 130 model/report
tests; the footer follow-up passed 45 generator tests and the official visual
validator reported zero errors and warnings. An older upstream alias-reproduction
test was corrected to keep exercising the raw alias separately from staging's
normalization; both upstream and application regressions pass.

Task 4 (app routes and guide) is implemented and independently reviewed at
`0b86a72`: 226 web tests and production build pass. The controller passed twelve
desktop/mobile route variants plus twelve existing card-link variants and
inspected both route layouts. These are local browser checks with mocked live
configuration, not native Power BI acceptance.
The packaged API artifact marker was regenerated and independently reviewed at
`f32969e` after the coordinated model/pages/app changes. Its digest is
`6ad16988dd95593c80f597a0892a251b558f28910f46256fe1f6932bb379d3b6`.
The activation regression set passes 62 tests, including raw-settings versus
composed-report-URL bindings. No reporting receipt has been issued or installed.

Final-review corrections at `605015e` subsequently refreshed the digest; see the
[activation checkpoint](2026-09-09-report-activation.md#execution-checkpoint)
for its current value. Those corrections passed 184 focused local checks and
independent source re-review. The user subsequently approved the four-file
private-VM upload and adding protected customer orders to the comparison,
resolving the fixed-column-list conflict in favor of the specification. Updated
real-SQL verification passed 137 tests in 14.58 seconds; the disposable synthetic
database was removed. The comparison column is implemented at `5a57e36`, with
an explicit neutrality test strengthened at `4a365c7`. The focused report/model
suite passes 185 tests, full non-live Python passes 1,182 tests, and the web suite
passes 226 tests plus the production build. The final focused test and generated
page equality rerun passed two tests. Final independent whole-branch re-review
through `1ef0aaf` approved local readiness with no remaining critical or important
findings. No native DAX/rendering or live publication is implied.

Native serialization is now established by Microsoft's authored Power BI Visuals sample, with formatting confirmed by official `@microsoft/powerbi-report-authoring-cli@0.1.4` and its `@microsoft/powerbi-core-visual-schema@0.1.1` dependency. The sample uses `actionButton`, `visualContainerObjects.visualLink`, and literal expressions for `show`, `type='PageNavigation'`, and `navigationSection='<page name>'`. The concrete helper below follows that artifact, not an inferred schema value. Its source artifact uses visualContainer 2.7.0; this project's generator uses pinned 2.9.0 and must validate the resulting structure against that version.

There is no remaining serialization blocker to implementation. Read-only actual-engine navigation/layout acceptance remains part of the existing release gate, not this design task. Generated JSON/TMDL validation cannot establish that case/analysis context persists in a real session. Do not claim runtime Stage 5 acceptance or activate externally until that check is recorded.

## Invariants and observations

- `buildReportUrl` currently puts SavedRecords/record_family and record_key into report-wide URL filters. Native page navigation preserves the report context; these filters conflict with another page's family. Do not start the traditional route from a shipment card URL and add buttons.
- Current `Selected Record Key` requires explicit record key and family. Preserve that branch byte-for-byte, apart from renaming its measure to `Explicit Selected Record Key`.
- Traditional entry has no originating record. Singleton resolution under exact case + analysis + page family is therefore an explicit, narrow inference. It must count all candidate rows before excluding invalid rows; two rows, including one invalid row, are ambiguous.
- No supplied record ID, including an invalid ID, may invoke singleton fallback. An explicit source_record_id also prevents fallback.
- `Selected Analysis Key` already rejects missing, conflicting, unavailable or multiple analyses. `Overview Analysis Key` currently falls back to current analysis when none is requested; traditional mode must disable that fallback.
- Existing response-options table has no recommendation flag/binding or recommendation color. Keep that property and add stable name sorting, not rank sorting.
- `useCaseWorkspace` keeps current case/analysis in memory. Initial mount reads runtime only. It does not restore an analysis from a URL. No Return to demo link is supportable in this scope. The guide instructs returning to the still-open app tab and verifying the displayed IDs. Reloading loses that context; stop the rehearsal if it happens.
- The current case selector combined with a URL case key can produce an intentional conflict/empty state. It must never silently switch analyses. Changing/clearing a case selection requires a deliberate new route launch from a loaded app context.
- This adds a presentation constant to one SELECT projection. It does not change SQL views, source records or calculation outputs. The controller proposed this smaller alternative to a sixth disconnected table; use it.

## Task 1: constant mode and exact-analysis selection

Files: `fabric/reporting/queries/CaseCommandCenter.sql`, `fabric/report_model.py`, `tests/fabric/test_report_generators.py`; regenerated native model after controller integration.

- [x] Add this SELECT expression to the existing CaseCommandCenter SELECT list; preserve all existing columns and joins:

```sql
CAST(N'traditional' AS nvarchar(16)) AS walkthrough_route,
```

- [x] Add `"walkthrough_route"` to `COLUMNS[CC]` in report_model.py. TYPES already defaults columns to string. Do not add relationships or a sixth table. The generated directQuery partition automatically takes the updated query.

- [x] Add these measures inside `measures()` after defining `external`:

```python
external(
    "Walkthrough Requested",
    "INT(ISFILTERED(CaseCommandCenter[walkthrough_route]))",
    CC, "int64",
)
external(
    "Traditional Mode",
    '''INT(ISFILTERED(CaseCommandCenter[walkthrough_route])
        && HASONEFILTER(CaseCommandCenter[walkthrough_route])
        && SELECTEDVALUE(CaseCommandCenter[walkthrough_route]) == "traditional")''',
    CC, "int64",
)
add(
    "Review Approach",
    '''IF([Walkthrough Requested] == 1,
        IF([Traditional Mode] == 1,
            "Compare cost, service exposure, parts still needed and planning blockers. State your proposed response before reviewing AI assistance.",
            "Walkthrough selection unavailable"),
        [Recommendation Answer])''',
)
```

The route has one allowed filter value, traditional. Absence preserves current app-linked report behavior. Unknown or conflicting route values hide the recommendation and produce selection-unavailable; do not interpret them as assisted mode. Filtering a constant column to an unknown value naturally removes all case rows.

- [x] In `Overview Analysis Key`, replace its final return with:

```dax
RETURN IF([Walkthrough Requested] == 1 || [Analysis Requested] == 1,
    [Selected Analysis Key],
    IF(NOT ISBLANK(C) && NOT ISBLANK(A) && N == 1,A))
```

Use the existing generator's variable-renaming helper as usual. No direct case-only traditional entry can now resolve a current analysis implicitly.

- [x] Add concrete structural regression tests:

```python
def test_traditional_marker_is_a_presentation_column_not_a_new_table():
    model = report_model.manifest()
    assert set(model["tables"]) == set(report_model.TABLES)
    assert len(model["tables"]) == 5
    assert model["tables"]["CaseCommandCenter"]["columns"]["walkthrough_route"] == "string"
    sql = (QUERIES / "CaseCommandCenter.sql").read_text()
    assert "CAST(N'traditional' AS nvarchar(16)) AS walkthrough_route" in sql
    assert model["relationships"] == []

def test_traditional_entry_never_falls_back_to_current_analysis():
    measures = report_model.measures()[report_model.CC]
    expression = measures["Overview Analysis Key"].expression
    assert "[Walkthrough Requested] == 1 || [Analysis Requested] == 1" in expression
    assert "[Selected Analysis Key]" in expression
    approach = measures["Review Approach"].expression
    assert "[Walkthrough Requested] == 1" in approach
    assert "Walkthrough selection unavailable" in approach
```

Run `uv run --extra dev pytest tests/fabric/test_report_generators.py -q`. These assert artifact contracts, not DAX engine semantics. Record that distinction.

## Task 2: strict singleton record resolution

File: `fabric/report_model.py`; tests in `tests/fabric/test_report_generators.py` plus the later actual-engine acceptance matrix.

- [x] Rename the current external `Selected Record Key` definition to `Explicit Selected Record Key`, retaining its full existing expression. Add the following definitions immediately after it and before `Selected Record Family`:

```python
external(
    "Record Identity Requested",
    '''INT(ISFILTERED(SavedRecords[record_key])
        || ISFILTERED(SavedRecords[source_record_id]))''',
    SR, "int64",
)
external(
    "Walkthrough Record Key",
    '''VAR CaseKey = [Selected Case Key]
    VAR AnalysisKey = [Selected Analysis Key]
    VAR Family = SELECTEDVALUE(SavedRecords[record_family])
    VAR Candidates = CALCULATETABLE(SavedRecords,
        REMOVEFILTERS(SavedRecords),
        TREATAS({CaseKey}, SavedRecords[case_key]),
        TREATAS({AnalysisKey}, SavedRecords[analysis_key]),
        TREATAS({Family}, SavedRecords[record_family]))
    VAR ValidCandidates = FILTER(Candidates,
        SavedRecords[record_state] == "available"
        && SavedRecords[evidence_state] == "available"
        && SavedRecords[runtime_mode] == "live"
        && SavedRecords[provenance] == "saved_fabric")
    RETURN IF([Traditional Mode] == 1
        && [Record Identity Requested] == 0
        && NOT ISBLANK(CaseKey) && NOT ISBLANK(AnalysisKey)
        && ISFILTERED(SavedRecords[record_family])
        && HASONEFILTER(SavedRecords[record_family])
        && Family IN {"shipment","transfer","qualification"}
        && COUNTROWS(Candidates) == 1 && COUNTROWS(ValidCandidates) == 1,
        MAXX(ValidCandidates, SavedRecords[record_key]))''',
    SR,
)
add(
    "Selected Record Key",
    '''IF([Record Identity Requested] == 1,
        [Explicit Selected Record Key],
        [Walkthrough Record Key])''',
    hidden=True,
)
```

`evidence_state`/`provenance` come from the existing saved-evidence projection, which validates matching source identity/retrieval lineage. Do not replace that validation with a name or availability-only check. `Candidates` clears row/table filters only after capturing the page family and reapplying exact case/analysis. Therefore a selected supporting table row cannot hide a duplicate.

The existing page-local family filter supplies family. Stock and customer-order collection pages continue to use their own complete-collection gates; they receive no stale SavedRecords URL filters. The selected family and all downstream row/metric measures continue using existing `Selected Record Key`.

- [x] Add this regression test; update existing selection-expression tests to inspect `External Explicit Selected Record Key` where their intention is the explicit card branch, retaining all their current assertions:

```python
def test_walkthrough_does_not_replace_explicit_record_identity_validation():
    measures = report_model.measures()[report_model.CC]
    explicit = measures["External Explicit Selected Record Key"].expression
    assert "HASONEFILTER(SavedRecords[record_key])" in explicit
    assert '"shipment","transfer","qualification"' in explicit
    selected = measures["Selected Record Key"].expression
    assert "[Record Identity Requested] == 1" in selected
    assert "[Explicit Selected Record Key]" in selected
    singleton = measures["External Walkthrough Record Key"].expression
    assert "COUNTROWS(Candidates) == 1 && COUNTROWS(ValidCandidates) == 1" in singleton
    assert "REMOVEFILTERS(SavedRecords)" in singleton
    assert '[Record Identity Requested] == 0' in singleton
    assert 'SavedRecords[provenance] == "saved_fabric"' in singleton
```

Run the same generator tests. Do not build a Python model that pretends to execute these DAX expressions; it would duplicate rather than verify engine behavior.

## Task 3: neutral report presentation and route sequence

File: `fabric/report_pages.py`, generator tests, regenerated native pages.

- [x] In overview's existing recommendation-answer card, keep its visual identity but replace its title/binding with `"Review approach", "Review Approach"`. All recommendation text must be behind the mode branch. Do not put recommended metrics in titles, tooltips, source tables, conditional formats or sorting in traditional mode.
- [x] Preserve response-options projections and add the user-approved protected-customer-orders field (option_name, is_baseline, executable, response_cost, revenue_at_risk, otif_loss_percentage, uncovered_part_demand, protected_customer_order_count, blockers_text, required_roles_text). Label the added field **Customer orders protected**. This supersedes the original fixed list after final review and user approval. No is_recommended column or conditional recommendation color. Set its query's sortDefinition using the already pinned QuerySort schema:

```python
comparison["visual"]["query"]["sortDefinition"] = {
    "sort": [{"field": field("Column", SO, "option_name"), "direction": "Ascending"}],
    "isDefaultSort": False,
}
```

Capture the existing comparison table in local variable `comparison` before appending it to `items`; its existing arguments are unchanged. Alphabetical ordering does not imply ranking. The traditional builder never supplies option_key, so selected-option cards stay in comparison state.

- [x] Define the sequence independently of report tab ORDER (preserve current identities):

```python
WALKTHROUGH = (
    ("command-center", "1. Investigate the delay"),
    ("available-stock", "2. Check available stock"),
    ("customer-orders", "2. Inspect affected order lines"),
    ("supplier-shipment", "3. Check the partial shipment"),
    ("plant-transfer", "3. Check the plant transfer"),
    ("supplier-qualification", "3. Check qualification"),
    ("response-options", "4. Weigh the trade-offs"),
    ("actions-outcomes", "5. Review the decision boundary"),
)
```

Use the same sequence's Previous/Next destinations in native fixtures once established. First page has no Previous; last page has no Next. Retain free page tabs and a clearly named Case dashboard destination. Do not use Back as Previous: Back depends on browsing history rather than the approved sequence. Do not use bookmarks that capture case/analysis filters.

The inspected layout ends at y=708 on a 720px page. Allocate a real navigation band by extending all pages to height 808: step textbox `(24, 714, 768, 44)`, Previous control `(800, 714, 220, 44)`, Next `(1036, 714, 220, 44)`, footer `(24, 770, 1232, 30)`. Move the existing fictional-footer from y=682 to y=770 and replace its final sentence with `Return to the existing demo tab for original messages and AI assistance.` Existing business visual positions stay stable. Update canvas bounds test to use page dimensions rather than hardcoded 720. Actual visual review must check FitToPage legibility at this increased height. Rebase these positions on the controller's concurrent layout corrections before implementation; avoid reintroducing textbox floor warnings. The 44px step height was corrected after running the proposed helper through the official CLI.

## Task 4: exact-context route URL and two app actions

Files: `apps/web/src/reporting/reportNavigation.ts`, its existing tests, new `apps/web/src/components/PlanningRoutes.tsx`, `App.tsx`, `InvestigationFlow.tsx`, component tests. Integrate with the Stage 4 worker's mounted link changes rather than overwriting CaseHeader.

- [x] Export the following helper alongside buildReportUrl:

```typescript
export function buildTraditionalReportUrl(
  runtime: RuntimeStatus,
  target: { caseId: string; analysisId: string; runtimeMode: "live" | "fallback" },
): string | null {
  const base = buildReportUrl(runtime, { ...target, page: "command-center" });
  if (!base || !usableIdentity(target.analysisId)) return null;
  const url = new URL(base);
  const filter = url.searchParams.get("filter");
  if (!filter) return null;
  url.searchParams.set("filter", filter + " and CaseCommandCenter/walkthrough_route eq 'traditional'");
  return url.search.length <= 2000 ? url.href : null;
}
```

Keep the existing exact report release guard. The controller has decided Stage 4 and Stage 5 co-release and the API artifact digest is regenerated after Stage 5; no additional feature flag or receipt is needed. Do not activate a partial Stage 4 report with this route.

- [x] New component code:

```tsx
import type { AnalysisVersion, CaseInstance, RuntimeStatus } from "../types";
import { buildTraditionalReportUrl } from "../reporting/reportNavigation";

export function PlanningRoutes({ runtime, caseInstance, analysis }: {
  runtime: RuntimeStatus | null;
  caseInstance: Pick<CaseInstance, "case_id" | "runtime_mode"> | null;
  analysis: Pick<AnalysisVersion, "analysis_id" | "case_id" | "runtime_mode"> | null;
}) {
  if (!runtime || !caseInstance || !analysis
    || caseInstance.case_id !== analysis.case_id
    || caseInstance.runtime_mode !== analysis.runtime_mode) return null;
  const url = buildTraditionalReportUrl(runtime, {
    caseId: caseInstance.case_id, analysisId: analysis.analysis_id,
    runtimeMode: analysis.runtime_mode,
  });
  return <nav aria-label="Planning routes" className="panel">
    <div className="planning-route-actions">
      {url && <a href={url} target="_blank" rel="noopener noreferrer">Explore in Power BI</a>}
      <a href="#assisted-review">Review with AI assistance</a>
    </div>
    <p>{url
      ? "Both routes use this saved analysis. Power BI opens in a new tab. Keep this tab open for original email and Teams sources and AI-assisted review."
      : "The Power BI comparison is not available for this analysis. You can still review the saved evidence and AI assistance here."}</p>
    <p>Replay of saved evidence; this is not a new discovery run.</p>
  </nav>;
}
```

Mount immediately after CaseHeader with `runtime={workspace.runtime} caseInstance={workspace.caseInstance} analysis={workspace.analysis}`. Add `id="assisted-review"` to InvestigationFlow's outer div. These are navigation affordances, not application routes that reconstruct state. Do not call analyze, selectOption, create, approve or playback handlers when switching.

Controller preflight correction: also own this small addition to `apps/web/src/styles.css`, so adjacent links remain distinct, keyboard accessible and wrap on mobile. This is the only additional presentation file in scope:

```css
.planning-route-actions { display: flex; flex-wrap: wrap; gap: 0.75rem 1.25rem; }
.planning-route-actions a { display: inline-flex; align-items: center; min-height: 2.75rem; }
```

Extend the fallback component test below to assert `screen.getByText(/The Power BI comparison is not available/)` is visible and `screen.queryByText(/Both routes use this saved analysis/)` is absent. Repeat the unavailable-copy assertion in the invalid activation/URL test. Do not promise an available Power BI route when its link is hidden.

- [x] Add to reportNavigation.test.ts (reuse existing runtime and reportIdentityKey fixture):

```typescript
it("launches traditional mode without a record or option preselection", () => {
  const result = new URL(buildTraditionalReportUrl(runtime, {
    caseId: "Case-A", analysisId: "Historical-A", runtimeMode: "live",
  })!);
  expect(result.pathname.endsWith("/command-center")).toBe(true);
  expect(result.searchParams.get("filter")).toBe([
    `CaseCommandCenter/case_key eq '${reportIdentityKey("Case-A")}'`,
    `SavedAnalyses/analysis_key eq '${reportIdentityKey("Historical-A")}'`,
    "CaseCommandCenter/walkthrough_route eq 'traditional'",
  ].join(" and "));
  expect(result.search).not.toContain("SavedRecords");
  expect(result.search).not.toContain("SavedOptions");
});
it("rejects a traditional route without an explicit analysis", () => {
  expect(buildTraditionalReportUrl(runtime, {
    caseId: "Case-A", analysisId: "", runtimeMode: "live",
  })).toBeNull();
});
```

The component accepts only the identity fields it reads, allowing precise component fixtures without constructing unrelated analysis material. Create `apps/web/src/components/PlanningRoutes.test.tsx` with this complete code:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RuntimeStatus } from "../types";
import { reportIdentityKey } from "../reporting/reportNavigation";
import { PlanningRoutes } from "./PlanningRoutes";

const runtime: RuntimeStatus = {
  runtime_mode: "live", work_iq: "work_iq", operational_store: "fabric_sql",
  agent_runtime: "foundry", power_bi_available: true,
  power_bi_url: "https://app.powerbi.com/groups/dc3ac590-d892-40a7-9388-65dec120d67a/reports/e7611c8c-c887-443f-858a-13b1044bb4b9",
  deployment_contract: { power_bi_reporting_contract: "saved-analysis-v1" },
};
const caseInstance = { case_id: "Case-A", runtime_mode: "live" as const };
const analysis = { case_id: "Case-A", analysis_id: "Historical-A1", runtime_mode: "live" as const };
const props = { runtime, caseInstance, analysis };

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("planning routes", () => {
  it("names both routes and opens an exact unselected traditional context", () => {
    render(<PlanningRoutes {...props} />);
    expect(screen.getByRole("navigation", { name: "Planning routes" })).toBeVisible();
    const report = screen.getByRole("link", { name: "Explore in Power BI" });
    expect(report).toHaveAttribute("target", "_blank");
    expect(report).toHaveAttribute("rel", "noopener noreferrer");
    const href = new URL(report.getAttribute("href")!);
    expect(href.searchParams.get("filter")).toBe([
      `CaseCommandCenter/case_key eq '${reportIdentityKey(caseInstance.case_id)}'`,
      `SavedAnalyses/analysis_key eq '${reportIdentityKey(analysis.analysis_id)}'`,
      "CaseCommandCenter/walkthrough_route eq 'traditional'",
    ].join(" and "));
    expect(screen.getByRole("link", { name: "Review with AI assistance" }))
      .toHaveAttribute("href", "#assisted-review");
    expect(screen.getByText(/Replay of saved evidence/)).toBeVisible();
    expect(screen.queryByRole("link", { name: "Return to demo" })).not.toBeInTheDocument();
  });

  it("keeps assisted review local and makes no request", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    render(<><PlanningRoutes {...props} /><div id="assisted-review">Existing analysis</div></>);
    const before = structuredClone(props);
    await userEvent.click(screen.getByRole("link", { name: "Review with AI assistance" }));
    expect(fetch).not.toHaveBeenCalled();
    expect(props).toEqual(before);
    expect(screen.getByText("Existing analysis")).toBeVisible();
  });

  it("does not offer Power BI for fallback", () => {
    render(<PlanningRoutes runtime={{ ...runtime, runtime_mode: "fallback" }}
      caseInstance={{ ...caseInstance, runtime_mode: "fallback" }}
      analysis={{ ...analysis, runtime_mode: "fallback" }} />);
    expect(screen.queryByRole("link", { name: "Explore in Power BI" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review with AI assistance" })).toBeVisible();
  });

  it.each([
    { ...props, runtime: null },
    { ...props, caseInstance: null },
    { ...props, analysis: null },
    { ...props, analysis: { ...analysis, case_id: "Case-B" } },
    { ...props, analysis: { ...analysis, runtime_mode: "fallback" as const } },
  ])("hides routes without a matching loaded context", invalid => {
    render(<PlanningRoutes {...invalid} />);
    expect(screen.queryByRole("navigation", { name: "Planning routes" })).not.toBeInTheDocument();
  });

  it("keeps assistance available when report activation or URL is invalid", () => {
    const { rerender } = render(<PlanningRoutes {...props}
      runtime={{ ...runtime, deployment_contract: null }} />);
    expect(screen.queryByRole("link", { name: "Explore in Power BI" })).not.toBeInTheDocument();
    rerender(<PlanningRoutes {...props} runtime={{ ...runtime, power_bi_url: "https://evil.example" }} />);
    expect(screen.queryByRole("link", { name: "Explore in Power BI" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review with AI assistance" })).toBeVisible();
  });
});
```

Add this integration test to existing App.test.tsx using its current lifecycle mock. It creates/analyzes only mocked local fixture data before capturing the request count; clicking the route must perform no lifecycle action:

```tsx
it("keeps the loaded analysis when entering assisted review", async () => {
  const fetchMock = mockFallbackCaseLifecycle();
  render(<App />);
  await screen.findByText("Fallback mode");
  await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
  await screen.findByText("RL-CASE-1");
  await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
  await screen.findByText("Combined response");
  const content = document.getElementById("assisted-review")!;
  expect(content).not.toBeNull();
  const beforeContent = content.textContent;
  const beforeCalls = fetchMock.mock.calls.length;
  await userEvent.click(screen.getByRole("link", {name: "Review with AI assistance"}));
  expect(fetchMock.mock.calls).toHaveLength(beforeCalls);
  expect(content.textContent).toBe(beforeContent);
});
```

Add this invalid-helper matrix to reportNavigation.test.ts, alongside the valid exact URL test above:

```typescript
it.each([
  { ...runtime, deployment_contract: null },
  { ...runtime, power_bi_available: false },
  { ...runtime, runtime_mode: "fallback" as const },
  { ...runtime, power_bi_url: "https://evil.example" },
  { ...runtime, power_bi_url: base + "?filter=stale" },
])("rejects unavailable traditional report configurations", unavailable => {
  expect(buildTraditionalReportUrl(unavailable, {
    caseId: "Case-A", analysisId: "Analysis-A", runtimeMode: "live",
  })).toBeNull();
});
it.each(["", " ", "bad\nidentity", "x".repeat(257)])("rejects invalid traditional analysis IDs", analysisId => {
  expect(buildTraditionalReportUrl(runtime, { caseId: "Case-A", analysisId, runtimeMode: "live" })).toBeNull();
});
it("rejects an overlong encoded traditional query", () => {
  expect(buildTraditionalReportUrl(runtime, {
    caseId: "C".repeat(256), analysisId: "A".repeat(256), runtimeMode: "live",
  })).toBeNull();
});
```

Run `npm --prefix apps/web test -- --run` and `npm --prefix apps/web run build` after integration. No live environment calls.

## Task 5: native controls and generated-navigation tests

Authoritative artifact: [Microsoft Power BI Visuals.pbix at commit 315f69601ecd9911ff7dcad057c9610d48176cf6](https://github.com/microsoft/powerbi-desktop-samples/blob/315f69601ecd9911ff7dcad057c9610d48176cf6/Power%20BI%20Visuals%20report/Power%20BI%20Visuals.pbix), downloaded read-only to `/private/tmp/supply-response-navigation-sample.5l7LCX/visuals.pbix`. The commit is the GitHub API's last change to this sample path when inspected. SHA256: `63d327bb8f637e8f3995987a7071223616f395129d3d61a9eeac270bf3390fe1`. Native ZIP entry: `Report/definition/pages/e0df29a8eae09c034499/visuals/b10f7a4d626abaaabf0c/visual.json`. It is an actionButton pointing to page `e8fbc6661062172617a0`. Its action fields are exactly:

```json
{"visualLink":[{"properties":{"show":{"expr":{"Literal":{"Value":"true"}}},"type":{"expr":{"Literal":{"Value":"'PageNavigation'"}}},"navigationSection":{"expr":{"Literal":{"Value":"'e8fbc6661062172617a0'"}}}}}]}
```

Add the following helper to report_pages.py. Names, rects and colors are local presentation choices. Action serialization follows the official artifact and formatting follows the official catalog:

```python
def navigation_button(name, label, rect, destination):
    if destination not in ORDER:
        raise ValueError("Unknown walkthrough page: " + destination)
    visual = base_visual(name, "actionButton", rect, fill=CREAM)
    visual["visual"]["objects"] = {
        "text": [
            {"properties": {"show": literal(True)}},
            {"selector": {"id": "default"}, "properties": {
                "text": literal(label), "fontFamily": literal("Segoe UI"),
                "fontSize": literal(14), "fontColor": color(WHITE),
            }},
        ],
        "fill": [
            {"properties": {"show": literal(True)}},
            {"selector": {"id": "default"}, "properties": {
                "fillColor": color(GREEN), "transparency": literal(0),
            }},
            {"selector": {"id": "hover"}, "properties": {
                "fillColor": color(TEAL), "transparency": literal(0),
            }},
        ],
        "outline": [
            {"properties": {"show": literal(False)}},
            {"selector": {"id": "default"}, "properties": {"show": literal(False)}},
        ],
    }
    visual["visual"]["visualContainerObjects"]["visualLink"] = obj({
        "show": literal(True),
        "type": literal("PageNavigation"),
        "navigationSection": literal(destination),
    })
    visual["visual"]["visualContainerObjects"]["general"] = obj({"altText": literal(label)})
    return visual
```

Metadata inspection commands (all offline) were `formatting describe-object actionButton visualLink`, `text`, `fill`, and `outline`; the raw reference type is at `node_modules/@microsoft/powerbi-core-visual-schema/data/vco-capabilities.json` under `visualLink.properties.navigationSection.type`.

Add this helper, then call `items.extend(walkthrough_controls(page))` in `artifacts()` after selecting its overview/detail/options/actions items and before sorting/tabOrder assignment:

```python
def walkthrough_controls(page):
    sequence = tuple(name for name, title in WALKTHROUGH)
    index = sequence.index(page)
    items = [text("walkthrough-step", WALKTHROUGH[index][1], (24, 714, 768, 44), 18)]
    if index > 0:
        items.append(navigation_button(
            "walkthrough-previous", "Previous", (800, 714, 220, 44), sequence[index - 1],
        ))
    if index + 1 < len(sequence):
        items.append(navigation_button(
            "walkthrough-next", "Next", (1036, 714, 220, 44), sequence[index + 1],
        ))
    return items
```

Use the 808px page and footer allocation in Task 3, rebasing positions if the concurrent native-layout worker changes the base geometry. Preserve step order, 44px buttons, readable footer, no overlap, and page bounds. Both ordinary and traditional report sessions can use these navigation controls; ordinary explicit record links still deliberately retain their strict record identity/filter context and may show an unavailable state on another family. Only the clearly named traditional launch is the guided multi-family route. Explain that distinction in card-link report footer if needed; do not silently broaden existing card filters.

Concrete acceptance for that helper:

```python
def test_walkthrough_sequence_uses_all_existing_pages_once():
    sequence = tuple(page for page, title in report_pages.WALKTHROUGH)
    assert len(sequence) == len(set(sequence)) == 8
    assert set(sequence) == set(report_pages.ORDER)
    assert sequence[0] == "command-center"
    assert sequence[-1] == "actions-outcomes"
```

Extend generated artifact tests to verify 14 controls, absence of Previous on first and Next on last, exact adjacent destinations, no filters/bookmarks/URLs in those controls, deterministic output, pinned schema success, field binding success, keyboard order and canvas bounds. Inspect actual exported fields in those assertions; do not write self-fulfilling assertions around a guessed serializer.

Concrete test code (the official action shape is now established):

```python
def test_native_previous_next_match_official_action_shape():
    artifacts = report_pages.artifacts()
    sequence = tuple(page for page, _ in report_pages.WALKTHROUGH)
    controls = []
    for index, page in enumerate(sequence):
        prefix = f"pages/{page}/visuals/"
        expected = {}
        if index:
            expected["walkthrough-previous"] = sequence[index - 1]
        if index + 1 < len(sequence):
            expected["walkthrough-next"] = sequence[index + 1]
        for name in ("walkthrough-previous", "walkthrough-next"):
            key = prefix + name + "/visual.json"
            if name not in expected:
                assert key not in artifacts
                continue
            control = artifacts[key]
            controls.append(control)
            assert control["visual"]["visualType"] == "actionButton"
            assert "filterConfig" not in control
            assert control["visual"]["visualContainerObjects"]["visualLink"] == [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "type": {"expr": {"Literal": {"Value": "'PageNavigation'"}}},
                    "navigationSection": {"expr": {"Literal": {"Value": "'" + expected[name] + "'"}}},
                },
            }]
            assert control["position"]["height"] >= 44
            assert control["visual"]["visualContainerObjects"]["general"][0]["properties"]["altText"]
    assert len(controls) == 14

def test_native_navigation_rejects_unrecognized_destinations():
    with pytest.raises(ValueError, match="Unknown walkthrough page"):
        report_pages.navigation_button("next", "Next", (0, 0, 220, 44), "https://evil.example")
```

The existing deterministic pinned-schema generation test exercises all newly generated controls. Run it plus the controller-installed CLI validator after integrating the concurrent generator corrections; do not copy or fix unrelated outstanding CLI findings in this task. Record actual-engine filtering/navigation and rendered accessibility as still unrun.

Offline verification performed during this design update: `/private/tmp/supply-response-navigation-sample.5l7LCX/check_plan.py` extracts the exact Python helpers from this note, generates all 14 buttons and eight step titles into a temporary report copy, and runs the repository's `_validate_offline_json_schemas` against it. Result: passed. Official CLI 0.1.4 `validate --no-schema --format json` reports **zero diagnostics on the walkthrough controls or step titles**. The full temporary report still has the known concurrent baseline findings: 164 missing nativeQueryRef errors, 16 existing textbox floor warnings, and 11 duplicate-filter warnings; those are owned by the separate generator correction task. Initial inspection caught the proposed 32px step height below the CLI's 37px floor; this note now uses 44px, and the exact amended helper was rerun successfully. No claim of complete-report CLI success or runtime rendering is made.

## Presenter guide text

Create `docs/demo/traditional-and-assisted-walkthrough.md` during implementation and link it from the existing human overview. This is a short focused guide, not a new project overview; Markdown is appropriate. Text:

> Open an existing analyzed fictional case in the demo and keep its tab open. Note the case ID, analysis ID and saved time in Analysis source details. This walkthrough replays those saved records; it does not demonstrate a fresh discovery run. Do not create or analyze a case for this rehearsal.
>
> Start with the original supplier email from the disruption card. Identify the affected component and Chicago plant, original delivery requirement, missed quantity, and what the sender has and has not confirmed. Choose Explore in Power BI. Confirm the same case and analysis in Source details. The report shows the saved snapshot used for that analysis.
>
> On the case dashboard, orient yourself to the disruption without selecting a response. Continue to Available stock: inspect on-hand units, quality holds and protected allocation, then usable component units. Continue to Affected customer orders: inspect order lines and due dates. The saved baseline predicts exposure without a response; line values are not an independently calculated total of predicted missed revenue or service.
>
> Continue through the partial shipment, Dallas-to-Chicago transfer and alternate-supplier qualification pages. Compare quantities, dates, per-unit costs and unresolved conditions. Review the original supplier email and Quality Teams post in the existing demo tab as needed. A qualification review date is neither approval nor a delivery promise. These Power BI views present the same saved evidence, not independent corroboration.
>
> On Response options, compare all alternatives on the same units and assumptions: cost, expected service exposure, parts still needed and planning requirements. No option is highlighted as the recommendation. State your proposed response and remaining questions before opening the assisted comparison. A plan meeting requirements still needs the applicable human review.
>
> The report's option predictions come from the application's shared saved calculation engine. Power BI is presenting them, not recalculating an independent analysis. Do not attribute deterministic arithmetic or ranking to Work IQ or an LLM. Discovery, source retrieval, validation, deterministic calculation and human approval have different responsibilities in this implementation.
>
> Finish at Actions and outcomes. State the recorded decision status accurately. If a governing decision belongs to another saved analysis, explain that lineage rather than comparing its observations as outcomes of the selected analysis. No outcomes means no recorded outcomes; simulated observations remain labeled Simulated. Do not approve, plan execution or start playback during this walkthrough.
>
> Return manually to the existing demo tab and confirm the same case and analysis. Choose Review with AI assistance. Review the three investigation rows: source attribution and disruption, stock and exposure, then partial shipment, transfer and qualification. Show the recommendation and explanation alongside the saved comparison and original sources. Human judgment still addresses uncertainty, trade-offs and authorization.
>
> The comparison is how information is found, connected, checked and interpreted. This traditional route uses report pages plus original email and Teams sources; this app brings them together. It does not establish that Power BI cannot integrate those sources. Do not claim measured time savings, click savings, accuracy gains or operational outcomes. Future timings must separate replayed/cached material from fresh runs.
>
> If the report selection is unavailable, a record is missing/ambiguous, the report has not caught up, or an ID differs, stop the comparison and use the working inline source view. Do not select a similar record or the latest analysis to make the screen populate. If the demo tab was reloaded or lost, this version cannot restore its exact context with a return link: stop and re-establish that existing context through a separately supported workflow. There is deliberately no Return to demo button.

## Later acceptance matrix, without claiming it ran

After local structural/build checks pass, the release controller must obtain read-only actual-engine/render evidence for: exact case A + historical analysis A1 alongside newer A2 and another case B; missing analysis; wrong case/analysis pair; no case; multiple cases; empty/unknown route; absent mode; all eight Previous/Next transitions; free tab movement; refresh; conflicting case selector; exactly one family record; zero records; two records; one valid plus one invalid; one valid record with evidence mismatch; explicit invalid record_key and source_record_id; legitimate zero/false values; options unselected and without recommendation cues; same values as the app; original sources accessible; manual existing-tab assisted navigation preserving IDs. Any stale persistent record/option filters must show a clear conflict, never a substituted record. Verify the report service's persistent filter behavior specifically; Microsoft documents AND-combination with preexisting filters. A new URL alone is not proof they were cleared.

The current native buttons and DAX have not been executed by this design task. Do not run tests/fabric/test_power_bi_live.py: it mutates the environment. Do not publish, change access, execute DAX against live services, approve a decision or run playback under this task.

## Primary-source evidence

- Microsoft Learn, [Create and configure buttons](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-buttons): supports Page navigation to another page without bookmarks; also distinguishes Back and Web URL actions. It describes UI authoring, not the serialized enum.
- Microsoft Learn, [URL filters](https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-url-filters): hidden columns can be filtered, values are case-insensitive (hence existing hexadecimal identity keys), and existing filters combine with URL filters.
- Microsoft [visual configuration schema](https://github.com/microsoft/json-schemas/blob/main/fabric/item/report/definition/visualConfiguration/2.3.0/schema.json), also pinned locally in `fabric/schemas/microsoft/b63824c35f98a0f5ed86.json`: VisualLink property names are specified, but their values use empty schemas. A guessed action can validate.
- Microsoft [report authoring examples](https://github.com/microsoft/skills-for-fabric/blob/main/skills/powerbi-report-authoring/references/authoring.md) and [formatting reference](https://github.com/microsoft/skills-for-fabric/blob/main/skills/powerbi-report-authoring/references/formatting.md): require exact visual-format property inspection; actionButton formatting uses instance selectors. These did not establish a complete navigation action export in the inspected material.

## Handoff

Only this scratch note was edited; four bounded public Microsoft sample downloads are under the temporary directory cited above. No production files, native artifacts, source data or docs were modified, no commit was made, and no live authentication/query/publish was performed. Native action serialization is now supported by an official source artifact. The controller should review the singleton interpretation and mode activation order before implementing these independent tasks. Actual-engine and rendered navigation acceptance remains the existing release gate.
