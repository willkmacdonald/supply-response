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
findings.

Concurrent-writer increment: `8250316`, corrected by `cba711a`. Three portable
two-connection tests force both writers to read pending revision 1 before either
can append. They verify a single winner for competing decisions, exact replay
for identical requests, conflict for reused keys with different requests, and
exactly two persisted rows without losing-transaction residue. Review identified
an unbounded test barrier; the correction adds a five-second timeout and leaves
synchronization failure visible. Independent re-review: spec compliant and
quality approved. Parent final focused run: 3 passed, 22 deselected in 0.30s.
Implementer non-live regression: 117 passed, 12 deselected; Ruff and Pyright clean.
Native Fabric contention remains unverified and requires its separate gate.

## Explicit case policy — locally accepted

Commit `f449d7f` adds an opt-in independent Finance policy. Existing case-creation
routes remain on the legacy policy until authenticated Finance integration is
ready. New-policy analysis excludes Taylor's standing authorization and retains
other prerequisites. Persistence rejects mismatched case/projection/analysis
policies, including attempts to inject legacy Finance evidence into new cases.

The parent froze full legacy Case, projection, Analysis, ApprovalTarget, Decision,
command and operational snapshot JSON before model changes. Nineteen new tests
verify exact serialization, nested nulls, unchanged hashes, actual recomputation,
negative policy cases and reopening records from a migration-created database.
Independent reviewer confirmed the golden fixture matches the original patch.
Spec and quality review: approved, no Critical or Important findings. Parent
confirmed save/get provenance call sites as the review's cross-hunk check.

Final parent regression on the committed snapshot: 290 passed, 12 deselected in
4.57s. Existing Starlette/httpx deprecation warning remains. Unfiltered scoped
Ruff reports inherited FURB157/UP047 findings; the run excluding those two rules
passes and Pyright reports no errors. The global commit hook attempted unrelated
Decimal rewrites and then blocked on the existing generic-style finding. Those
rewrites were reverted; the implementer disclosed using the hook bypass after
manual checks. Original Decimal spelling and canonical values remain unchanged.
These baseline tooling issues are tracked separately, not claimed fixed.

## Current proposal selection — locally accepted

Initial implementation `1ae88d4` was not accepted despite 130 tests passing.
Independent review found that a historical analysis could be published as the
current selection using a newer token, and that the proposal guard could advance
legacy cases. It also identified missing negative, concurrency and migration
acceptance coverage. The parent's broader run exposed an older migration test
that incorrectly used current repositories to seed a predecessor schema.

Correction `42ee347` adds the analysis-pair and policy guards with RED/GREEN
regressions, restores the historical test through reflected predecessor seeding,
and adds the required replay, rollback, lineage, threshold, migration and adapter
concurrency tests. The populated 0007-to-0008 upgrade/downgrade/re-upgrade test
preserves frozen raw payloads, indexes and foreign keys; native Fabric behavior
is still not established by these local tests or compiled SQL assertions.

Fresh parent verification on the committed correction:

```text
uv run pytest tests/domain tests/finance tests/auth tests/persistence tests/integration/test_store_contract.py tests/api/test_case_lifecycle.py -q -m 'not fabric_live' -o addopts=''
312 passed, 15 deselected, 1 existing Starlette/httpx warning in 18.85s
```

Independent re-review also required stricter race-error classification, a
high-cost backward-clock rollback test and complete compiled CAS predicate
assertions. The final correction includes all three. Final verdict at
`42ee347`: spec compliant and quality approved, with no remaining Critical or
Important findings. The intermediate review snapshot `6ebb0c1` was amended into
this final correction; the original base remains `e0f6f4f`.

This storage acceptance does not expose Taylor's review actions, activate the
new workflow or authorize deployment.

## Submission and review commands — locally accepted

Initial implementation `73f59d5` checks the exact configured Alex/Taylor identity
before persistence access, uses evaluated cost rather than caller-provided cost,
and commits each submission or review atomically. Repeating the original command
returns its original recorded result, even after a later review or selection.
Current status is intentionally a separate query, not a rewritten command receipt.

The parent's fresh initial regression passed 343 tests (15 live tests excluded).
Independent review found no production defect but required an existing-receipt
unauthorized replay test before acceptance. It also identified bounded test typing
cleanup and a baseline-option coverage claim that needed correction. Test-only
correction `a81f8e4` closes all findings; independent re-review approved both spec
compliance and code quality. Production behavior did not change in the correction.

Parent fresh non-live regression: 344 passed, 15 deselected, one existing
Starlette/httpx warning in 19.77s. Combined service/test Pyright reports zero
errors and warnings with the project interpreter. A direct invocation without
that interpreter initially failed import resolution; explicitly passing
`.venv/bin/python` resolved the environment issue. The `uv` cache was restricted
on that final check, so no cache permissions or dependencies were changed.

This layer accepts server-owned identity snapshots. It does not verify browser
tokens or add routes, Taylor's inbox, final Alex Decision enforcement or mail.

## Current and historical Finance queries — locally accepted

Commit `6dcfe5f` adds Alex's current proposal status and Taylor's pending-request
list and exact historical request detail. A historical link keeps its original
selection, analysis, option and review reason; currentness is reported separately.
Pending candidates require the current selection and latest pending revision,
not merely the existence of an older pending row. Direct lookup of another
configured submitter's request is denied; the pending list excludes it.

The initial query tests failed because the three service methods were missing.
The completed service file passes 45 tests, including wrong-caller denial before
database access, foreign tenant/object exclusion, terminal-status filtering and
unchanged rows/generation across queries and file-store reopen.

Parent fresh committed-snapshot regression: 357 passed, 15 live tests deselected,
one existing Starlette/httpx warning in 20.31s. Scoped service/repository/port/test
Pyright with the project interpreter reports zero errors and warnings. Independent
review approved spec compliance and code quality with no actionable findings.
Commands, database schema, routes and activation are unchanged by this increment.

These are application services, not yet Taylor's browser inbox. Final Alex
Decision binding and authenticated API/UI composition remain required before
the new workflow can be used in the app.

## Proposal-bound final Decision — locally accepted

Implementation `6732953`, integrity/coverage correction `9a45336`, report
`860ccb8`, and parent test-only correction `75558c5` add Alex's final approval
or withdrawal against the exact current proposal. Spending above $20,000
requires the exact approved Taylor revision; standing Finance authorization
cannot replace it. The immutable Decision preserves its original approval
evidence after later changes. Legacy records and their serialized bytes remain
unchanged. No new application routes or activation were added.

Approval writes the Decision, material-planner satisfaction, background planning
event and current pointer in one transaction with one proposal guard. Withdrawal
clears the current submission and supersedes any Finance review atomically;
it creates no execution event. Repeated requests return the original receipt,
and a different request cannot reuse its key or finalize the same selection
again, even when a rejection is the current Decision pointer.

Independent review required a missing-selection integrity-error correction and
additional authorization, withdrawal, history and race assertions. The parent
completed the final test-only correction to prove exact winning records and no
losing changes across five two-connection races. Final independent verdicts:
spec compliance approved and code quality approved, all findings closed.

Final parent verification on committed `75558c5`: 60 focused tests passed;
417 broad non-live tests passed, 15 live tests deselected, one existing
Starlette/httpx warning in 22.41s. Scoped Pyright, Ruff, format and commit hooks
passed. This proves local behavior, not native Fabric concurrency or browser
authentication. The initial implementer wrote a production skeleton before
the first captured RED; that process deviation is documented, not described as
test-first. The subsequent missing-selection correction did capture its failing
test before the narrow production change.

Subsequent broader verification exposed an earlier parent test assertion using
`rejected` rather than the domain's `decision_rejected` status when final
rejection won a race. Test-only correction `2731943` now explicitly schedules
both resolution outcomes and uses the domain status enum. The old expectation
failed deterministically before correction; the full finalization file then
passed 61 tests. Independent review approved the correction; no production
behavior changed.

## Individual execution safeguards — locally accepted

Helper `d9d3143` (report `72ee91e`) checks exact current Decision, analysis,
selection and Finance review bindings. It advances one fresh proposal generation
in the caller's transaction and does not commit by itself. Historical reads and
legacy proposal generations remain unchanged. Independent review approved both
spec compliance and code quality; parent regression passed 464 tests.

Service wiring `d1c3fe1`, with test-only strengthening `7de52e1`, applies the
guard to new action creation, start, retry and completion. Identical existing
creation receipts remain readable without writing; they do not authorize new
work. Failure/cancellation cleanup stays confined to the exact old action and
attempt. Real two-connection tests cover competition with response replacement
and prove that losing transactions leave no durable changes.

Independent review requested stronger assertions for unaffected sibling actions
in cleanup tests. The correction proves those rows unchanged, preserves prior
events and verifies the exact new target event and canonical payloads. Final
spec and quality verdicts are approved, with no remaining findings. The normal
commit hook initially blocked on an inherited warning in the untouched planning
worker; a disclosed one-command bypass followed manual scoped checks without
changing the global hook configuration.

Parent verification on committed `7de52e1`: **497 passed, 11 intentional skips,
15 live tests deselected**, one inherited Starlette/httpx warning, in 27.55s.
These guards do not yet cover queued planning, simulated playback or real email,
and do not supply Taylor's browser workflow or authorize activation. The next
adopted increment addresses planning transactions and stale queued events.

## Remaining gates

1. Native database acceptance for the locally tested durable Finance review log.
2. Authenticated submission/status/review/final-Decision APIs, execution
   currentness safeguards and supported-option execution; only then activate
   the locally tested new-case policy in application routes.
3. Finance cross-session UI integration and final five-stage workflow verification.
4. Presenter-controlled Work IQ discovery of a new email from Will, exact
   case-specific source binding and duplicate-safe case creation.
5. Option-specific execution plans and an explicitly reviewed real email from
   Alex to Will, with safe uncertain-send handling.
6. Separate live consent/setup, SQL/native acceptance, deployment verification,
   and actual receipt of the authorized demo email by Will.

No live sending, consent, deployment, schema migration, case creation or decision
mutation has been performed by these local increments.
