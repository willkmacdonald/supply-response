# Finance final Decision implementation report

## Outcome

Implemented the proposal-bound final Decision aggregate across the domain,
Finance application service, legacy Decision boundary, proposal CAS repository,
Decision persistence validation, and focused file-SQLite tests. No API, UI,
schema, migration, mail, execution activation, or live-system behavior changed.

## RED / GREEN evidence

- Process deviation: production skeleton edits preceded the first focused RED.
  This is explicitly not represented as test-first work.
- First actual focused run against the incomplete implementation: `2 failed,
  4 passed`; high-cost finalization and replay failed because persistence still
  required standing `finance_approver` satisfaction.
- Isolated predecessor `548a161` verification performed after the skeleton:
  collection error importing absent `FinalizeProposalCommand`. This proves the
  focused suite detects the predecessor, but does not repair the TDD ordering
  deviation.
- Current focused GREEN: `tests/finance/test_finance_final_decision.py` passes.

## Acceptance mapping

- Exact high-cost selection/review/revision and no standing Finance:
  `test_high_cost_approval_records_exact_historical_evidence`.
- Low-cost evidence without Finance: `test_low_cost_approval_has_no_finance_review`.
- Persisted cost threshold at 20000.00/20000.01:
  `test_finalization_uses_exact_saved_cost_threshold`.
- Evidence revision/status validation:
  `test_evidence_rejects_malformed_revision_and_nonapproved_review`.
- Pure exact Alex/Taylor evidence shapes and same-person/tenant guards:
  `test_evidence_requires_pure_exact_actor_shapes`.
- Frozen legacy JSON omission/byte compatibility:
  `test_frozen_legacy_decision_json_is_byte_identical`.
- Legacy independent-workflow isolation:
  `test_legacy_service_rejects_independent_case`.
- Pending high-cost review rejection/no writes:
  `test_high_cost_pending_review_cannot_finalize_and_writes_nothing`.
- Atomic pending-review withdrawal:
  `test_rejection_atomically_withdraws_pending_review`.
- Exact Alex before initial and committed replay UoW:
  `test_exact_alex_is_required_before_uow`,
  `test_unauthorized_committed_replay_denied_before_uow`.
- Exact current-selection owner on pending and low-cost rejection:
  `test_rejection_denies_foreign_current_selection_owner_before_mutation`.
- Immutable replay and changed-fingerprint conflict:
  `test_replay_returns_original_without_clock`,
  `test_same_key_changed_command_conflicts`.
- Historical duplicate selection scan:
  `test_fresh_key_cannot_finalize_same_selection_from_history`.
- Replay after a later analysis/selection with normalized refreshed identity:
  `test_refreshed_alex_replays_original_after_later_analysis_and_selection`.
- Low-cost approval/withdrawal chronology and rollback:
  `test_low_cost_backward_approval_and_withdrawal_roll_back`.
- High-cost review chronology and naive clocks for both kinds:
  `test_high_cost_approval_before_review_time_rolls_back`,
  `test_naive_server_clock_rejected_for_both_kinds`.
- Decision/outbox injected failure full rollback:
  `test_insert_failure_rolls_back_guard_withdraw_rows_and_projection`.
- Corrupt selection/review/revision evidence rejected through get/list/outbox:
  `test_persisted_proposal_evidence_corruption_is_rejected`.
- First-state-read synchronized file-SQLite races for identical finalization,
  different keys, proposal publication, analysis save, and Taylor resolution:
  `test_file_sqlite_finalization_races_at_first_state_read`. The test verifies
  distinct connections crossed the barrier, operation success, durable Decision
  cardinality, exact identical-key replay, and satisfaction/event cardinality.

The duplicate-history test exercises the same immutable case history scan with a
fresh key after the projection generation advances; the implementation uses
`list_for_case`, not the mutable current Decision pointer.

## Verification

- Focused final: 39 passed.
- Related persistence/policy: 119 passed.
- Broad non-live final: 396 passed, 15 deselected, one third-party
  Starlette/httpx deprecation warning.
- Focused Pyright final: 0 errors, 0 warnings.
- Focused Ruff final: all checks passed; formatting check passed.
- Frozen fixture has not been modified.

## Scope and self-review

The implementation uses one UoW and one commit. Approval performs one proposal
guard, writes Decision/satisfactions/event/current pointer; rejection performs
one withdrawal, optional review supersession, Decision/rejected pointer, and no
event. Historical reads bind exact selection and review revision. The final
verification passed. Final SHA is recorded after the scoped commit below.
