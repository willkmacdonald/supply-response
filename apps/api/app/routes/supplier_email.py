# FastAPI dependency markers are intentionally declared in signature defaults.
# ruff: noqa: B008

from fastapi import APIRouter, Depends, HTTPException

from apps.api.app.auth import AuthenticatedActor
from apps.api.app.contracts import SupplierEmailCapabilityResponse
from apps.api.app.dependencies import ApplicationServices, get_services, require_planner
from integrations.graph_mail.client import GraphMailError

router = APIRouter(tags=["supplier-email"])


@router.get(
    "/api/supplier-email/capability",
    response_model=SupplierEmailCapabilityResponse,
)
async def get_supplier_email_capability(
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(require_planner),
) -> SupplierEmailCapabilityResponse:
    if actor is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTHENTICATION_REQUIRED"},
        )
    if services.graph_mail is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SUPPLIER_EMAIL_CAPABILITY_UNAVAILABLE",
                "message": "Mailbox verification is not available.",
            },
        )
    try:
        capability = await services.graph_mail.capability(actor)
    except GraphMailError:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SUPPLIER_EMAIL_CAPABILITY_FAILED",
                "message": "Mailbox verification could not be completed.",
            },
        ) from None
    return SupplierEmailCapabilityResponse(
        mailbox_address=capability.mailbox_address,
        sample_sent_message_verified=True,
    )
