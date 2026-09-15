# ruff: noqa: B008
"""Planner-controlled supplier email review and source-bound case creation."""

import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field

from apps.api.app.auth import AuthenticatedActor
from apps.api.app.contracts import CaseResponse, InboxCheckResponse
from apps.api.app.dependencies import ApplicationServices, get_services, require_planner
from apps.api.app.routes.cases import case_response
from data.domain import CaseInstance, CasePurpose, RuntimeMode
from data.domain.cases import PRESENTER_RUN_PATTERN, WorkflowVersion
from data.domain.inbound import (
    InboundEmailError,
    SupplierEmailSource,
    validate_supplier_facts,
)
from integrations.workiq.inbox import InboxCheck
from services.persistence.store import ImmutableRecordConflict, RecordNotFound


class _PrivateInboxRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private_handler(request: Request) -> Response:
            try:
                response = await handler(request)
            except HTTPException as error:
                error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
                raise
            except RequestValidationError:
                raise HTTPException(
                    422,
                    detail={"code": "INVALID_INBOUND_REQUEST"},
                    headers={"Cache-Control": "no-store"},
                ) from None
            response.headers["Cache-Control"] = "no-store"
            return response

        return private_handler


router = APIRouter(tags=["inbox"], route_class=_PrivateInboxRoute)


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateInboundCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presenter_run_id: str = Field(pattern=PRESENTER_RUN_PATTERN)
    internet_message_id: str = Field(min_length=3, max_length=998)
    review_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


def _matching_case(
    services: ApplicationServices,
    case_id: str,
    source: SupplierEmailSource,
    presenter_run_id: str,
) -> bool:
    try:
        case = services.store.get_case(case_id)
    except RecordNotFound:
        return False
    saved = case.supplier_email
    if (
        saved is None
        or case.runtime_mode is not RuntimeMode.LIVE
        or case.presenter_run_id != presenter_run_id
        or (saved.tenant_id, saved.mailbox_object_id, saved.internet_message_id)
        != (source.tenant_id, source.mailbox_object_id, source.internet_message_id)
    ):
        raise InboundEmailError("INBOUND_EMAIL_CONFLICT")
    if saved.review_fingerprint != source.review_fingerprint:
        raise InboundEmailError("INBOUND_EMAIL_CHANGED")
    if saved.facts != source.facts:
        raise InboundEmailError("INBOUND_EMAIL_CONFLICT")
    return True


@router.post("/api/inbox/cases", response_model=CaseResponse)
async def create_inbound_case(
    request: CreateInboundCaseRequest,
    response: Response,
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(require_planner),
) -> CaseResponse:
    headers = {"Cache-Control": "no-store"}
    if (
        services.settings.runtime_mode is not RuntimeMode.LIVE
        or services.inbox_service is None
        or services.live_operational_data is None
    ):
        raise HTTPException(
            503, detail={"code": "INBOUND_EMAIL_UNAVAILABLE"}, headers=headers
        )
    if actor is None:
        raise HTTPException(
            401, detail={"code": "AUTHENTICATION_REQUIRED"}, headers=headers
        )
    try:
        source = SupplierEmailSource.model_validate(
            await services.inbox_service.review_inbound_email(
                actor=actor,
                internet_message_id=request.internet_message_id,
                review_fingerprint=request.review_fingerprint,
                checked_at=services.clock(),
            )
        )
        if (
            source.tenant_id != actor.tenant_id
            or source.mailbox_object_id != actor.object_id
            or source.internet_message_id != request.internet_message_id
        ):
            raise InboundEmailError("INBOUND_EMAIL_CONFLICT")
        if source.review_fingerprint != request.review_fingerprint:
            raise InboundEmailError("INBOUND_EMAIL_CHANGED")
        key = json.dumps(
            [
                actor.tenant_id,
                actor.object_id,
                source.internet_message_id,
                request.presenter_run_id,
            ],
            separators=(",", ":"),
        )
        case_id = "RL-INBOUND-" + hashlib.sha256(key.encode()).hexdigest()
        if not _matching_case(services, case_id, source, request.presenter_run_id):
            live = await services.live_operational_data.retrieve(
                case_id=case_id,
                purpose=CasePurpose.SHOWCASE,
                analysis_id=f"case-bootstrap-{case_id}",
                retrieved_at=services.clock(),
            )
            if (
                live.case.case_id != case_id
                or live.case.runtime_mode is not RuntimeMode.LIVE
                or live.case.purpose is not CasePurpose.SHOWCASE
            ):
                raise InboundEmailError("INBOUND_EMAIL_CONFLICT")
            validate_supplier_facts(source.facts, live.snapshot)
            values = {
                **live.case.model_dump(),
                "supplier_email": source,
                "presenter_run_id": request.presenter_run_id,
            }
            if services.settings.independent_finance_enabled:
                values["workflow_version"] = WorkflowVersion.INDEPENDENT_FINANCE
            case = CaseInstance.model_validate(values)
            try:
                services.store.create_presenter_case(case, live.snapshot)
            except ImmutableRecordConflict:
                if not _matching_case(
                    services, case_id, source, request.presenter_run_id
                ):
                    raise InboundEmailError("INBOUND_EMAIL_CONFLICT") from None
        result = case_response(services, case_id)
    except InboundEmailError as error:
        statuses = {
            "INBOUND_EMAIL_CHANGED": 409,
            "INBOUND_EMAIL_CONFLICT": 409,
            "INBOUND_EMAIL_UNSUPPORTED": 422,
        }
        code = error.code if error.code in statuses else "INBOUND_EMAIL_UNAVAILABLE"
        raise HTTPException(
            statuses.get(code, 503), detail={"code": code}, headers=headers
        ) from None
    except Exception:  # noqa: BLE001 - do not return provider or persistence payloads
        raise HTTPException(
            503, detail={"code": "INBOUND_EMAIL_UNAVAILABLE"}, headers=headers
        ) from None
    response.headers.update(headers)
    return result


@router.post("/api/inbox/check", response_model=InboxCheckResponse)
async def check_inbox(
    request: CheckRequest,
    response: Response,
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(require_planner),
) -> InboxCheckResponse:
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
        provider_result = InboxCheck.model_validate(
            await services.inbox_service.check_inbox(
                actor=actor,
                checked_at=services.clock(),
            )
        )
        result = InboxCheckResponse(
            **provider_result.model_dump(),
            presenter_run_id=f"RL-RUN-{uuid4().hex}",
        )
    except Exception:  # noqa: BLE001 - never expose provider payloads or tokens
        raise HTTPException(
            503, detail={"code": "INBOX_CHECK_FAILED"}, headers=headers
        ) from None
    response.headers.update(headers)
    return result
