import json
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier, local
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

import services.persistence.proposals as proposals_module
from data.domain import CasePurpose, RuntimeMode
from data.domain.analysis import AnalysisResponseOptionMaterial
from data.domain.cases import WorkflowVersion
from data.domain.decisions import (
    ApprovalSatisfaction,
    ApprovalTarget,
    CorpusScope,
    Decision,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
    StandingAuthorization,
)
from data.domain.evidence import IdentitySource
from data.domain.execution import ActionPlanningRequested
from data.domain.finance import FinanceReviewStatus
from data.domain.finance_decisions import ProposalApprovalEvidence
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import (
    DecisionPolicy,
    DecisionPolicyViolation,
    DecisionService,
)
from services.finance.contracts import (
    FinalizeProposalCommand,
    ResolutionResult,
    ResolveFinanceCommand,
    SubmissionResult,
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
from services.persistence.sqlite import SqliteStore, build_sqlite_engine, sqlite_store
from services.persistence.store import (
    PersistenceIntegrityError,
    RecordNotFound,
    serialize_model,
)
from services.persistence.tables import (
    analysis_versions,
    approval_satisfactions,
    case_projection,
    case_proposal_selections,
    decisions,
    evidence_items,
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
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
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


def submit(ctx, option="RL-OPTION-COMBINED", *, key=None):
    return ctx.finance.submit(
        SubmitProposalCommand(
            case_id=ctx.case.case_id,
            option_id=option,
            expected=current(ctx).token,
            idempotency_key=key or f"submit-{option}",
        ),
        ctx.alex,
    )


def approve(ctx, option="RL-OPTION-COMBINED"):
    selected = submit(ctx, option)
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


def journal_snapshot(ctx):
    tables = {
        "selections": case_proposal_selections,
        "reviews": finance_review_revisions,
        "analyses": analysis_versions,
        "evidence": evidence_items,
        "decisions": decisions,
        "satisfactions": approval_satisfactions,
        "events": outbox_events,
    }
    with ctx.store.engine.connect() as connection:
        rows: dict[str, Any] = {
            name: tuple(
                sorted(
                    (dict(row) for row in connection.execute(select(table)).mappings()),
                    key=repr,
                )
            )
            for name, table in tables.items()
        }
        rows["projection"] = dict(
            connection.execute(
                select(case_projection).where(
                    case_projection.c.case_id == ctx.case.case_id
                )
            )
            .mappings()
            .one()
        )
    return rows


def test_high_cost_approval_records_exact_historical_evidence(final_ctx):
    selected, resolved = approve(final_ctx)
    before_generation = current(final_ctx).token.generation
    decision = final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    assert decision.proposal_approval.selection == selected.selection
    assert decision.proposal_approval.review == resolved.review
    assert decision.proposal_approval.review_revision == resolved.review_revision
    assert {item.role for item in decision.approval_satisfactions} == {
        "material_planner"
    }
    assert current(final_ctx).token.generation == before_generation + 1
    assert row_counts(final_ctx)[0:3] == (1, 1, 1)


@pytest.mark.parametrize("option", ("RL-OPTION-TRANSFER", "RL-OPTION-RESEQUENCE"))
def test_low_cost_approval_has_no_finance_review(final_ctx, option):
    selected = submit(final_ctx, option)
    before_generation = current(final_ctx).token.generation
    decision = final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    assert decision.proposal_approval.selection == selected.selection
    assert decision.proposal_approval.review is None
    assert current(final_ctx).token.generation == before_generation + 1
    assert row_counts(final_ctx)[0:3] == (1, 1, 1)


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


@pytest.mark.parametrize("selection_state", ("none", "pending", "approved"))
def test_rejection_withdraws_each_prefinalization_state_atomically(
    final_ctx, selection_state
):
    selected = None
    if selection_state == "pending":
        selected = submit(final_ctx)
    elif selection_state == "approved":
        selected, _ = approve(final_ctx)
    before = current(final_ctx)
    decision = final_ctx.finalizer.finalize(
        command(final_ctx, DecisionKind.REJECTED), final_ctx.alex
    )
    assert decision.proposal_approval is None
    after = current(final_ctx)
    assert after.selection is None
    assert after.token.generation == before.token.generation + 1
    assert after.token.analysis_id == before.token.analysis_id
    assert row_counts(final_ctx)[0:3] == (1, 0, 0)
    if selected is not None:
        with final_ctx.store.uow_factory() as uow:
            review, revision = uow.finance_reviews.get_latest(selected.review.review_id)
        assert review.status.value == "superseded"
        assert revision == (3 if selection_state == "approved" else 2)


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


@pytest.mark.parametrize("kind", (DecisionKind.APPROVED, DecisionKind.REJECTED))
def test_legacy_service_rejects_independent_case_for_both_kinds(final_ctx, kind):
    selected_option_id = None
    if kind is DecisionKind.APPROVED:
        selected_option_id = submit(
            final_ctx, "RL-OPTION-TRANSFER"
        ).selection.proposal.option_id
    with pytest.raises(
        DecisionPolicyViolation, match="INDEPENDENT_FINANCE_REQUIRED"
    ) as raised:
        DecisionService(final_ctx.store.uow_factory).record(
            RecordDecisionCommand(
                case_id=final_ctx.case.case_id,
                analysis_id=final_ctx.analysis.analysis_id,
                selected_option_id=selected_option_id,
                kind=kind,
                idempotency_key=f"legacy-{kind.value}",
                rejection_reason=("reject" if kind is DecisionKind.REJECTED else None),
            ),
            final_ctx.alex,
        )
    assert raised.value.code == "INDEPENDENT_FINANCE_REQUIRED"


def test_legacy_service_rejects_existing_independent_receipt(final_ctx):
    approve(final_ctx)
    request = command(final_ctx)
    decision = final_ctx.finalizer.finalize(request, final_ctx.alex)
    legacy = RecordDecisionCommand(
        case_id=decision.case_id,
        analysis_id=decision.analysis_id,
        selected_option_id=decision.selected_option_id,
        kind=decision.kind,
        idempotency_key=decision.idempotency_key,
    )
    with pytest.raises(DecisionPolicyViolation) as raised:
        DecisionService(final_ctx.store.uow_factory).record(legacy, final_ctx.alex)
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
        {"review_revision": True},
        {"review_revision": "2"},
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


def independent_policy_inputs(ctx):
    selected, resolved = approve(ctx, "RL-OPTION-EXPEDITE")
    with ctx.store.uow_factory() as uow:
        projection = uow.cases.get_projection(ctx.case.case_id)
        analysis = uow.cases.get_analysis(ctx.analysis.analysis_id)
    evidence = ProposalApprovalEvidence(
        selection=selected.selection,
        review=resolved.review,
        review_revision=resolved.review_revision,
    )
    option = next(
        item
        for item in analysis.response_options
        if item.option_id == selected.selection.proposal.option_id
    )
    assert option.predicted is not None
    target = ApprovalTarget(
        case=ctx.case,
        corpus=analysis.material.corpus,
        scenario_effective_time=ctx.case.scenario_effective_time,
        total_response_cost=option.predicted.response_cost,
        requested_side_effects=option.requested_side_effects,
    )
    injected = ApprovalSatisfaction.from_authorization(
        analysis.analysis_id,
        option,
        StandingAuthorization.taylor_rl001(),
        target,
    )
    analysis = analysis.model_copy(
        update={"approval_satisfactions": (*analysis.approval_satisfactions, injected)}
    )
    record = RecordDecisionCommand(
        case_id=ctx.case.case_id,
        analysis_id=analysis.analysis_id,
        selected_option_id=selected.selection.proposal.option_id,
        kind=DecisionKind.APPROVED,
        idempotency_key="policy",
    )
    return record, projection, analysis, evidence


def test_independent_policy_ignores_actual_injected_standing_finance(final_ctx):
    record, projection, analysis, evidence = independent_policy_inputs(final_ctx)
    assert any(
        item.role == "finance_approver" for item in analysis.approval_satisfactions
    )
    result = DecisionPolicy().authorize_independent_and_materialize(
        record, final_ctx.alex, final_ctx.case, projection, analysis, evidence
    )
    assert {item.role for item in result} == {"material_planner"}
    with pytest.raises(DecisionPolicyViolation, match="proposal evidence"):
        DecisionPolicy().authorize_independent_and_materialize(
            record, final_ctx.alex, final_ctx.case, projection, analysis, None
        )


def test_independent_policy_preserves_missing_nonfinance_prerequisite(final_ctx):
    record, projection, analysis, evidence = independent_policy_inputs(final_ctx)
    option = next(
        item
        for item in analysis.response_options
        if item.option_id == record.selected_option_id
    )
    changed = option.model_copy(
        update={"prerequisite_roles": (*option.prerequisite_roles, "quality_approver")}
    )
    changed_analysis = analysis.model_copy(
        update={
            "response_options": tuple(
                changed if item.option_id == changed.option_id else item
                for item in analysis.response_options
            ),
            "material": analysis.material.model_copy(
                update={
                    "response_options": tuple(
                        AnalysisResponseOptionMaterial.from_option(changed)
                        if item.option_id == changed.option_id
                        else item
                        for item in analysis.material.response_options
                    )
                }
            ),
        }
    )
    with pytest.raises(DecisionPolicyViolation, match="quality_approver"):
        DecisionPolicy().authorize_independent_and_materialize(
            record,
            final_ctx.alex,
            final_ctx.case,
            projection,
            changed_analysis,
            evidence,
        )


@pytest.mark.parametrize("review_state", ("pending", "rejected", "superseded"))
def test_high_cost_requires_current_approved_review_and_writes_nothing(
    final_ctx, review_state
):
    first = submit(final_ctx)
    if review_state != "pending":
        state = current(final_ctx)
        final_ctx.finance.resolve(
            ResolveFinanceCommand(
                review_id=state.review.review_id,
                expected=state.token,
                expected_review_revision=state.review_revision,
                approved=False,
                reason="no",
                idempotency_key="deny-review",
            ),
            final_ctx.taylor,
        )
    if review_state == "superseded":
        submit(final_ctx, "RL-OPTION-TRANSFER")
        with final_ctx.store.engine.begin() as connection:
            connection.execute(
                update(case_projection)
                .where(case_projection.c.case_id == final_ctx.case.case_id)
                .values(current_selection_id=first.selection.selection_id)
            )
    before = row_counts(final_ctx)
    with pytest.raises(FinanceFinalizationInvalid, match="lacks Finance approval"):
        final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    assert row_counts(final_ctx) == before


@pytest.mark.parametrize(
    ("cause", "option_id"),
    (("blocked", "RL-OPTION-BETA"), ("infeasible", "RL-OPTION-NO-MITIGATION")),
)
def test_independent_policy_rejects_distinct_blocked_and_infeasible_options(
    final_ctx, cause, option_id
):
    _, projection, analysis, evidence = independent_policy_inputs(final_ctx)
    option = next(
        item for item in analysis.response_options if item.option_id == option_id
    )
    if cause == "blocked":
        assert option.blocking_codes and not option.executable
    else:
        assert not option.active_mitigation and not option.executable
        assert not option.blocking_codes
    record = RecordDecisionCommand(
        case_id=final_ctx.case.case_id,
        analysis_id=analysis.analysis_id,
        selected_option_id=option_id,
        kind=DecisionKind.APPROVED,
        idempotency_key=f"{cause}-policy",
    )
    with pytest.raises(DecisionPolicyViolation, match="not executable"):
        DecisionPolicy().authorize_independent_and_materialize(
            record, final_ctx.alex, final_ctx.case, projection, analysis, evidence
        )


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
    changed_kind = request.model_copy(
        update={"kind": DecisionKind.REJECTED, "rejection_reason": "changed"}
    )
    for conflicting in (changed, changed_kind):
        with pytest.raises(FinanceFinalizationConflict):
            final_ctx.finalizer.finalize(conflicting, final_ctx.alex)


def test_rejection_same_key_changed_normalized_reason_conflicts(final_ctx):
    request = command(final_ctx, DecisionKind.REJECTED, key="reason-key")
    original = FinalizeProposalCommand.model_validate(
        {**request.model_dump(mode="python"), "rejection_reason": " first "}
    )
    final_ctx.finalizer.finalize(original, final_ctx.alex)
    changed = request.model_copy(update={"rejection_reason": "different"})
    with pytest.raises(FinanceFinalizationConflict):
        final_ctx.finalizer.finalize(changed, final_ctx.alex)


def test_fresh_key_cannot_finalize_same_selection_from_history(final_ctx):
    approve(final_ctx)
    final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    with pytest.raises(FinanceFinalizationConflict, match="already finalized"):
        final_ctx.finalizer.finalize(
            command(final_ctx, key="another-finalization"), final_ctx.alex
        )


def test_duplicate_history_scan_survives_rejected_current_decision_pointer(final_ctx):
    approve(final_ctx)
    approved = final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    rejection_command = RecordDecisionCommand(
        case_id=final_ctx.case.case_id,
        analysis_id=final_ctx.analysis.analysis_id,
        selected_option_id=None,
        kind=DecisionKind.REJECTED,
        idempotency_key="test-rejected-pointer",
        rejection_reason="pointer only",
    )
    rejected = Decision.from_command(
        rejection_command,
        final_ctx.alex,
        final_ctx.analysis,
        (),
        request_fingerprint="0" * 64,
        decided_at=FINALIZED + timedelta(minutes=1),
    )
    with final_ctx.store.uow_factory() as uow:
        uow.decisions.insert(rejected)
        uow.decisions.insert_satisfactions(rejected.decision_id, ())
        uow.cases.mark_rejected(final_ctx.case.case_id, rejected.decision_id)
        uow.commit()
    with final_ctx.store.uow_factory() as uow:
        assert (
            uow.cases.get_projection(final_ctx.case.case_id).current_decision_id
            == rejected.decision_id
        )
    with pytest.raises(FinanceFinalizationConflict, match="already finalized"):
        final_ctx.finalizer.finalize(
            command(final_ctx, key="fresh-after-rejected-pointer"), final_ctx.alex
        )
    with final_ctx.store.uow_factory() as uow:
        assert approved in uow.decisions.list_for_case(final_ctx.case.case_id)


def test_finalized_selection_cannot_be_withdrawn_without_writes(final_ctx):
    approve(final_ctx)
    final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    before = row_counts(final_ctx), current(final_ctx)
    with pytest.raises(FinanceFinalizationConflict, match="active execution"):
        final_ctx.finalizer.finalize(
            command(final_ctx, DecisionKind.REJECTED, key="withdraw-finalized"),
            final_ctx.alex,
        )
    assert (row_counts(final_ctx), current(final_ctx)) == before


def test_withdrawal_stales_old_taylor_command_and_resubmit_creates_new_review(
    final_ctx,
):
    first = submit(final_ctx)
    state = current(final_ctx)
    old = ResolveFinanceCommand(
        review_id=state.review.review_id,
        expected=state.token,
        expected_review_revision=state.review_revision,
        approved=True,
        reason=None,
        idempotency_key="old-taylor",
    )
    final_ctx.finalizer.finalize(
        command(final_ctx, DecisionKind.REJECTED, key="withdraw"), final_ctx.alex
    )
    with pytest.raises(FinanceCommandConflict):
        final_ctx.finance.resolve(old, final_ctx.taylor)
    second = submit(final_ctx, key="resubmit-after-withdraw")
    assert second.selection.selection_id != first.selection.selection_id
    assert second.review.review_id != first.review.review_id


def invalid_alex_actors(ctx):
    return (
        ctx.taylor,
        ctx.alex.model_copy(
            update={"object_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
        ),
        ctx.alex.model_copy(
            update={"effective_roles": (*ctx.alex.effective_roles, "finance_approver")}
        ),
    )


def test_exact_alex_variants_are_denied_before_initial_uow(final_ctx):
    service = FinanceDecisionService(
        lambda: (_ for _ in ()).throw(AssertionError("opened UoW")),
        actors=final_ctx.finalizer._actors,
    )
    for denied in invalid_alex_actors(final_ctx):
        with pytest.raises(FinancePermissionDenied):
            service.finalize(command(final_ctx, DecisionKind.REJECTED), denied)


def test_unauthorized_variants_committed_replay_denied_before_uow(final_ctx):
    approve(final_ctx)
    request = command(final_ctx)
    original = final_ctx.finalizer.finalize(request, final_ctx.alex)
    service = FinanceDecisionService(
        lambda: (_ for _ in ()).throw(AssertionError("opened UoW")),
        actors=final_ctx.actors,
        clock=lambda: (_ for _ in ()).throw(AssertionError("read clock")),
    )
    for denied in invalid_alex_actors(final_ctx):
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


def test_approved_decision_reopens_after_later_supersession(final_ctx):
    approve(final_ctx)
    decision = final_ctx.finalizer.finalize(command(final_ctx), final_ctx.alex)
    submit(final_ctx, "RL-OPTION-TRANSFER", key="later-selection-for-reopen")
    url = str(final_ctx.store.engine.url)
    reopened = SqliteStore(build_sqlite_engine(url), runtime_mode=RuntimeMode.FALLBACK)
    try:
        with reopened.uow_factory() as uow:
            assert uow.decisions.get(decision.decision_id) == decision
    finally:
        reopened.engine.dispose()


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


@pytest.mark.parametrize("boundary", ("naive", "stale", "blank", "legacy"))
def test_direct_withdrawal_boundaries_roll_back_without_writes(final_ctx, boundary):
    submit(final_ctx, "RL-OPTION-TRANSFER")
    before = row_counts(final_ctx), current(final_ctx)
    case_id = final_ctx.case.case_id
    expected = before[1].token
    now = FINALIZED
    operation_id = "direct-withdraw"
    if boundary == "naive":
        now = datetime.fromisoformat("2026-09-01T00:00:00")
    elif boundary == "stale":
        expected = expected.model_copy(update={"generation": expected.generation - 1})
    elif boundary == "blank":
        operation_id = "  "
    else:
        legacy, snapshot = instantiate_rl001(
            case_id="RL-CASE-DIRECT-LEGACY",
            purpose=CasePurpose.AUTOMATED_TEST,
            runtime_mode=RuntimeMode.FALLBACK,
            workflow_version=WorkflowVersion.LEGACY,
        )
        final_ctx.store.create_case(legacy, snapshot)
        case_id = legacy.case_id
        with final_ctx.store.uow_factory() as uow:
            expected = uow.proposals.get_state(case_id).token
    with (
        pytest.raises((ValueError, StaleProposal, PersistenceIntegrityError)),
        final_ctx.store.uow_factory() as uow,
    ):
        uow.proposals.withdraw_current(
            case_id,
            expected=expected,
            now=now,
            operation_id=operation_id,
        )
        uow.commit()
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
    "mutation",
    ("selection_snapshot", "review_snapshot", "review_revision", "missing_selection"),
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
        elif mutation == "review_revision":
            evidence["review_revision"] += 1
        else:
            evidence["selection"]["selection_id"] = "RL-SELECTION-VERIFIED-ABSENT"
        connection.execute(
            update(decisions)
            .where(decisions.c.decision_id == decision.decision_id)
            .values(
                payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":"))
            )
        )
    if mutation == "selection_snapshot":
        assert evidence["selection"][
            "submitted_by"
        ] != decision.proposal_approval.selection.submitted_by.model_dump(mode="json")
    elif mutation == "review_snapshot":
        assert evidence["review"][
            "reviewed_by"
        ] != decision.proposal_approval.review.reviewed_by.model_dump(mode="json")
    elif mutation == "review_revision":
        assert evidence["review_revision"] != decision.proposal_approval.review_revision
    else:
        with final_ctx.store.engine.connect() as connection:
            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(case_proposal_selections)
                    .where(
                        case_proposal_selections.c.selection_id
                        == "RL-SELECTION-VERIFIED-ABSENT"
                    )
                )
                == 0
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
            pytest.raises(PersistenceIntegrityError) as raised,
            final_ctx.store.uow_factory() as uow,
        ):
            check(uow)
        if mutation == "missing_selection":
            assert isinstance(raised.value.__cause__, RecordNotFound)


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

    baseline = journal_snapshot(final_ctx)
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
    durable = journal_snapshot(final_ctx)
    assert (
        durable_state.token.generation
        == baseline["projection"]["proposal_generation"] + 1
    )
    projection_changes = {
        key
        for key, value in durable["projection"].items()
        if value != baseline["projection"][key]
    }
    assert projection_changes <= {
        "status",
        "current_analysis_id",
        "current_analysis_hash",
        "proposal_generation",
        "current_selection_id",
        "current_decision_id",
        "updated_at",
        "payload_json",
    }
    for key in ("case_id", "purpose", "runtime_mode", "scenario_effective_time"):
        assert durable["projection"][key] == baseline["projection"][key]
    assert (
        durable["projection"]["current_analysis_id"] == projection.current_analysis_id
    )
    assert (
        durable["projection"]["current_analysis_hash"]
        == projection.current_analysis_hash
    )
    assert (
        durable["projection"]["current_decision_id"] == projection.current_decision_id
    )
    assert (
        durable["projection"]["current_selection_id"]
        == durable_state.token.selection_id
    )
    expected_status = (
        "action_planning"
        if stored and stored[0].kind is DecisionKind.APPROVED
        else "rejected"
        if stored
        else "open"
    )
    assert durable["projection"]["status"] == expected_status
    durable_payload = json.loads(durable["projection"]["payload_json"])
    baseline_payload = json.loads(baseline["projection"]["payload_json"])
    assert durable_payload == {**baseline_payload, "status": expected_status}
    if operation == "identical":
        committed = [item for item in results if hasattr(item, "decision_id")]
        assert committed
        original = final_ctx.finalizer.finalize(primary, final_ctx.alex)
        assert stored == (original,)
        assert all(item == original for item in committed)
        assert projection.current_decision_id == original.decision_id
        assert durable_state.token.selection_id == primary.expected.selection_id
        for name in ("selections", "reviews", "analyses", "evidence"):
            assert durable[name] == baseline[name]
    elif operation == "different_key":
        assert len(stored) == 1
        assert projection.current_decision_id == stored[0].decision_id
        assert durable_state.token.selection_id == primary.expected.selection_id
        assert durable["selections"] == baseline["selections"]
        assert durable["reviews"] == baseline["reviews"]
        assert durable["analyses"] == baseline["analyses"]
        assert durable["evidence"] == baseline["evidence"]
    elif operation == "proposal_publish":
        if stored:
            assert projection.current_decision_id == stored[0].decision_id
            assert durable_state.token.selection_id == primary.expected.selection_id
            assert durable_state.review is not None
            assert durable_state.review.status is FinanceReviewStatus.APPROVED
            assert durable["selections"] == baseline["selections"]
            assert durable["reviews"] == baseline["reviews"]
        else:
            assert durable_state.selection is not None
            assert durable_state.selection.proposal.option_id == "RL-OPTION-TRANSFER"
            assert durable_state.review is None
            assert projection.current_decision_id is None
            assert len(durable["selections"]) == len(baseline["selections"]) + 1
            assert len(durable["reviews"]) == len(baseline["reviews"]) + 1
            assert all(row in durable["selections"] for row in baseline["selections"])
            assert all(row in durable["reviews"] for row in baseline["reviews"])
            assert any(
                row["selection_id"] == durable_state.selection.selection_id
                for row in durable["selections"]
                if row not in baseline["selections"]
            )
            newest = max(durable["reviews"], key=lambda row: row["revision"])
            assert newest["status"] == FinanceReviewStatus.SUPERSEDED.value
            assert durable["analyses"] == baseline["analyses"]
            assert durable["evidence"] == baseline["evidence"]
    elif operation == "analysis_save":
        if stored:
            assert projection.current_decision_id == stored[0].decision_id
            assert durable_state.token.analysis_id == primary.expected.analysis_id
            assert durable_state.token.selection_id == primary.expected.selection_id
            assert durable["analyses"] == baseline["analyses"]
            assert durable["evidence"] == baseline["evidence"]
            assert durable["selections"] == baseline["selections"]
            assert durable["reviews"] == baseline["reviews"]
        else:
            assert durable_state.token.analysis_id == "RL-ANALYSIS-RACE-LATER"
            assert durable_state.token.selection_id is None
            assert projection.current_decision_id is None
            assert len(durable["analyses"]) == len(baseline["analyses"]) + 1
            assert len(durable["evidence"]) > len(baseline["evidence"])
            assert all(row in durable["analyses"] for row in baseline["analyses"])
            assert all(row in durable["evidence"] for row in baseline["evidence"])
            assert any(
                row["analysis_id"] == "RL-ANALYSIS-RACE-LATER"
                for row in durable["analyses"]
                if row not in baseline["analyses"]
            )
            assert durable["selections"] == baseline["selections"]
            assert len(durable["reviews"]) == len(baseline["reviews"]) + 1
    else:
        if stored:
            assert stored[0].kind is DecisionKind.REJECTED
            assert durable_state.selection is None
            assert durable_state.review is None
            assert projection.current_decision_id == stored[0].decision_id
            assert len(durable["reviews"]) == len(baseline["reviews"]) + 1
            assert all(row in durable["reviews"] for row in baseline["reviews"])
            newest = max(durable["reviews"], key=lambda row: row["revision"])
            assert newest["status"] == FinanceReviewStatus.SUPERSEDED.value
        else:
            assert durable_state.selection is not None
            assert durable_state.review is not None
            assert durable_state.review.status is FinanceReviewStatus.APPROVED
            assert durable_state.review_revision == 2
            assert projection.current_decision_id is None
            assert durable["decisions"] == baseline["decisions"]
            assert durable["satisfactions"] == baseline["satisfactions"]
            assert durable["events"] == baseline["events"]
            assert durable["selections"] == baseline["selections"]
            assert len(durable["reviews"]) == len(baseline["reviews"]) + 1
            assert durable["analyses"] == baseline["analyses"]
            assert durable["evidence"] == baseline["evidence"]
    if operation != "identical":
        successful = [
            item
            for item in results
            if not isinstance(item, Exception) and item != "lock"
        ]
        assert len(successful) == 1
        winner = successful[0]
        if stored:
            assert isinstance(winner, Decision)
            assert winner == stored[0]
        elif operation == "proposal_publish":
            assert isinstance(winner, SubmissionResult)
            assert winner.selection == durable_state.selection
        elif operation == "analysis_save":
            assert winner is None
        else:
            assert isinstance(winner, ResolutionResult)
            assert winner.review == durable_state.review
    approved_count = sum(item.kind is DecisionKind.APPROVED for item in stored)
    counts = row_counts(final_ctx)
    assert counts[1] == approved_count
    assert counts[2] == approved_count
