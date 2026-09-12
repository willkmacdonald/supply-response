# Recommendation Explanation Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Place the saved recommendation explanation beside its recommended option in an accessible sheet.

**Architecture:** One coherent frontend task reuses ExposurePanel and PredictionComparison as the explanation body. OptionComparison owns the action and open state; a small native dialog wrapper provides modal behavior. The parent verifies the built preview while an independent reviewer checks the implementation.

**Tech Stack:** Existing React/TypeScript, CSS, Vitest/Testing Library, Playwright. No new dependency.

## Global Constraints

- Binding spec: docs/superpowers/specs/2026-09-12-recommendation-explanation-sheet-design.md (approved).
- “ⓘ Click here to understand why” beside “Recommended for review”.
- Sheet title: “Why this response is recommended”. Below 640px it fills the screen.
- Opening or closing the sheet does not select, approve, reject, execute, fetch new evidence, or change the current analysis.
- Preserve latest USD formatting, source links, safety messages, ranking rules, and disabled preview approvals.
- No Azure deployment. Do not change the other two investigation tabs.

### Task 1: Recommendation sheet, integration, and regression tests

**Files:**
- Create: apps/web/src/components/RecommendationSheet.tsx (native modal lifecycle only).
- Create: apps/web/src/components/recommendationState.ts (shared recommendation resolution).
- Modify: apps/web/src/components/OptionComparison.tsx (action/open state and unavailable message).
- Modify: apps/web/src/components/ExposurePanel.tsx (reuse body, plain-language recorded reasons).
- Modify: apps/web/src/components/InvestigationFlow.tsx (remove duplicate card).
- Modify: apps/web/src/styles.css (scoped sheet and badge/button layout).
- Test: apps/web/src/components/RecommendationSheet.test.tsx; existing InvestigationFlow.test.tsx, reportCardLinks.test.tsx, and affected component/integration tests.

**Interfaces:**
- Consumes existing AnalysisVersion, PlannerSnapshot, RuntimeStatus and ReportAnalysisContext.
- `recommendedOption(analysis: AnalysisVersion): ResponseOption | null` resolves a single consistent executable active response, with valid prediction and no blocking codes; conflicting/duplicate/missing identities fail closed. Reuse this result in trigger and body.
- `RecommendationSheet({onClose, children}: {onClose: () => void; children: ReactNode})` renders a native modal dialog with title/Close, children, backdrop/Escape close and focus restoration. Mount only while open; cleanup closes and restores page scroll. Native showModal supplies focus containment and background inertness; browser tests verify actual behavior.
- OptionComparison stores the open analysis identity (case ID plus analysis ID). Render only for the same current identity and valid recommendation; reset on identity change to prevent reappearance after navigating away/back.

- [x] Step 1: Write failing interaction tests using existing fixture factories. Assert one button only on the recommended option (also test a non-combined recommendation), no standalone explanation, no selection handler calls, correct dialog content, Close/Escape/backdrop behavior, and state reset on analysis/case changes. Test duplicate/conflicting/absent/blocked recommendation and missing predictions. Test retained report destinations and monetary values. Example assertion:

```tsx
await user.click(screen.getByRole("button", {name: /Click here to understand why/}));
expect(screen.getByRole("dialog", {name: "Why this response is recommended"})).toBeVisible();
expect(onSelect).not.toHaveBeenCalled();
await user.click(screen.getByRole("button", {name: "Close"}));
expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
```

- [x] Step 2: Run focused tests before implementation: `cd apps/web && npx vitest run src/components/RecommendationSheet.test.tsx src/components/InvestigationFlow.test.tsx`. Record expected missing action/layout failures, not unrelated test errors. If jsdom needs native-dialog shims, restrict them to the absent platform behavior and retain real browser coverage.
- [x] Step 3: Implement the defined files with the smallest solution. Native dialog uses `showModal()` in an effect, `onCancel` for Escape, and backdrop-only pointer interaction for dismissal; visible Close uses the same handler. Use `aria-labelledby`, initial focus on Close, restore prior focus, preserve previous body overflow style. Keep body separate from wrapper; use rankingReason for recorded stages, clearly distinguish policy from new AI analysis, and retain unavailable ranking details. CSS positions dialog right with bounded width, viewport height, independent scrolling and dimmed `::backdrop`; media query `(max-width: 639px)` sets width 100%. Do not add selection highlighting or enable approvals.
- [x] Step 4: Run focused tests then all `npm test` and `npm run build`. Resolve test expectations for the approved two-card decision tab and overlay content without weakening assertions. Self-review and commit only this task. Write full RED/GREEN evidence to `.superpowers/sdd/recommendation-sheet-task-1-report.md`.
- [x] Step 5: Independent task review of committed diff against binding spec; resolve Important/Critical findings and rerun covering tests before parent acceptance.

### Parent verification and handoff

- [x] Use the existing isolated fixture at `http://127.0.0.1:5190/.tmp/presenter-preview.html`. Inspect rendered DOM before authoring browser assertions. Run native dialog focus cycling, Escape/Close/backdrop dismissal, in-sheet click persistence, selection persistence, zero action/network effects, and scrolling at 1440px/390px. Check all other tabs still stack correctly and source/monetary displays persist.
- [x] Inspect screenshots of the trigger and open sheet, including the full-screen phone version. Fix real rendering issues through the reviewed implementation task.
- [x] Final review and fresh frontend test/build evidence; write verification note and progress ledger. Hand off the local preview with concrete click instructions, explicitly not deployed.

## Self-review

All approved content, safety, accessibility, failure-state, responsive, and source-data requirements map to Task 1 and parent browser acceptance. No new permission, backend, or reporting change. Existing uncommitted USD fixes must be checkpointed separately before the implementation baseline.
