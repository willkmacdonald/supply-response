# Planner Spec Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task, with independent spec and quality review after every task.

**Goal:** Bring the deployed-source planner experience into conformance with the already-approved planner language, meaning, and footer-placement requirements.

**Architecture:** Correct the existing React presentation and Power BI display generators; preserve typed snapshot parsing, calculations, identities, navigation and approval gates. Do not rename source records or rewrite original messages. Reuse the existing isolated `codex/planner-experience` worktree.

**Tech Stack:** React/TypeScript, Vitest, local headless Playwright, Python report generators, existing report schema/TMDL checks.

## Global Constraints

Binding design: `docs/superpowers/specs/2026-09-08-evidence-records-and-case-dashboard-design.md` (approved before implementation). The audit `docs/reviews/2026-09-09-planner-language-audit.md` identifies deviations; it is not a replacement spec.

- “Lead with a business question, a short answer, and the specific quantities, dates, costs, or requirements that explain it.”
- “Use normal supply-chain language throughout cards, status labels, source actions, empty states, and the case dashboard.”
- “The reading order is business question, answer and supporting facts, clearly named source actions, then the platform/activity footer.”
- “Business blockers and critical source failures remain near the affected claim rather than buried in the footer.”
- “Preserve original message text, source identifiers, citations, and immutable analysis records.”
- “Preserve distinctions between an offer, a scheduled receipt, a qualification review date, and an approved action.”
- “Preserve zero values and explicit false flags. Dates and currency must be formatted without timezone-related day shifts or invented units.”
- “Details explicitly say **Snapshot used for this analysis** and **Demo corpus — fictional**.”
- “Provide two clearly named routes through the same scenario: **Explore in Power BI** and **Review with AI assistance**.”
- “Neither `healthy`, `certain`, nor a live-mode configuration alone may produce unsupported validation or live-activity claims.”

Additional execution boundaries: no live cases/analyses/approvals/playback; no source edits, schema/data migrations, permissions, licensing, push, merge, publication, or reporting-receipt activation. New report links remain gated. Local commits are checkpoints, not deployment. The user's Mac is locked, so current-tab diagnosis remains unverified; local headless tests must not be described as live UI acceptance.

## Coverage and acceptance ledger

| Spec requirement | Task | Required proof |
| --- | --- | --- |
| Business-first nine-card sequence; meaningful supplier names | 1 | Rendered card assertions; read every default card against spec |
| Original delay versus optional recovery; zero/null/false preserved | 1, 3 | Original quantity retained; optional receipt excluded from baseline unchanged; absent dates not invented |
| Bottom-of-card source pills, after content and links | 1 | DOM order and headless desktop/mobile element bounds, including Work IQ and Fabric examples |
| Actual retrieval/check transparency, fallback and critical warnings | 1 | Current/failed/conflicting/historical/fallback tests; no broad truth claims |
| Human-readable approval, errors, drafts and outcomes | 2 | Safe error and state-specific tests; controls unchanged |
| Same card meaning and naming in Power BI | 3 | Generator/output labels and DAX checks; no schema/filter/calculation changes |
| Fair traditional versus assisted walkthrough | 3 | Explicit shared calculation/replay disclosure, business steps and preserved route labels |
| Cross-cutting and visual verification | Parent | Fresh full tests/build, artifact checks, screenshots reviewed, final independent review |

## Task 1: Business-first cards and genuine bottom footers

**Files:** Modify `apps/web/src/components/InvestigationEvidence.tsx`, `InvestigationFlow.tsx`, `ExposurePanel.tsx`, `OptionComparison.tsx`, `PredictionSummary.tsx`, `EvidenceSource.tsx`, `EvidenceFooter.tsx`, `evidenceStatus.ts`, `plannerFormatting.ts`, `optionLabels.ts`, `SupportingRecordDetails.tsx`, `CaseHeader.tsx`, `PlanningRoutes.tsx`, `apps/web/src/styles.css`; tests in the corresponding existing `*.test.ts(x)` files. Create a small presentation helper/test only when needed to keep conditional narrative logic readable. Add `apps/web/e2e/planner-presentation.spec.ts` for actual viewport checks using isolated local test data, not the live project.

**Interfaces:** Consume existing `AnalysisVersion`, `PlannerSnapshot`, `EvidenceStatus`, `ResponseOption` and source links. Preserve all input contracts, status boolean logic, trusted URLs, immutable evidence and report URL construction. Task 2 consumes any shared display helpers without changing their semantics.

- [ ] Add failing rendered tests for the first-card problem and main-content technical-language leakage. Extend existing fixtures rather than introducing production hardcoded facts. A canonical assertion is:

```tsx
expect(within(firstCard).queryByText(/Saved disruption:|Recorded partial supply:/)).not.toBeInTheDocument();
expect(within(firstCard).getByText(/8,000 component units.*September 3, 2026/)).toBeVisible();
expect(within(firstCard).getByRole('link', {name: 'Open supplier email'})).toBeVisible();
```

- [ ] Run `npm --prefix apps/web test -- --run src/components/InvestigationEvidence.test.tsx` and record expected RED. Use npm, not the environment's pnpm wrapper (it attempts automatic dependency installation).
- [ ] Implement the business-first narrative. First card: `Original delivery: {quantity} component units of {part} were due at {plant} on {date}.` Explain the disruption without converting it into an observed receipt or claiming a source commitment not validated. Put disruption partial fields in source details if needed; do not confuse them with the optional expedite. Do not subtract a late partial receipt from the original affected quantity. Recovery card: identify its quantity/date as a proposed/planned response option, separate from doing nothing, and preserve supplier statement versus record distinction. Null recovery field is `No recovery date recorded`; use “not confirmed” only with supported source meaning. No globally replacing every null with an inferred reason.
- [ ] Preserve stock arithmetic and replace verbose storage explanations with one footer note. Label assumptions honestly (`Assumptions and unresolved questions` is safe for the mixed collection). Show recommendation actions and existing predicted metrics before comparator detail. Do not invent reasons or recompute ranking. Move raw comparator thresholds and tie-break identifiers into calculation details. Keep missing/no-recommendation distinctions.
- [ ] Keep required exact detail and route labels from Global Constraints. Simplify processing text without claiming checks not recorded: retain `Retrieved for this analysis` and actual timestamp, use `Required checks passed` only under the unchanged passed condition, and explain context-only/non-authoritative/failure states accurately. Configuration may say `Live-service mode`, not imply continuous checks. Preserve conspicuous fictional/sample-data and simulation disclosures.
- [ ] Trace all render paths and CSS for source pills. Keep source footers as the final card child; ensure nested/multiple footers and expanded details remain below content and links. Add bounds checks, not just source-name assertions:

```ts
const footer = card.locator('.source-footers');
const title = await card.locator('h3').boundingBox();
const status = await footer.boundingBox();
expect(status!.y).toBeGreaterThan(title!.y + title!.height);
for (const link of await card.locator('a').all()) {
  const box = await link.boundingBox();
  if (box) expect(status!.y).toBeGreaterThanOrEqual(box.y + box.height);
}
expect(await card.locator('.badge').evaluateAll(nodes => nodes.every(node => Boolean(node.closest('footer'))))).toBe(true);
```

Use actual rendered source-bearing cards, desktop 1440×1000 and mobile 390×844. Check screenshot text and horizontal overflow. If no top-pill defect reproduces, report that honestly, retain regression checks, and do not invent a CSS fix or blame browser cache.
- [ ] Run focused tests, full `npm --prefix apps/web test`, `npm --prefix apps/web run build`, and local presentation browser tests. Record RED/GREEN and screenshot paths. Commit only Task 1 files and write `.superpowers/sdd/conformance-task-1-report.md`.
- [ ] Independent task spec/quality review, fix findings, re-review; parent checks spec wording and screenshots before proceeding.

## Task 2: Actionable lifecycle, approval and failure language

**Files:** `apps/web/src/components/DecisionPanel.tsx`, `ExecutionPanel.tsx`, `OutcomePanel.tsx`, `apps/web/src/App.tsx`, `apps/web/src/api.ts`, `apps/web/src/hooks/useCaseWorkspace.ts`, and corresponding tests (`api.test.ts`, `App.test.tsx`, `LiveSafety.test.tsx`); create `components/DecisionPanel.test.tsx` or a small tested display-message helper if needed.

**Interfaces:** Preserve HTTP methods, payloads, operation names, action/approval controls and retries. Treat backend messages as untrusted diagnostic content, not display copy. Consume Task 1's role and option naming helpers.

- [ ] Write failing tests proving a 503 with `LIVE_SOURCE_UNAVAILABLE` gives a plain-language error without raw JSON/internal exception text; generic/unknown responses remain safe and do not invent a source or retry instruction:

```ts
await expect(requestUnderTest()).rejects.toThrow('The information needed for this analysis could not be retrieved.');
// Existing request fixture supplies the non-OK response; also test unknown error bodies.
```

Also assert raw HTML/exception fields never appear, a disabled approval stays disabled, valid rejection reasons still submit, and approved/rejected receipts show friendly option/state rather than raw runtime/IDs as the main story.
- [ ] Run the focused test file and record RED, then map known error codes to safe exact messages. Generic failures say `The request could not be completed.` Preserve status/code in typed diagnostics only if needed; do not expose raw response bodies. Keep current retry/new-case restrictions, not optimistic advice.
- [ ] Replace `Recorded authorization satisfied` with `Authorization recorded`; replace its negative with `Authorization still required`. Do not call standing authorizations newly granted approvals. Show required roles and selected response; IDs/runtime move to decision details. Map action names by actual kind, keep unsent drafts explicit; `Draft Artifact` becomes `Draft for review` unless its type proves a more specific label. Outcome copy uses `Simulated results` / `Simulation in progress` where supported; keep real versus simulated fields distinct and current restrictions intact. Align post-decision sequence labels to follow the three investigation rows.
- [ ] Run full web tests and build, self-review actual default/error/action text, commit Task 2 files, write `.superpowers/sdd/conformance-task-2-report.md`.
- [ ] Independent spec/quality review and correction loop before Task 3.

## Task 3: Matching Power BI presentation and walkthrough

**Files:** `fabric/report_pages.py`, `fabric/report_model.py`, generated `fabric/power-bi/` definitions/manifest as required by existing generator; `tests/fabric/test_report_generators.py`, `tests/fabric/test_power_bi_project.py`, `docs/demo/traditional-and-assisted-walkthrough.md`. Existing artifact digest packaging must be regenerated through its supported script if changed; no deployment receipt creation/activation.

**Interfaces:** Keep table/measure/source column names, source keys, page IDs, URL filters, model relationships and SQL unchanged. Only display text/projections and generated artifacts change; DAX computations and scope predicates remain unchanged. Match Task 1's business meanings.

- [ ] Add failing generator tests for explicit column labels and absence of zero-as-partial-response wording:

```python
assert column('SavedOptions', 'uncovered_part_demand')['displayName'] == 'Parts still needed'
assert column('SavedOptions', 'executable')['displayName'] == 'Meets planning requirements'
assert column('SavedOptions', 'is_baseline')['displayName'] == 'Do-nothing comparison'
```

Test the generated `Disruption Answer` no longer says `in the partial response`, while its original quantity/date measures and scope remain intact. Test exact approved route names, role-qualified supplier displays, fictional/time context, and unchanged field bindings.
- [ ] Run `.venv/bin/python -m pytest tests/fabric/test_report_generators.py -q` and record RED.
- [ ] Add explicit display-name mapping in `column()` (retain internal field references). Translate headline and explanation strings, not internal identifiers. `Supporting saved records` → `Supporting records`; `Review the decision boundary` → `Review the decision`; `Current governing decision` → `Current decision`; `Projection updated` → `Report data updated`. Preserve exact `Snapshot used for this analysis` detail/footer text, original facts, missing states and current-versus-historical decision notice. Plain-language stock reserved for other requirements must not imply those requirements are specifically customers when data does not establish that. Never relabel currencyless amounts as dollars.
- [ ] Align supplier/disruption/option explanations with Task 1. Distinguish original requirement from separate optional receipt. Main response explanation answers quantity/date/cost or blocker; technical calculation/provenance notes belong below, remain readable. Do not highlight an AI recommendation in the traditional route.
- [ ] Rewrite the walkthrough into concise business steps plus separate presenter notes. Preserve existing route labels, same-analysis/replay/shared-calculation disclosure, exact-source checks, neutral traditional comparison, and prohibition on creating live cases, approving or starting simulations during rehearsal.
- [ ] Run existing generators using their documented `--help`/existing project commands, update generated definitions and digest with supported tool, run both fabric test files and `tests/test_reporting_activation.py`. Verify artifact/schema checks available locally. Record any unavailable native/DAX check rather than fabricate acceptance. Commit Task 3 and write `.superpowers/sdd/conformance-task-3-report.md`.
- [ ] Independent spec/quality review and correction loop.

## Parent final acceptance

- [ ] Review each approved spec section against the coverage table; explicitly retain fulfilled existing behavior and list any unresolved deviation.
- [ ] Fresh full web tests/build, focused reporting/artifact tests, local browser screenshots and viewport/footers assertions. Inspect screenshots personally; do not rely on DOM tests alone.
- [ ] Final independent review of the entire correction range (base `1217401`), including cross-app terminology and the spec requirements, not just the plan's claims.
- [ ] Record commits, actual tests, unresolved live pill-location diagnosis/native Power BI acceptance, and deployment status. No push/merge/deploy/receipt activation without applicable authorization.

## Execution notes

- Baseline before edits: 226 frontend tests passed. Existing worktree retained; audit doc is the only pre-existing untracked change, created by the assistant in the preceding review.
- The package-manager shim attempted dependency installation during the first baseline invocation; it was stopped and its moved packages restored. Baseline passed with npm; no dependency/lockfile change is intended.
- Spec recheck: explicit snapshot labels in details and the two route names stay unchanged. This plan does not treat every occurrence of “saved” or “unavailable” as a defect. No conflict with the approved design requires renewed user approval.
