from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from threading import Barrier
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import update

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
from services.persistence.sqlite import sqlite_store
from services.persistence.store import (
    ImmutableRecordConflict,
    PersistenceIntegrityError,
    SqlAlchemyStore,
)
from services.persistence.tables import case_projection


StoreFactory = Callable[[], SqlAlchemyStore]


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


def _alex() -> IdentitySnapshot:
    return IdentitySnapshot(
        persona_id="RL-PERSONA-ALEX",
        effective_roles=("material_planner", "response_approver"),
        identity_source=IdentitySource.ENTRA,
        source_id="RL-ENTRA-ALEX",
        display_name="Alex Morgan",
        user_principal_name="alex@example.invalid",
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


def _persist_complete_rl001(store: SqlAlchemyStore) -> tuple[str, str, str, str]:
    context = _persist_analysis(store)
    started_at = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    decision = _record_approved(context)
    assert ActionPlanningWorker(context.uow_factory).process_next_outbox()
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
):
    first = store_factory()
    ids = _persist_complete_rl001(first)
    expected = _load_complete_rl001(first, ids)

    restored = _load_complete_rl001(store_factory(), ids)

    assert restored == expected
    assert len(cast(tuple[object, ...], restored["actions"])) == 5
    assert len(cast(tuple[object, ...], restored["drafts"])) == 1
    assert len(cast(tuple[object, ...], restored["observations"])) == 10


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
):
    context = _persist_analysis(store_factory())
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


def test_concurrent_same_key_creates_one_decision_and_outbox(
    store_factory: StoreFactory,
):
    context = _persist_analysis(store_factory())
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


def test_outbox_failure_targeted_retry_and_global_retry_are_durable(
    store_factory: StoreFactory,
):
    store = store_factory()
    first = _persist_analysis(store)
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
    assert not ActionPlanningWorker(first.uow_factory).process_next_unattempted_outbox()
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
    second_decision = _record_approved(second)
    with second.uow_factory() as uow:
        second_event = uow.execution.list_outbox(
            decision_id=second_decision.decision_id
        )[0]
    assert ActionPlanningWorker(
        second.uow_factory,
        planner=fail_planning,
    ).process_decision_outbox(second_decision.decision_id)
    assert ActionPlanningWorker(second.uow_factory).process_next_outbox()
    with second.uow_factory() as uow:
        globally_recovered = uow.execution.get_outbox_state(second_event.event_id)
        assert globally_recovered.attempt_count == 1
        assert globally_recovered.last_error is None
        assert globally_recovered.processed_at is not None


def test_immutable_conflict_and_projection_tamper_are_detected(
    store_factory: StoreFactory,
):
    context = _persist_analysis(store_factory())

    with pytest.raises(ImmutableRecordConflict, match="case already exists"):
        context.store.create_case(context.case, context.snapshot)

    with context.store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == context.case.case_id)
            .values(status=CaseStatus.EXECUTING.value)
        )
    with pytest.raises(PersistenceIntegrityError, match="case projection"):
        context.store.get_case(context.case.case_id)


def test_repeated_and_concurrent_playback_start_return_one_record(
    store_factory: StoreFactory,
):
    context = _persist_analysis(store_factory())
    decision = _record_approved(context)
    assert ActionPlanningWorker(context.uow_factory).process_next_outbox()
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
):
    context = _persist_analysis(store_factory())
    decision = _record_approved(context)
    assert ActionPlanningWorker(context.uow_factory).process_next_outbox()
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
