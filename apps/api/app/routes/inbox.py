# ruff: noqa: B008
"""Presenter-controlled, read-only supplier email check."""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict

from apps.api.app.auth import AuthenticatedActor
from apps.api.app.dependencies import ApplicationServices, get_services, require_planner
from data.domain import RuntimeMode
from integrations.workiq.inbox import InboxCheck

router = APIRouter(tags=["inbox"])


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/api/inbox/check", response_model=InboxCheck)
async def check_inbox(
    request: CheckRequest,
    response: Response,
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(require_planner),
) -> InboxCheck:
    headers = {"Cache-Control": "no-store"}
    if (
        services.settings.runtime_mode is not RuntimeMode.LIVE
        or services.inbox_service is None
    ):
        raise HTTPException(
            503, detail={"code": "INBOX_CHECK_UNAVAILABLE"}, headers=headers
        )
    if actor is None:
        raise HTTPException(
            401, detail={"code": "AUTHENTICATION_REQUIRED"}, headers=headers
        )
    try:
        result = InboxCheck.model_validate(
            await services.inbox_service.check_inbox(
                actor=actor,
                checked_at=services.clock(),
            )
        )
    except Exception:  # noqa: BLE001 - never expose provider payloads or tokens
        raise HTTPException(
            503, detail={"code": "INBOX_CHECK_FAILED"}, headers=headers
        ) from None
    response.headers.update(headers)
    return result
