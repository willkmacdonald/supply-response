# Email-to-mitigation implementation evidence

## Scope and current boundary

The user approved the written workflow September 13, 2026. Work is on the
existing `codex/planner-experience` branch, in the isolated planner-experience
worktree. This record distinguishes completed local increments from the full
workflow and its eventual deployment. Website revision28 remains unchanged.

## Finance review lifecycle — locally accepted

Commits: `45a8553`, `449c3a2`, `e712a32`.

- Added immutable proposal-bound review models and pure submission, resolution
  and supersession policy, separately from existing standing authorization.
- Strictly greater than $20,000 requires Finance. Alex submits; Taylor resolves.
  Rejection requires a reason; approval may include an optional note.
- Changed proposals and terminal re-resolution are rejected. Supersession keeps
  earlier objects unchanged and retains reviewer metadata in the new snapshot.
- Timestamps, money representation, state shape and identifiers are validated.
- Independent review found textual UUID comparison could mistake equivalent
  identity spellings for different people. Fixed by comparing parsed UUIDs on
  both sides; two RED/GREEN regressions cover false acceptance and rejection.
- Independent re-review: spec compliant and quality approved, no remaining
  findings within this increment.

Final parent verification, after the identity fix:

```text
.venv/bin/python -m pytest tests/domain tests/auth tests/persistence/test_decision_outbox.py -o addopts='' -q
171 passed in 15.75s
```

The implementer also recorded 56 focused Finance lifecycle tests passing and
clean scoped Ruff/format/diff checks. Tests use fictional identity fixtures and
local storage; there were no tenant calls or real approval actions.

This lifecycle increment alone does **not** authenticate a Taylor browser session,
enforce a review at final Decision creation, or provide a Finance inbox. The
separate persistence increment below adds durable storage.
Identity snapshots remain inputs owned by the future authenticated service layer.

## Five-stage navigation — local browser verification passed

Implementation commit: `cacc412`. Existing frontend baseline: 326 tests across
22 files. New navigation tests first failed against the three-tab implementation.
Parent verification after implementation: 331 tests passed across 22 files;
TypeScript and Vite production build passed.

The local browser check passed at 1440px and 390px: five exact tab labels,
manual keyboard activation and wrapping, preserved selection, one visible panel,
hidden/inert inactive panels, visible email/Teams source links, explicit execution
prerequisites, no horizontal overflow and no operation requests from navigation.
An extended rerun also verified loaded Outlook/Teams icons, `$955,000` revenue,
`$328,000` margin, `$0` response cost, `$7.50` per component, and the recommendation
overlay's values, dismissal and focus return at both widths.
Screenshots are saved locally in `.artifacts/five-stage-navigation/`; the parent
visually inspected desktop approval and phone execution views. The check's first
post-change run used an obsolete exact approval-button label; the actual button
includes the selected option. Corrected that test locator before the passing run.

Independent review found no navigation-code defects. Its initial scope finding
concerned parent-owned documentation commit `676f6bb`, included because the review
package retained the original dispatch base `e712a32`. That documentation is
separately accounted for here. Reviewer acknowledgment: spec compliant and quality
approved, with no remaining findings.

Local preview data and source links are explicitly simulated; no live services
or real case mutations were used. The approval panel still represents the legacy
workflow until the independent Finance service/UI integration is implemented.

## Finance review persistence — locally accepted

Initial implementation commit: `5c939c7`. The implementer recorded 122 focused
tests passing; the parent broader domain/auth/persistence regression passed 237
tests in 16.50s. These passing suites did not establish complete acceptance.

Independent review required fixes for a mismatch between the hashed analysis
material and its outer response-option cost, incomplete immutable Case
provenance validation, and missing historical Case/Analysis/Decision migration
proof. The parent reproduced the cost mismatch in a disposable database: an
outer cost of $21,000 was accepted while the hashed material still said $24,750.
Correction `0f23db5` now rejects that mismatch and validates immutable Case
provenance. Additional fixes cover the migrated check-constraint name and
rereading all persisted review snapshots. The migration regression preserves
historical Case, Analysis and Decision raw payloads and hashes across upgrade
and downgrade. Parent rerun: 239 domain/auth/persistence tests passed in 16.48s;
the original disposable-database cost reproduction is now correctly rejected.
Independent re-review: spec compliant and quality approved, no remaining
findings. Concurrent-writer tests remain a separate increment in progress.

## Remaining gates

1. Durable append-only Finance review, idempotency and concurrency.
2. Versioned new-case policy, independent Taylor authentication and API access,
   current-proposal checks, and final Alex Decision enforcement.
3. Finance cross-session UI integration and final five-stage workflow verification.
4. Presenter-controlled Work IQ discovery of a new email from Will, exact
   case-specific source binding and duplicate-safe case creation.
5. Option-specific execution plans and an explicitly reviewed real email from
   Alex to Will, with safe uncertain-send handling.
6. Separate live consent/setup, SQL/native acceptance, deployment verification,
   and actual receipt of the authorized demo email by Will.

No live sending, consent, deployment, schema migration, case creation or decision
mutation has been performed by these local increments.
