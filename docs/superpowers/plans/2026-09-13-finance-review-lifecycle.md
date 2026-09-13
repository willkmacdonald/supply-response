# Finance Review Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the immutable proposal-bound Finance review lifecycle that the approved independent approval workflow will persist and expose.

**Architecture:** Add an isolated immutable domain record and pure transitions, following existing Pydantic models and identity snapshots. This first bounded increment deliberately does not enable production approval or replace existing Decision authorization; database integration, API authentication and five-stage UI follow in separately reviewed increments using these interfaces.

**Tech Stack:** Python 3.12+, Pydantic 2, pytest, existing Decimal money and identity types.

## Global Constraints

- Costs strictly greater than $20,000 require an explicit Taylor review.
- Server-side tenant/object/role binding determines authority; a query parameter, display name or local persona selector does not.
- Never overwrite the rejected record or reuse its approval.
- Existing historical Decisions and standing-authorization evidence remain readable and immutable under their original workflow version.
- No tenant changes, live case mutations, sending, deployment or production workflow activation in this increment.
- Inputs to domain policy are server-owned snapshots, not independently authenticated credentials; later API composition must authenticate and load them.

## Sequence and coverage boundary

This plan covers proposal identity and review transitions in the approved independent-approval spec. It produces a separately testable unit for the next persistence increment, not a working Finance inbox. Remaining integration gates: append-only persistence with concurrency/idempotency, workflow-version selection, final-Decision enforcement, Taylor authentication and read authorization, five-stage UI, cross-session and native verification. Inbound discovery and mail execution retain their separate approved specs.

### Task 1: Immutable proposal and Finance review transitions

**Files:**
- Create: `data/domain/finance.py` (proposal and lifecycle models).
- Create: `services/policy/finance_review.py` (server-owned identity and transition rules).
- Test: `tests/domain/test_finance_review.py`.

**Interfaces:**
- Consumes: existing `FrozenModel`, `Money`, `IdentitySnapshot`, `IdentitySource.ENTRA`, `requires_finance_approval(Decimal) -> bool`.
- Produces: `FinanceProposal(case_id, analysis_id, analysis_material_hash, option_id, response_cost)` with computed `fingerprint: str`.
- Produces: `FinanceReviewStatus` values `pending`, `approved`, `rejected`, `superseded`.
- Produces: `FinanceReview(review_id, proposal, submitted_by, submitted_at, status, reviewed_by=None, reviewed_at=None, reason=None, superseded_at=None)`.
- Produces: `submit_finance_review(*, review_id: str, proposal: FinanceProposal, actor: IdentitySnapshot, now: datetime) -> FinanceReview`.
- Produces: `resolve_finance_review(*, review: FinanceReview, current_proposal: FinanceProposal, actor: IdentitySnapshot, approved: bool, reason: str | None, now: datetime) -> FinanceReview`.
- Produces: `supersede_finance_review(*, review: FinanceReview, now: datetime) -> FinanceReview`.
- Produces: `FinanceReviewViolation(ValueError)` for policy denials.

- [ ] **Step 1: Write focused failing tests.** Use synthetic identity UUIDs; never load tenant secrets. Establish this fixture and first transition test:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest
from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceProposal, FinanceReviewStatus
from services.policy.finance_review import submit_finance_review, resolve_finance_review

NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)
TENANT = "11111111-1111-4111-8111-111111111111"

def actor(persona):
    return IdentitySnapshot(
        persona_id=f"RL-PERSONA-{persona}", source_id=f"RL-ENTRA-{persona}",
        identity_source=IdentitySource.ENTRA, tenant_id=TENANT,
        object_id=("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" if persona == "ALEX"
                   else "cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        effective_roles=(("material_planner", "response_approver") if persona == "ALEX"
                         else ("finance_approver",)),
    )

def proposal(**changes):
    values = dict(case_id="case-1", analysis_id="analysis-1", analysis_material_hash="a" * 64,
                  option_id="combined", response_cost=Decimal("24750.00"))
    values.update(changes)
    return FinanceProposal(**values)

def test_rejection_preserves_original_request():
    pending = submit_finance_review(review_id="review-1", proposal=proposal(), actor=actor("ALEX"), now=NOW)
    rejected = resolve_finance_review(review=pending, current_proposal=proposal(), actor=actor("TAYLOR"),
                                     approved=False, reason="Use a lower-cost response", now=NOW + timedelta(seconds=1))
    assert pending.status == FinanceReviewStatus.PENDING
    assert rejected.status == FinanceReviewStatus.REJECTED
    assert rejected.reason == "Use a lower-cost response"
    assert rejected.reviewed_by == actor("TAYLOR")
```

Add parameterized cases for $20,000 (no request), $20,000.01 (request), $22,500 and $24,750; all proposal fields affecting fingerprint; equivalent Decimal scales sharing a fingerprint; negative/nonfinite/fractional-cent costs and malformed hashes rejected; blank identifiers; naive or backwards timestamps; blank rejection reasons; Alex trying to resolve; Taylor trying to submit; wrong source/role/tenant/object; terminal transitions; supersession preserving review metadata and earlier objects; serialization round-trip validation. Assert an old approved record cannot resolve another proposal. Give each missing behavior its own RED/GREEN cycle rather than introducing untested transitions.

- [ ] **Step 2: Run RED.**

Run `.venv/bin/python -m pytest tests/domain/test_finance_review.py -q`.
Expected initial failure: the new finance module does not exist; subsequent tests fail on the missing individual rule. Record output before production code is written.

- [ ] **Step 3: Implement the models and pure policy.** Use explicit fields and these validation/transition rules, without changing existing Decision or analysis models:

```python
# Fingerprint property on FinanceProposal; imports hashlib and json.
payload = self.model_dump(mode="json")
return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

# Submission, after validating actor and aware time:
if not requires_finance_approval(proposal.response_cost):
    raise FinanceReviewViolation("Finance review is not required for this cost")
return FinanceReview(review_id=review_id, proposal=proposal, submitted_by=actor,
                     submitted_at=now, status=FinanceReviewStatus.PENDING)

# Resolution, after validating Taylor and aware time:
if review.status is not FinanceReviewStatus.PENDING:
    raise FinanceReviewViolation("Only a pending review can be resolved")
if review.proposal != current_proposal:
    raise FinanceReviewViolation("The proposal has changed; submit a new review")
values = review.model_dump()
values.update(status=FinanceReviewStatus.APPROVED if approved else FinanceReviewStatus.REJECTED,
              reviewed_by=actor, reviewed_at=now, reason=reason)
return FinanceReview.model_validate(values)

# Supersession, after validating aware time and chronological order:
if review.status is FinanceReviewStatus.SUPERSEDED:
    return review
values = review.model_dump()
values.update(status=FinanceReviewStatus.SUPERSEDED, superseded_at=now)
return FinanceReview.model_validate(values)
```

Model declarations use existing `FrozenModel`; identifiers are nonblank strings;
analysis hash is exactly 64 lowercase hex characters. `response_cost` uses Money,
must be finite, nonnegative and exactly representable to cents. All timestamps
are timezone-aware. Pending records have no review metadata; approved/rejected
records require reviewer/time; rejection requires nonblank reason; superseded
records require superseded time and retain any prior reviewer/time/reason.
For all states, reviewer/time are paired, review time is not before submission,
and supersession is not before submission or review. Validate on construction
and JSON reload, not only in transition functions. No `model_copy(update=...)`
that bypasses validation. Normalize optional reason whitespace to trimmed text
or None; enforce a 4,000-character maximum. Reject invalid metadata mixtures.

Policy requires exact Alex persona/source, Entra identity and the two existing
Alex roles for submission. Resolution requires exact Taylor persona/source,
Entra identity and only the Finance role. Both need valid tenant/object UUIDs.
Taylor must share the submitter's tenant and have a different object ID. These
checks supplement—not replace—the future AuthService verification of snapshots.
Reject time travel, empty IDs and rejected/approved re-resolution explicitly.

- [ ] **Step 4: Run GREEN and regressions.**

Run `.venv/bin/python -m pytest tests/domain/test_finance_review.py -q`, then
`.venv/bin/python -m pytest tests/domain tests/auth tests/persistence/test_decision_outbox.py -q`.
Expected: all pass, existing standing-authorization and Decision tests unchanged.
Run `git diff --check`. Review the changed files against every rule above.

- [ ] **Step 5: Commit and independent review.**

```sh
git add data/domain/finance.py services/policy/finance_review.py tests/domain/test_finance_review.py
git commit -m "feat: model independent proposal-bound finance review"
```

Write a report with RED/GREEN commands and outputs, model interfaces, changed
files and remaining integration boundaries. Parent generates a review package
and requests separate spec and quality verdicts before accepting the increment.

## Self-review

The scope deliberately isolates lifecycle rules; it does not claim persistence,
concurrency guarantees, authenticated HTTP access or final-Decision enforcement.
Current-iteration interfaces are defined above and use existing money/identity
types. Required broader workflow gates are recorded in Sequence and coverage
boundary and remain open until implemented and verified separately.
