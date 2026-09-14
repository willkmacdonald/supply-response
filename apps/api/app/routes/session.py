# FastAPI dependency markers are intentionally declared in signature defaults.
# ruff: noqa: B008

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.app.auth import AuthenticatedActor
from apps.api.app.dependencies import ApplicationServices, get_actor, get_services

router = APIRouter(tags=["session"])


class SessionResponse(BaseModel):
    mode: Literal["entra", "fallback"]
    persona_id: str | None
    display_name: str | None
    independent_finance_enabled: bool


@router.get("/api/me", response_model=SessionResponse)
def current_session(
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(get_actor),
) -> SessionResponse:
    return SessionResponse(
        mode="fallback" if actor is None else "entra",
        persona_id=None if actor is None else actor.persona_id,
        display_name=None if actor is None else actor.display_name,
        independent_finance_enabled=services.settings.independent_finance_enabled,
    )
