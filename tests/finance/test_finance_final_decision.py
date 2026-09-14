import json
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier, local
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

import services.persistence.proposals as proposals_module
from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import (
    CorpusScope,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
)
from data.domain.evidence import IdentitySource
from data.domain.execution import ActionPlanningRequested
from data.domain.finance import FinanceReviewStatus
from data.domain.finance_decisions import ProposalApprovalEvidence
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import DecisionPolicyViolation, DecisionService
from services.finance.contracts import (
    FinalizeProposalCommand,
    ResolveFinanceCommand,
    SubmitProposalCommand,
)
from services.finance.decisions import (
    FinanceDecisionService,
    FinanceFinalizationConflict,
    FinanceFinalizationInvalid,
)
from services.finance.identity import BoundFinanceActors, FinancePermissionDenied
from services.finance.service import FinanceCommandConflict, FinanceService
from services.persistence.finance_reviews import FinanceReviewRevisionConflict
from services.persistence.ports import UnitOfWork
from services.persistence.proposals import StaleProposal
from services.persistence.sqlite import sqlite_store
from services.persistence.store import PersistenceIntegrityError, serialize_model
from services.persistence.tables import (
    approval_satisfactions,
    decisions,
    finance_review_revisions,
    outbox_events,
)

START = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
SUBMITTED = datetime.fromisoformat("2026-09-01T14:02:00+00:00")
REVIEWED = SUBMITTED + timedelta(minutes=1)
FINALIZED = REVIEWED + timedelta(minutes=1)


@pytest.fixture
def final_ctx(tmp_path):
    tenant = "11111111-1111-4111-8111-111111111111"
    alex_id = "22222222-2222-4222-8222-222222222222"
    taylor_id = "33333333-3333-4333-8333-333333333333"
    actors = BoundFinanceActors(
        tenant_id=UUID(tenant),
        alex_object_id=UUID(alex_id),
        taylor_object_id=UUID(taylor_id),
    )
    alex = IdentitySnapshot(
        persona_id="RL-PERSONA-ALEX",
        source_id="RL-ENTRA-ALEX",
        identity_source=IdentitySource.ENTRA,
        tenant_id=tenant,
        object_id=alex_id,
        effective_roles=("material_planner", "response_approver"),
    )
    taylor = IdentitySnapshot(
        persona_id="RL-PERSONA-TAYLOR",
        source_id="RL-ENTRA-TAYLOR",
        identity_source=IdentitySource.ENTRA,
        tenant_id=tenant,
        object_id=taylor_id,
        effective_roles=("finance_approver",),
    )
    store = sqlite_store(f"sqlite:///{tmp_path / 'final.db'}")
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-FINAL",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    analysis = analyze_case(
        AnalyzeCaseCommand(
            analysis_id="RL-ANALYSIS-FINAL",
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot, analysis_id="RL-ANALYSIS-FINAL", retrieved_at=START
            ),
            analysis_started_at=START,
            created_at=START,
            calculation_version="rl001-options-v1",
        )
    )
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    times = iter(SUBMITTED + timedelta(minutes=index) for index in range(20))
    factory = cast(Callable[[], UnitOfWork], store.uow_factory)
    finance = FinanceService(factory, actors=actors, clock=lambda: next(times))
    finalizer = FinanceDecisionService(factory, actors=actors, clock=lambda: FINALIZED)
    yield SimpleNamespace(
        store=store,
        case=case,
        analysis=analysis,
        snapshot=snapshot,
        actors=actors,
        alex=alex,
        taylor=taylor,
        finance=finance,
        finalizer=finalizer,
    )
    store.engine.dispose()


def current(ctx):
    with ctx.store.uow_factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)


def submit(ctx, option="RL-OPTION-COMBINED"):
    return ctx.finance.submit(
        SubmitProposalCommand(
            case_id=ctx.case.case_id,
            option_id=option,
            expected=current(ctx).token,
            idempotency_key=f"submit-{option}",
        ),
        ctx.alex,
    )


def approve(ctx):
    selected = submit(ctx)
    state = current(ctx)
    resolved = ctx.finance.resolve(
        ResolveFinanceCommand(
            review_id=state.review.review_id,
            expected=state.token,
            expected_review_revision=state.review_revision,
            approved=True,
            reason=None,
            idempotency_key="approve",
        ),
        ctx.taylor,
    )
    return selected, resolved


def command(ctx, kind=DecisionKind.APPROVED, *, key="final"):
    return FinalizeProposalCommand(
        case_id=ctx.case.case_id,
        expected=current(ctx).token,
        kind=kind,
        idempotency_key=key,
        rejection_reason="reject" if kind is DecisionKind.REJECTED else None,
    )


def row_counts(ctx):
    with ctx.store.engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (
                decisions,
                approval_satisfactions,
                outbox_events,
                finance_review_revisions,
            )
        )


def test_high_cost_approval_records_exact_historical_evidence(final_ctx):
    selected, resolved = approve(final_ctx)
    decision = final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    assert decision.proposal_approval.selection == selected.selection
    assert decision.proposal_approval.review == resolved.review
    assert decision.proposal_approval.review_revision == resolved.review_revision
    assert {item.role for item in decision.approval_satisfactions} == {
        "material_planner"
    }


def test_low_cost_approval_has_no_finance_review(final_ctx):
    selected = submit(final_ctx, "RL-OPTION-TRANSFER")
    decision = final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    assert decision.proposal_approval.selection == selected.selection
    assert decision.proposal_approval.review is None


@pytest.mark.parametrize(
    ("cost", "needs_review"), (("20000.00", False), ("20000.01", True))
)
def test_finalization_uses_exact_saved_cost_threshold(
    final_ctx, tmp_path, cost, needs_review
):
    case, snapshot = instantiate_rl001(
        case_id=f"RL-CASE-COST-{cost}",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    assert snapshot.alpha_expedite is not None
    snapshot = snapshot.model_copy(
        update={
            "alpha_expedite": snapshot.alpha_expedite.model_copy(
                update={"quantity": 1, "incremental_cost_per_unit": Decimal(cost)}
            )
        }
    )
    analysis_id = f"RL-ANALYSIS-COST-{cost}"
    analysis = analyze_case(
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
    store = sqlite_store(f"sqlite:///{tmp_path / ('cost-' + cost + '.db')}")
    try:
        store.create_case(case, snapshot)
        store.save_analysis(analysis)
        factory = cast(Callable[[], UnitOfWork], store.uow_factory)
        times = iter((SUBMITTED, REVIEWED))
        finance = FinanceService(
            factory, actors=final_ctx.actors, clock=lambda: next(times)
        )
        selected = finance.submit(
            SubmitProposalCommand(
                case_id=case.case_id,
                option_id="RL-OPTION-EXPEDITE",
                expected=finance.status(case.case_id, final_ctx.alex).token,
                idempotency_key="cost-submit",
            ),
            final_ctx.alex,
        )
        if needs_review:
            status = finance.status(case.case_id, final_ctx.alex)
            assert status.review is not None
            assert status.review_revision is not None
            finance.resolve(
                ResolveFinanceCommand(
                    review_id=status.review.review_id,
                    expected=status.token,
                    expected_review_revision=status.review_revision,
                    approved=True,
                    reason=None,
                    idempotency_key="cost-resolve",
                ),
                final_ctx.taylor,
            )
        status = finance.status(case.case_id, final_ctx.alex)
        decision = FinanceDecisionService(
            factory, actors=final_ctx.actors, clock=lambda: FINALIZED
        ).finalize(
            FinalizeProposalCommand(
                case_id=case.case_id,
                expected=status.token,
                kind=DecisionKind.APPROVED,
                idempotency_key="cost-final",
            ),
            final_ctx.alex,
        )
        assert selected.selection.proposal.response_cost == Decimal(cost)
        assert decision.proposal_approval is not None
        assert (decision.proposal_approval.review is not None) is needs_review
    finally:
        store.engine.dispose()


def test_rejection_atomically_withdraws_pending_review(final_ctx):
    selected = submit(final_ctx)
    decision = final_ctx.finalizer.finalize(
        command(final_ctx, DecisionKind.REJECTED), final_ctx.alex
    )
    assert decision.proposal_approval is None
    assert current(final_ctx).selection is None
    with final_ctx.store.uow_factory() as uow:
        review, revision = uow.finance_reviews.get_latest(selected.review.review_id)
    assert review.status.value == "superseded"
    assert revision == 2


def test_replay_returns_original_without_clock(final_ctx):
    approve(final_ctx)
    request = command(final_ctx)
    original = final_ctx.finalizer.finalize(request, final_ctx.alex)
    replay = FinanceDecisionService(
        cast(Callable[[], UnitOfWork], final_ctx.store.uow_factory),
        actors=final_ctx.finalizer._actors,
        clock=lambda: (_ for _ in ()).throw(AssertionError("clock read")),
    )
    assert replay.finalize(request, final_ctx.alex) == original


def test_legacy_service_rejects_independent_case(final_ctx):
    with pytest.raises(
        DecisionPolicyViolation, match="INDEPENDENT_FINANCE_REQUIRED"
    ) as raised:
        DecisionService(final_ctx.store.uow_factory).record(
            RecordDecisionCommand(
                case_id=final_ctx.case.case_id,
                analysis_id=final_ctx.analysis.analysis_id,
                selected_option_id=None,
                kind=DecisionKind.REJECTED,
                idempotency_key="legacy",
                rejection_reason="reject",
            ),
            final_ctx.alex,
        )
    assert raised.value.code == "INDEPENDENT_FINANCE_REQUIRED"


def test_frozen_legacy_decision_json_is_byte_identical():
    fixture = __import__("json").loads(
        Path("tests/finance/fixtures/legacy-policy.json").read_text()
    )
    from data.domain.decisions import Decision

    decision = Decision.model_validate_json(fixture["decision"])
    assert decision.proposal_approval is None
    assert serialize_model(decision) == fixture["decision"]


def test_evidence_rejects_malformed_revision_and_nonapproved_review(final_ctx):
    selected, resolved = approve(final_ctx)
    valid = {
        "selection": selected.selection,
        "review": resolved.review,
        "review_revision": resolved.review_revision,
    }
    for changed in (
        {"review_revision": 1},
        {"review_revision": None},
        {
            "review": resolved.review.model_copy(
                update={"status": FinanceReviewStatus.REJECTED, "reason": "no"}
            )
        },
    ):
        with pytest.raises(ValidationError):
            ProposalApprovalEvidence.model_validate({**valid, **changed})


@pytest.mark.parametrize(
    ("target", "field", "value"),
    (
        ("submitter", "identity_source", "fixture"),
        ("submitter", "effective_roles", ("material_planner",)),
        ("submitter", "object_id", "not-a-uuid"),
        ("reviewer", "persona_id", "RL-PERSONA-ALEX"),
        ("reviewer", "effective_roles", ("finance_approver", "extra")),
        ("reviewer", "tenant_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("reviewer", "object_id", "22222222-2222-4222-8222-222222222222"),
    ),
)
def test_evidence_requires_pure_exact_actor_shapes(final_ctx, target, field, value):
    selected, resolved = approve(final_ctx)
    selection = selected.selection
    review = resolved.review
    if target == "submitter":
        selection = selection.model_copy(
            update={
                "submitted_by": selection.submitted_by.model_copy(update={field: value})
            }
        )
    else:
        review = review.model_copy(
            update={"reviewed_by": review.reviewed_by.model_copy(update={field: value})}
        )
    with pytest.raises(ValidationError):
        ProposalApprovalEvidence(
            selection=selection,
            review=review,
            review_revision=resolved.review_revision,
        )


def test_high_cost_pending_review_cannot_finalize_and_writes_nothing(final_ctx):
    submit(final_ctx)
    before = row_counts(final_ctx)
    with pytest.raises(FinanceFinalizationInvalid, match="lacks Finance approval"):
        final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    assert row_counts(final_ctx) == before


def test_same_key_changed_command_conflicts(final_ctx):
    approve(final_ctx)
    request = command(final_ctx)
    final_ctx.finalizer.finalize(request, final_ctx.alex)
    changed = request.model_copy(
        update={
            "expected": request.expected.model_copy(
                update={"generation": request.expected.generation + 1}
            )
        }
    )
    with pytest.raises(FinanceFinalizationConflict):
        final_ctx.finalizer.finalize(changed, final_ctx.alex)


def test_fresh_key_cannot_finalize_same_selection_from_history(final_ctx):
    approve(final_ctx)
    final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    with pytest.raises(FinanceFinalizationConflict, match="already finalized"):
        final_ctx.finalizer.finalize(
            command(final_ctx, key="another-finalization"), final_ctx.alex
        )


def test_exact_alex_is_required_before_uow(final_ctx):
    denied = final_ctx.alex.model_copy(
        update={"object_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
    )
    service = FinanceDecisionService(
        lambda: (_ for _ in ()).throw(AssertionError("opened UoW")),
        actors=final_ctx.finalizer._actors,
    )
    with pytest.raises(FinancePermissionDenied):
        service.finalize(command(final_ctx, DecisionKind.REJECTED), denied)


def test_unauthorized_committed_replay_denied_before_uow(final_ctx):
    approve(final_ctx)
    request = command(final_ctx)
    original = final_ctx.finalizer.finalize(request, final_ctx.alex)
    denied = final_ctx.alex.model_copy(
        update={"object_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
    )
    service = FinanceDecisionService(
        lambda: (_ for _ in ()).throw(AssertionError("opened UoW")),
        actors=final_ctx.actors,
        clock=lambda: (_ for _ in ()).throw(AssertionError("read clock")),
    )
    with pytest.raises(FinancePermissionDenied):
        service.finalize(request, denied)
    assert final_ctx.finalizer.finalize(request, final_ctx.alex) == original


def test_refreshed_alex_replays_original_after_later_analysis_and_selection(final_ctx):
    approve(final_ctx)
    request = command(final_ctx)
    original = final_ctx.finalizer.finalize(request, final_ctx.alex)
    later_id = "RL-ANALYSIS-AFTER-FINAL"
    later = analyze_case(
        AnalyzeCaseCommand(
            analysis_id=later_id,
            case=final_ctx.case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=final_ctx.snapshot,
            evidence_items=build_rl001_evidence(
                final_ctx.snapshot, analysis_id=later_id, retrieved_at=FINALIZED
            ),
            analysis_started_at=FINALIZED,
            created_at=FINALIZED,
            calculation_version="rl001-options-v1",
        )
    )
    final_ctx.store.save_analysis(later)
    submit(final_ctx, "RL-OPTION-TRANSFER")
    refreshed = final_ctx.alex.model_copy(
        update={
            "tenant_id": UUID(final_ctx.alex.tenant_id).hex,
            "object_id": UUID(final_ctx.alex.object_id).hex,
            "display_name": "Refreshed Alex",
        }
    )
    service = FinanceDecisionService(
        cast(Callable[[], UnitOfWork], final_ctx.store.uow_factory),
        actors=final_ctx.actors,
        clock=lambda: (_ for _ in ()).throw(AssertionError("read clock")),
    )
    assert service.finalize(request, refreshed) == original


@pytest.mark.parametrize(
    ("state", "option"),
    (("pending", "RL-OPTION-COMBINED"), ("low", "RL-OPTION-TRANSFER")),
)
def test_rejection_denies_foreign_current_selection_owner_before_mutation(
    final_ctx, state, option
):
    other_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    other = final_ctx.alex.model_copy(update={"object_id": other_id})
    foreign_actors = BoundFinanceActors(
        tenant_id=final_ctx.actors.tenant_id,
        alex_object_id=UUID(other_id),
        taylor_object_id=final_ctx.actors.taylor_object_id,
    )
    foreign = FinanceService(
        cast(Callable[[], UnitOfWork], final_ctx.store.uow_factory),
        actors=foreign_actors,
        clock=lambda: SUBMITTED,
    )
    foreign.submit(
        SubmitProposalCommand(
            case_id=final_ctx.case.case_id,
            option_id=option,
            expected=current(final_ctx).token,
            idempotency_key=f"foreign-{state}",
        ),
        other,
    )
    before = row_counts(final_ctx), current(final_ctx)
    with pytest.raises(FinancePermissionDenied):
        final_ctx.finalizer.finalize(
            command(final_ctx, DecisionKind.REJECTED, key=f"reject-{state}"),
            final_ctx.alex,
        )
    assert (row_counts(final_ctx), current(final_ctx)) == before


def test_low_cost_backward_approval_and_withdrawal_roll_back(final_ctx):
    selected = submit(final_ctx, "RL-OPTION-TRANSFER")
    before = row_counts(final_ctx), current(final_ctx)
    service = FinanceDecisionService(
        cast(Callable[[], UnitOfWork], final_ctx.store.uow_factory),
        actors=final_ctx.finalizer._actors,
        clock=lambda: selected.selection.submitted_at - timedelta(seconds=1),
    )
    with pytest.raises(ValueError):
        service.finalize(command(final_ctx), final_ctx.alex)
    assert (row_counts(final_ctx), current(final_ctx)) == before
    with pytest.raises(ValueError, match="precede proposal submission"):
        service.finalize(command(final_ctx, DecisionKind.REJECTED), final_ctx.alex)
    assert (row_counts(final_ctx), current(final_ctx)) == before


def test_high_cost_approval_before_review_time_rolls_back(final_ctx):
    _, resolved = approve(final_ctx)
    before = row_counts(final_ctx), current(final_ctx)
    service = FinanceDecisionService(
        cast(Callable[[], UnitOfWork], final_ctx.store.uow_factory),
        actors=final_ctx.actors,
        clock=lambda: resolved.review.reviewed_at - timedelta(seconds=1),
    )
    with pytest.raises(ValidationError):
        service.finalize(command(final_ctx), final_ctx.alex)
    assert (row_counts(final_ctx), current(final_ctx)) == before


@pytest.mark.parametrize("kind", (DecisionKind.APPROVED, DecisionKind.REJECTED))
def test_naive_server_clock_rejected_for_both_kinds(final_ctx, kind):
    if kind is DecisionKind.APPROVED:
        approve(final_ctx)
    service = FinanceDecisionService(
        cast(Callable[[], UnitOfWork], final_ctx.store.uow_factory),
        actors=final_ctx.actors,
        clock=lambda: datetime.fromisoformat("2026-09-01T00:00:00"),
    )
    with pytest.raises(FinanceFinalizationInvalid, match="timezone-aware"):
        service.finalize(command(final_ctx, kind), final_ctx.alex)


@pytest.mark.parametrize(
    ("kind", "seam"),
    (
        (DecisionKind.APPROVED, "decision"),
        (DecisionKind.APPROVED, "outbox"),
        (DecisionKind.REJECTED, "decision"),
    ),
)
def test_insert_failure_rolls_back_guard_withdraw_rows_and_projection(
    final_ctx, kind, seam
):
    if kind is DecisionKind.APPROVED:
        approve(final_ctx)
    else:
        submit(final_ctx)
    before = row_counts(final_ctx), current(final_ctx)
    injected = IntegrityError("injected", {}, Exception("injected"))

    def fail():
        raise injected

    kwargs = (
        {"before_decision_insert": fail}
        if seam == "decision"
        else {"before_outbox_insert": fail}
    )
    factory = cast(
        Callable[[], UnitOfWork], lambda: final_ctx.store.uow_factory(**kwargs)
    )
    service = FinanceDecisionService(
        factory, actors=final_ctx.finalizer._actors, clock=lambda: FINALIZED
    )
    with pytest.raises(IntegrityError) as raised:
        service.finalize(command(final_ctx, kind), final_ctx.alex)
    assert raised.value is injected
    assert (row_counts(final_ctx), current(final_ctx)) == before


@pytest.mark.parametrize(
    "mutation", ("selection_snapshot", "review_snapshot", "review_revision")
)
def test_persisted_proposal_evidence_corruption_is_rejected(final_ctx, mutation):
    approve(final_ctx)
    decision = final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    with final_ctx.store.engine.begin() as connection:
        raw = connection.scalar(
            select(decisions.c.payload_json).where(
                decisions.c.decision_id == decision.decision_id
            )
        )
        payload = json.loads(raw)
        evidence = payload["proposal_approval"]
        if mutation == "selection_snapshot":
            evidence["selection"]["submitted_by"]["display_name"] = "tampered"
        elif mutation == "review_snapshot":
            evidence["review"]["reviewed_by"]["display_name"] = "tampered"
        else:
            evidence["review_revision"] += 1
        connection.execute(
            update(decisions)
            .where(decisions.c.decision_id == decision.decision_id)
            .values(
                payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":"))
            )
        )
    checks = (
        lambda uow: uow.decisions.get(decision.decision_id),
        lambda uow: uow.decisions.list_for_case(decision.case_id),
        lambda uow: uow.execution.insert_outbox(
            ActionPlanningRequested.for_decision(decision)
        ),
    )
    for check in checks:
        with (
            pytest.raises(PersistenceIntegrityError),
            final_ctx.store.uow_factory() as uow,
        ):
            check(uow)


def _sqlite_lock_or_raise(error: OperationalError) -> str:
    code = getattr(error.orig, "sqlite_errorcode", None)
    if code is None or (code & 0xFF) not in (
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    ):
        raise error
    return "lock"


@pytest.mark.parametrize(
    "operation",
    ("identical", "different_key", "proposal_publish", "analysis_save", "resolve"),
)
def test_file_sqlite_finalization_races_at_first_state_read(
    final_ctx, monkeypatch, operation
):
    if operation == "resolve":
        submit(final_ctx)
        primary = command(final_ctx, DecisionKind.REJECTED, key="race-reject")
        state = current(final_ctx)
        other_call = lambda: final_ctx.finance.resolve(
            ResolveFinanceCommand(
                review_id=state.review.review_id,
                expected=state.token,
                expected_review_revision=state.review_revision,
                approved=True,
                reason=None,
                idempotency_key="race-resolve",
            ),
            final_ctx.taylor,
        )
    else:
        approve(final_ctx)
        primary = command(final_ctx, key="race-final")
        if operation == "identical":
            other_call = lambda: final_ctx.finalizer.finalize(primary, final_ctx.alex)
        elif operation == "different_key":
            other = primary.model_copy(update={"idempotency_key": "race-other"})
            other_call = lambda: final_ctx.finalizer.finalize(other, final_ctx.alex)
        elif operation == "proposal_publish":
            replacement = SubmitProposalCommand(
                case_id=final_ctx.case.case_id,
                option_id="RL-OPTION-TRANSFER",
                expected=primary.expected,
                idempotency_key="race-publish",
            )
            other_call = lambda: final_ctx.finance.submit(replacement, final_ctx.alex)
        else:
            later_id = "RL-ANALYSIS-RACE-LATER"
            later = analyze_case(
                AnalyzeCaseCommand(
                    analysis_id=later_id,
                    case=final_ctx.case,
                    corpus=CorpusScope.DEMO_CORPUS,
                    operational_snapshot=final_ctx.snapshot,
                    evidence_items=build_rl001_evidence(
                        final_ctx.snapshot,
                        analysis_id=later_id,
                        retrieved_at=FINALIZED,
                    ),
                    analysis_started_at=FINALIZED,
                    created_at=FINALIZED,
                    calculation_version="rl001-options-v1",
                )
            )
            other_call = lambda: final_ctx.store.save_analysis(later)

    barrier = Barrier(2, timeout=5)
    thread_state = local()
    crossed: set[int] = set()
    original_get_state = proposals_module.SqlAlchemyProposalRepository.get_state

    def synchronized_state(repository, case_id):
        value = original_get_state(repository, case_id)
        if getattr(thread_state, "first", False):
            thread_state.first = False
            crossed.add(id(repository._connection))
            barrier.wait()
        return value

    monkeypatch.setattr(
        proposals_module.SqlAlchemyProposalRepository,
        "get_state",
        synchronized_state,
    )

    def invoke(call):
        try:
            thread_state.first = True
            return call()
        except OperationalError as error:
            return _sqlite_lock_or_raise(error)
        except (
            FinanceCommandConflict,
            FinanceFinalizationConflict,
            FinanceReviewRevisionConflict,
            StaleProposal,
        ) as error:
            return error
        except BaseException:
            barrier.abort()
            raise

    calls = (lambda: final_ctx.finalizer.finalize(primary, final_ctx.alex), other_call)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(invoke, item) for item in calls]
        results = [future.result(timeout=15) for future in futures]
    assert len(crossed) == 2
    monkeypatch.undo()
    with final_ctx.store.uow_factory() as uow:
        stored = uow.decisions.list_for_case(final_ctx.case.case_id)
        durable_state = uow.proposals.get_state(final_ctx.case.case_id)
        projection = uow.cases.get_projection(final_ctx.case.case_id)
    if operation == "identical":
        committed = [item for item in results if hasattr(item, "decision_id")]
        assert committed
        original = final_ctx.finalizer.finalize(primary, final_ctx.alex)
        assert stored == (original,)
        assert all(item == original for item in committed)
        assert projection.current_decision_id == original.decision_id
        assert durable_state.token.selection_id == primary.expected.selection_id
    elif operation == "different_key":
        assert len(stored) == 1
        assert projection.current_decision_id == stored[0].decision_id
        assert durable_state.token.selection_id == primary.expected.selection_id
    elif operation == "proposal_publish":
        if stored:
            assert projection.current_decision_id == stored[0].decision_id
            assert durable_state.token.selection_id == primary.expected.selection_id
            assert durable_state.review is not None
            assert durable_state.review.status is FinanceReviewStatus.APPROVED
        else:
            assert durable_state.selection is not None
            assert durable_state.selection.proposal.option_id == "RL-OPTION-TRANSFER"
            assert durable_state.review is None
            assert projection.current_decision_id is None
    elif operation == "analysis_save":
        if stored:
            assert projection.current_decision_id == stored[0].decision_id
            assert durable_state.token.analysis_id == primary.expected.analysis_id
            assert durable_state.token.selection_id == primary.expected.selection_id
        else:
            assert durable_state.token.analysis_id == "RL-ANALYSIS-RACE-LATER"
            assert durable_state.token.selection_id is None
            assert projection.current_decision_id is None
    else:
        if stored:
            assert stored[0].kind is DecisionKind.REJECTED
            assert durable_state.selection is None
            assert durable_state.review is None
            assert projection.current_decision_id == stored[0].decision_id
        else:
            assert durable_state.selection is not None
            assert durable_state.review is not None
            assert durable_state.review.status is FinanceReviewStatus.APPROVED
            assert durable_state.review_revision == 2
            assert projection.current_decision_id is None
    if operation != "identical":
        assert any(
            not isinstance(item, Exception) and item != "lock" for item in results
        )
    approved_count = sum(item.kind is DecisionKind.APPROVED for item in stored)
    counts = row_counts(final_ctx)
    assert counts[1] == approved_count
    assert counts[2] == approved_count
