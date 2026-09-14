from collections.abc import Callable
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError

from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import (
    CorpusScope,
    Decision,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
    StandingAuthorization,
)
from data.domain.evidence import IdentitySource
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import DecisionService
from services.execution.currentness import (
    ExecutionProposalStale,
    check_execution_current,
    guard_execution_current,
)
from services.finance.contracts import (
    FinalizeProposalCommand,
    ResolveFinanceCommand,
    SubmitProposalCommand,
)
from services.finance.decisions import FinanceDecisionService
from services.finance.identity import BoundFinanceActors
from services.finance.service import FinanceService
from services.persistence.ports import UnitOfWork
from services.persistence.proposals import StaleProposal
from services.persistence.sqlite import sqlite_store
from services.persistence.store import PersistenceIntegrityError
from services.persistence.tables import (
    case_projection,
    case_proposal_selections,
    decisions,
    execution_actions,
    execution_attempts,
    execution_events,
    finance_review_revisions,
    outbox_events,
    outcome_observations,
    playbacks,
)

START = datetime.fromisoformat("2026-09-01T14:01:00+00:00")


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
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
            analysis_started_at=START,
            created_at=START,
            calculation_version="rl001-options-v1",
        )
    )


def state(ctx):
    with ctx.factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)


def counts(ctx):
    tables = (
        case_proposal_selections,
        finance_review_revisions,
        decisions,
        outbox_events,
        execution_actions,
        execution_attempts,
        execution_events,
        playbacks,
        outcome_observations,
    )
    with ctx.store.engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in tables
        )


@pytest.fixture(params=("RL-OPTION-COMBINED", "RL-OPTION-TRANSFER"))
def ctx(tmp_path, request):
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
    store = sqlite_store(f"sqlite:///{tmp_path / 'currentness.db'}")
    factory = cast(Callable[[], UnitOfWork], store.uow_factory)
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-EXECUTION-GUARD",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    analysis = build_analysis(case, snapshot, "RL-ANALYSIS-EXECUTION-GUARD")
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    moments = iter(START + timedelta(minutes=n) for n in range(1, 30))
    finance = FinanceService(factory, actors=actors, clock=lambda: next(moments))
    context = SimpleNamespace(
        store=store,
        factory=factory,
        case=case,
        snapshot=snapshot,
        analysis=analysis,
        actors=actors,
        alex=alex,
        taylor=taylor,
        finance=finance,
    )
    submitted = finance.submit(
        SubmitProposalCommand(
            case_id=case.case_id,
            option_id=request.param,
            expected=state(context).token,
            idempotency_key="guard-submit",
        ),
        alex,
    )
    if submitted.review is not None:
        current = state(context)
        assert current.review_revision is not None
        finance.resolve(
            ResolveFinanceCommand(
                review_id=submitted.review.review_id,
                expected=current.token,
                expected_review_revision=current.review_revision,
                approved=True,
                idempotency_key="guard-review",
            ),
            taylor,
        )
    context.decision = FinanceDecisionService(
        factory, actors=actors, clock=lambda: next(moments)
    ).finalize(
        FinalizeProposalCommand(
            case_id=case.case_id,
            expected=state(context).token,
            kind=DecisionKind.APPROVED,
            idempotency_key="guard-finalize",
        ),
        alex,
    )
    yield context
    store.engine.dispose()


def test_check_is_read_only_and_guard_uses_fresh_generation(ctx):
    before, rows = state(ctx), counts(ctx)
    with ctx.factory() as uow:
        decision, token = check_execution_current(uow, ctx.decision.decision_id)
        assert decision == ctx.decision and token == before.token
    assert state(ctx) == before and counts(ctx) == rows
    for increment in (1, 2):
        with ctx.factory() as uow:
            assert (
                guard_execution_current(uow, ctx.decision.decision_id) == ctx.decision
            )
            uow.commit()
        assert state(ctx).token.generation == before.token.generation + increment
    assert counts(ctx) == rows


def test_guard_rolls_back_with_its_caller(ctx):
    before, rows = state(ctx), counts(ctx)
    with pytest.raises(RuntimeError, match="caller failed"), ctx.factory() as uow:
        guard_execution_current(uow, ctx.decision.decision_id)
        raise RuntimeError("caller failed")
    assert state(ctx) == before and counts(ctx) == rows


@pytest.mark.parametrize("change", ("selection", "same-hash-analysis", "decision"))
def test_changed_binding_is_stale_but_history_stays_readable(ctx, change):
    if change == "selection":
        ctx.finance.submit(
            SubmitProposalCommand(
                case_id=ctx.case.case_id,
                option_id="RL-OPTION-TRANSFER",
                expected=state(ctx).token,
                idempotency_key="replacement",
            ),
            ctx.alex,
        )
    elif change == "same-hash-analysis":
        replacement = build_analysis(ctx.case, ctx.snapshot, "RL-ANALYSIS-NEXT")
        assert replacement.material_hash == ctx.analysis.material_hash
        ctx.store.save_analysis(replacement)
    else:
        with ctx.store.engine.begin() as connection:
            connection.execute(
                update(case_projection)
                .where(case_projection.c.case_id == ctx.case.case_id)
                .values(current_decision_id=None)
            )
    before, rows = state(ctx), counts(ctx)
    with ctx.factory() as uow:
        assert uow.decisions.get(ctx.decision.decision_id) == ctx.decision
        with pytest.raises(ExecutionProposalStale):
            guard_execution_current(uow, ctx.decision.decision_id)
    assert state(ctx) == before and counts(ctx) == rows


@pytest.mark.parametrize("change", ("revision", "snapshot"))
def test_exact_review_binding_is_checked(ctx, monkeypatch, change):
    current = state(ctx)
    if current.review is None:
        pytest.skip("review binding applies to high cost")
    assert current.review_revision is not None
    altered = (
        current.model_copy(update={"review_revision": current.review_revision + 1})
        if change == "revision"
        else current.model_copy(
            update={"review": current.review.model_copy(update={"reason": "different"})}
        )
    )
    before, rows = current, counts(ctx)
    with ctx.factory() as uow:
        monkeypatch.setattr(
            type(uow.proposals), "get_state", lambda self, case_id: altered
        )
        with pytest.raises(ExecutionProposalStale):
            guard_execution_current(uow, ctx.decision.decision_id)
    monkeypatch.undo()
    assert state(ctx) == before and counts(ctx) == rows


def test_cas_failure_is_dedicated_stale_and_not_committed(ctx, monkeypatch):
    before, rows = state(ctx), counts(ctx)
    with ctx.factory() as uow:

        def lose(self, case_id, *, expected):
            assert expected == before.token
            raise StaleProposal("injected contention")

        monkeypatch.setattr(type(uow.proposals), "guard_current", lose)
        with pytest.raises(ExecutionProposalStale) as caught:
            guard_execution_current(uow, ctx.decision.decision_id)
        assert isinstance(caught.value.__cause__, StaleProposal)
    assert state(ctx) == before and counts(ctx) == rows


@pytest.mark.parametrize("error_type", (PersistenceIntegrityError, OperationalError))
def test_unrelated_database_errors_are_not_disguised(ctx, monkeypatch, error_type):
    injected = (
        error_type("corrupt historical record")
        if error_type is PersistenceIntegrityError
        else error_type("injected", {}, RuntimeError("database unavailable"))
    )
    with ctx.factory() as uow:

        def fail(self, decision_id):
            raise injected

        monkeypatch.setattr(type(uow.decisions), "get", fail)
        with pytest.raises(error_type) as caught:
            guard_execution_current(uow, ctx.decision.decision_id)
        assert caught.value is injected


def test_low_cost_unexpected_review_is_stale(ctx, monkeypatch):
    evidence = ctx.decision.proposal_approval
    assert evidence is not None
    if evidence.review is not None:
        pytest.skip("low-cost fixture only")
    current = state(ctx)
    altered = current.model_copy(
        update={"review": cast(Any, object()), "review_revision": 2}
    )
    with ctx.factory() as uow:
        monkeypatch.setattr(
            type(uow.proposals), "get_state", lambda self, case_id: altered
        )
        with pytest.raises(ExecutionProposalStale):
            check_execution_current(uow, ctx.decision.decision_id)


def test_rejected_decision_is_never_execution_current(ctx):
    command = RecordDecisionCommand(
        case_id=ctx.case.case_id,
        analysis_id=ctx.analysis.analysis_id,
        selected_option_id=None,
        kind=DecisionKind.REJECTED,
        idempotency_key="test-rejected",
        rejection_reason="rejected",
    )
    rejected = Decision.from_command(
        command,
        ctx.alex,
        ctx.analysis,
        (),
        request_fingerprint="0" * 64,
        decided_at=START + timedelta(minutes=20),
    )
    with ctx.factory() as uow:
        uow.decisions.insert(rejected)
        uow.decisions.insert_satisfactions(rejected.decision_id, ())
        uow.cases.mark_rejected(ctx.case.case_id, rejected.decision_id)
        uow.commit()
    with (
        ctx.factory() as uow,
        pytest.raises(ExecutionProposalStale, match="approved Decision"),
    ):
        check_execution_current(uow, rejected.decision_id)


def test_legacy_guard_never_reads_or_mutates_proposals(ctx, monkeypatch):
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-LEGACY-GUARD",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.LEGACY,
    )
    analysis = build_analysis(case, snapshot, "RL-ANALYSIS-LEGACY-GUARD")
    ctx.store.create_case(case, snapshot)
    ctx.store.save_analysis(analysis)
    decision = DecisionService(
        ctx.factory, clock=lambda: START + timedelta(minutes=5)
    ).record(
        RecordDecisionCommand(
            case_id=case.case_id,
            analysis_id=analysis.analysis_id,
            selected_option_id="RL-OPTION-COMBINED",
            kind=DecisionKind.APPROVED,
            idempotency_key="legacy-decision",
        ),
        ctx.alex,
    )

    def forbidden(*args: Any, **kwargs: Any):
        raise AssertionError("legacy must not use proposal protocol")

    with ctx.factory() as uow:
        monkeypatch.setattr(type(uow.proposals), "get_state", forbidden)
        monkeypatch.setattr(type(uow.proposals), "guard_current", forbidden)
        assert check_execution_current(uow, decision.decision_id) == (decision, None)
        assert guard_execution_current(uow, decision.decision_id) == decision
