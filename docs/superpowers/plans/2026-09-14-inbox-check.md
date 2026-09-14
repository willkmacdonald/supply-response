# Inbox check implementation plan

**Goal:** Make Check email for disruptions perform a real, presenter-controlled Work IQ mailbox search and show reviewable source messages.

**Architecture:** A read-only Work IQ port searches a bounded mail collection and retrieves each candidate. An Alex-only API exposes validated candidates. A React card shows checking, matches, empty, incomplete and error states. Existing case creation and historic evidence bindings are not modified by this increment.

**Tech Stack:** Existing Python Work IQ MCP/OBO client, FastAPI, React, Vitest, pytest.

## Constraints

- Supplier sender: will@willmacdonald.com; recipient: agent@willmacdonald.com.
- Require [Supply Response Demo], RL-001 and Supplier Alpha in the subject, RL-MAT-10247 in the actual inert body, and trusted sender/recipient metadata.
- No direct Graph discovery, fixed-message-ID substitution, timer, case creation, approval or mail sending on check.
- Show actual sender/subject/received time and validated Outlook citation. Never assert a newly received or unprocessed message without proof; use “Supplier Alpha email found”.
- At most 25 collection entries and five body reads, 120-second total timeout. Next links or excess candidates mean incomplete, never exhaustive empty. Do not follow unsupported pagination or untrusted URLs.
- This increment is check/review only. Creating a case from a fresh email remains gated on per-case source binding and atomic durable deduplication from the approved broader spec; do not route candidates into seeded showcase creation.
- Remove all three explanatory launcher caveats requested by Will. Keep old work under Other saved cases, not as the primary start action.

## Task 1 — bounded live discovery and retrieval

Files: integrations/workiq/inbox.py, integrations/workiq/mcp_evidence.py, tests/integration/test_workiq_inbox.py.
Public interfaces: InboxMessage(BaseModel) with message_id, subject, sender, received_at(datetime), excerpt, citation_url; InboxCheck(BaseModel) with checked_at(datetime), messages(list[InboxMessage]), incomplete(bool).
`discover_inbox(session, *, binding: SourceBinding, checked_at: datetime) -> InboxCheck` consumes the existing fetch session. `WorkIQMcpEvidencePort.check_inbox(*, actor: AuthenticatedActor, checked_at: datetime) -> InboxCheck` owns tenant/Alex check, OBO and bounded session.
- [ ] Write failing tests for no matches, new non-seed ID, multiple candidates, wrong sender/recipient/marker/body/reference, invalid citation, unsafe HTML, truncation and transport failure.
- [ ] Implement using existing location parser and fetched-message validator with a per-candidate copied binding; never alter the configured historic binding.
- [ ] Run `.venv/bin/pytest tests/integration/test_workiq_inbox.py tests/integration/test_workiq_mcp_evidence.py -q` and review.

## Task 2 — authenticated API and visible presenter card

Files: dependencies.py, main.py, routes/inbox.py, tests/api/test_inbox.py; apps/web/src/components/InboxCheck.tsx and .test.tsx, api.ts, App.tsx, CaseHeader.tsx, styles.css.
POST /api/inbox/check with empty body only, Alex planner auth and no-cache response. Uses services.inbox_service.check_inbox(actor=actor, checked_at=services.clock()). Returns InboxCheck. Disabled/fallback returns 503 INBOX_CHECK_UNAVAILABLE; transport/validation returns 503 INBOX_CHECK_FAILED, no raw errors.
- [ ] Write failing API tests for fallback unavailable, actor requirement, delegated forwarding and safe failures.
- [ ] Write failing React tests: no automatic check, explicit click calls checkInbox once, pending lock, result preview/link, empty/incomplete distinction, retry after error, no case calls.
- [ ] Connect live-mode primary Outlook-icon Check email for disruptions; keep saved-case list collapsed and make prior resume secondary inside it. Remove header new-case action in live mode so it cannot bypass the email flow accidentally; retain fallback creation for tests.
- [ ] Run API/integration tests and all web tests/build; inspect browser desktop/mobile.

## Task 3 — review, live proof and release

- [ ] Review full increment against constraints and publish via existing approved Azure target after validation.
- [ ] Verify actual Alex browser check. No matched marked message is a valid observed empty result, not proof of successful new-mail retrieval. Ask Will to send a marked message if none exists; do not send one on his behalf or use the seed.
- [ ] Record exactly what works and what remains gated in README/ROADMAP/CONTEXT.
