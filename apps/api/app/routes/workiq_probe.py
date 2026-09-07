from __future__ import annotations

# FastAPI dependency markers are intentionally declared in signature defaults.
# ruff: noqa: B008
from datetime import UTC
from threading import Lock

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from opentelemetry.context import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    attach,
    detach,
    set_value,
)

from apps.api.app.auth import AuthenticatedActor
from apps.api.app.dependencies import ApplicationServices, get_actor, get_services
from data.domain import RuntimeMode
from integrations.workiq.mcp_probe import ProbeUnavailable, WorkIQMcpProbe
from integrations.workiq.obo import build_obo_exchange
from integrations.workiq.probe_binding import PROBE_END_UTC, PROBE_START_UTC
from integrations.workiq.probe_http import DiagnosticMsalHttp

router = APIRouter(prefix="/api/diagnostics/workiq-fetch", tags=["diagnostics"])
_probe_creation_lock = Lock()


@router.post("")
async def run_probe(
    request: Request,
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(get_actor),
):
    if request.query_params or await request.body():
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_DIAGNOSTIC_REQUEST"}
        )
    now = services.clock().astimezone(UTC)
    if (
        services.settings.runtime_mode is not RuntimeMode.LIVE
        or actor is None
        or PROBE_START_UTC is None
        or PROBE_END_UTC is None
        or PROBE_START_UTC.tzinfo is None
        or PROBE_END_UTC.tzinfo is None
        or not (PROBE_START_UTC <= now < PROBE_END_UTC)
        or (PROBE_END_UTC - PROBE_START_UTC).total_seconds() > 1800
    ):
        raise HTTPException(status_code=404, detail={"code": "DIAGNOSTIC_UNAVAILABLE"})
    settings = services.settings
    client_id = settings.api_client_id
    client_secret = settings.entra_client_secret
    tenant_id = settings.allowed_tenant_id
    auth_service = services.auth_service
    if not client_id or not client_secret or not tenant_id or auth_service is None:
        raise HTTPException(status_code=404, detail={"code": "DIAGNOSTIC_UNAVAILABLE"})
    with _probe_creation_lock:
        probe = getattr(request.app.state, "workiq_mcp_probe", None)
        if probe is None:
            http = httpx.AsyncClient(
                follow_redirects=False,
                timeout=httpx.Timeout(12.0, connect=3.0, read=8.0, write=3.0, pool=3.0),
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            )
            obo_http = DiagnosticMsalHttp()
            probe = WorkIQMcpProbe(
                http=http,
                obo=build_obo_exchange(
                    client_id=client_id,
                    client_secret=client_secret,
                    tenant_id=tenant_id,
                    auth_service=auth_service,
                    http_client=obo_http,
                ),
            )
            request.app.state.workiq_mcp_probe = probe
    try:
        context_token = attach(set_value(_SUPPRESS_INSTRUMENTATION_KEY, True))
        try:
            result = await probe.run(actor, auth_service)
        finally:
            detach(context_token)
    except ProbeUnavailable:
        raise HTTPException(
            status_code=409, detail={"code": "DIAGNOSTIC_UNAVAILABLE"}
        ) from None
    return result.safe_dict()
