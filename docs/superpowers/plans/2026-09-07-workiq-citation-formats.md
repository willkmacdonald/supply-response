# Work IQ citation-format correction

The user approved implementing the targeted link correction and verifying
retrieval/evidence before another deployment. This continues the approved
discovery/evidence design; no new permission, source, or deployment is implied.

## Design and boundaries

- Normalize Outlook OWA EWS-format ItemID values to REST IDs using Microsoft's
  Outlook conversion (`/` → `-`, `+` → `_`). Do not transform already-REST resource
  paths or complete missing identities from deployment configuration.
- Allow the observed UUID-valued `EntityRepresentationId` citation metadata on
  OWA links. Preserve duplicate-key, query allowlist, origin, traversal, and
  fragment rejection. Citation metadata never becomes message identity.
- Teams `contextType=chat` links are not complete channel locations. Keep them
  rejected, and clarify the existing topic-only question to request complete
  channel locations explicitly, excluding personal/group chats and search pages.
- Keep existing message/author/mailbox/team/source-text validation unchanged.
- Retain live answers only in operator process memory; synthetic fixtures only.

## Execution

- [x] Add failing parser/discovery tests for OWA metadata, EWS ID normalization,
  complete channel-location prompting, and chat-link rejection.
- [x] Update `integrations/workiq/locations.py` and `discovery.py` narrowly.
- [x] Exercise discovery → fetch → evidence with the new format in integration
  tests, including wrong-message/author/scope and malformed metadata cases.
- [x] Recheck retained in-memory live responses, then run a bounded Alex CLI
  discovery/fetch/validation check. Distinguish CLI proof from deployed OBO proof.
  Result: retained supplier links now parse. Fresh supplier parsed=1/scoped=1/
  matched=0; Quality parsed=0. No fetch; evidence gate remains blocked. Local
  bindings exactly match deployment. No new deployment.
- [x] Run relevant suites/static checks, record sanitized results and any blocker.
  Do not deploy unless both sources pass the pre-deployment evidence gate.
  Result: 124 targeted tests; 1,055 full regression tests passed, 14 skipped,
  existing dependency warning. Scoped Ruff/Pyright/package build passed.
  Independent review: no actionable findings, 84 tests passed. Source-identity
  and complete-channel discovery blockers recorded in the deployment result.

## Primary reference

Microsoft's published Outlook library, inspected 2026-09-07:
https://appsforoffice.microsoft.com/lib/1/hosted/outlook-web-16.01.js
`convertToRestId` maps slash to hyphen and plus to underscore; this is not generic
base64url encoding. Teams chat-link semantics:
https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/build-and-test/deep-link-teams

Self-review: no configured locator inputs, no Graph fallback, no chat-to-channel
reinterpretation, no policy relaxation, and no claim that parser success is
evidence or deployment acceptance.
