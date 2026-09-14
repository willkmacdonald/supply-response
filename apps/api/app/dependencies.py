# FastAPI dependency markers are intentionally declared in signature defaults.
# ruff: noqa: B008

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select

from apps.api.app.auth import (
    AuthenticatedActor,
    AuthenticationError,
    AuthorizationError,
    AuthService,
)
from apps.api.app.readiness import (
    FallbackReadiness,
    ReadinessPort,
    UnverifiedLiveReadiness,
)
from apps.api.app.settings import Settings
from apps.api.app.test_support import AutomatedTestFaults
from data.domain import RuntimeMode
from data.domain.analysis import AnalysisVersion
from data.domain.cases import WorkflowVersion
from data.domain.decisions import DecisionKind, IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.execution import PlaybackStatus
from services.analysis.application import FallbackAnalysisApplicationService
from services.decisions.service import DecisionService, UnitOfWorkFactory
from services.execution.planner import plan_actions
from services.execution.playback import PlaybackClock, PlaybackService, RealClock
from services.execution.worker import ActionPlanningWorker, ExecutionService
from services.finance.decisions import FinanceDecisionService
from services.finance.identity import BoundFinanceActors
from services.finance.service import FinanceService
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
    live_operational_data: Any | None = None
    readiness: ReadinessPort = field(default_factory=FallbackReadiness)
    finance_actors: BoundFinanceActors | None = None
    finance_service: FinanceService | None = None
    finance_decision_service: FinanceDecisionService | None = None

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
        readiness: ReadinessPort = FallbackReadiness()
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
        readiness = live_components.get("readiness", UnverifiedLiveReadiness())
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
            processable_workflow_versions=(WorkflowVersion.LEGACY,),
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
        live_operational_data=(
            None if live_components is None else live_components.get("operational_data")
        ),
        readiness=readiness,
    )
    if settings.runtime_mode is RuntimeMode.LIVE and all(
        (settings.allowed_tenant_id, settings.alex_object_id, settings.taylor_object_id)
    ):
        actors = BoundFinanceActors(
            tenant_id=UUID(cast(str, settings.allowed_tenant_id)),
            alex_object_id=UUID(cast(str, settings.alex_object_id)),
            taylor_object_id=UUID(cast(str, settings.taylor_object_id)),
        )
        services.finance_actors = actors
        services.finance_service = FinanceService(
            services.uow_factory, actors=actors, clock=now
        )
        services.finance_decision_service = FinanceDecisionService(
            services.uow_factory, actors=actors, clock=now
        )
    return services


def _required_live_setting(settings: Settings, name: str) -> str:
    value = getattr(settings, name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"live dependency setting is missing: {name}")
    return value


def _validate_workiq_binding_values(values: dict[str, str]) -> None:
    sender = values["workiq_supplier_sender"]
    if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,255}", sender):
        raise RuntimeError("live dependency setting is invalid: workiq_supplier_sender")
    for name in ("workiq_quality_author_object_id", "workiq_team_id"):
        try:
            UUID(values[name])
        except ValueError:
            raise RuntimeError(f"live dependency setting is invalid: {name}") from None
    if not re.fullmatch(
        r"19:[^\s/?#]{1,2048}@thread\.tacv2", values["workiq_channel_id"]
    ):
        raise RuntimeError("live dependency setting is invalid: workiq_channel_id")


def _workiq_binding_receipt_parts(values: dict[str, str]) -> tuple[str, ...]:
    return (
        "workiq-binding-v2",
        values["workiq_corpus_version"],
        values["workiq_supplier_source_id"],
        values["workiq_quality_source_id"],
        values["workiq_supplier_sender"],
        values["workiq_quality_author_object_id"],
        values["workiq_team_id"],
        values["workiq_channel_id"],
    )


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
    from apps.api.app.readiness import (
        FabricBoundReadiness,
        verify_binding_receipt,
        verify_power_bi_deployment_receipt,
    )
    from integrations.fabric.operational import FabricLiveOperationalDataPort
    from integrations.workiq.async_obo import AsyncWorkIQOboExchange
    from integrations.workiq.mcp import WorkIQMcpClient
    from integrations.workiq.mcp_evidence import WorkIQMcpEvidencePort
    from integrations.workiq.models import SourceBinding
    from services.analysis.service import analyze_case
    from services.persistence.fabric_sql import build_credential

    required_names = (
        "allowed_tenant_id",
        "api_client_id",
        "alex_object_id",
        "entra_client_secret",
        "tenant_sharepoint_host",
        "workiq_supplier_source_id",
        "workiq_quality_source_id",
        "workiq_supplier_sender",
        "workiq_quality_author_object_id",
        "workiq_team_id",
        "workiq_channel_id",
        "workiq_corpus_version",
        "foundry_project_endpoint",
        "foundry_signal_agent_name",
        "foundry_signal_agent_version",
        "foundry_context_agent_name",
        "foundry_context_agent_version",
        "foundry_decision_agent_name",
        "foundry_decision_agent_version",
        "power_bi_report_url",
        "fabric_citation_base_url",
    )
    values = {name: _required_live_setting(settings, name) for name in required_names}
    _validate_workiq_binding_values(values)
    work_iq_receipt_verified = verify_binding_receipt(
        _workiq_binding_receipt_parts(values), settings.workiq_deployment_receipt
    )
    if not work_iq_receipt_verified:
        raise RuntimeError("live dependency binding receipt is invalid: workiq")
    tenant_id = values["allowed_tenant_id"]
    client_id = values["api_client_id"]
    power_bi_url = validate_live_https_url(
        values["power_bi_report_url"], allowed_hosts={"app.powerbi.com"}
    )
    validate_live_https_url(
        values["fabric_citation_base_url"], allowed_hosts={"app.powerbi.com"}
    )
    sharepoint_host = values["tenant_sharepoint_host"].lower()
    if (
        ":" in sharepoint_host
        or "/" in sharepoint_host
        or not sharepoint_host.endswith(".sharepoint.com")
    ):
        raise RuntimeError("live dependency setting is invalid: tenant_sharepoint_host")
    auth_service = AuthService(
        tenant_id=tenant_id,
        audience=client_id,
        bindings=tuple(
            binding
            for binding in (
                PersonaBinding.alex(tenant_id, values["alex_object_id"]),
                (
                    PersonaBinding.taylor(tenant_id, settings.taylor_object_id)
                    if settings.taylor_object_id
                    else None
                ),
            )
            if binding is not None
        ),
    )
    credential = build_credential(settings)
    store = fabric_store(settings, credential)
    operational_data = FabricLiveOperationalDataPort(store.engine)
    http = httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(retries=0),
        trust_env=False,
        follow_redirects=False,
    )
    work_iq = WorkIQMcpEvidencePort(
        client=WorkIQMcpClient(http=http),
        obo=AsyncWorkIQOboExchange(
            client_id=client_id,
            client_secret=values["entra_client_secret"],
            tenant_id=tenant_id,
            auth_service=auth_service,
        ),
        binding=SourceBinding(
            tenant_id=tenant_id,
            alex_object_id=values["alex_object_id"],
            supplier_sender=values["workiq_supplier_sender"],
            quality_author_object_id=values["workiq_quality_author_object_id"],
            team_id=values["workiq_team_id"],
            channel_id=values["workiq_channel_id"],
            supplier_source_id=values["workiq_supplier_source_id"],
            quality_source_id=values["workiq_quality_source_id"],
        ),
    )
    endpoint = values["foundry_project_endpoint"]
    bindings = {
        role: FoundryAgentBinding(
            project_endpoint=endpoint,
            agent_name=values[f"foundry_{role}_agent_name"],
            agent_version=values[f"foundry_{role}_agent_version"],
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
    analysis = LiveAnalysisApplicationService(
        store=store,
        operational_data=operational_data,
        work_iq=work_iq,
        orchestrator=orchestrator,
        supplier_source_id=values["workiq_supplier_source_id"],
        quality_source_id=values["workiq_quality_source_id"],
        fabric_citation_base_url=values["fabric_citation_base_url"],
        tenant_sharepoint_host=sharepoint_host,
        clock=clock,
    )
    return {
        "store": store,
        "analysis_service": analysis,
        "auth_service": auth_service,
        "power_bi_url": power_bi_url,
        "async_resources": (http,),
        "operational_data": operational_data,
        "readiness": FabricBoundReadiness(
            engine=store.engine,
            power_bi_receipt_verified=verify_power_bi_deployment_receipt(
                power_bi_url, settings.power_bi_deployment_receipt
            ),
            work_iq_receipt_verified=work_iq_receipt_verified,
            foundry_receipt_verified=verify_binding_receipt(
                (
                    endpoint,
                    values["foundry_signal_agent_name"],
                    values["foundry_signal_agent_version"],
                    values["foundry_context_agent_name"],
                    values["foundry_context_agent_version"],
                    values["foundry_decision_agent_name"],
                    values["foundry_decision_agent_version"],
                ),
                settings.foundry_deployment_receipt,
            ),
        ),
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


def require_planner(
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(get_actor),
) -> AuthenticatedActor | None:
    if actor is None:
        return None
    try:
        configured_tenant = str(UUID(services.settings.allowed_tenant_id or ""))
        configured_alex = str(UUID(services.settings.alex_object_id or ""))
    except ValueError:
        raise HTTPException(
            status_code=403, detail={"code": "PLANNER_ACCESS_REQUIRED"}
        ) from None
    expected = (
        configured_tenant,
        configured_alex,
        "RL-PERSONA-ALEX",
        "RL-ENTRA-ALEX",
        ("material_planner", "response_approver"),
    )
    actual = (
        actor.tenant_id,
        actor.object_id,
        actor.persona_id,
        actor.source_id,
        actor.effective_roles,
    )
    if actual != expected:
        raise HTTPException(status_code=403, detail={"code": "PLANNER_ACCESS_REQUIRED"})
    return actor


def require_finance_actor(
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(get_actor),
) -> IdentitySnapshot:
    if actor is None or services.finance_actors is None:
        raise HTTPException(status_code=403, detail={"code": "FINANCE_ACCESS_REQUIRED"})
    identity = actor.to_identity_snapshot()
    try:
        services.finance_actors.require_taylor(identity)
    except PermissionError:
        raise HTTPException(
            status_code=403, detail={"code": "FINANCE_ACCESS_REQUIRED"}
        ) from None
    return identity


def require_alex_identity(
    planner: AuthenticatedActor | None = Depends(require_planner),
    services: ApplicationServices = Depends(get_services),
) -> IdentitySnapshot:
    return services.identity if planner is None else planner.to_identity_snapshot()
