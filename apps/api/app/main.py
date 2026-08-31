from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI

from apps.api.app.dependencies import (
    ApplicationServices,
    build_composition,
    default_settings,
)
from apps.api.app.routes.cases import router as cases_router
from apps.api.app.routes.decisions import router as decisions_router
from apps.api.app.routes.dashboard import router as dashboard_router
from apps.api.app.routes.execution import router as execution_router
from apps.api.app.routes.health import router as health_router
from apps.api.app.settings import Settings
from services.execution.planner import plan_actions
from services.execution.playback import PlaybackClock


def create_app(
    settings: Settings | None = None,
    *,
    services: ApplicationServices | None = None,
    clock: Callable[[], datetime] | None = None,
    playback_clock: PlaybackClock | None = None,
    planner=plan_actions,
) -> FastAPI:
    api = FastAPI(title="Supply Response API", version="0.3.0")
    api.state.services = services or build_composition(
        settings or default_settings(),
        clock=clock,
        playback_clock=playback_clock,
        planner=planner,
    )
    api.include_router(health_router)
    api.include_router(cases_router)
    api.include_router(decisions_router)
    api.include_router(execution_router)
    api.include_router(dashboard_router)
    return api


app = create_app()
