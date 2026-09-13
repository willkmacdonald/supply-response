import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects import mssql, sqlite
from sqlalchemy.exc import IntegrityError, OperationalError

from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import CorpusScope, IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceProposal, FinanceReviewStatus
from data.domain.proposals import ProposalSelection, ProposalToken, SelectionReceipt
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.persistence.finance_reviews import FinanceReviewRevisionConflict
from services.persistence.proposals import (
    SelectionIdempotencyConflict,
    StaleProposal,
    _cas_projection,
)
from services.persistence.sqlite import sqlite_store
from services.persistence.store import (
    PersistenceIntegrityError,
    RecordNotFound,
    serialize_model,
)
from services.persistence.tables import (
    analysis_claims,
    analysis_versions,
    approval_satisfactions,
    case_projection,
    case_proposal_selections,
    decisions,
    evidence_items,
    finance_review_revisions,
    outbox_events,
)
from services.policy.finance_review import resolve_finance_review, submit_finance_review

START = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
SUBMITTED = datetime.fromisoformat("2026-09-01T14:02:00+00:00")


def _is_sqlite_lock_contention(error: OperationalError) -> bool:
    original = error.orig
    code = getattr(original, "sqlite_errorcode", None)
    return (
        isinstance(original, sqlite3.OperationalError)
        and isinstance(code, int)
        and (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    )


def _capture_sqlite_contender(barrier, call):
    try:
        return call()
    except (StaleProposal, IntegrityError) as error:
        return error
    except OperationalError as error:
        if _is_sqlite_lock_contention(error):
            return error
        barrier.abort()
        raise
    except BaseException:
        barrier.abort()
        raise


def fingerprint(value):
    return hashlib.sha256(serialize_model(value).encode()).hexdigest()


def actor(taylor=False):
    return IdentitySnapshot(
        persona_id="RL-PERSONA-TAYLOR" if taylor else "RL-PERSONA-ALEX",
        source_id="RL-ENTRA-TAYLOR" if taylor else "RL-ENTRA-ALEX",
        effective_roles=("finance_approver",)
        if taylor
        else ("material_planner", "response_approver"),
        identity_source=IdentitySource.ENTRA,
        tenant_id="11111111-1111-4111-8111-111111111111",
        object_id="33333333-3333-4333-8333-333333333333"
        if taylor
        else "22222222-2222-4222-8222-222222222222",
        display_name="Taylor" if taylor else "Alex",
    )


def build_analysis(case, snapshot, analysis_id):
    return analyze_case(
        AnalyzeCaseCommand(
            analysis_id=analysis_id,
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot, analysis_id=analysis_id, retrieved_at=START
            ),
            analysis_started_at=START,
            created_at=START,
            calculation_version="rl001-options-v1",
        )
    )


@dataclass
class SelectionContext:
    store: object
    case: object
    snapshot: object
    analysis: object
    serial: int = 0
    alex: IdentitySnapshot = field(default_factory=actor)
    taylor: IdentitySnapshot = field(default_factory=lambda: actor(True))

    def state(self):
        with self.store.uow_factory() as uow:
            return uow.proposals.get_state(self.case.case_id)

    def publish_option(self, option_id):
        self.serial += 1
        high = next(
            o for o in self.analysis.response_options if o.option_id == option_id
        ).predicted.response_cost > Decimal(20000)
        command = receipt(
            self,
            option_id,
            f"selection-{self.serial}",
            f"review-{self.serial}" if high else None,
            self.state().token,
            submitted_at=SUBMITTED + timedelta(minutes=2 * self.serial),
        )
        return persist(self, command)

    def publish_combined(self):
        return self.publish_option("RL-OPTION-COMBINED")

    def publish_transfer(self):
        return self.publish_option("RL-OPTION-TRANSFER")


@pytest.fixture
def selection_context(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'selection.db'}")
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-SELECTION",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    analysis = build_analysis(case, snapshot, "RL-ANALYSIS-SELECTION-1")
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    yield SelectionContext(store, case, snapshot, analysis)
    store.engine.dispose()


def receipt(
    ctx, option_id, selection_id, review_id, expected, *, submitted_at=SUBMITTED
):
    option = next(o for o in ctx.analysis.response_options if o.option_id == option_id)
    selection = ProposalSelection(
        selection_id=selection_id,
        proposal=FinanceProposal(
            case_id=ctx.case.case_id,
            analysis_id=ctx.analysis.analysis_id,
            analysis_material_hash=ctx.analysis.material_hash,
            option_id=option_id,
            response_cost=option.predicted.response_cost,
        ),
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
        submitted_by=ctx.alex,
        submitted_at=submitted_at,
        finance_review_id=review_id,
    )
    material = json.dumps(
        {
            "selection": selection.model_dump(mode="json"),
            "expected": expected.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return SelectionReceipt(
        selection=selection,
        expected=expected,
        idempotency_key=f"publish:{selection_id}",
        request_fingerprint=hashlib.sha256(material.encode()).hexdigest(),
    )


def persist(ctx, command):
    with ctx.store.uow_factory() as uow:
        if command.selection.finance_review_id:
            pending = submit_finance_review(
                review_id=command.selection.finance_review_id,
                proposal=command.selection.proposal,
                actor=command.selection.submitted_by,
                now=command.selection.submitted_at,
            )
            uow.finance_reviews.append(
                pending,
                expected_revision=None,
                idempotency_key=f"pending:{command.selection.selection_id}",
                request_fingerprint=fingerprint(pending),
            )
        result = uow.proposals.publish(command)
        uow.commit()
        return result


def counts(store):
    with store.engine.connect() as connection:
        return {
            table.name: connection.scalar(select(func.count()).select_from(table))
            for table in (
                case_proposal_selections,
                finance_review_revisions,
                analysis_versions,
                evidence_items,
                decisions,
                approval_satisfactions,
                outbox_events,
            )
        }


def test_initial_publication_and_pointer(selection_context):
    ctx = selection_context
    state = ctx.state()
    assert state.token.generation == 1 and state.selection is None
    command = receipt(ctx, "RL-OPTION-COMBINED", "selection-1", "review-1", state.token)
    assert persist(ctx, command) == command.selection
    current = ctx.state()
    assert current.token.generation == 2
    assert current.selection == command.selection
    assert (
        current.review.status is FinanceReviewStatus.PENDING
        and current.review_revision == 1
    )


def test_transfer_replaces_rejected_review_without_new_review(selection_context):
    ctx = selection_context
    first = ctx.publish_combined()
    with ctx.store.uow_factory() as uow:
        state = uow.proposals.get_state(ctx.case.case_id)
        rejected = resolve_finance_review(
            review=state.review,
            current_proposal=state.selection.proposal,
            actor=ctx.taylor,
            approved=False,
            reason="Budget 10000",
            now=first.submitted_at + timedelta(minutes=1),
        )
        uow.finance_reviews.append(
            rejected,
            expected_revision=1,
            idempotency_key="reject-1",
            request_fingerprint="b" * 64,
        )
        uow.proposals.guard_current(ctx.case.case_id, expected=state.token)
        uow.commit()
    second = ctx.publish_transfer()
    state = ctx.state()
    with ctx.store.uow_factory() as uow:
        original = uow.finance_reviews.get_revision(first.finance_review_id, 2)
        superseded, revision = uow.finance_reviews.get_latest(first.finance_review_id)
    assert state.selection == second and state.review is None and original == rejected
    assert (
        superseded.status is FinanceReviewStatus.SUPERSEDED
        and superseded.reason == "Budget 10000"
        and revision == 3
    )


def test_two_selections_have_one_winner(selection_context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ctx = selection_context
    expected = ctx.state().token
    commands = [
        receipt(ctx, "RL-OPTION-TRANSFER", f"race-{i}", None, expected) for i in (1, 2)
    ]
    barrier = Barrier(2)

    def contender(command):
        def publish():
            barrier.wait(timeout=5)
            return persist(ctx, command)

        return _capture_sqlite_contender(barrier, publish)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=15)
            for future in [pool.submit(contender, command) for command in commands]
        ]
    winners = [result for result in results if isinstance(result, ProposalSelection)]
    assert len(winners) == 1
    assert ctx.state().selection == winners[0]


def test_late_cas_failure_rolls_back_pending_receipt_and_pointer(
    selection_context, monkeypatch
):
    import services.persistence.proposals as module
    from services.persistence.proposals import StaleProposal

    ctx = selection_context
    before_state, before_counts = ctx.state(), counts(ctx.store)
    command = receipt(
        ctx,
        "RL-OPTION-COMBINED",
        "late-failure",
        "late-review",
        before_state.token,
    )

    def fail_cas(connection, **kwargs):
        assert kwargs
        assert (
            connection.scalar(
                select(func.count()).select_from(case_proposal_selections)
            )
            == 1
        )
        assert (
            connection.scalar(
                select(func.count()).select_from(finance_review_revisions)
            )
            == 1
        )
        raise StaleProposal("injected late CAS failure")

    monkeypatch.setattr(module, "_cas_projection", fail_cas)
    with pytest.raises(StaleProposal):
        persist(ctx, command)
    assert counts(ctx.store) == before_counts
    assert ctx.state() == before_state


def test_new_analysis_invalidates_selection_and_supersedes_review(selection_context):
    ctx = selection_context
    selected = ctx.publish_combined()
    replacement = build_analysis(ctx.case, ctx.snapshot, "RL-ANALYSIS-SELECTION-2")
    assert replacement.material_hash == ctx.analysis.material_hash
    ctx.store.save_analysis(replacement)
    state = ctx.state()
    assert state.token.generation == 3
    assert state.token.analysis_id == replacement.analysis_id
    assert state.selection is None
    with ctx.store.uow_factory() as uow:
        review, revision = uow.finance_reviews.get_latest(selected.finance_review_id)
    assert review.status is FinanceReviewStatus.SUPERSEDED
    assert revision == 2


def test_publish_rejects_historical_analysis_with_current_token_and_rolls_back(
    selection_context,
):
    ctx = selection_context
    old_analysis = ctx.analysis
    replacement = build_analysis(ctx.case, ctx.snapshot, "RL-ANALYSIS-SELECTION-2")
    ctx.store.save_analysis(replacement)
    expected = ctx.state().token
    command = receipt(ctx, "RL-OPTION-TRANSFER", "historical", None, expected)
    command = command.model_copy(
        update={
            "selection": command.selection.model_copy(
                update={
                    "proposal": command.selection.proposal.model_copy(
                        update={
                            "analysis_id": old_analysis.analysis_id,
                            "analysis_material_hash": old_analysis.material_hash,
                        }
                    )
                }
            )
        }
    )
    before = counts(ctx.store)
    with pytest.raises(PersistenceIntegrityError):
        persist(ctx, command)
    assert counts(ctx.store) == before
    assert ctx.state().token == expected


def test_guard_current_rejects_legacy_workflow_without_writes(tmp_path):
    from tests.persistence.test_sqlite_store import (
        fallback_rl001_analysis,
        fallback_rl001_case,
    )

    store = sqlite_store(f"sqlite:///{tmp_path / 'legacy-guard.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-LEGACY-GUARD")
    analysis = fallback_rl001_analysis(case, snapshot, "RL-ANALYSIS-LEGACY-GUARD")
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    expected = ProposalToken(
        generation=0,
        analysis_id=analysis.analysis_id,
        analysis_material_hash=analysis.material_hash,
        selection_id=None,
    )
    with store.uow_factory() as uow, pytest.raises(PersistenceIntegrityError):
        uow.proposals.guard_current(case.case_id, expected=expected)
    with store.engine.connect() as connection:
        row = (
            connection.execute(
                select(case_projection).where(case_projection.c.case_id == case.case_id)
            )
            .mappings()
            .one()
        )
    assert row["proposal_generation"] == 0
    assert row["current_selection_id"] is None


def test_replay_conflicts_and_original_replay_after_supersession(selection_context):
    ctx = selection_context
    expected = ctx.state().token
    original = receipt(ctx, "RL-OPTION-COMBINED", "replay", "replay-review", expected)
    persist(ctx, original)
    changed_expected = original.model_copy(
        update={"expected": expected.model_copy(update={"generation": 0})}
    )
    changed_selection = original.model_copy(
        update={
            "selection": original.selection.model_copy(
                update={"selection_id": "changed"}
            )
        }
    )
    with ctx.store.uow_factory() as uow:
        with pytest.raises(SelectionIdempotencyConflict):
            uow.proposals.publish(changed_expected)
        with pytest.raises(SelectionIdempotencyConflict):
            uow.proposals.publish(changed_selection)
    ctx.publish_transfer()
    with ctx.store.uow_factory() as uow:
        assert uow.proposals.publish(original) == original.selection
        assert uow.proposals.get_state(ctx.case.case_id).selection != original.selection


def test_selection_rejects_cost_actor_and_lineage_tampering(selection_context):
    ctx = selection_context
    expected = ctx.state().token
    base = receipt(ctx, "RL-OPTION-TRANSFER", "tamper", None, expected)
    variants = (
        base.model_copy(
            update={
                "selection": base.selection.model_copy(
                    update={"submitted_by": ctx.taylor}
                )
            }
        ),
        base.model_copy(
            update={
                "selection": base.selection.model_copy(
                    update={
                        "submitted_by": ctx.alex.model_copy(
                            update={"identity_source": "fixture"}
                        )
                    }
                )
            }
        ),
        base.model_copy(
            update={
                "selection": base.selection.model_copy(
                    update={
                        "submitted_by": ctx.alex.model_copy(
                            update={"effective_roles": ("material_planner",)}
                        )
                    }
                )
            }
        ),
        base.model_copy(
            update={
                "selection": base.selection.model_copy(
                    update={
                        "proposal": base.selection.proposal.model_copy(
                            update={"response_cost": Decimal("1.00")}
                        )
                    }
                )
            }
        ),
        base.model_copy(
            update={
                "selection": base.selection.model_copy(
                    update={
                        "proposal": base.selection.proposal.model_copy(
                            update={"case_id": "another-case"}
                        )
                    }
                )
            }
        ),
    )
    before = counts(ctx.store)
    for command in variants:
        with pytest.raises((PersistenceIntegrityError, RecordNotFound, StaleProposal)):
            persist(ctx, command)
    assert counts(ctx.store) == before


@pytest.mark.parametrize("mismatch", ("time", "actor", "option-and-cost"))
def test_high_cost_selection_rejects_mismatched_pending_review(
    selection_context, mismatch
):
    ctx = selection_context
    command = receipt(
        ctx, "RL-OPTION-COMBINED", "mismatch", "mismatch-review", ctx.state().token
    )
    proposal = command.selection.proposal
    submitter = command.selection.submitted_by
    submitted_at = command.selection.submitted_at
    if mismatch == "option-and-cost":
        option = next(
            item
            for item in ctx.analysis.response_options
            if item.option_id == "RL-OPTION-EXPEDITE"
        )
        proposal = proposal.model_copy(
            update={
                "option_id": option.option_id,
                "response_cost": option.predicted.response_cost,
            }
        )
    elif mismatch == "actor":
        submitter = submitter.model_copy(update={"display_name": "Different Alex"})
    else:
        submitted_at += timedelta(seconds=1)
    mismatched = submit_finance_review(
        review_id="mismatch-review",
        proposal=proposal,
        actor=submitter,
        now=submitted_at,
    )
    before = counts(ctx.store)
    with pytest.raises(PersistenceIntegrityError), ctx.store.uow_factory() as uow:
        uow.finance_reviews.append(
            mismatched,
            expected_revision=None,
            idempotency_key="pending:mismatch",
            request_fingerprint=fingerprint(mismatched),
        )
        uow.proposals.publish(command)
    assert counts(ctx.store) == before


def test_high_cost_selection_rejects_review_from_another_case_and_analysis(
    selection_context,
):
    ctx = selection_context
    foreign_case, foreign_snapshot = instantiate_rl001(
        case_id="RL-CASE-FOREIGN-REVIEW",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    foreign_analysis = build_analysis(
        foreign_case, foreign_snapshot, "RL-ANALYSIS-FOREIGN-REVIEW"
    )
    ctx.store.create_case(foreign_case, foreign_snapshot)
    ctx.store.save_analysis(foreign_analysis)
    foreign_option = next(
        item
        for item in foreign_analysis.response_options
        if item.option_id == "RL-OPTION-COMBINED"
    )
    foreign_proposal = FinanceProposal(
        case_id=foreign_case.case_id,
        analysis_id=foreign_analysis.analysis_id,
        analysis_material_hash=foreign_analysis.material_hash,
        option_id=foreign_option.option_id,
        response_cost=foreign_option.predicted.response_cost,
    )
    command = receipt(
        ctx,
        "RL-OPTION-COMBINED",
        "foreign-review-selection",
        "foreign-review",
        ctx.state().token,
    )
    pending = submit_finance_review(
        review_id="foreign-review",
        proposal=foreign_proposal,
        actor=ctx.alex,
        now=command.selection.submitted_at,
    )
    before = counts(ctx.store)
    with pytest.raises(PersistenceIntegrityError), ctx.store.uow_factory() as uow:
        uow.finance_reviews.append(
            pending,
            expected_revision=None,
            idempotency_key="pending:foreign-review",
            request_fingerprint=fingerprint(pending),
        )
        uow.proposals.publish(command)
    assert counts(ctx.store) == before


def test_selection_and_review_ids_cannot_be_reused(selection_context):
    ctx = selection_context
    first = receipt(
        ctx, "RL-OPTION-COMBINED", "unique", "unique-review", ctx.state().token
    )
    persist(ctx, first)
    current = ctx.state().token
    same_selection = receipt(
        ctx, "RL-OPTION-TRANSFER", "unique", None, current
    ).model_copy(update={"idempotency_key": "different-key"})
    with pytest.raises(IntegrityError):
        persist(ctx, same_selection)
    second = receipt(ctx, "RL-OPTION-COMBINED", "unique-2", "unique-review", current)
    with pytest.raises((FinanceReviewRevisionConflict, IntegrityError)):
        persist(ctx, second)


def test_strict_proposal_models_reject_invalid_tokens_and_ids():
    with pytest.raises(ValidationError):
        ProposalToken(
            generation=True,
            analysis_id=None,
            analysis_material_hash=None,
            selection_id=None,
        )
    with pytest.raises(ValidationError):
        SelectionReceipt(
            selection=object(),
            expected=ProposalToken(
                generation=0,
                analysis_id=None,
                analysis_material_hash=None,
                selection_id=None,
            ),
            idempotency_key=" ",
            request_fingerprint="A" * 64,
        )
    with pytest.raises(ValidationError):
        ProposalToken(
            generation=0,
            analysis_id="analysis",
            analysis_material_hash=None,
            selection_id=None,
        )
    with pytest.raises(ValidationError):
        ProposalToken(
            generation=0,
            analysis_id=None,
            analysis_material_hash=None,
            selection_id="pointer",
        )
    with pytest.raises(ValidationError):
        ProposalToken(
            generation=0,
            analysis_id="x" * 129,
            analysis_material_hash="a" * 64,
            selection_id=None,
        )


def test_cas_predicate_compiles_for_sqlite_and_mssql():
    class Result:
        rowcount = 1

    class Capture:
        statement = None

        def execute(self, statement):
            self.statement = statement
            return Result()

    connection = Capture()
    expected = ProposalToken(
        generation=7,
        analysis_id="analysis",
        analysis_material_hash="a" * 64,
        selection_id=None,
    )
    _cas_projection(
        connection,
        case_id="case",
        expected=expected,
        values={"current_selection_id": None},
    )
    for dialect in (sqlite.dialect(), mssql.dialect()):
        compiled_statement = connection.statement.compile(dialect=dialect)
        compiled = str(compiled_statement)
        assert "WHERE case_projection.case_id =" in compiled
        assert "case_projection.proposal_generation =" in compiled
        assert "case_projection.current_analysis_id =" in compiled
        assert "case_projection.current_analysis_hash =" in compiled
        assert "proposal_generation" in compiled
        assert "case_projection.current_selection_id IS NULL" in compiled
        assert expected.generation in compiled_statement.params.values()
        assert expected.analysis_id in compiled_statement.params.values()
        assert expected.analysis_material_hash in compiled_statement.params.values()


def test_two_high_cost_selections_roll_back_losing_pending_review(selection_context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ctx = selection_context
    expected = ctx.state().token
    commands = [
        receipt(ctx, "RL-OPTION-COMBINED", f"high-{i}", f"high-review-{i}", expected)
        for i in (1, 2)
    ]
    barrier = Barrier(2)

    def contender(command):
        def publish():
            barrier.wait(timeout=5)
            return persist(ctx, command)

        return _capture_sqlite_contender(barrier, publish)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=15)
            for future in [pool.submit(contender, command) for command in commands]
        ]
    assert sum(isinstance(item, ProposalSelection) for item in results) == 1
    after = counts(ctx.store)
    assert after[case_proposal_selections.name] == 1
    assert after[finance_review_revisions.name] == 1


def test_competing_guards_have_one_winner(selection_context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ctx = selection_context
    expected = ctx.state().token
    barrier = Barrier(2)

    def contender():
        def guard():
            with ctx.store.uow_factory() as uow:
                barrier.wait(timeout=5)
                result = uow.proposals.guard_current(
                    ctx.case.case_id, expected=expected
                )
                uow.commit()
                return result

        return _capture_sqlite_contender(barrier, guard)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=15)
            for future in [pool.submit(contender) for _ in range(2)]
        ]
    assert sum(isinstance(item, ProposalToken) for item in results) == 1
    assert ctx.state().token.generation == expected.generation + 1
    with ctx.store.uow_factory() as uow, pytest.raises(StaleProposal):
        uow.proposals.guard_current(ctx.case.case_id, expected=expected)


@pytest.mark.parametrize(
    ("target_cost", "review_id"),
    (("20000.00", None), ("20000.01", "threshold-review")),
)
def test_exact_finance_threshold_uses_actual_analysis_cost(
    tmp_path, target_cost, review_id
):
    store = sqlite_store(f"sqlite:///{tmp_path / f'threshold-{target_cost}.db'}")
    case, snapshot = instantiate_rl001(
        case_id=f"RL-CASE-THRESHOLD-{target_cost}",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    snapshot = snapshot.model_copy(
        update={
            "alpha_expedite": snapshot.alpha_expedite.model_copy(
                update={
                    "quantity": 1,
                    "incremental_cost_per_unit": Decimal(target_cost),
                }
            )
        }
    )
    analysis = build_analysis(case, snapshot, f"RL-ANALYSIS-THRESHOLD-{target_cost}")
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    ctx = SelectionContext(store, case, snapshot, analysis)
    command = receipt(
        ctx, "RL-OPTION-EXPEDITE", "threshold-selection", review_id, ctx.state().token
    )
    assert command.selection.proposal.response_cost == Decimal(target_cost)
    assert persist(ctx, command) == command.selection
    assert (ctx.state().review is not None) == (review_id is not None)


@pytest.mark.parametrize("approved", (True, False))
def test_resolved_review_is_superseded_by_new_analysis(selection_context, approved):
    ctx = selection_context
    selected = ctx.publish_combined()
    with ctx.store.uow_factory() as uow:
        state = uow.proposals.get_state(ctx.case.case_id)
        resolved = resolve_finance_review(
            review=state.review,
            current_proposal=state.selection.proposal,
            actor=ctx.taylor,
            approved=approved,
            reason="accepted" if approved else "declined",
            now=selected.submitted_at + timedelta(minutes=1),
        )
        uow.finance_reviews.append(
            resolved,
            expected_revision=1,
            idempotency_key=f"resolve-{approved}",
            request_fingerprint=("c" if approved else "d") * 64,
        )
        uow.proposals.guard_current(ctx.case.case_id, expected=state.token)
        uow.commit()
    replacement = build_analysis(ctx.case, ctx.snapshot, "RL-ANALYSIS-RESOLVED")
    ctx.store.save_analysis(replacement)
    with ctx.store.uow_factory() as uow:
        superseded, revision = uow.finance_reviews.get_latest(
            selected.finance_review_id
        )
    assert superseded.status is FinanceReviewStatus.SUPERSEDED
    assert superseded.reviewed_by == resolved.reviewed_by
    assert superseded.reviewed_at == resolved.reviewed_at
    assert superseded.reason == resolved.reason
    assert revision == 3


def test_low_cost_selection_is_cleared_without_finance_revision(selection_context):
    ctx = selection_context
    ctx.publish_transfer()
    assert counts(ctx.store)[finance_review_revisions.name] == 0
    ctx.store.save_analysis(
        build_analysis(ctx.case, ctx.snapshot, "RL-ANALYSIS-LOW-COST")
    )
    assert ctx.state().selection is None
    assert counts(ctx.store)[finance_review_revisions.name] == 0


def test_failed_claim_completion_retains_claim_and_all_rows(
    selection_context, monkeypatch
):
    import services.persistence.proposals as module

    ctx = selection_context
    before = counts(ctx.store)
    assert ctx.store.try_claim_analysis(
        case_id=ctx.case.case_id,
        material_version="claim-material",
        claim_id="claim-id",
        claimed_at=SUBMITTED,
    )
    replacement = build_analysis(ctx.case, ctx.snapshot, "RL-ANALYSIS-CLAIM")

    def fail_cas(*args, **kwargs):
        raise StaleProposal("injected publication failure")

    monkeypatch.setattr(module, "_cas_projection", fail_cas)
    with pytest.raises(StaleProposal):
        ctx.store.complete_analysis_claim(
            analysis=replacement,
            projected_case=ctx.case,
            material_version="claim-material",
            claim_id="claim-id",
            completed_at=SUBMITTED,
        )
    assert counts(ctx.store) == before
    with ctx.store.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(analysis_claims)) == 1


def test_concurrent_analysis_and_selection_have_valid_order(selection_context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ctx = selection_context
    old_token = ctx.state().token
    command = receipt(ctx, "RL-OPTION-TRANSFER", "analysis-race", None, old_token)
    replacement = build_analysis(ctx.case, ctx.snapshot, "RL-ANALYSIS-RACE")
    barrier = Barrier(2)

    def select_contender():
        def publish():
            barrier.wait(timeout=5)
            return persist(ctx, command)

        return _capture_sqlite_contender(barrier, publish)

    def analysis_contender():
        def publish():
            barrier.wait(timeout=5)
            ctx.store.save_analysis(replacement)
            return replacement

        return _capture_sqlite_contender(barrier, publish)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(select_contender), pool.submit(analysis_contender)]
        results = [future.result(timeout=15) for future in futures]
    state = ctx.state()
    if state.token.analysis_id == replacement.analysis_id:
        assert state.selection is None
    else:
        assert state.token.analysis_id == old_token.analysis_id
        assert state.selection == command.selection
    assert any(not isinstance(item, BaseException) for item in results)


def test_pointer_analysis_tampering_is_rejected(selection_context):
    ctx = selection_context
    ctx.publish_transfer()
    with ctx.store.engine.begin() as connection:
        connection.execute(
            case_projection.update()
            .where(case_projection.c.case_id == ctx.case.case_id)
            .values(current_analysis_hash="e" * 64)
        )
    with ctx.store.uow_factory() as uow, pytest.raises(PersistenceIntegrityError):
        uow.proposals.get_state(ctx.case.case_id)


def test_explicit_initial_and_replacement_rollbacks_preserve_current_state(
    selection_context,
):
    ctx = selection_context
    initial = receipt(
        ctx,
        "RL-OPTION-COMBINED",
        "rollback-initial",
        "rollback-review",
        ctx.state().token,
    )
    before = counts(ctx.store)
    with ctx.store.uow_factory() as uow:
        pending = submit_finance_review(
            review_id=initial.selection.finance_review_id,
            proposal=initial.selection.proposal,
            actor=initial.selection.submitted_by,
            now=initial.selection.submitted_at,
        )
        uow.finance_reviews.append(
            pending,
            expected_revision=None,
            idempotency_key="pending:rollback-initial",
            request_fingerprint=fingerprint(pending),
        )
        uow.proposals.publish(initial)
        uow.rollback()
    assert counts(ctx.store) == before
    assert ctx.state().selection is None

    original = ctx.publish_combined()
    original_state, original_counts = ctx.state(), counts(ctx.store)
    replacement = receipt(
        ctx,
        "RL-OPTION-TRANSFER",
        "rollback-replacement",
        None,
        original_state.token,
        submitted_at=original.submitted_at + timedelta(minutes=1),
    )
    with ctx.store.uow_factory() as uow:
        uow.proposals.publish(replacement)
        uow.rollback()
    assert counts(ctx.store) == original_counts
    assert ctx.state() == original_state


def test_backward_supersession_rolls_back_new_selection(selection_context):
    ctx = selection_context
    original = ctx.publish_combined()
    with ctx.store.uow_factory() as uow:
        state = uow.proposals.get_state(ctx.case.case_id)
        approved = resolve_finance_review(
            review=state.review,
            current_proposal=state.selection.proposal,
            actor=ctx.taylor,
            approved=True,
            reason="approved",
            now=original.submitted_at + timedelta(minutes=5),
        )
        uow.finance_reviews.append(
            approved,
            expected_revision=1,
            idempotency_key="approved-before-backward",
            request_fingerprint="f" * 64,
        )
        uow.proposals.guard_current(ctx.case.case_id, expected=state.token)
        uow.commit()
    before_state, before_counts = ctx.state(), counts(ctx.store)
    replacement = receipt(
        ctx,
        "RL-OPTION-COMBINED",
        "backward",
        "backward-review",
        before_state.token,
        submitted_at=original.submitted_at + timedelta(minutes=4),
    )
    assert replacement.selection.finance_review_id == "backward-review"
    assert before_counts[case_proposal_selections.name] == 1
    assert before_counts[finance_review_revisions.name] == 2
    with pytest.raises(ValueError):
        persist(ctx, replacement)
    assert counts(ctx.store) == before_counts
    after_state = ctx.state()
    assert after_state == before_state
    assert after_state.token.selection_id == original.selection_id


def test_sqlite_contention_classifier_rejects_unrelated_operational_error():
    unrelated = sqlite3.OperationalError("unrelated failure")
    unrelated.sqlite_errorcode = sqlite3.SQLITE_ERROR
    error = OperationalError("statement", {}, unrelated)
    assert not _is_sqlite_lock_contention(error)


def test_sqlite_contention_classifier_accepts_busy_and_extended_locked_codes():
    for code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED | (1 << 8)):
        original = sqlite3.OperationalError("contention")
        original.sqlite_errorcode = code
        assert _is_sqlite_lock_contention(OperationalError("statement", {}, original))


def test_failed_analysis_invalidation_rolls_back_all_rows(
    selection_context, monkeypatch
):
    import services.persistence.proposals as module

    ctx = selection_context
    ctx.publish_combined()
    before_state, before_counts = ctx.state(), counts(ctx.store)
    replacement = build_analysis(ctx.case, ctx.snapshot, "RL-ANALYSIS-FAILED")

    def fail_cas(*args, **kwargs):
        raise StaleProposal("injected analysis CAS failure")

    monkeypatch.setattr(module, "_cas_projection", fail_cas)
    with pytest.raises(StaleProposal):
        ctx.store.save_analysis(replacement)
    assert counts(ctx.store) == before_counts
    assert ctx.state() == before_state
