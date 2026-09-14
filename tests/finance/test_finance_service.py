from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
from typing import Never, cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import CorpusScope, IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.finance.contracts import (
    ResolutionResult,
    ResolveFinanceCommand,
    SubmitProposalCommand,
)
from services.finance.identity import BoundFinanceActors, FinancePermissionDenied
from services.finance.service import (
    FinanceCommandConflict,
    FinanceRequestInvalid,
    FinanceService,
)
from services.persistence.finance_reviews import SqlAlchemyFinanceReviewRepository
from services.persistence.ports import UnitOfWork
from services.persistence.proposals import (
    SelectionIdempotencyConflict,
    SqlAlchemyProposalRepository,
    StaleProposal,
)
from services.persistence.sqlite import SqliteStore, build_sqlite_engine, sqlite_store
from services.persistence.tables import (
    case_proposal_selections,
    decisions,
    finance_review_revisions,
    outbox_events,
)

START = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
SUBMITTED = datetime.fromisoformat("2026-09-01T14:02:00+00:00")


@pytest.fixture
def ctx(tmp_path):
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
        display_name="Original Alex",
        user_principal_name="alex@example.invalid",
    )
    taylor = IdentitySnapshot(
        persona_id="RL-PERSONA-TAYLOR",
        source_id="RL-ENTRA-TAYLOR",
        identity_source=IdentitySource.ENTRA,
        tenant_id=tenant,
        object_id=taylor_id,
        effective_roles=("finance_approver",),
    )
    store = sqlite_store(f"sqlite:///{tmp_path / 'finance-service.db'}")
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-FINANCE-SERVICE",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    analysis = analyze_case(
        AnalyzeCaseCommand(
            analysis_id="RL-ANALYSIS-FINANCE-SERVICE",
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot,
                analysis_id="RL-ANALYSIS-FINANCE-SERVICE",
                retrieved_at=START,
            ),
            analysis_started_at=START,
            created_at=START,
            calculation_version="rl001-options-v1",
        )
    )
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    times = iter(SUBMITTED + timedelta(minutes=index) for index in range(30))
    service = FinanceService(
        _finance_uow_factory(store), actors=actors, clock=lambda: next(times)
    )
    yield SimpleNamespace(
        store=store,
        service=service,
        actors=actors,
        alex=alex,
        taylor=taylor,
        case=case,
        snapshot=snapshot,
        analysis=analysis,
    )
    store.engine.dispose()


def current(ctx):
    with ctx.store.uow_factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)


def submission(ctx, option="RL-OPTION-COMBINED", key="submit-1"):
    return SubmitProposalCommand(
        case_id=ctx.case.case_id,
        option_id=option,
        expected=current(ctx).token,
        idempotency_key=key,
    )


def resolution(
    ctx, *, approved=False, reason: str | None = "Budget 10000", key="resolve-1"
):
    state = current(ctx)
    return ResolveFinanceCommand(
        review_id=state.review.review_id,
        expected=state.token,
        expected_review_revision=state.review_revision,
        approved=approved,
        reason=reason,
        idempotency_key=key,
    )


def rows(ctx):
    with ctx.store.engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (
                case_proposal_selections,
                finance_review_revisions,
                decisions,
                outbox_events,
            )
        )


def no_clock():
    raise AssertionError("replay must not read clock")


def _finance_uow_factory(store) -> Callable[[], UnitOfWork]:
    # The concrete UoW satisfies the protocol at runtime. Its mutable repository
    # attributes prevent pyright from inferring structural compatibility.
    return cast(Callable[[], UnitOfWork], store.uow_factory)


def _seed_pending_request(
    ctx, *, suffix: str, tenant: str, alex_object: str, taylor_object: str
):
    case_id = f"RL-CASE-FOREIGN-{suffix}"
    analysis_id = f"RL-ANALYSIS-FOREIGN-{suffix}"
    case, snapshot = instantiate_rl001(
        case_id=case_id,
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
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
    ctx.store.create_case(case, snapshot)
    ctx.store.save_analysis(analysis)
    actors = BoundFinanceActors(
        tenant_id=UUID(tenant),
        alex_object_id=UUID(alex_object),
        taylor_object_id=UUID(taylor_object),
    )
    alex = IdentitySnapshot(
        persona_id="RL-PERSONA-ALEX",
        source_id="RL-ENTRA-ALEX",
        identity_source=IdentitySource.ENTRA,
        tenant_id=tenant,
        object_id=alex_object,
        effective_roles=("material_planner", "response_approver"),
    )
    service = FinanceService(
        _finance_uow_factory(ctx.store), actors=actors, clock=lambda: SUBMITTED
    )
    with ctx.store.uow_factory() as uow:
        token = uow.proposals.get_state(case_id).token
    result = service.submit(
        SubmitProposalCommand(
            case_id=case_id,
            option_id="RL-OPTION-COMBINED",
            expected=token,
            idempotency_key=f"foreign-{suffix}",
        ),
        alex,
    )
    assert result.review is not None
    return result


def test_original_submit_and_resolution_replay_after_supersession(ctx):
    submit = submission(ctx)
    first = ctx.service.submit(submit, ctx.alex)
    resolve = resolution(ctx)
    rejected = ctx.service.resolve(resolve, ctx.taylor)
    transfer = ctx.service.submit(
        submission(ctx, "RL-OPTION-TRANSFER", "submit-2"), ctx.alex
    )
    assert transfer.review is None and transfer.review_revision is None
    replay = FinanceService(ctx.store.uow_factory, actors=ctx.actors, clock=no_clock)
    assert replay.submit(submit, ctx.alex) == first
    renamed_taylor = ctx.taylor.model_copy(
        update={
            "tenant_id": "{11111111-1111-4111-8111-111111111111}",
            "object_id": "{33333333-3333-4333-8333-333333333333}",
            "display_name": "Updated Taylor",
        }
    )
    assert replay.resolve(resolve, renamed_taylor) == rejected
    assert rejected.review.reviewed_by == ctx.taylor
    assert current(ctx).selection == transfer.selection
    assert first.selection.submitted_by == ctx.alex
    assert rows(ctx) == (2, 3, 0, 0)


def test_rejected_same_option_new_key_is_new_request(ctx):
    first = ctx.service.submit(submission(ctx), ctx.alex)
    ctx.service.resolve(resolution(ctx), ctx.taylor)
    second = ctx.service.submit(submission(ctx, key="submit-2"), ctx.alex)
    assert second.selection.selection_id != first.selection.selection_id
    assert second.review.review_id != first.review.review_id


def test_changed_submit_and_resolve_commands_conflict(ctx):
    submit = submission(ctx)
    ctx.service.submit(submit, ctx.alex)
    with pytest.raises(FinanceCommandConflict):
        ctx.service.submit(
            submit.model_copy(update={"expected": current(ctx).token}), ctx.alex
        )
    resolve = resolution(ctx)
    ctx.service.resolve(resolve, ctx.taylor)
    for changed in (
        resolve.model_copy(update={"approved": True, "reason": None}),
        resolve.model_copy(update={"reason": "different"}),
        resolve.model_copy(update={"expected_review_revision": 2}),
        resolve.model_copy(update={"expected": current(ctx).token}),
    ):
        with pytest.raises(FinanceCommandConflict):
            ctx.service.resolve(changed, ctx.taylor)


@pytest.mark.parametrize(
    "field,value",
    (
        ("tenant_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("object_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("persona_id", "RL-PERSONA-TAYLOR"),
        ("source_id", "RL-ENTRA-TAYLOR"),
        ("identity_source", "fixture"),
        ("effective_roles", ("material_planner",)),
        ("effective_roles", ("material_planner", "response_approver", "extra")),
    ),
)
def test_submit_permission_denied_before_database_access(ctx, field, value):
    denied_actor = ctx.alex.model_copy(update={field: value})

    def forbidden():
        raise AssertionError("unauthorized command must not open UoW")

    denied = FinanceService(forbidden, actors=ctx.actors, clock=no_clock)
    with pytest.raises(FinancePermissionDenied):
        denied.submit(submission(ctx), denied_actor)


def test_resolve_permission_denied_before_database_access(ctx):
    command = ResolveFinanceCommand(
        review_id="review",
        expected=current(ctx).token.model_copy(update={"selection_id": "selection"}),
        expected_review_revision=1,
        approved=True,
        idempotency_key="resolve",
    )
    denied = FinanceService(
        lambda: (_ for _ in ()).throw(AssertionError("database accessed")),
        actors=ctx.actors,
        clock=no_clock,
    )
    with pytest.raises(FinancePermissionDenied):
        denied.resolve(command, ctx.alex)


def test_display_and_equivalent_uuid_replay_original_snapshot(ctx):
    command = submission(ctx)
    result = ctx.service.submit(command, ctx.alex)
    renamed = ctx.alex.model_copy(
        update={
            "tenant_id": "{11111111-1111-4111-8111-111111111111}",
            "object_id": "{22222222-2222-4222-8222-222222222222}",
            "display_name": "Updated Alex",
            "user_principal_name": "updated@example.invalid",
        }
    )
    replay = FinanceService(ctx.store.uow_factory, actors=ctx.actors, clock=no_clock)
    assert replay.submit(command, renamed) == result
    assert result.selection.submitted_by == ctx.alex


def test_contracts_reject_client_material_and_bad_shapes(ctx):
    payload = submission(ctx).model_dump(mode="python")
    for extra in ("response_cost", "submitted_at", "actor", "analysis_material_hash"):
        with pytest.raises(ValidationError):
            SubmitProposalCommand.model_validate({**payload, extra: "client"})
    with pytest.raises(ValidationError):
        SubmitProposalCommand.model_validate({**payload, "idempotency_key": " "})
    state = current(ctx).token.model_copy(update={"selection_id": "selection"})
    base = {
        "review_id": "review",
        "expected": state,
        "expected_review_revision": 1,
        "approved": False,
        "reason": "reason",
        "idempotency_key": "key",
    }
    with pytest.raises(ValidationError):
        ResolveFinanceCommand.model_validate({**base, "approved": 1})
    with pytest.raises(ValidationError):
        ResolveFinanceCommand.model_validate({**base, "expected_review_revision": True})
    with pytest.raises(ValidationError):
        ResolveFinanceCommand.model_validate({**base, "reason": " "})
    assert (
        ResolveFinanceCommand.model_validate(
            {**base, "approved": True, "reason": " "}
        ).reason
        is None
    )


def test_invalid_option_clock_and_low_cost_behavior(ctx):
    before = rows(ctx)
    for invalid_option in ("RL-OPTION-BETA", "RL-OPTION-NO-MITIGATION"):
        with pytest.raises(FinanceRequestInvalid):
            ctx.service.submit(submission(ctx, invalid_option), ctx.alex)
    assert rows(ctx) == before
    invalid_clock = FinanceService(
        ctx.store.uow_factory,
        actors=ctx.actors,
        clock=lambda: datetime(2026, 9, 1),  # noqa: DTZ001 - invalid clock fixture
    )
    with pytest.raises(FinanceRequestInvalid):
        invalid_clock.submit(submission(ctx, "RL-OPTION-TRANSFER"), ctx.alex)
    low = ctx.service.submit(submission(ctx, "RL-OPTION-TRANSFER"), ctx.alex)
    assert low.review is None and low.selection.proposal.response_cost <= Decimal(20000)


def test_bound_actor_configuration_rejects_same_person_and_malformed_actor(ctx):
    with pytest.raises(ValidationError):
        BoundFinanceActors(
            tenant_id=ctx.actors.tenant_id,
            alex_object_id=ctx.actors.alex_object_id,
            taylor_object_id=ctx.actors.alex_object_id,
        )
    malformed = ctx.alex.model_copy(update={"object_id": "not-a-uuid"})

    def forbidden() -> Never:
        raise AssertionError("unauthorized command must not open UoW")

    with pytest.raises(FinancePermissionDenied):
        FinanceService(forbidden, actors=ctx.actors).submit(submission(ctx), malformed)


@pytest.mark.parametrize(
    "field,value",
    (
        ("tenant_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("object_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("persona_id", "RL-PERSONA-ALEX"),
        ("source_id", "RL-ENTRA-ALEX"),
        ("identity_source", "fixture"),
        ("effective_roles", ()),
        ("effective_roles", ("finance_approver", "extra")),
    ),
)
def test_resolve_permission_variants_denied_before_database_access(ctx, field, value):
    actor = ctx.taylor.model_copy(update={field: value})
    command = ResolveFinanceCommand(
        review_id="review",
        expected=current(ctx).token.model_copy(update={"selection_id": "selection"}),
        expected_review_revision=1,
        approved=True,
        idempotency_key="resolve",
    )

    def forbidden():
        raise AssertionError("unauthorized command must not open UoW")

    with pytest.raises(FinancePermissionDenied):
        FinanceService(forbidden, actors=ctx.actors, clock=no_clock).resolve(
            command, actor
        )


def test_authorization_precedes_replay_for_persisted_submit_and_resolution(ctx):
    submit_command = submission(ctx)
    ctx.service.submit(submit_command, ctx.alex)
    resolve_command = resolution(ctx, approved=True, reason=None)
    ctx.service.resolve(resolve_command, ctx.taylor)
    before_rows, before_state = rows(ctx), current(ctx)

    def forbidden() -> Never:
        raise AssertionError("unauthorized replay must not open UoW")

    denied = FinanceService(forbidden, actors=ctx.actors, clock=no_clock)
    wrong_alex_object = ctx.alex.model_copy(
        update={"object_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
    )
    wrong_taylor_object = ctx.taylor.model_copy(
        update={"object_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}
    )

    with pytest.raises(FinancePermissionDenied):
        denied.submit(submit_command, wrong_alex_object)
    with pytest.raises(FinancePermissionDenied):
        denied.resolve(resolve_command, wrong_taylor_object)
    with pytest.raises(FinancePermissionDenied):
        denied.resolve(resolve_command, ctx.alex)

    assert rows(ctx) == before_rows
    assert current(ctx) == before_state


def test_late_submission_cas_failure_rolls_back_pending_and_pointer(ctx, monkeypatch):
    import services.persistence.proposals as proposals_module

    before = rows(ctx)
    token = current(ctx).token
    monkeypatch.setattr(
        proposals_module,
        "_cas_projection",
        lambda *args, **kwargs: (_ for _ in ()).throw(StaleProposal("late CAS")),
    )
    with pytest.raises(StaleProposal):
        ctx.service.submit(
            SubmitProposalCommand(
                case_id=ctx.case.case_id,
                option_id="RL-OPTION-COMBINED",
                expected=token,
                idempotency_key="late-cas",
            ),
            ctx.alex,
        )
    assert rows(ctx) == before
    assert current(ctx).token == token


def test_resolution_append_failure_rolls_back_guard_and_revision(ctx, monkeypatch):
    ctx.service.submit(submission(ctx), ctx.alex)
    command = resolution(ctx, approved=True, reason=None)
    before_state, before_rows = current(ctx), rows(ctx)
    original = SqlAlchemyFinanceReviewRepository.append
    injected = IntegrityError("append", {}, Exception("unrelated"))

    def fail_resolution(repository, review, **kwargs):
        if kwargs["idempotency_key"].startswith("finance-resolve:"):
            raise injected
        return original(repository, review, **kwargs)

    monkeypatch.setattr(SqlAlchemyFinanceReviewRepository, "append", fail_resolution)
    with pytest.raises(IntegrityError) as raised:
        ctx.service.resolve(command, ctx.taylor)
    assert raised.value is injected
    assert current(ctx) == before_state
    assert rows(ctx) == before_rows


def test_unrelated_integrity_error_is_not_disguised(ctx, monkeypatch):
    command = submission(ctx)
    injected = IntegrityError("publish", {}, Exception("unrelated"))
    monkeypatch.setattr(
        SqlAlchemyProposalRepository,
        "publish",
        lambda *args, **kwargs: (_ for _ in ()).throw(injected),
    )
    with pytest.raises(IntegrityError) as raised:
        ctx.service.submit(command, ctx.alex)
    assert raised.value is injected


def test_fresh_uow_recovery_returns_identical_winner_without_losing_pending(
    ctx, monkeypatch
):
    command = submission(ctx)
    original = SqlAlchemyFinanceReviewRepository.append
    winner_service = FinanceService(
        ctx.store.uow_factory, actors=ctx.actors, clock=lambda: SUBMITTED
    )
    winner_result = None

    def race(repository, review, **kwargs):
        nonlocal winner_result
        if winner_result is None and kwargs["idempotency_key"].startswith(
            "finance-pending:"
        ):
            monkeypatch.setattr(SqlAlchemyFinanceReviewRepository, "append", original)
            winner_result = winner_service.submit(command, ctx.alex)
            raise SelectionIdempotencyConflict("lost generated snapshot")
        return original(repository, review, **kwargs)

    monkeypatch.setattr(SqlAlchemyFinanceReviewRepository, "append", race)
    result = ctx.service.submit(command, ctx.alex)
    assert result == winner_result
    assert rows(ctx) == (1, 1, 0, 0)


def _run_concurrently(*calls):
    barrier = Barrier(len(calls))

    def invoke(call):
        try:
            barrier.wait(timeout=5)
            return call()
        except (FinanceCommandConflict, StaleProposal, IntegrityError) as error:
            return error
        except BaseException:
            barrier.abort()
            raise

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = [pool.submit(invoke, call) for call in calls]
        return [future.result(timeout=15) for future in futures]


def test_concurrent_same_and_different_submissions(ctx):
    same = submission(ctx)
    same_results = _run_concurrently(
        lambda: ctx.service.submit(same, ctx.alex),
        lambda: ctx.service.submit(same, ctx.alex),
    )
    assert same_results[0] == same_results[1]
    assert rows(ctx) == (1, 1, 0, 0)
    expected = current(ctx).token
    first = SubmitProposalCommand(
        case_id=ctx.case.case_id,
        option_id="RL-OPTION-TRANSFER",
        expected=expected,
        idempotency_key="different-1",
    )
    second = first.model_copy(update={"idempotency_key": "different-2"})
    results = _run_concurrently(
        lambda: ctx.service.submit(first, ctx.alex),
        lambda: ctx.service.submit(second, ctx.alex),
    )
    assert sum(hasattr(item, "selection") for item in results) == 1
    assert sum(isinstance(item, FinanceCommandConflict) for item in results) == 1


def test_concurrent_approve_reject_has_one_resolution(ctx):
    ctx.service.submit(submission(ctx), ctx.alex)
    approve = resolution(ctx, approved=True, reason=None, key="approve")
    reject = approve.model_copy(
        update={"approved": False, "reason": "reject", "idempotency_key": "reject"}
    )
    results = _run_concurrently(
        lambda: ctx.service.resolve(approve, ctx.taylor),
        lambda: ctx.service.resolve(reject, ctx.taylor),
    )
    assert sum(hasattr(item, "review") for item in results) == 1
    assert sum(isinstance(item, FinanceCommandConflict) for item in results) == 1


def test_concurrent_identical_resolution_replays_one_revision(ctx):
    ctx.service.submit(submission(ctx), ctx.alex)
    command = resolution(ctx, approved=True, reason=None, key="same-resolution")
    results = _run_concurrently(
        lambda: ctx.service.resolve(command, ctx.taylor),
        lambda: ctx.service.resolve(command, ctx.taylor),
    )
    assert results[0] == results[1]
    assert isinstance(results[0], ResolutionResult)
    assert results[0].review_revision == 2
    assert rows(ctx) == (1, 2, 0, 0)


@pytest.mark.parametrize(
    ("target_cost", "requires_review"), (("20000.00", False), ("20000.01", True))
)
def test_exact_cost_threshold_comes_from_persisted_analysis(
    tmp_path, ctx, target_cost, requires_review
):
    store = sqlite_store(f"sqlite:///{tmp_path / f'cost-{target_cost}.db'}")
    case, snapshot = instantiate_rl001(
        case_id=f"RL-CASE-COST-{target_cost}",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    assert snapshot.alpha_expedite is not None
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
    analysis_id = f"RL-ANALYSIS-COST-{target_cost}"
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
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    with store.uow_factory() as uow:
        token = uow.proposals.get_state(case.case_id).token
    command = SubmitProposalCommand(
        case_id=case.case_id,
        option_id="RL-OPTION-EXPEDITE",
        expected=token,
        idempotency_key="cost-threshold",
    )
    result = FinanceService(
        _finance_uow_factory(store), actors=ctx.actors, clock=lambda: SUBMITTED
    ).submit(command, ctx.alex)
    assert result.selection.proposal.response_cost == Decimal(target_cost)
    assert (result.review is not None) is requires_review
    store.engine.dispose()


def test_pending_list_and_exact_historical_detail(ctx):
    first = ctx.service.submit(submission(ctx), ctx.alex)
    assert first.review is not None
    listed = ctx.service.list_pending(ctx.taylor)
    assert [detail.review.review_id for detail in listed] == [first.review.review_id]
    assert listed[0].is_current

    ctx.service.resolve(resolution(ctx), ctx.taylor)
    assert ctx.service.list_pending(ctx.taylor) == ()
    second = ctx.service.submit(submission(ctx, key="submit-2"), ctx.alex)
    assert second.review is not None
    assert [
        detail.review.review_id for detail in ctx.service.list_pending(ctx.taylor)
    ] == [second.review.review_id]

    historical = ctx.service.detail(first.review.review_id, ctx.taylor)
    assert historical.review.review_id == first.review.review_id
    assert historical.selection == first.selection
    assert historical.option.option_id == first.selection.proposal.option_id
    assert historical.analysis.analysis_id == first.selection.proposal.analysis_id
    assert historical.review.reason == "Budget 10000"
    assert historical.review.status.value == "superseded"
    assert not historical.is_current
    assert historical.current_token.selection_id == second.selection.selection_id
    assert historical.review.review_id != second.review.review_id


@pytest.mark.parametrize("approved", (True, False))
def test_latest_terminal_review_is_not_pending(ctx, approved):
    result = ctx.service.submit(submission(ctx), ctx.alex)
    assert result.review is not None
    ctx.service.resolve(
        resolution(ctx, approved=approved, reason=None if approved else "declined"),
        ctx.taylor,
    )
    assert ctx.service.list_pending(ctx.taylor) == ()


def test_current_status_and_pending_queries_are_read_only(ctx):
    ctx.service.submit(submission(ctx), ctx.alex)
    ctx.service.resolve(resolution(ctx), ctx.taylor)
    transfer = ctx.service.submit(
        submission(ctx, "RL-OPTION-TRANSFER", "transfer"), ctx.alex
    )
    before_state, before_rows = current(ctx), rows(ctx)

    assert (
        ctx.service.status(ctx.case.case_id, ctx.alex).selection == transfer.selection
    )
    assert ctx.service.list_pending(ctx.taylor) == ()
    assert current(ctx) == before_state
    assert rows(ctx) == before_rows


def test_status_rejects_legacy_workflow_without_mutation(ctx):
    legacy, snapshot = instantiate_rl001(
        case_id="RL-CASE-FINANCE-LEGACY-STATUS",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.LEGACY,
    )
    ctx.store.create_case(legacy, snapshot)
    before_rows = rows(ctx)

    with pytest.raises(FinanceRequestInvalid):
        ctx.service.status(legacy.case_id, ctx.alex)

    assert rows(ctx) == before_rows
    with ctx.store.uow_factory() as uow:
        assert uow.proposals.get_state(legacy.case_id).token.generation == 0


@pytest.mark.parametrize(
    ("method", "actor"),
    (
        ("list_pending", "alex"),
        ("detail", "alex"),
        ("status", "taylor"),
        ("list_pending", "bad_taylor"),
        ("status", "bad_alex"),
    ),
)
def test_query_authorization_precedes_data_access(ctx, method, actor):
    def forbidden() -> Never:
        raise AssertionError("unauthorized query opened a UoW")

    service = FinanceService(forbidden, actors=ctx.actors)
    identities = {
        "alex": ctx.alex,
        "taylor": ctx.taylor,
        "bad_taylor": ctx.taylor.model_copy(update={"effective_roles": ()}),
        "bad_alex": ctx.alex.model_copy(
            update={"effective_roles": ("material_planner",)}
        ),
    }
    arguments = {
        "list_pending": (identities[actor],),
        "detail": ("known-review-id", identities[actor]),
        "status": (ctx.case.case_id, identities[actor]),
    }

    with pytest.raises(FinancePermissionDenied):
        getattr(service, method)(*arguments[method])


def test_queries_survive_store_reopen_without_mutation(ctx):
    result = ctx.service.submit(submission(ctx), ctx.alex)
    assert result.review is not None
    expected = ctx.service.detail(result.review.review_id, ctx.taylor)
    before_state, before_rows = current(ctx), rows(ctx)
    url = str(ctx.store.engine.url)
    ctx.store.engine.dispose()
    reopened = SqliteStore(build_sqlite_engine(url), runtime_mode=RuntimeMode.FALLBACK)
    try:
        service = FinanceService(_finance_uow_factory(reopened), actors=ctx.actors)
        assert service.detail(result.review.review_id, ctx.taylor) == expected
        assert service.list_pending(ctx.taylor) == (expected,)
        assert service.status(ctx.case.case_id, ctx.alex).selection == result.selection
        with reopened.uow_factory() as uow:
            assert uow.proposals.get_state(ctx.case.case_id) == before_state
        with reopened.engine.connect() as connection:
            assert (
                tuple(
                    connection.scalar(select(func.count()).select_from(table))
                    for table in (
                        case_proposal_selections,
                        finance_review_revisions,
                        decisions,
                        outbox_events,
                    )
                )
                == before_rows
            )
    finally:
        reopened.engine.dispose()


def test_pending_and_detail_enforce_exact_persisted_submitter(ctx):
    own = ctx.service.submit(submission(ctx), ctx.alex)
    assert own.review is not None
    other_tenant = _seed_pending_request(
        ctx,
        suffix="TENANT",
        tenant="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        alex_object="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        taylor_object="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    )
    other_alex = _seed_pending_request(
        ctx,
        suffix="ALEX",
        tenant=str(ctx.actors.tenant_id),
        alex_object="dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        taylor_object=str(ctx.actors.taylor_object_id),
    )
    before_rows = rows(ctx)
    own_state = current(ctx)

    assert [
        detail.review.review_id for detail in ctx.service.list_pending(ctx.taylor)
    ] == [own.review.review_id]
    for foreign in (other_tenant, other_alex):
        assert foreign.review is not None
        with pytest.raises(FinancePermissionDenied):
            ctx.service.detail(foreign.review.review_id, ctx.taylor)

    assert rows(ctx) == before_rows
    assert current(ctx) == own_state


def test_historical_detail_read_does_not_advance_generation_or_rows(ctx):
    first = ctx.service.submit(submission(ctx), ctx.alex)
    assert first.review is not None
    rejected = ctx.service.resolve(resolution(ctx), ctx.taylor)
    replacement = ctx.service.submit(
        submission(ctx, "RL-OPTION-TRANSFER", "replacement"), ctx.alex
    )
    before_state, before_rows = current(ctx), rows(ctx)

    detail = ctx.service.detail(first.review.review_id, ctx.taylor)

    assert detail.selection == first.selection
    assert detail.review.review_id == rejected.review.review_id
    assert detail.review.status.value == "superseded"
    assert detail.review.reason == "Budget 10000"
    assert detail.analysis == ctx.analysis
    assert detail.current_token.selection_id == replacement.selection.selection_id
    assert current(ctx) == before_state
    assert rows(ctx) == before_rows
