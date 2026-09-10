# Business comparison conformance correction

Date: 2026-09-09

Base: `38b1ca2`

## Outcome

The recommendation card now compares the unique recorded do-nothing prediction with the recorded recommended-option prediction before the closed ranking details. It presents the existing values from doing nothing to taking the response for parts still needed, service-target exposure, revenue at risk, margin at risk, and response cost. It does not calculate monetary deltas, rerank options, or infer a recommendation reason from an identifier tie-break.

The comparison is shown only when exactly one `no_mitigation` option and both valid predictions are present. Missing, duplicate, malformed, and absent prediction states state why the comparison is unavailable and retain the existing recommended prediction summary. When all five displayed measures are equal, the card says that the shown values are unchanged and makes no benefit claim.

The customer-order-line wording and denominators are used only when the existing snapshot linkage and percentage-consistency guard validates both predictions against the same customer-line total. Otherwise the card uses the established `Production orders expected to miss the on-time, in-full target` fallback.
The comparison retains the validated component identity and the existing explanation of whether revenue/service exposure has a customer-line or production-order calculation basis.

The option details now explain the existing execution score as a weighted coordination-factor comparison: an unconfirmed external commitment contributes 2 points; a cross-plant movement, schedule change, and each coordinated action after the first contribute 1 point each. This wording is based on `services/analysis/options.py`; `services/analysis/ranking.py` confirms lower is better. The UI does not recompute the score and explicitly says it is not a probability of failure.

## TDD record

Initial focused RED:

```text
npm --prefix apps/web test -- --run src/components/InvestigationFlow.test.tsx
```

- Expected result: 4 failed, 242 passed. The missing populated comparison, absent/duplicate/invalid baseline states, tied-result language, and execution-score explanation were all observed failing before implementation.
- First GREEN: 246/246.

Review-refinement RED:

- Expected result: 3 failed, 243 passed. The failures captured plain-language copy, the malformed `undefined` prediction crash, removal of duplicate recommendation metrics, inclusion of margin, and tie wording limited to the measures actually shown.
- Refined GREEN: 246/246.
- A final terminology RED was 1 failed / 245 passed before naming the value `Execution coordination comparison score`; the focused suite returned to 246/246 after the copy change.
- A final basis-copy RED was 2 failed / 244 passed before restoring the validated part ID, production-order fallback heading, and revenue/service basis explanation; the suite returned to 246/246.

## Final verification

- `npm --prefix apps/web test`: PASS — 18 files, 246 tests.
- `npm --prefix apps/web run build`: PASS — TypeScript and Vite production build, 192 modules.
- `npm --prefix apps/web run test:e2e -- planner-presentation.spec.ts --project=fallback`: PASS — 2/2 isolated desktop/mobile cases.
- `git diff --check`: PASS for the correction files and report.
- Refreshed render evidence: `.artifacts/planner-presentation/desktop-recommendation-card.png`, `.artifacts/planner-presentation/mobile-recommendation-card.png`, `.artifacts/planner-presentation/desktop.png`, and `.artifacts/planner-presentation/mobile.png`.

## Scope and limitations

- Changed only `ExposurePanel`, `OptionComparison`, their existing investigation-flow presentation tests, the small `PredictionComparison` presentation helper, and the existing isolated presentation test for order assertions and card captures.
- The parent-owned modified plan and untracked review document were not edited or staged.
- No backend values, numeric sources, ranking stages, identifiers, approval gates, source footers, styles, APIs, hooks, Power BI artifacts, or external systems were changed.
- The comparison intentionally does not characterize why the ranking selected the option. Exact ranking stages remain under `How the options were compared`.
- A score alone cannot reveal which coordination factors contributed to it, so the UI explains the frozen weights without claiming a per-option factor breakdown.
- The existing Vite bundle-size advisory remains informational; the build succeeds.
