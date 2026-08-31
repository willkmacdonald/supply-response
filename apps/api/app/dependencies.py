from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, cast

from fastapi import Request
from sqlalchemy import select

from apps.api.app.settings import Settings
from apps.api.app.test_support import AutomatedTestFaults
from data.domain import RuntimeMode
from data.domain.analysis import AnalysisVersion
from data.domain.decisions import DecisionKind, IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.execution import PlaybackStatus
from services.analysis.application import FallbackAnalysisApplicationService
from services.decisions.service import DecisionService, UnitOfWorkFactory
from services.execution.planner import plan_actions
from services.execution.playback import PlaybackClock, PlaybackService, RealClock
from services.execution.worker import ActionPlanningWorker, ExecutionService
from services.persistence.sqlite import sqlite_store
from services.persistence.store import SqlAlchemyStore
from services.persistence.tables import (
    action_projection,
    case_instances,
    case_projection,
    playbacks,
)


def fallback_identity() -> IdentitySnapshot:
    """Resolve Alex from the server-owned fallback identity binding."""
    return IdentitySnapshot(
        persona_id="RL-PERSONA-ALEX",
        effective_roles=("material_planner", "response_approver"),
        identity_source=IdentitySource.ENTRA,
        source_id="RL-ENTRA-ALEX",
    )


class AnalysisApplicationService(Protocol):
    def create(self, case_id: str) -> AnalysisVersion: ...


@dataclass
class ApplicationServices:
    settings: Settings
    store: SqlAlchemyStore
    analysis_service: AnalysisApplicationService
    decision_service: DecisionService
    planning_worker: ActionPlanningWorker
    playback_service: PlaybackService
    playback_clock: PlaybackClock
    clock: Callable[[], datetime]
    identity: IdentitySnapshot
    test_faults: AutomatedTestFaults

    @property
    def uow_factory(self) -> UnitOfWorkFactory:
        return cast(UnitOfWorkFactory, self.store.uow_factory)

    def run_worker_until_idle(self) -> None:
        while self.planning_worker.process_next_outbox():
            pass

    def in_progress_playback_ids(self) -> tuple[str, ...]:
        with self.store.engine.connect() as connection:
            values = connection.execute(
                select(playbacks.c.playback_id)
                .where(playbacks.c.status == PlaybackStatus.IN_PROGRESS.value)
                .order_by(playbacks.c.started_at, playbacks.c.playback_id)
            ).scalars()
            return tuple(values)

    @staticmethod
    def _utc_timestamp(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    def projection_updated_at(self, case_id: str) -> datetime:
        with self.store.engine.connect() as connection:
            value = connection.scalar(
                select(case_projection.c.updated_at).where(
                    case_projection.c.case_id == case_id
                )
            )
        if value is None:
            raise LookupError(f"case projection does not exist: {case_id}")
        return self._utc_timestamp(value)

    def case_recorded_at(self, case_id: str) -> datetime:
        with self.store.engine.connect() as connection:
            value = connection.scalar(
                select(case_instances.c.recorded_at).where(
                    case_instances.c.case_id == case_id
                )
            )
        if value is None:
            raise LookupError(f"case does not exist: {case_id}")
        return self._utc_timestamp(value)

    def action_projection_updated_at(self, action_id: str) -> datetime:
        with self.store.engine.connect() as connection:
            value = connection.scalar(
                select(action_projection.c.updated_at).where(
                    action_projection.c.action_id == action_id
                )
            )
        if value is None:
            raise LookupError(f"action projection does not exist: {action_id}")
        return self._utc_timestamp(value)

    def planning_status(
        self,
        decision_id: str,
        kind: DecisionKind,
    ) -> Literal["not_applicable", "pending", "failed", "complete"]:
        if kind is DecisionKind.REJECTED:
            return "not_applicable"
        with self.uow_factory() as uow:
            event = uow.execution.list_outbox(decision_id=decision_id)[0]
            state = uow.execution.get_outbox_state(event.event_id)
        if state.processed_at is not None:
            return "complete"
        if state.last_error is not None:
            return "failed"
        return "pending"


def default_settings() -> Settings:
    configured_mode = os.getenv("SUPPLY_RESPONSE_RUNTIME_MODE")
    if configured_mode is not None:
        return Settings()  # pyright: ignore[reportCallIssue]
    database_path = Path("/tmp/supply-response-fallback.db")
    return Settings(
        runtime_mode=RuntimeMode.FALLBACK,
        database_url=os.getenv(
            "SUPPLY_RESPONSE_DATABASE_URL",
            f"sqlite:///{database_path}",
        ),
    )


def build_composition(
    settings: Settings,
    *,
    clock: Callable[[], datetime] | None = None,
    playback_clock: PlaybackClock | None = None,
    planner=plan_actions,
) -> ApplicationServices:
    if settings.runtime_mode is not RuntimeMode.FALLBACK:
        raise RuntimeError("live runtime composition is not available in this build")
    now = clock or (lambda: datetime.now(UTC))
    store = sqlite_store(
        settings.database_url,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    uow_factory = cast(UnitOfWorkFactory, store.uow_factory)
    active_playback_clock = playback_clock or RealClock()
    test_faults = AutomatedTestFaults(settings.automated_test_faults_enabled)
    execution_service = ExecutionService(uow_factory, clock=now)
    return ApplicationServices(
        settings=settings,
        store=store,
        analysis_service=FallbackAnalysisApplicationService(store, clock=now),
        decision_service=DecisionService(uow_factory, clock=now),
        planning_worker=ActionPlanningWorker(
            uow_factory,
            planner=test_faults.wrap(planner),
            after_plan=lambda decision, actions: test_faults.after_plan(
                decision,
                actions,
                execution_service,
            ),
        ),
        playback_service=PlaybackService(
            uow_factory,
            clock=active_playback_clock,
        ),
        playback_clock=active_playback_clock,
        clock=now,
        identity=fallback_identity(),
        test_faults=test_faults,
    )


def get_services(request: Request) -> ApplicationServices:
    return cast(ApplicationServices, request.app.state.services)


def get_server_identity(request: Request) -> IdentitySnapshot:
    return get_services(request).identity
