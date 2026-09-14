from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from apps.api.app.dependencies import (
    ApplicationServices,
    build_composition,
    default_settings,
    require_planner,
)
from apps.api.app.routes.cases import router as cases_router
from apps.api.app.routes.dashboard import router as dashboard_router
from apps.api.app.routes.decisions import router as decisions_router
from apps.api.app.routes.execution import router as execution_router
from apps.api.app.routes.finance import router as finance_router
from apps.api.app.routes.health import router as health_router
from apps.api.app.routes.session import router as session_router
from apps.api.app.routes.test_support import router as test_support_router
from apps.api.app.runtime import RuntimeProgression
from apps.api.app.settings import Settings
from apps.api.app.telemetry import configure_azure_monitor_from_environment
from services.execution.planner import plan_actions
from services.execution.playback import PlaybackClock


def create_app(
    settings: Settings | None = None,
    *,
    services: ApplicationServices | None = None,
    clock: Callable[[], datetime] | None = None,
    playback_clock: PlaybackClock | None = None,
    planner=plan_actions,
    static_directory: Path | None = None,
) -> FastAPI:
    active_services = services or build_composition(
        settings or default_settings(),
        clock=clock,
        playback_clock=playback_clock,
        planner=planner,
    )

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        progression = RuntimeProgression(active_services)
        api.state.runtime_progression = progression
        await progression.start()
        try:
            yield
        finally:
            await progression.stop()
            await active_services.close()

    api = FastAPI(
        title="Supply Response API",
        version="0.3.0",
        lifespan=lifespan,
    )
    api.state.services = active_services
    api.include_router(health_router)
    api.include_router(session_router)
    planner_dependencies = [Depends(require_planner)]
    api.include_router(cases_router, dependencies=planner_dependencies)
    api.include_router(decisions_router, dependencies=planner_dependencies)
    api.include_router(execution_router, dependencies=planner_dependencies)
    api.include_router(dashboard_router, dependencies=planner_dependencies)
    api.include_router(finance_router)
    if active_services.settings.automated_test_faults_enabled:
        api.include_router(test_support_router, dependencies=planner_dependencies)

    distribution = static_directory or Path(__file__).resolve().parents[1] / "static"
    index = distribution / "index.html"
    if index.is_file():
        assets = distribution / "assets"
        if assets.is_dir():
            api.mount("/assets", StaticFiles(directory=assets), name="spa-assets")

        @api.get("/{spa_path:path}", include_in_schema=False)
        async def spa_fallback(spa_path: str):
            if spa_path in {"api", "health"} or spa_path.startswith(
                ("api/", "health/")
            ):
                raise HTTPException(status_code=404)
            return FileResponse(index)

    return api


configure_azure_monitor_from_environment()
app = create_app()
