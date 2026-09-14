# Reviewed supplier email → case → analysis

> Execute the already-approved presenter-controlled inbound design. Work in the existing `codex/planner-experience` worktree. Review delegated implementation before deployment.

## Outcome and constraints

The presenter checks email, reviews the actual message and identified facts, explicitly creates its case, and runs the existing analysis against that email. No automatic approval or email sending. No fixed seed email substitution. Preserve old cases. Fabric remains authoritative for operational values. Missing/conflicting facts block creation visibly. Repeated/concurrent creates return the same case.

Use tenant + Alex mailbox object ID + Internet Message-ID as an email-level identity only if live Work IQ retrieval and same-mailbox folder-move tests establish the supported behavior. This is not Graph's immutable item ID: duplicate physical copies of the same email represent one inbound event; inconsistent copies are rejected. Keep this release gated on that proof. Do not add Graph discovery or permissions. Prior research's stricter immutable-item requirement is not a replacement for the approved spec's stable-mailbox-message acceptance test.

The existing transactional case primary key is the atomic claim: derive `RL-INBOUND-` plus SHA-256 of the scoped identity. Persist the complete source binding in existing immutable case JSON. No new SQL database/table or migration is needed. Do not base the identity on subject, time, or body hash. Use a separate fingerprint to detect content changes, not to create another case. For this bounded release, multiple physical matches block as ambiguous, even if they might be equivalent; they never create separate cases.

## Task 1: Backend source-bound case journey

Own Python runtime and tests only. Add `data/domain/inbound.py` with immutable `SupplierEmailSource` and parsed `SupplierDisruptionFacts`. Persist source as optional `CaseInstance.supplier_email`; omit it from legacy serialization when absent. Enforce binding immutability in validated model copies and case projection integrity.

Extend `InboxMessage` with nullable/defaulted `internet_message_id`, `review_fingerprint`, `facts`, and `creation_blocker`. Existing callers remain compatible. Discovery returns reviewed facts from the actual inert body. A bounded RL-001 parser supports the message Will actually sent (supplier cannot deliver quantity/component at Chicago on date; partial shipment quantity by air/date/additional USD per unit; remaining quantity without confirmed date). Parse quantities/dates/cost from source, require one coherent set, no ambiguous or contradictory relevant statements. No requirement for `DEMO CORPUS` or an imperative closing sentence. Clear blocker for unsupported wording or missing identity. Facts are checked against the Fabric snapshot at creation and again at analysis: original quantity/date/part/plant, partial option quantity/date/cost, remainder, recovery uncertainty. Never overwrite Fabric values to make a conflict pass.

Work IQ port method `review_inbound_email(actor, internet_message_id, review_fingerprint, checked_at)` re-fetches a bounded collection filtered by escaped Internet Message-ID, validates actual sender/recipient/markers, fetches actual entities, checks identity and fingerprint; reject incomplete/ambiguous/conflicting copies. Return full validated SupplierEmailSource. A helper for analysis retrieves the same bound email through Work IQ and produces normal validated supplier evidence/lineage using the current locator. Preserve existing seeded supplier retrieval for cases without a source binding.

POST `/api/inbox/cases`, planner-authenticated and live-only, request exactly `{internet_message_id, review_fingerprint}`. Re-fetch before trusting; never accept caller-supplied facts/body/sender. Derive case ID from authenticated scope and validated identity. Existing matching case returns `case_response`; different fingerprint for same identity returns HTTP409. Retrieve Fabric, validate extracted facts, create independent-finance case when enabled with immutable binding using normal transaction. On concurrent primary-key conflict, load/validate/return winner. A failed creation leaves no orphan. Do not run analysis inside create; existing Analyze action remains explicit.

Return meaningful constant error codes (missing/changed/unsupported/conflicting source) without raw provider exceptions. Use no-store. Add tests first for parser, malicious text, missing facts, identity lookup/escaping/copies/move locators, API auth/tamper/conflict/retry/concurrency, persistence immutability and legacy serialization, live analysis dynamically using bound email and never fixed seed fallback. Keep tests scoped while iterating, then run relevant integration suites once. Report `.tmp/email-case-backend-report.md`, commit only owned files, no deployment.

## Task 2: Presenter interaction (parent)

Extend types/API for the optional review fields and create request. Review disruption expands actual excerpt plus clearly labeled extracted original delivery/partial offer/remaining uncertainty. Include explicit Create case from this email only when review identity/facts permit; show clear blocker otherwise. Pending state immediately says Creating disruption case…; disable repeat clicks and other workspace actions. On success reopen returned case via existing workspace hook; show existing Analyze disruption action. Failed request retains reviewed email and offers retry. Older read-only fixtures still render safely. Tests first for request shape, visible progress, success handoff, blocked source, errors, double-click prevention. Desktop/mobile browser proof.

## Task 3: Integrated review and live acceptance

Review combined diff for exact-source continuity, legacy preservation, atomic dedup, and visible user journey. Resolve Important findings together. Run Python integration, web tests/build and release checks. Verify actual Work IQ Internet Message-ID/filter plus same-mailbox folder move/retrieval before activation; restore moved demo email if a temporary move is performed. Deploy only with that proof and passing checks using existing approved Azure workflow. Create from Will's 0914-A message, analyze, verify actual citation/new source, and repeated creation reopens one case. Record what was proved; no claims about remaining execution/outbound email.

## Progress

- Baseline: f4b1de8; deployed read-only inbox source 736c339.
- Backend implementation and tests delegated; parent presenter implementation complete locally.
- 360 web tests and production build pass. Desktop/mobile actual-component browser proof passes with explicitly simulated API responses. Actual sender/subject/received time included in case source details.
- Work IQ metadata identity/filter verified before and after Inbox → Archive → Inbox; ordinary locator changed, Internet Message-ID remained identical. Demo email restored to Inbox.
- User explicitly approved actual body/Outlook link retrieval, saving this email into its case, and analysis. Final independent review passed; revision33/source974d4a1 deployed. Real browser creation, bound analysis, exact Outlook citation and repeat-create same-case/same-analysis acceptance passed. See docs/reviews/2026-09-14-email-to-case-release.md. No mail send or Finance action.
