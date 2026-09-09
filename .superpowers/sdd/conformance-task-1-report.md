# Task 1 conformance report: business-first cards and bottom source footers

Date: 2026-09-09

Branch: `codex/planner-experience`

Base: `d1f7227`

## Outcome

Task 1 now presents the planner's evidence and recommendation cards in business language while preserving the saved analysis, source records, evidence validation, trusted navigation, and approval/execution gates. Source status remains the final child of source-bearing cards and is covered by rendered desktop and mobile bounds checks.

The reported source-pill-at-top defect did not reproduce in the local implementation or in the isolated rendered fixtures. The existing footer layout already places `.source-footers` at the bottom of the card. No CSS change or unverified root-cause claim was made; the new browser regression proves the actual element order and bounds instead.

## Spec decisions implemented

- The disruption card leads with the original 8,000-unit delivery, due date, part, and plant. It does not treat the saved partial disruption fields as a receipt or expedite, and does not subtract them from the original affected quantity. Those raw fields remain available in closed source details.
- The recovery card identifies the 3,000-unit shipment and its date as a proposed response under review, keeps the supplier statement separate from the shipment record, and derives the recorded per-unit incremental cost without implying approval.
- A missing `disruption.recovery_date` is shown as `No date recorded for full recovery`, preserving the distinction between missing data and an unconfirmed source statement.
- Inventory arithmetic is unchanged. The storage/provenance explanation is condensed into the card footer.
- Recommendation actions and saved predictions appear before the closed `How the options were compared` details. Raw thresholds and retained/eliminated identifiers remain in that detail. Mixed assumptions are labeled `Assumptions and unresolved questions`.
- `No option meets the planning requirements` remains distinct from `Recommendation unavailable for this analysis`.
- Evidence status keeps its existing boolean and binding logic. Passed authoritative sources say `Required checks passed`; contextual sources say `Context only — not authoritative evidence`; failures and missing checks remain conspicuous. Fixture provenance uses `Demo data` and `Sample data — not a live retrieval`.
- Runtime configuration says `Live-service mode`, which does not claim continuous checking.
- Exact navigation labels remain `Explore in Power BI` and `Review with AI assistance`. Existing trusted URL construction and navigation availability gates are unchanged.
- Missing disruption, inventory, shipment, transfer, qualification, prediction, and recommendation paths use plain missing-record language. Explicit snapshot/source-detail labels remain precise.

## TDD record

The required first RED command was:

```text
npm --prefix apps/web test -- --run src/components/InvestigationEvidence.test.tsx
```

The package test script runs the complete Vitest source suite. The initial RED was expected: 1 failed and 225 passed because the first card still rendered `Saved disruption` and `Recorded partial supply`. After the minimal first-card correction, the same command was GREEN at 226/226.

Further focused RED/GREEN cycles covered:

- Recovery and recommendation narrative: expected RED 2 failed / 225 passed, then GREEN 227/227.
- Header, routes, missing-data copy, and evidence status: expected RED 8 failed / 219 passed, then GREEN.
- Source labels, no-feasible recommendation, and warning copy: expected RED 4 failed / 224 passed, then GREEN.
- Fallback record provenance: expected RED 1 failed / 228 passed, then GREEN 229/229.
- Presentation browser test: the first run exposed an overly broad test locator matching four `Demo corpus` elements. Narrowing the assertion to the intended card retained the bounds coverage; no product defect was inferred from that test-only failure.

## Final verification

- `npm --prefix apps/web test`: PASS — 16 files, 229 tests.
- `npm --prefix apps/web run build`: PASS — TypeScript build and Vite production bundle, 191 modules.
- `npm --prefix apps/web run test:e2e -- planner-presentation.spec.ts --project=fallback`: PASS — 2/2 Playwright cases (desktop 1440×1000 and mobile 390×844).
- `git diff --check`: PASS.

The Playwright fixture starts only the repository's isolated fallback API and Vite server, intercepts the local endpoints, and supplies source-bearing presentation data from the checked-in demo corpus. It does not enable the live project, mutate external systems, or make an external service claim.

The browser test verifies that each `.source-footers` group is the card's final child, each badge is inside a footer, footer bounds are below titles/content/links and expanded record details, both Work IQ and Microsoft Fabric variants render, and the page has no horizontal overflow.

## Rendered evidence

Full pages:

- `.artifacts/planner-presentation/desktop.png`
- `.artifacts/planner-presentation/mobile.png`

Readable card/row captures:

- `.artifacts/planner-presentation/desktop-understand-row.png`
- `.artifacts/planner-presentation/mobile-understand-row.png`
- `.artifacts/planner-presentation/desktop-original-delivery-card.png`
- `.artifacts/planner-presentation/mobile-original-delivery-card.png`
- `.artifacts/planner-presentation/desktop-recovery-card.png`
- `.artifacts/planner-presentation/mobile-recovery-card.png`
- `.artifacts/planner-presentation/desktop-qualification-card.png`
- `.artifacts/planner-presentation/mobile-qualification-card.png`

Direct inspection of the final desktop understand row, desktop recovery card, and mobile qualification card confirmed the source status at the bottom, including after shipment and qualification record details were expanded.

## Scope and self-review

- No changes were made to `DecisionPanel`, `ExecutionPanel`, `OutcomePanel`, API/hooks, Power BI, domain contracts, or analysis persistence.
- No input object is mutated during rendering; the existing immutability assertion remains and was extended around the edited fixture setup.
- No source text, evidence item, validation requirement, source-link trust check, report URL construction, or approval/execution gate was removed.
- No deployment, push, live-project access, or external mutation was performed.

## Remaining concern

The user-observed live/current-tab top-pill placement could not be inspected because live UI access was unavailable. The local source tree and isolated final rendering both place the status at the bottom, so the report deliberately does not assert a live root cause. The rendered regression test will catch a future local ordering or bounds regression.
