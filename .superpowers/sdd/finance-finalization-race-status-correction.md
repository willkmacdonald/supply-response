# Finalization race assertion correction

Parent's broad verification of d1c3fe1 found one earlier test defect: the
resolve race asserted literal `rejected`, but the domain CaseStatus and repository
correctly store `decision_rejected`. This expectation was introduced in the
parent's test-only 75558c5. Earlier passing runs happened to take the other race
ordering. No production regression was identified, and no production code is
changed here.

The parent added bounded Event scheduling after both connections read the old
state, before either losing reader can write, to exercise both resolution
orderings explicitly. The preferred winner must return a real Decision or
ResolutionResult, not a contention/error surrogate. Both paths keep the existing
full durable journal and single-generation assertions. Other race variants remain
unconstrained.

Before correcting the expected value, the deterministic two-variant run produced
one failure (final rejection wins) and one pass (Taylor resolution wins), exactly
reproducing the status mismatch. The assertion now uses the existing CaseStatus
enum for all three expected outcomes.

Verification after correction:

- Full finalization file: 61 passed in 2.91s, excluding fabric_live.
- Scoped unfiltered Ruff and format check passed.
- Scoped Pyright: zero errors or warnings.
- Independent review and fresh broader committed regression are pending.

This is a test-only correction and stronger acceptance coverage. No deployment,
live calls, schema updates, identity changes or sends occurred.
