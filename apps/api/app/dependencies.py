# FastAPI dependency markers are intentionally declared in signature defaults.
# ruff: noqa: B008

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select

from apps.api.app.auth import (
    AuthenticatedActor,
    AuthenticationError,
    AuthorizationError,
    AuthService,
)
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
from services.persistence.fabric_sql import fabric_store
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
    async def create(
        self, case_id: str, *, actor: AuthenticatedActor | None = None
    ) -> AnalysisVersion: ...


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
    operational_store: Literal["sqlite", "fabric_sql"]
    power_bi_available: bool
    fabric_schema_version: int | None = None
    auth_service: AuthService | None = None
    power_bi_url: str | None = None
    async_resources: tuple[Any, ...] = ()

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

    async def close(self) -> None:
        for resource in self.async_resources:
            closer = getattr(resource, "aclose", None)
            if closer is not None:
                await closer()
        self.store.engine.dispose()


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
    live_components: dict[str, Any] | None = None,
) -> ApplicationServices:
    now = clock or (lambda: datetime.now(UTC))
    owned_resources: tuple[Any, ...] = ()
    if settings.runtime_mode is RuntimeMode.FALLBACK:
        if settings.database_url is None:
            raise RuntimeError("fallback database URL is not configured")
        store = sqlite_store(
            settings.database_url,
            runtime_mode=RuntimeMode.FALLBACK,
        )
        operational_store: Literal["sqlite", "fabric_sql"] = "sqlite"
        power_bi_available = False
        fabric_schema_version = None
        analysis_service: AnalysisApplicationService = (
            FallbackAnalysisApplicationService(store, clock=now)
        )
    else:
        if live_components is None:
            live_components = build_live_components(settings, clock=now)
        assert live_components is not None
        owned_resources = tuple(live_components.get("async_resources", ()))
        store = live_components["store"]
        if store.runtime_mode is not RuntimeMode.LIVE:
            raise RuntimeError("live dependency graph requires a live store")
        operational_store = "fabric_sql"
        power_bi_available = True
        fabric_schema_version = live_components.get("fabric_schema_version")
        analysis_service = live_components["analysis_service"]
    uow_factory = cast(UnitOfWorkFactory, store.uow_factory)
    active_playback_clock = playback_clock or RealClock()
    test_faults = AutomatedTestFaults(settings.automated_test_faults_enabled)
    execution_service = ExecutionService(uow_factory, clock=now)
    services = ApplicationServices(
        settings=settings,
        store=store,
        analysis_service=analysis_service,
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
        operational_store=operational_store,
        power_bi_available=power_bi_available,
        fabric_schema_version=fabric_schema_version,
        auth_service=(
            None if live_components is None else live_components["auth_service"]
        ),
        power_bi_url=(
            None if live_components is None else live_components["power_bi_url"]
        ),
        async_resources=owned_resources,
    )
    return services


def _required_live_setting(settings: Settings, name: str) -> str:
    value = getattr(settings, name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"live dependency setting is missing: {name}")
    return value


def build_live_components(
    settings: Settings,
    *,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Construct the live graph without opening a source/user-context connection."""
    import httpx

    from agents.foundry import FoundryAgentBinding, build_foundry_agent_set
    from agents.orchestrator.workflow import Orchestrator
    from apps.api.app.auth import PersonaBinding
    from apps.api.app.live import (
        LiveAnalysisApplicationService,
        validate_live_https_url,
    )
    from integrations.workiq.client import WorkIQClient, WorkIQEvidencePort
    from integrations.workiq.obo import build_obo_exchange
    from services.analysis.service import analyze_case
    from services.persistence.fabric_sql import build_credential

    tenant_id = _required_live_setting(settings, "allowed_tenant_id")
    client_id = _required_live_setting(settings, "api_client_id")
    auth_service = AuthService(
        tenant_id=tenant_id,
        audience=client_id,
        bindings=(
            PersonaBinding.alex(
                tenant_id, _required_live_setting(settings, "alex_object_id")
            ),
        ),
    )
    credential = build_credential(settings)
    store = fabric_store(settings, credential)
    http = httpx.AsyncClient()
    work_iq = WorkIQEvidencePort(
        client=WorkIQClient(http=http),
        obo=build_obo_exchange(
            client_id=client_id,
            client_secret=_required_live_setting(settings, "entra_client_secret"),
            tenant_id=tenant_id,
            auth_service=auth_service,
        ),
        tenant_sharepoint_host=_required_live_setting(
            settings, "tenant_sharepoint_host"
        ),
    )
    endpoint = _required_live_setting(settings, "foundry_project_endpoint")
    bindings = {
        role: FoundryAgentBinding(
            project_endpoint=endpoint,
            agent_name=_required_live_setting(settings, f"foundry_{role}_agent_name"),
            agent_version=_required_live_setting(
                settings, f"foundry_{role}_agent_version"
            ),
        )
        for role in ("signal", "context", "decision")
    }
    orchestrator = Orchestrator(
        lambda: build_foundry_agent_set(
            bindings=bindings,
            credential=credential,
        ),
        analyze_case,
    )
    power_bi_url = validate_live_https_url(
        _required_live_setting(settings, "power_bi_report_url"),
        allowed_hosts={"app.powerbi.com"},
    )
    analysis = LiveAnalysisApplicationService(
        store=store,
        work_iq=work_iq,
        orchestrator=orchestrator,
        supplier_source_id=_required_live_setting(
            settings, "workiq_supplier_source_id"
        ),
        quality_source_id=_required_live_setting(settings, "workiq_quality_source_id"),
        fabric_citation_base_url=_required_live_setting(
            settings, "fabric_citation_base_url"
        ),
        tenant_sharepoint_host=_required_live_setting(
            settings, "tenant_sharepoint_host"
        ),
        clock=clock,
    )
    return {
        "store": store,
        "analysis_service": analysis,
        "auth_service": auth_service,
        "power_bi_url": power_bi_url,
        "async_resources": (http,),
    }


def get_services(request: Request) -> ApplicationServices:
    return cast(ApplicationServices, request.app.state.services)


def get_server_identity(request: Request) -> IdentitySnapshot:
    return get_services(request).identity


def get_actor(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedActor | None:
    services = get_services(request)
    if services.settings.runtime_mode is RuntimeMode.FALLBACK:
        return None
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTHENTICATION_REQUIRED"},
        )
    token = authorization.removeprefix("Bearer ")
    try:
        if services.auth_service is None:
            raise AuthenticationError("authentication is unavailable")
        return services.auth_service.authenticate(token)
    except AuthenticationError:
        raise HTTPException(
            status_code=401, detail={"code": "INVALID_ACCESS_TOKEN"}
        ) from None
    except AuthorizationError:
        raise HTTPException(
            status_code=403, detail={"code": "PERSONA_NOT_AUTHORIZED"}
        ) from None


def get_decision_identity(
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(get_actor),
) -> IdentitySnapshot:
    if actor is None:
        return services.identity
    return actor.to_identity_snapshot()
