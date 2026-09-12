# Presenter stage tabs implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development and test-driven-development, with review between tasks.

**Goal:** Build the approved presenter-oriented header, three local stage tabs with stacked cards, and recognizable source-action icons.

**Architecture:** Keep current data/state ownership. CaseHeader owns presentation copy; InvestigationFlow owns local tab selection with mounted hidden panels; EvidenceSource renders decorative product icons only beside its existing validated source links. No new data layer.

**Tech Stack:** React, TypeScript, Vitest, Playwright, existing Vite app.

## Global constraints

- Binding spec: `docs/superpowers/specs/2026-09-12-presenter-header-and-stage-tabs-design.md` (written spec approved by user).
- No backend, schema, synthetic-data, calculations, source URL, reporting view, Microsoft permissions, authentication, or approval behavior changes.
- Keep source notes and platform/retrieval/validation footers at the bottom of each card. Do not promote platform branding above the business question.
- Switching tabs must not fetch sources, create an analysis, change the case/analysis URL, reset the selected option or decision form, submit an approval, or replay an operation.
- Preserve mounted card state while hiding inactive panels and excluding their controls from focus and the accessibility tree.
- Keep actual errors, required-source warnings, and analysis-level provenance visible outside hidden panels.
- No live data writes, Git push, merge, or deployment by implementers. Parent owns browser acceptance and release decisions.

## Task 1: Presenter header and accessible stage panels

**Files:** modify `apps/web/src/components/CaseHeader.tsx`, `InvestigationFlow.tsx`, `apps/web/src/styles.css`; create `CaseHeader.test.tsx` if useful; update `InvestigationFlow.test.tsx`, `LiveSafety.test.tsx`, and affected existing tests. A small local `InvestigationTabs.tsx` is allowed if it makes state/keyboard responsibilities clearer.

**Interfaces:** Consume existing CaseHeaderProps and CaseWorkspaceState unchanged. Keep current InvestigationEvidence, OptionComparison, ExposurePanel and DecisionPanel props unchanged.

- [ ] Add failing assertions for the approved header copy in live/fallback/null-runtime states. Exact strings:

```ts
expect(screen.getByRole('heading', {level: 1})).toHaveTextContent('Respond to supply disruptions with AI');
expect(screen.getByText('AI brings together supplier messages, inventory, and customer orders to assess the impact of a delay, compare recovery options, and support the planner\'s decision.')).toBeVisible();
```

Mode strings are `Fictional scenario · Uses live Microsoft services`, `Fictional scenario · Uses predefined sample data`, and `Fictional scenario · Service mode not yet available`. Eyebrow is `RL-001 · Supply Disruption Response`. Preserve existing controls and report URLs.

- [ ] Extend the existing `state()` fixture tests to assert only the first three headings are visible initially; switching to each tab reveals exactly its three existing cards, with others hidden. Assert all stage labels match the spec. Tests must click the decision tab before querying its controls. Retain original business assertions rather than replacing them with snapshots.

```ts
const user = userEvent.setup();
render(<InvestigationFlow state={state()} />);
expect(screen.getAllByRole('heading', {level: 3})).toHaveLength(3);
await user.click(screen.getByRole('tab', {name: '3. Make the decision'}));
expect(screen.getByRole('region', {name: 'Review and approve.'})).toBeVisible();
```

- [ ] Run `npm test -- --run` from apps/web; record intended RED for new missing behavior. Build tabs with local React state and stable IDs, role=tablist/tab/tabpanel, aria-selected, aria-controls/labelledby, and roving tabIndex. ArrowLeft/Right and Home/End move focus; Enter/Space selects via native button click. Use manual activation so keyboard focus alone does not switch panels.

```tsx
<section role="tabpanel" aria-labelledby={tabId} id={panelId}
  hidden={!active} inert={!active} tabIndex={0}>
  {children}
</section>
```

Keep all panels mounted. A case-keyed inner presentation component can reset only tab state when case identity changes. Do not place hooks after conditional returns. Preserve selection across same-case rerenders/operation completion. Add tests for this, for keyboard focus/activation/wrapping, and for rejection input surviving a tab round trip. Assert operation callbacks untouched by tab navigation, no fetch, and unchanged location.

- [ ] Replace only scoped layout rules: one-column cards at every width, align-items:start, content-height spacing, restrained paragraph width, full-width tab row with readable wrapping at 390px. Explicit `.investigation-panel[hidden] { display: none; }` prevents grid/flex CSS overriding native hidden. Header title should have sufficient width for readable lines; put mode line after controls at bottom. Keep warnings and analysis context outside panels. Do not create nested scroll containers.
- [ ] Run focused tests while iterating, then full frontend suite and `npm run build` once stable. Record RED/GREEN and commit only Task 1 files. Independent review is required before Task 2.

## Task 2: Source-action product icons and consistent details

**Files:** modify `apps/web/src/components/EvidenceSource.tsx` and scoped `styles.css`; create small `SourceActionIcon.tsx`, local Outlook/Teams vector assets and provenance README, and `EvidenceSource.test.tsx` if no direct tests exist. Inspect source-detail placement in InvestigationEvidence and change only genuine inconsistencies while preserving derived-card explanations.

**Interfaces:** Keep EvidenceSource props and trustedServerCitation filtering unchanged. SourceActionIcon accepts `product: 'outlook' | 'teams'`; renders a local image with alt empty and aria-hidden. No icon for other/missing/untrusted links.

- [ ] Verify actual Microsoft product assets and usage guidance; parent supplies research while Task 1 executes. Store unmodified assets locally using apply_patch and record source URL/date/terms. Never silently substitute generated logos. This step is blocked only if suitable assets cannot be verified.
- [ ] Add RED tests using actual EvidenceSource and live validated fixtures: Outlook and Teams links retain exact href/target/rel and accessible text, have decorative correctly selected icons; absent/untrusted URLs have no link/icon; fallback remains non-live; generic validated destinations are not mislabeled. Preserve existing Source details and excerpt behavior.
- [ ] Implement only after RED:

```tsx
export function SourceActionIcon({product}: {product: 'outlook' | 'teams'}) {
  return <img className="source-action-icon" src={product === 'outlook' ? outlookIcon : teamsIcon}
    width={24} height={24} alt="" aria-hidden="true" />;
}
```

Imports refer to the verified local SVG files. Select product only after existing citation validation, from exact destination hostname plus the existing authority criteria used by citationLabel. Keep adjacent descriptive text. Scope link styling as inline-flex, aligned center, gap, with flexible wrapping, visible focus and retained underline.
- [ ] Audit the three source-bearing response cards and initial supplier card: source identity, excerpt/details, action, footer remain in predictable lower-card order. Preserve missing-source notices; no fake links or made-up detail sections on derived cards.
- [ ] Run focused source-link tests, full frontend tests, build, diff check. Record RED/GREEN and commit scoped files. Independent review and final integrated review follow.

## Parent acceptance and handoff

- [ ] Inspect actual rendered DOM, then capture all three stages at desktop and 390px mobile using a controlled fixture with valid saved analysis data. Use existing local browser tooling; do not create live cases for screenshots.
- [ ] Check keyboard behavior, mounted state, no navigation/network side effects on tab changes, footer placement, icon appearance and exact source links. Inspect images rather than relying solely on DOM assertions.
- [ ] Review combined change for interactions and spec coverage, resolve findings, run fresh full frontend suite/build.
- [ ] Show the built result in a functioning local browser preview (not a file:// TSX fixture) and provide proof. Do not label it deployed until existing Azure release gates have been executed.

## Progress

Spec approved. Existing isolated worktree `codex/planner-experience`; baseline `ab62899`. No plan conflicts found. Task 1 pending; Task 2 pending; visual/final acceptance pending.
