from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from typing import cast
from uuid import uuid4

import pytest

from data.domain import CasePurpose, CaseStatus
from data.domain.decisions import (
    CorpusScope,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
    StandingAuthorization,
)
from data.domain.evidence import IdentitySource
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import DecisionService
from services.execution.playback import ImmediateClock, PlaybackService
from services.execution.worker import ActionPlanningWorker, UnitOfWorkFactory
from services.persistence.sqlite import sqlite_store
from services.persistence.store import SqlAlchemyStore


StoreFactory = Callable[[], SqlAlchemyStore]


def _fabric_configured() -> bool:
    return bool(
        os.getenv("SUPPLY_RESPONSE_FABRIC_SQL_SERVER")
        and os.getenv("SUPPLY_RESPONSE_FABRIC_SQL_DATABASE")
    )


@pytest.fixture(
    params=["sqlite", pytest.param("fabric", marks=pytest.mark.fabric_live)]
)
def store_factory(request, tmp_path) -> StoreFactory:
    if request.param == "sqlite":
        database_url = f"sqlite:///{tmp_path / 'contract.db'}"
        return lambda: sqlite_store(database_url)
    if not _fabric_configured():
        pytest.skip("Fabric SQL live settings are not configured")
    from services.persistence.fabric_sql import fabric_store_from_environment

    return fabric_store_from_environment


def _alex() -> IdentitySnapshot:
    return IdentitySnapshot(
        persona_id="RL-PERSONA-ALEX",
        effective_roles=("material_planner", "response_approver"),
        identity_source=IdentitySource.ENTRA,
        source_id="RL-ENTRA-ALEX",
        display_name="Alex Morgan",
        user_principal_name="alex@example.invalid",
    )


def _persist_complete_rl001(store: SqlAlchemyStore) -> tuple[str, str, str, str]:
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
    uow_factory = cast(UnitOfWorkFactory, store.uow_factory)
    decision = DecisionService(uow_factory).record(
        RecordDecisionCommand(
            case_id=case.case_id,
            analysis_id=analysis.analysis_id,
            selected_option_id="RL-OPTION-COMBINED",
            kind=DecisionKind.APPROVED,
            idempotency_key=f"RL-IDEMPOTENCY-CONTRACT-{suffix}",
        ),
        _alex(),
    )
    assert ActionPlanningWorker(uow_factory).process_next_outbox()
    playback_service = PlaybackService(
        uow_factory,
        clock=ImmediateClock(started_at),
    )
    playback = playback_service.start(decision.decision_id, _alex())
    playback_service.run_to_completion(playback.playback_id, clock=ImmediateClock())
    return (
        case.case_id,
        analysis.analysis_id,
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
    assert len(restored["actions"]) == 5
    assert len(restored["drafts"]) == 1
    assert len(restored["observations"]) == 10
