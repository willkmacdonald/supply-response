"""Cross-database contract using only Decision-targeted queue operations.

Unscoped global-worker behavior is covered by isolated SQLite worker tests so an
opted-in Fabric run can never consume unrelated persistent application work.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier, Lock
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update

from data.domain import CasePurpose, CaseStatus
from data.domain.analysis import AnalysisVersion
from data.domain.cases import CaseInstance
from data.domain.decisions import (
    CorpusScope,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
    StandingAuthorization,
)
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceProposal, FinanceReview
from data.synthetic.rl001 import (
    OperationalSnapshot,
    build_rl001_evidence,
    instantiate_rl001,
)
from integrations.fabric.config import FabricEnvironmentState, fabric_environment_state
from integrations.fabric.schema import apply_fabric_schema
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import DecisionService, IdempotencyKeyConflict
from services.execution.playback import ImmediateClock, PlaybackService
from services.execution.worker import ActionPlanningWorker, UnitOfWorkFactory
from services.persistence.finance_reviews import (
    FinanceReviewIdempotencyConflict,
    FinanceReviewRevisionConflict,
    SqlAlchemyFinanceReviewRepository,
    append_finance_review,
)
from services.persistence.sqlite import sqlite_store
from services.persistence.store import (
    ImmutableRecordConflict,
    PersistenceIntegrityError,
    SqlAlchemyCaseRepository,
    SqlAlchemyStore,
)
from services.persistence.tables import (
    case_projection,
    execution_actions,
    finance_review_revisions,
    outbox_events,
)
from services.policy.finance_review import resolve_finance_review, submit_finance_review

StoreFactory = Callable[[], SqlAlchemyStore]
OutboxCleanup = Callable[["DecisionContext"], None]


@pytest.fixture(
    params=["sqlite", pytest.param("fabric", marks=pytest.mark.fabric_live)]
)
def store_factory(request, tmp_path) -> StoreFactory:
    if request.param == "sqlite":
        database_url = f"sqlite:///{tmp_path / 'contract.db'}"
        return lambda: sqlite_store(database_url)
    if fabric_environment_state() is FabricEnvironmentState.ABSENT:
        pytest.skip("Fabric SQL live settings are not configured")
    from services.persistence.fabric_sql import fabric_store_from_environment

    def configured_fabric_store() -> SqlAlchemyStore:
        store = fabric_store_from_environment()
        apply_fabric_schema(store.engine)
        return store

    return configured_fabric_store


@pytest.fixture
def outbox_cleanup() -> Iterator[OutboxCleanup]:
    """Finish only this test's registered Decision events during teardown."""

    owned: dict[str, DecisionContext] = {}

    def register(context: DecisionContext) -> None:
        owned[context.case.case_id] = context

    yield register
    _finish_test_owned_outbox(tuple(owned.values()))


def _alex() -> IdentitySnapshot:
    return IdentitySnapshot(
        persona_id="RL-PERSONA-ALEX",
        effective_roles=("material_planner", "response_approver"),
        identity_source=IdentitySource.ENTRA,
        source_id="RL-ENTRA-ALEX",
        display_name="Alex Morgan",
        user_principal_name="alex@example.invalid",
    )


def _finance_actor(persona: str) -> IdentitySnapshot:
    return IdentitySnapshot(
        persona_id=f"RL-PERSONA-{persona}",
        effective_roles=(
            ("material_planner", "response_approver")
            if persona == "ALEX"
            else ("finance_approver",)
        ),
        identity_source=IdentitySource.ENTRA,
        source_id=f"RL-ENTRA-{persona}",
        tenant_id="11111111-1111-4111-8111-111111111111",
        object_id=(
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            if persona == "ALEX"
            else "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        ),
    )


@dataclass(frozen=True)
class DecisionContext:
    store: SqlAlchemyStore
    case: CaseInstance
    snapshot: OperationalSnapshot
    analysis: AnalysisVersion
    suffix: str

    @property
    def uow_factory(self) -> UnitOfWorkFactory:
        return cast(UnitOfWorkFactory, self.store.uow_factory)


def _persist_analysis(store: SqlAlchemyStore) -> DecisionContext:
    suffix = str(uuid4())
    case, snapshot = instantiate_rl001(
        case_id=f"RL-CASE-CONTRACT-{suffix}",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=store.runtime_mode,
    )
    analysis_id = f"RL-ANALYSIS-CONTRACT-{suffix}"
    started_at = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    analysis = analyze_case(
        AnalyzeCaseCommand(
            analysis_id=analysis_id,
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot,
                analysis_id=analysis_id,
                retrieved_at=started_at,
            ),
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
            analysis_started_at=started_at,
            created_at=started_at,
            calculation_version="rl001-options-v1",
        )
    )
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    store.save_case_projection(
        case.model_copy(update={"status": CaseStatus.AWAITING_DECISION})
    )
    return DecisionContext(
        store=store,
        case=case,
        snapshot=snapshot,
        analysis=analysis,
        suffix=suffix,
    )


def _pending_finance_review(context: DecisionContext) -> FinanceReview:
    option = next(
        item
        for item in context.analysis.response_options
        if item.option_id == "RL-OPTION-COMBINED"
    )
    assert option.predicted is not None
    proposal = FinanceProposal(
        case_id=context.case.case_id,
        analysis_id=context.analysis.analysis_id,
        analysis_material_hash=context.analysis.material_hash,
        option_id=option.option_id,
        response_cost=Decimal(option.predicted.response_cost),
    )
    return submit_finance_review(
        review_id=f"RL-FINANCE-CONTRACT-{context.suffix}",
        proposal=proposal,
        actor=_finance_actor("ALEX"),
        now=datetime(2026, 9, 13, 12, tzinfo=UTC),
    )


def _resolved_finance_review(
    pending: FinanceReview, *, approved: bool
) -> FinanceReview:
    return resolve_finance_review(
        review=pending,
        current_proposal=pending.proposal,
        actor=_finance_actor("TAYLOR"),
        approved=approved,
        reason="Within budget" if approved else "Too costly",
        now=pending.submitted_at + timedelta(seconds=1),
    )


def _finance_rows(store: SqlAlchemyStore, review_id: str):
    with store.engine.connect() as connection:
        return tuple(
            connection.execute(
                select(finance_review_revisions)
                .where(finance_review_revisions.c.review_id == review_id)
                .order_by(finance_review_revisions.c.revision)
            )
            .mappings()
            .all()
        )


def _race_finance_appends(
    monkeypatch: pytest.MonkeyPatch,
    store: SqlAlchemyStore,
    calls: tuple[tuple[FinanceReview, str, str], tuple[FinanceReview, str, str]],
):
    barrier = Barrier(2)
    coordination_lock = Lock()
    original = SqlAlchemyFinanceReviewRepository.get_latest
    synchronized_connections: list[int] = []

    def synchronized_get_latest(repository, review_id):
        result = original(repository, review_id)
        synchronize = False
        with coordination_lock:
            if review_id == calls[0][0].review_id and len(synchronized_connections) < 2:
                synchronized_connections.append(id(repository._connection))
                synchronize = True
        if synchronize:
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(
        SqlAlchemyFinanceReviewRepository,
        "get_latest",
        synchronized_get_latest,
    )

    def append(call):
        review, key, fingerprint = call
        return append_finance_review(
            cast(UnitOfWorkFactory, store.uow_factory),
            review,
            expected_revision=1,
            idempotency_key=key,
            request_fingerprint=fingerprint,
        )

    def capture(call):
        try:
            return append(call)
        except (
            FinanceReviewRevisionConflict,
            FinanceReviewIdempotencyConflict,
        ) as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(capture, calls))

    assert len(synchronized_connections) == 2
    assert len(set(synchronized_connections)) == 2
    return results


def _delete_finance_review(store: SqlAlchemyStore, review_id: str) -> None:
    with store.engine.begin() as connection:
        connection.execute(
            delete(finance_review_revisions).where(
                finance_review_revisions.c.review_id == review_id
            )
        )


def _decision_command(
    context: DecisionContext,
    *,
    idempotency_key: str | None = None,
    kind: DecisionKind = DecisionKind.APPROVED,
) -> RecordDecisionCommand:
    approved = kind is DecisionKind.APPROVED
    return RecordDecisionCommand(
        case_id=context.case.case_id,
        analysis_id=context.analysis.analysis_id,
        selected_option_id="RL-OPTION-COMBINED" if approved else None,
        kind=kind,
        idempotency_key=idempotency_key or f"RL-IDEMPOTENCY-CONTRACT-{context.suffix}",
        rejection_reason=None if approved else "Refresh supplier recovery evidence.",
    )


def _record_approved(context: DecisionContext):
    return DecisionService(context.uow_factory).record(
        _decision_command(context),
        _alex(),
    )


def _record_approved_at(context: DecisionContext, decided_at: datetime):
    return DecisionService(
        context.uow_factory,
        clock=lambda: decided_at,
    ).record(_decision_command(context), _alex())


def _process_decision_outbox(
    context: DecisionContext,
    decision_id: str,
) -> None:
    assert ActionPlanningWorker(context.uow_factory).process_decision_outbox(
        decision_id
    )
    with context.uow_factory() as uow:
        event = uow.execution.list_outbox(decision_id=decision_id)[0]
        state = uow.execution.get_outbox_state(event.event_id)
        assert state.processed_at is not None
        assert state.last_error is None


def _finish_test_owned_outbox(contexts: tuple[DecisionContext, ...]) -> None:
    """Target unfinished events discoverable through this test's unique cases."""

    for context in contexts:
        pending_decision_ids: list[str] = []
        with context.uow_factory() as uow:
            decisions = uow.decisions.list_for_case(context.case.case_id)
            for decision in decisions:
                events = uow.execution.list_outbox(decision_id=decision.decision_id)
                if not events:
                    continue
                state = uow.execution.get_outbox_state(events[0].event_id)
                if state.processed_at is None:
                    pending_decision_ids.append(decision.decision_id)
        for decision_id in pending_decision_ids:
            _process_decision_outbox(context, decision_id)


def _unrelated_rows_snapshot(
    store: SqlAlchemyStore,
    *,
    case_ids: tuple[str, ...],
    decision_ids: tuple[str, ...],
) -> dict[str, tuple[dict[str, object], ...]]:
    with store.engine.connect() as connection:
        return {
            "outbox": tuple(
                dict(row)
                for row in connection.execute(
                    select(outbox_events)
                    .where(outbox_events.c.decision_id.in_(decision_ids))
                    .order_by(outbox_events.c.event_id)
                ).mappings()
            ),
            "case_projection": tuple(
                dict(row)
                for row in connection.execute(
                    select(case_projection)
                    .where(case_projection.c.case_id.in_(case_ids))
                    .order_by(case_projection.c.case_id)
                ).mappings()
            ),
            "execution_actions": tuple(
                dict(row)
                for row in connection.execute(
                    select(execution_actions)
                    .where(execution_actions.c.decision_id.in_(decision_ids))
                    .order_by(execution_actions.c.action_id)
                ).mappings()
            ),
        }


def _persist_complete_rl001(
    store: SqlAlchemyStore,
    register_outbox: OutboxCleanup | None = None,
) -> tuple[str, str, str, str]:
    context = _persist_analysis(store)
    if register_outbox is not None:
        register_outbox(context)
    started_at = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    decision = _record_approved(context)
    _process_decision_outbox(context, decision.decision_id)
    playback_service = PlaybackService(
        context.uow_factory,
        clock=ImmediateClock(started_at),
    )
    playback = playback_service.start(decision.decision_id, _alex())
    playback_service.run_to_completion(playback.playback_id, clock=ImmediateClock())
    return (
        context.case.case_id,
        context.analysis.analysis_id,
        decision.decision_id,
        playback.playback_id,
    )


def _load_complete_rl001(
    store: SqlAlchemyStore,
    ids: tuple[str, str, str, str],
) -> dict[str, object]:
    case_id, analysis_id, decision_id, playback_id = ids
    with cast(UnitOfWorkFactory, store.uow_factory)() as uow:
        actions = uow.execution.list_actions(decision_id=decision_id)
        return {
            "case": uow.cases.get_case(case_id),
            "analysis": uow.cases.get_analysis(analysis_id),
            "decision": uow.decisions.get(decision_id),
            "outbox": uow.execution.list_outbox(decision_id=decision_id),
            "actions": actions,
            "drafts": tuple(
                uow.execution.get_draft_artifact(action.action_id)
                for action in actions
                if action.draft_artifact_id is not None
            ),
            "attempts": tuple(
                uow.execution.list_attempts(action.action_id) for action in actions
            ),
            "events": tuple(
                uow.execution.list_status_events(action.action_id) for action in actions
            ),
            "playback": uow.execution.get_playback(playback_id),
            "observations": uow.execution.list_observations(decision_id),
        }


def test_case_analysis_decision_outbox_action_and_observation_round_trip(
    store_factory: StoreFactory,
    outbox_cleanup: OutboxCleanup,
):
    first = store_factory()
    ids = _persist_complete_rl001(first, outbox_cleanup)
    expected = _load_complete_rl001(first, ids)

    restored = _load_complete_rl001(store_factory(), ids)

    assert restored == expected
    assert len(cast(tuple[object, ...], restored["actions"])) == 5
    assert len(cast(tuple[object, ...], restored["drafts"])) == 1
    assert len(cast(tuple[object, ...], restored["observations"])) == 10


def test_concurrent_finance_review_resolutions_with_different_keys_have_one_winner(
    store_factory: StoreFactory,
    monkeypatch: pytest.MonkeyPatch,
):
    store = store_factory()
    pending = _pending_finance_review(_persist_analysis(store))
    approved = _resolved_finance_review(pending, approved=True)
    rejected = _resolved_finance_review(pending, approved=False)
    append_finance_review(
        cast(UnitOfWorkFactory, store.uow_factory),
        pending,
        expected_revision=None,
        idempotency_key=f"submit-{pending.review_id}",
        request_fingerprint="a" * 64,
    )
    try:
        results = _race_finance_appends(
            monkeypatch,
            store,
            (
                (approved, f"approve-{pending.review_id}", "b" * 64),
                (rejected, f"reject-{pending.review_id}", "c" * 64),
            ),
        )

        winners = tuple(item for item in results if isinstance(item, tuple))
        conflicts = tuple(
            item for item in results if isinstance(item, FinanceReviewRevisionConflict)
        )
        assert len(winners) == 1
        assert winners[0][1] == 2
        assert len(conflicts) == 1
        with store.uow_factory() as uow:
            assert uow.finance_reviews.get_latest(pending.review_id) == winners[0]
        rows = _finance_rows(store, pending.review_id)
        assert [row["revision"] for row in rows] == [1, 2]
        assert len(rows) == 2
    finally:
        _delete_finance_review(store, pending.review_id)


def test_concurrent_finance_review_replay_with_same_key_returns_one_revision(
    store_factory: StoreFactory,
    monkeypatch: pytest.MonkeyPatch,
):
    store = store_factory()
    pending = _pending_finance_review(_persist_analysis(store))
    approved = _resolved_finance_review(pending, approved=True)
    append_finance_review(
        cast(UnitOfWorkFactory, store.uow_factory),
        pending,
        expected_revision=None,
        idempotency_key=f"submit-{pending.review_id}",
        request_fingerprint="d" * 64,
    )
    call = (approved, f"approve-{pending.review_id}", "e" * 64)
    try:
        results = _race_finance_appends(monkeypatch, store, (call, call))

        assert results == ((approved, 2), (approved, 2))
        rows = _finance_rows(store, pending.review_id)
        assert [row["revision"] for row in rows] == [1, 2]
        assert sum(row["revision"] == 2 for row in rows) == 1
    finally:
        _delete_finance_review(store, pending.review_id)


def test_concurrent_finance_review_same_key_with_different_request_conflicts(
    store_factory: StoreFactory,
    monkeypatch: pytest.MonkeyPatch,
):
    store = store_factory()
    pending = _pending_finance_review(_persist_analysis(store))
    approved = _resolved_finance_review(pending, approved=True)
    rejected = _resolved_finance_review(pending, approved=False)
    append_finance_review(
        cast(UnitOfWorkFactory, store.uow_factory),
        pending,
        expected_revision=None,
        idempotency_key=f"submit-{pending.review_id}",
        request_fingerprint="f" * 64,
    )
    shared_key = f"resolve-{pending.review_id}"
    try:
        results = _race_finance_appends(
            monkeypatch,
            store,
            (
                (approved, shared_key, "1" * 64),
                (rejected, shared_key, "2" * 64),
            ),
        )

        winners = tuple(item for item in results if isinstance(item, tuple))
        conflicts = tuple(
            item
            for item in results
            if isinstance(item, FinanceReviewIdempotencyConflict)
        )
        assert len(winners) == 1
        assert winners[0][1] == 2
        assert len(conflicts) == 1
        rows = _finance_rows(store, pending.review_id)
        assert [row["revision"] for row in rows] == [1, 2]
        assert len(rows) == 2
    finally:
        _delete_finance_review(store, pending.review_id)


def test_decision_and_outbox_transaction_rolls_back_atomically(
    store_factory: StoreFactory,
):
    context = _persist_analysis(store_factory())

    def fail_before_outbox() -> None:
        raise RuntimeError("injected outbox failure")

    def faulting_uow():
        return context.store.uow_factory(before_outbox_insert=fail_before_outbox)

    with pytest.raises(RuntimeError, match="injected outbox failure"):
        DecisionService(cast(UnitOfWorkFactory, faulting_uow)).record(
            _decision_command(context),
            _alex(),
        )

    with context.uow_factory() as uow:
        assert uow.decisions.list_for_case(context.case.case_id) == ()
        projection = uow.cases.get_projection(context.case.case_id)
        assert projection.current_decision_id is None
        assert projection.case.status is CaseStatus.AWAITING_DECISION


def test_rejected_decision_has_no_outbox_event(store_factory: StoreFactory):
    context = _persist_analysis(store_factory())

    decision = DecisionService(context.uow_factory).record(
        _decision_command(context, kind=DecisionKind.REJECTED),
        _alex(),
    )

    with context.uow_factory() as uow:
        assert uow.decisions.get(decision.decision_id) == decision
        assert uow.execution.list_outbox(decision_id=decision.decision_id) == ()
        projection = uow.cases.get_projection(context.case.case_id)
        assert projection.current_decision_id == decision.decision_id
        assert projection.case.status is CaseStatus.DECISION_REJECTED


def test_decision_idempotent_replay_and_divergent_conflict(
    store_factory: StoreFactory,
    outbox_cleanup: OutboxCleanup,
):
    context = _persist_analysis(store_factory())
    outbox_cleanup(context)
    service = DecisionService(context.uow_factory)
    command = _decision_command(context)

    first = service.record(command, _alex())
    replay = service.record(command, _alex())

    assert replay == first
    with pytest.raises(IdempotencyKeyConflict, match="different request"):
        service.record(
            _decision_command(
                context,
                idempotency_key=command.idempotency_key,
                kind=DecisionKind.REJECTED,
            ),
            _alex(),
        )
    with context.uow_factory() as uow:
        assert uow.decisions.list_for_case(context.case.case_id) == (first,)
        assert len(uow.execution.list_outbox(decision_id=first.decision_id)) == 1
    _process_decision_outbox(context, first.decision_id)


def test_concurrent_same_key_creates_one_decision_and_outbox(
    store_factory: StoreFactory,
    outbox_cleanup: OutboxCleanup,
):
    context = _persist_analysis(store_factory())
    outbox_cleanup(context)
    command = _decision_command(context)
    barrier = Barrier(2)

    def record() -> str:
        barrier.wait()
        return DecisionService(context.uow_factory).record(command, _alex()).decision_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        decision_ids = tuple(executor.map(lambda _: record(), range(2)))

    assert len(set(decision_ids)) == 1
    with context.uow_factory() as uow:
        decisions = uow.decisions.list_for_case(context.case.case_id)
        assert len(decisions) == 1
        assert len(uow.execution.list_outbox(decision_id=decision_ids[0])) == 1
    _process_decision_outbox(context, decision_ids[0])


def test_outbox_failure_and_targeted_retries_are_durable(
    store_factory: StoreFactory,
    outbox_cleanup: OutboxCleanup,
):
    store = store_factory()
    first = _persist_analysis(store)
    outbox_cleanup(first)
    first_decision = _record_approved(first)
    with first.uow_factory() as uow:
        first_event = uow.execution.list_outbox(decision_id=first_decision.decision_id)[
            0
        ]

    def fail_planning(decision):
        raise RuntimeError(f"cannot plan {decision.decision_id}")

    failing_worker = ActionPlanningWorker(first.uow_factory, planner=fail_planning)
    assert failing_worker.process_decision_outbox(first_decision.decision_id)
    with first.uow_factory() as uow:
        state = uow.execution.get_outbox_state(first_event.event_id)
        assert state.attempt_count == 1
        assert state.last_error == "RUNTIME_ERROR"
        assert state.processed_at is None
    assert ActionPlanningWorker(first.uow_factory).process_decision_outbox(
        first_decision.decision_id
    )
    with first.uow_factory() as uow:
        recovered = uow.execution.get_outbox_state(first_event.event_id)
        assert recovered.attempt_count == 1
        assert recovered.last_error is None
        assert recovered.processed_at is not None
        assert (
            len(uow.execution.list_actions(decision_id=first_decision.decision_id)) == 5
        )

    second = _persist_analysis(store)
    outbox_cleanup(second)
    second_decision = _record_approved(second)
    with second.uow_factory() as uow:
        second_event = uow.execution.list_outbox(
            decision_id=second_decision.decision_id
        )[0]
    assert ActionPlanningWorker(
        second.uow_factory,
        planner=fail_planning,
    ).process_decision_outbox(second_decision.decision_id)
    assert ActionPlanningWorker(second.uow_factory).process_decision_outbox(
        second_decision.decision_id
    )
    with second.uow_factory() as uow:
        targeted_recovery = uow.execution.get_outbox_state(second_event.event_id)
        assert targeted_recovery.attempt_count == 1
        assert targeted_recovery.last_error is None
        assert targeted_recovery.processed_at is not None


def test_immutable_conflict_and_projection_tamper_are_detected(
    store_factory: StoreFactory,
):
    context = _persist_analysis(store_factory())
    original = context.store.get_case(context.case.case_id)

    with pytest.raises(ImmutableRecordConflict, match="case already exists"):
        context.store.create_case(context.case, context.snapshot)

    connection = context.store.engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == context.case.case_id)
            .values(status=CaseStatus.EXECUTING.value)
        )
        with pytest.raises(PersistenceIntegrityError, match="case projection"):
            SqlAlchemyCaseRepository(context.store, connection).get_case(
                context.case.case_id
            )
    finally:
        transaction.rollback()
        connection.close()
    assert context.store.get_case(context.case.case_id) == original


def test_targeted_contract_helpers_preserve_unrelated_shared_database_work(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'shared-contract.db'}")
    pending = _persist_analysis(store)
    pending_decision = _record_approved_at(
        pending,
        datetime(2020, 1, 1, tzinfo=UTC),
    )
    failed = _persist_analysis(store)
    failed_decision = _record_approved_at(
        failed,
        datetime(2021, 1, 1, tzinfo=UTC),
    )

    def fail_planning(decision):
        raise RuntimeError(f"cannot plan {decision.decision_id}")

    assert ActionPlanningWorker(
        failed.uow_factory,
        planner=fail_planning,
    ).process_decision_outbox(failed_decision.decision_id)
    with pending.uow_factory() as uow:
        pending_event = uow.execution.list_outbox(
            decision_id=pending_decision.decision_id
        )[0]
        pending_state = uow.execution.get_outbox_state(pending_event.event_id)
        failed_event = uow.execution.list_outbox(
            decision_id=failed_decision.decision_id
        )[0]
        failed_state = uow.execution.get_outbox_state(failed_event.event_id)
        assert pending_state.processed_at is None
        assert pending_state.attempt_count == 0
        assert pending_state.last_error is None
        assert failed_state.processed_at is None
        assert failed_state.attempt_count == 1
        assert failed_state.last_error == "RUNTIME_ERROR"
    unrelated_case_ids = (pending.case.case_id, failed.case.case_id)
    unrelated_decision_ids = (
        pending_decision.decision_id,
        failed_decision.decision_id,
    )
    before = _unrelated_rows_snapshot(
        store,
        case_ids=unrelated_case_ids,
        decision_ids=unrelated_decision_ids,
    )

    completed_ids = _persist_complete_rl001(store)
    current = _persist_analysis(store)
    current_decision = _record_approved(current)
    assert ActionPlanningWorker(
        current.uow_factory,
        planner=fail_planning,
    ).process_decision_outbox(current_decision.decision_id)
    _finish_test_owned_outbox((current,))

    after = _unrelated_rows_snapshot(
        store,
        case_ids=unrelated_case_ids,
        decision_ids=unrelated_decision_ids,
    )
    assert after == before
    with current.uow_factory() as uow:
        assert (
            uow.execution.get_outbox_state(
                uow.execution.list_outbox(decision_id=completed_ids[2])[0].event_id
            ).processed_at
            is not None
        )
        assert (
            uow.execution.get_outbox_state(
                uow.execution.list_outbox(decision_id=current_decision.decision_id)[
                    0
                ].event_id
            ).processed_at
            is not None
        )


def test_repeated_and_concurrent_playback_start_return_one_record(
    store_factory: StoreFactory,
    outbox_cleanup: OutboxCleanup,
):
    context = _persist_analysis(store_factory())
    outbox_cleanup(context)
    decision = _record_approved(context)
    _process_decision_outbox(context, decision.decision_id)
    service = PlaybackService(context.uow_factory)
    barrier = Barrier(2)

    def start():
        barrier.wait()
        return service.start(decision.decision_id, _alex())

    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent = tuple(executor.map(lambda _: start(), range(2)))
    repeated = service.start(decision.decision_id, _alex())

    assert len({item.playback_id for item in (*concurrent, repeated)}) == 1
    with context.uow_factory() as uow:
        assert uow.execution.get_playback_for_decision(decision.decision_id) == repeated


def test_completed_playback_replay_adds_no_attempts_events_or_observations(
    store_factory: StoreFactory,
    outbox_cleanup: OutboxCleanup,
):
    context = _persist_analysis(store_factory())
    outbox_cleanup(context)
    decision = _record_approved(context)
    _process_decision_outbox(context, decision.decision_id)
    service = PlaybackService(context.uow_factory)
    playback = service.start(decision.decision_id, _alex())
    first = service.run_to_completion(playback.playback_id, clock=ImmediateClock())

    def counts() -> tuple[tuple[int, ...], tuple[int, ...], int]:
        with context.uow_factory() as uow:
            actions = uow.execution.list_actions(decision_id=decision.decision_id)
            attempts = tuple(
                len(uow.execution.list_attempts(action.action_id)) for action in actions
            )
            events = tuple(
                len(uow.execution.list_status_events(action.action_id))
                for action in actions
            )
            observations = len(uow.execution.list_observations(decision.decision_id))
        return attempts, events, observations

    before = counts()
    replay = service.run_to_completion(playback.playback_id, clock=ImmediateClock())

    assert replay == first
    assert counts() == before
    assert before == ((1, 1, 1, 1, 1), (3, 3, 3, 3, 3), 10)
