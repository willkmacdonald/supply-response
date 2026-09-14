# FastAPI dependency markers are intentionally declared in signature defaults.
# ruff: noqa: B008

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import ValidationError

from apps.api.app.contracts import DecisionResponse
from apps.api.app.dependencies import (
    ApplicationServices,
    get_services,
    require_alex_identity,
    require_finance_actor,
)
from apps.api.app.finance_contracts import (
    FinalizeProposalRequest,
    ResolveFinanceRequest,
    SubmitProposalRequest,
)
from apps.api.app.routes.decisions import decision_response
from data.domain.decisions import DecisionKind, IdentitySnapshot
from data.domain.proposals import ProposalState
from services.finance.contracts import (
    FinalizeProposalCommand,
    FinanceReviewDetail,
    ResolutionResult,
    ResolveFinanceCommand,
    SubmissionResult,
    SubmitProposalCommand,
)
from services.finance.decisions import (
    FinanceFinalizationConflict,
    FinanceFinalizationInvalid,
)
from services.finance.identity import FinancePermissionDenied
from services.finance.service import (
    FinanceCommandConflict,
    FinanceRequestInvalid,
)
from services.persistence.finance_reviews import FinanceReviewRevisionConflict
from services.persistence.proposals import StaleProposal
from services.persistence.store import RecordNotFound

router = APIRouter(tags=["finance"])

_MAPPED_ERRORS = (
    FinancePermissionDenied,
    RecordNotFound,
    StaleProposal,
    FinanceCommandConflict,
    FinanceReviewRevisionConflict,
    FinanceFinalizationConflict,
    FinanceRequestInvalid,
    FinanceFinalizationInvalid,
)


def _enabled(services: ApplicationServices) -> None:
    if not services.settings.independent_finance_enabled:
        raise HTTPException(
            status_code=409, detail={"code": "FINANCE_WORKFLOW_DISABLED"}
        )


def _service(services: ApplicationServices):
    if services.finance_service is None:
        raise HTTPException(
            status_code=503, detail={"code": "FINANCE_WORKFLOW_UNAVAILABLE"}
        )
    return services.finance_service


def _map(error: Exception, *, operation: str) -> HTTPException:
    if isinstance(error, FinancePermissionDenied):
        return HTTPException(status_code=403, detail={"code": "PERSONA_NOT_AUTHORIZED"})
    if isinstance(error, RecordNotFound):
        return HTTPException(
            status_code=404, detail={"code": "FINANCE_RECORD_NOT_FOUND"}
        )
    if isinstance(error, StaleProposal):
        code = "STALE_PROPOSAL" if operation == "submit" else "FINANCE_COMMAND_CONFLICT"
        return HTTPException(status_code=409, detail={"code": code})
    if isinstance(error, (FinanceCommandConflict, FinanceReviewRevisionConflict)):
        return HTTPException(
            status_code=409, detail={"code": "FINANCE_COMMAND_CONFLICT"}
        )
    if isinstance(error, FinanceFinalizationConflict):
        return HTTPException(
            status_code=409, detail={"code": "FINANCE_FINALIZATION_CONFLICT"}
        )
    if isinstance(error, (FinanceRequestInvalid, FinanceFinalizationInvalid)):
        return HTTPException(
            status_code=409, detail={"code": "FINANCE_REQUEST_INVALID"}
        )
    raise error


@router.get("/api/cases/{case_id}/proposal", response_model=ProposalState)
def proposal_status(
    case_id: str,
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(require_alex_identity),
) -> ProposalState:
    try:
        return _service(services).status(case_id, actor)
    except _MAPPED_ERRORS as error:
        raise _map(error, operation="status") from None


@router.post(
    "/api/cases/{case_id}/proposals", response_model=SubmissionResult, status_code=201
)
def submit_proposal(
    case_id: str,
    request: SubmitProposalRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(require_alex_identity),
) -> SubmissionResult:
    _enabled(services)
    try:
        command = SubmitProposalCommand(
            case_id=case_id,
            option_id=request.option_id,
            expected=request.expected,
            idempotency_key=idempotency_key,
        )
    except ValidationError:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_FINANCE_COMMAND"}
        ) from None
    try:
        return _service(services).submit(command, actor)
    except _MAPPED_ERRORS as error:
        raise _map(error, operation="submit") from None


@router.get("/api/finance/reviews", response_model=list[FinanceReviewDetail])
def list_reviews(
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(require_finance_actor),
) -> tuple[FinanceReviewDetail, ...]:
    try:
        return _service(services).list_pending(actor)
    except _MAPPED_ERRORS as error:
        raise _map(error, operation="list") from None


@router.get("/api/finance/reviews/{review_id}", response_model=FinanceReviewDetail)
def review_detail(
    review_id: str,
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(require_finance_actor),
) -> FinanceReviewDetail:
    try:
        return _service(services).detail(review_id, actor)
    except _MAPPED_ERRORS as error:
        raise _map(error, operation="detail") from None


@router.post(
    "/api/finance/reviews/{review_id}/resolutions",
    response_model=ResolutionResult,
    status_code=201,
)
def resolve_review(
    review_id: str,
    request: ResolveFinanceRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(require_finance_actor),
) -> ResolutionResult:
    _enabled(services)
    try:
        command = ResolveFinanceCommand(
            review_id=review_id,
            expected=request.expected,
            expected_review_revision=request.expected_review_revision,
            approved=request.approved,
            reason=request.reason,
            idempotency_key=idempotency_key,
        )
    except ValidationError:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_FINANCE_COMMAND"}
        ) from None
    try:
        return _service(services).resolve(command, actor)
    except _MAPPED_ERRORS as error:
        raise _map(error, operation="resolve") from None


@router.post(
    "/api/cases/{case_id}/proposal-decisions",
    response_model=DecisionResponse,
    status_code=201,
)
def finalize_proposal(
    case_id: str,
    request: FinalizeProposalRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(require_alex_identity),
) -> DecisionResponse:
    _enabled(services)
    if services.finance_decision_service is None:
        raise HTTPException(
            status_code=503, detail={"code": "FINANCE_WORKFLOW_UNAVAILABLE"}
        )
    try:
        command = FinalizeProposalCommand(
            case_id=case_id,
            expected=request.expected,
            kind=DecisionKind(request.kind),
            rejection_reason=request.rejection_reason,
            idempotency_key=idempotency_key,
        )
    except (ValidationError, ValueError):
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_FINANCE_COMMAND"}
        ) from None
    try:
        decision = services.finance_decision_service.finalize(command, actor)
    except _MAPPED_ERRORS as error:
        raise _map(error, operation="finalize") from None
    return decision_response(services, decision)
