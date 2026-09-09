# Report card links task 1 report

## Outcome

Mounted fail-closed, exact saved-analysis Power BI destinations on the case header, validated stock and customer-order cards, saved Fabric supporting records, option comparison, and recommendation. Existing source links, inline record details, footers, decision controls, and callbacks remain intact. The case-header link now has a scoped readable color and unavailable live reporting is described truthfully.

## TDD evidence

- RED: `cd apps/web && npx vitest run src/components/reportCardLinks.test.tsx`
  - Result: exit 1; 12 tests ran, 10 failed and 2 passed.
  - Expected failures covered missing exact destinations, the stale generic header link/release gate, and incorrect live-unavailable wording.
- Focused GREEN: `cd apps/web && npx vitest run src/components/reportCardLinks.test.tsx`
  - Result: exit 0; 1 file passed, 12 tests passed.
- Full suite, first run: `cd apps/web && npm test`
  - Result: exit 1; 203 tests passed and 1 obsolete `LiveSafety.test.tsx` header expectation failed.
- First build: `cd apps/web && npm run build`
  - Result: exit 1; TypeScript reported the same obsolete test omitted the newly required `analysis` prop.
- Scope amendment: controller authorized a narrow update to that obsolete header safety test. It now uses a canonical report URL, the `saved-analysis-v1` contract, a valid live case, `analysis={null}`, the exact case-filtered destination and new label, and verifies that removing the case removes the report anchor. All unrelated safety tests were preserved.
- Full GREEN: `cd apps/web && npm test`
  - Result: exit 0; 15 files passed, 204 tests passed.
- Production build: `cd apps/web && npm run build`
  - Result: exit 0; TypeScript and Vite completed, 190 modules transformed.

## Controller browser evidence

The controller independently reported all 12 local browser variants passing across 1440 px and 390 px widths for live-mock, fallback, legacy, malformed, zero-stock, and missing-time cases. Checks covered exact eight-or-zero report anchors, independent identity encoding, preserved sources, keyboard disclosures, header contrast/focus, no requests, no horizontal overflow, and no browser errors. Desktop and mobile response-row screenshots were inspected and the helper stopped cleanly.

## Remaining acceptance limits

The browser exercise used mocked local data and is not live Power BI acceptance. This task did not deploy, authenticate, probe report availability, refresh data, navigate a live report, or validate the report artifact and release contract in a deployed environment. The links remain hidden unless runtime explicitly exposes the usable `saved-analysis-v1` contract and a canonical Power BI base URL.
