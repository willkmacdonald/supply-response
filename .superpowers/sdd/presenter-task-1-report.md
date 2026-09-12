# Presenter Task 1 report

## Scope

Implemented the approved presenter header and accessible, manually activated investigation stage tabs. No source/footer markup, business callbacks, URLs, backend behavior, or icon work was changed.

## TDD evidence

### RED

Command:

`npm test -- --run src/components/CaseHeader.test.tsx src/components/InvestigationFlow.test.tsx`

Result against the untouched implementation: 7 intended failures and 303 existing passes. The failures showed the old header copy and the absence of tab roles/staged visibility, keyboard behavior, case reset, and decision-form round-trip behavior.

### GREEN

Focused command:

`npx vitest run src/components/CaseHeader.test.tsx src/components/InvestigationFlow.test.tsx`

Result: 2 files passed, 12 tests passed.

Affected integration/source-link command:

`npx vitest run src/components/reportCardLinks.test.tsx src/App.test.tsx src/components/LiveSafety.test.tsx`

Result: 3 files passed, 86 tests passed.

### Final verification

Commands:

`npm test -- --run`

`npm run build`

Result: 20 files passed, 310 tests passed; TypeScript and Vite production build completed successfully. An earlier build run caught an invalid test-fixture operation literal; it was corrected to the real `analyzing` operation and both commands were rerun successfully.

## Self-review

- Header uses the exact approved eyebrow, title, supporting paragraph, and all three mode lines. The legacy mode badge was removed; existing controls, case details, scenario time, report link, and availability messages remain.
- Header is single-column at desktop widths, with a wider readable title/intro and the quiet mode line last.
- Exactly three tabs use stable tab/panel IDs, `tablist`/`tab`/`tabpanel`, `aria-selected`, `aria-controls`, `aria-labelledby`, and roving `tabIndex`.
- Arrow Left/Right wrap; Home/End move focus. Focus does not select; native Enter/Space button activation selects.
- Panels stay mounted and inactive panels use `hidden` plus `inert`; explicit CSS preserves native hidden behavior.
- The case-keyed inner presentation resets only tab state for a different case and preserves the selected tab across same-case rerenders/operations.
- Tests cover three-card visibility and order per stage, keyboard behavior, form-state preservation, no operation callbacks, no fetch, unchanged location, and existing business/link behavior.
- Cards are a single full-width, content-height column at every width, with restrained paragraph measure/rhythm and mobile-wrapping tabs. No nested scrolling was introduced.

## Follow-up boundary

Independent review and browser proof remain the parent task's next gate. Outlook/Teams icon work belongs to the later task and is intentionally absent here.

## Independent-review correction

The Task 1 reviewer found that keyboard focus moved correctly but the roving `tabIndex=0` remained tied to the selected tab. A new RED assertion demonstrated the mismatch (`[0, -1, -1]` received after ArrowLeft instead of `[-1, -1, 0]`). The implementation now tracks focused and active stages independently: focus-only navigation moves the sole `tabIndex=0` without selecting a panel, while click and native Enter/Space activation update selection.

Covering GREEN verification:

`npx vitest run src/components/InvestigationFlow.test.tsx && npm run build`

Result: 1 file passed, 9 tests passed; TypeScript and Vite production build completed successfully.
