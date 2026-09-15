# FastAPI dependency markers are intentionally declared in signature defaults.
# ruff: noqa: B008

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from apps.api.app.auth import AuthenticatedActor
from apps.api.app.contracts import (
    ActionResponse,
    DraftResponse,
    ObservationResponse,
    PlaybackResponse,
    SupplierEmailResponse,
    SupplierEmailReviewRequest,
    SupplierEmailSaveRequest,
    SupplierEmailSendRequest,
)
from apps.api.app.dependencies import (
    ApplicationServices,
    get_decision_identity,
    get_services,
    require_alex_identity,
    require_planner,
)
from apps.api.app.routes.decisions import _decision, _require_role
from data.domain.decisions import IdentitySnapshot
from services.execution.currentness import ExecutionProposalStale
from services.execution.mail_service import (
    EmailAuthorizationError,
    EmailRevisionConflict,
    EmailSendDisabled,
    EmailStateError,
)
from services.execution.playback import (
    PlaybackAuthorizationError,
    PlaybackStateError,
)
from services.execution.worker import ExecutionService, IllegalExecutionTransition
from services.persistence.store import RecordNotFound

router = APIRouter(prefix="/api/decisions", tags=["execution"])


def _supplier_email_error(error: Exception) -> HTTPException:
    if isinstance(error, EmailSendDisabled):
        return HTTPException(
            status_code=409,
            detail={"code": "SUPPLIER_EMAIL_SEND_DISABLED"},
        )
    if isinstance(error, EmailAuthorizationError):
        return HTTPException(
            status_code=403,
            detail={"code": "SUPPLIER_EMAIL_ACCESS_REQUIRED"},
        )
    if isinstance(error, EmailRevisionConflict):
        return HTTPException(
            status_code=409,
            detail={
                "code": "SUPPLIER_EMAIL_CHANGED",
                "message": "The supplier email changed. Refresh it and try again.",
            },
        )
    if isinstance(error, ExecutionProposalStale):
        return HTTPException(
            status_code=409,
            detail={
                "code": "EXECUTION_PROPOSAL_STALE",
                "message": "The approved response changed. Refresh before continuing.",
            },
        )
    return HTTPException(
        status_code=409,
        detail={
            "code": "SUPPLIER_EMAIL_NOT_AVAILABLE",
            "message": str(error),
        },
    )


@router.get(
    "/{decision_id}/supplier-email",
    response_model=SupplierEmailResponse,
)
def get_supplier_email(
    decision_id: str,
    services: ApplicationServices = Depends(get_services),
) -> SupplierEmailResponse:
    _decision(services, decision_id)
    try:
        return SupplierEmailResponse.model_validate(
            services.mail_service.get(decision_id).model_dump()
        )
    except (EmailStateError, ExecutionProposalStale) as error:
        raise _supplier_email_error(error) from None


@router.put(
    "/{decision_id}/supplier-email",
    response_model=SupplierEmailResponse,
)
def save_supplier_email(
    decision_id: str,
    request: SupplierEmailSaveRequest,
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(require_alex_identity),
) -> SupplierEmailResponse:
    _decision(services, decision_id)
    try:
        return SupplierEmailResponse.model_validate(
            services.mail_service.save(
                decision_id,
                request.revision,
                request.subject,
                request.body,
                actor,
            ).model_dump()
        )
    except (
        EmailAuthorizationError,
        EmailRevisionConflict,
        EmailStateError,
        ExecutionProposalStale,
    ) as error:
        raise _supplier_email_error(error) from None


@router.post(
    "/{decision_id}/supplier-email/review",
    response_model=SupplierEmailResponse,
)
def review_supplier_email(
    decision_id: str,
    request: SupplierEmailReviewRequest,
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(require_alex_identity),
) -> SupplierEmailResponse:
    _decision(services, decision_id)
    try:
        return SupplierEmailResponse.model_validate(
            services.mail_service.review(
                decision_id, request.revision, actor
            ).model_dump()
        )
    except (
        EmailAuthorizationError,
        EmailRevisionConflict,
        EmailStateError,
        ExecutionProposalStale,
    ) as error:
        raise _supplier_email_error(error) from None


def _mail_actor(
    planner: AuthenticatedActor | None,
    services: ApplicationServices,
) -> object:
    return services.identity if planner is None else planner


@router.post(
    "/{decision_id}/supplier-email/send",
    response_model=SupplierEmailResponse,
)
async def send_supplier_email(
    decision_id: str,
    request: SupplierEmailSendRequest,
    services: ApplicationServices = Depends(get_services),
    planner: AuthenticatedActor | None = Depends(require_planner),
) -> SupplierEmailResponse:
    _decision(services, decision_id)
    try:
        state = await services.mail_service.send(
            decision_id,
            request.revision,
            _mail_actor(planner, services),
        )
        return SupplierEmailResponse.model_validate(state.model_dump())
    except (
        EmailAuthorizationError,
        EmailRevisionConflict,
        EmailSendDisabled,
        EmailStateError,
        ExecutionProposalStale,
    ) as error:
        raise _supplier_email_error(error) from None


@router.post(
    "/{decision_id}/supplier-email/check-send-status",
    response_model=SupplierEmailResponse,
)
async def check_supplier_email_send_status(
    decision_id: str,
    services: ApplicationServices = Depends(get_services),
    planner: AuthenticatedActor | None = Depends(require_planner),
) -> SupplierEmailResponse:
    _decision(services, decision_id)
    try:
        state = await services.mail_service.check_send_status(
            decision_id,
            _mail_actor(planner, services),
        )
        return SupplierEmailResponse.model_validate(state.model_dump())
    except (
        EmailAuthorizationError,
        EmailRevisionConflict,
        EmailSendDisabled,
        EmailStateError,
        ExecutionProposalStale,
    ) as error:
        raise _supplier_email_error(error) from None


def _action_response(services, decision, action) -> ActionResponse:
    return ActionResponse(
        **action.model_dump(),
        runtime_mode=decision.runtime_mode,
        scenario_effective_time=decision.scenario_effective_time,
        projection_updated_at=services.action_projection_updated_at(action.action_id),
    )


@router.get("/{decision_id}/actions", response_model=list[ActionResponse])
def list_actions(
    decision_id: str,
    services: ApplicationServices = Depends(get_services),
) -> list[ActionResponse]:
    decision = _decision(services, decision_id)
    with services.uow_factory() as uow:
        actions = uow.execution.list_actions(decision_id=decision_id)
    return [_action_response(services, decision, action) for action in actions]


@router.post(
    "/{decision_id}/actions/{action_id}/retry",
    response_model=ActionResponse,
)
def retry_failed_action(
    decision_id: str,
    action_id: str,
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(get_decision_identity),
) -> ActionResponse:
    _require_role(actor, "response_approver")
    decision = _decision(services, decision_id)
    execution = ExecutionService(services.uow_factory, clock=services.clock)
    try:
        with services.uow_factory() as uow:
            existing = uow.execution.get_action(action_id)
        if existing.decision_id != decision_id:
            raise RecordNotFound(action_id)
        execution.retry(action_id)
        with services.uow_factory() as uow:
            retried = uow.execution.get_action(action_id)
    except RecordNotFound:
        raise HTTPException(
            status_code=404,
            detail={"code": "ACTION_NOT_FOUND", "action_id": action_id},
        ) from None
    except IllegalExecutionTransition as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "ACTION_RETRY_NOT_AVAILABLE", "message": str(error)},
        ) from None
    except ExecutionProposalStale:
        raise HTTPException(
            status_code=409,
            detail={"code": "EXECUTION_PROPOSAL_STALE"},
        ) from None
    return _action_response(services, decision, retried)


@router.get("/{decision_id}/drafts", response_model=list[DraftResponse])
def list_drafts(
    decision_id: str,
    services: ApplicationServices = Depends(get_services),
) -> list[DraftResponse]:
    decision = _decision(services, decision_id)
    drafts = []
    with services.uow_factory() as uow:
        actions = uow.execution.list_actions(decision_id=decision_id)
        for action in actions:
            if action.draft_artifact_id is not None:
                drafts.append(uow.execution.get_draft_artifact(action.action_id))
    return [
        DraftResponse(
            **draft.model_dump(),
            runtime_mode=decision.runtime_mode,
            scenario_effective_time=decision.scenario_effective_time,
        )
        for draft in drafts
    ]


@router.post(
    "/{decision_id}/playback",
    response_model=PlaybackResponse,
    status_code=201,
)
def start_playback(
    decision_id: str,
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(get_decision_identity),
) -> PlaybackResponse:
    decision = _decision(services, decision_id)
    try:
        playback = services.playback_service.start(decision_id, actor)
    except PlaybackAuthorizationError:
        raise HTTPException(
            status_code=403,
            detail={"code": "ROLE_REQUIRED", "role": "response_approver"},
        ) from None
    except PlaybackStateError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "PLAYBACK_NOT_AVAILABLE", "message": str(error)},
        ) from None
    return PlaybackResponse(
        **playback.model_dump(exclude={"actor"}),
        runtime_mode=decision.runtime_mode,
        scenario_effective_time=decision.scenario_effective_time,
    )


@router.get(
    "/{decision_id}/playback",
    response_model=PlaybackResponse,
)
def get_playback(
    decision_id: str,
    services: ApplicationServices = Depends(get_services),
) -> PlaybackResponse:
    decision = _decision(services, decision_id)
    with services.uow_factory() as uow:
        playback = uow.execution.get_playback_for_decision(decision_id)
    if playback is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PLAYBACK_NOT_FOUND"},
        )
    return PlaybackResponse(
        **playback.model_dump(exclude={"actor"}),
        runtime_mode=decision.runtime_mode,
        scenario_effective_time=decision.scenario_effective_time,
    )


@router.get("/{decision_id}/observations", response_model=list[ObservationResponse])
def list_observations(
    decision_id: str,
    services: ApplicationServices = Depends(get_services),
) -> list[ObservationResponse]:
    decision = _decision(services, decision_id)
    observations = services.playback_service.observations(decision_id)
    return [
        ObservationResponse(
            **observation.model_dump(),
            display_label=observation.display_label,
            runtime_mode=decision.runtime_mode,
        )
        for observation in observations
    ]
