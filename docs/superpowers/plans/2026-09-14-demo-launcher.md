# Demo launcher implementation plan

**Goal:** Replace the long default case list with a clear entry to the user-approved verified demo.

**Architecture:** ExistingCases takes an optional featured case ID; App supplies the approved live-demo case only in live mode. Resume uses the existing authorized reopen handler. Older cases stay in a collapsed native disclosure. CaseHeader labels new showcase creation honestly.

**Tech Stack:** React, TypeScript, native details, Vitest, browser verification.

## Approved design and constraints

- Resume the analyzed disruption: Supplier Alpha delay; email and analysis are already saved, not a new inbound-email trigger.
- Exact featured case: RL-CASE-bcbb8740-c770-42fd-aa67-981d08b66383. Do not select an arbitrary newest test case.
- Other saved cases collapsed by default. Preserve all records and server authorization; no deletions.
- Start a new demo remains separate and explicitly creates a showcase case, not a fresh-email trigger.
- Retain busy/error handling, existing-case GET-only behavior and all approval boundaries.

## Single cohesive task

- [x] Add and run failing ExistingCases interaction tests for featured resume, collapsed older cases and operation locks.
- [x] Update ExistingCases, App wiring, CaseHeader copy and localized styling.
- [x] Update existing UI test selectors for the renamed button and disclosure; run `npm test` and `npm run build` (351 tests pass).
- [x] Verify responsive browser rendering and exact case navigation; review the diff (1440px/390px checks pass; independent review clear).
- [ ] Validate and deploy to the existing Azure target, then verify the live launcher without creating or deleting cases.
