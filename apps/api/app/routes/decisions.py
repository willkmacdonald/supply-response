# FastAPI dependency/body markers are intentionally declared in signature defaults.
# ruff: noqa: B008

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, HTTPException

from apps.api.app.contracts import (
    DecisionRequest,
    DecisionResponse,
    ServerMutationRequest,
)
from apps.api.app.dependencies import (
    ApplicationServices,
    get_decision_identity,
    get_services,
)
from apps.api.app.routes.cases import _projection
from data.domain.decisions import (
    Decision,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
)
from data.domain.evidence import IdentitySource
from services.decisions.service import (
    DecisionPolicyViolation,
    IdempotencyKeyConflict,
)
from services.persistence.store import RecordNotFound

router = APIRouter(tags=["decisions"])


def _decision(
    services: ApplicationServices,
    decision_id: str,
) -> Decision:
    try:
        with services.uow_factory() as uow:
            return uow.decisions.get(decision_id)
    except RecordNotFound:
        raise HTTPException(
            status_code=404,
            detail={"code": "DECISION_NOT_FOUND", "decision_id": decision_id},
        ) from None


def decision_response(
    services: ApplicationServices,
    decision: Decision,
) -> DecisionResponse:
    return DecisionResponse(
        decision_id=decision.decision_id,
        case_id=decision.case_id,
        analysis_id=decision.analysis_id,
        analysis_material_hash=decision.analysis_material_hash,
        kind=decision.kind.value,
        selected_option_id=decision.selected_option_id,
        rejection_reason=decision.rejection_reason,
        evidence_ids=decision.evidence_ids,
        assumptions=decision.assumptions,
        constraints=decision.constraints,
        prerequisite_roles=decision.prerequisite_roles,
        approval_satisfactions=decision.approval_satisfactions,
        calculation_version=decision.calculation_version,
        evidence_policy_version=decision.evidence_policy_version,
        approval_policy_version=decision.approval_policy_version,
        ranking_policy_version=decision.ranking_policy_version,
        runtime_mode=decision.runtime_mode,
        scenario_effective_time=decision.scenario_effective_time,
        decided_at=decision.decided_at,
        projection_updated_at=services.projection_updated_at(decision.case_id),
        action_planning_status=services.planning_status(
            decision.decision_id,
            decision.kind,
        ),
        new_analysis_available=decision.kind is DecisionKind.REJECTED,
        proposal_approval_evidence=decision.proposal_approval,
    )


def _require_role(actor: IdentitySnapshot, role: str) -> None:
    if (
        actor.persona_id != "RL-PERSONA-ALEX"
        or actor.identity_source is not IdentitySource.ENTRA
        or actor.source_id != "RL-ENTRA-ALEX"
        or role not in actor.effective_roles
    ):
        raise HTTPException(
            status_code=403,
            detail={"code": "ROLE_REQUIRED", "role": role},
        )


def _policy_http_error(
    error: DecisionPolicyViolation,
) -> HTTPException:
    if error.code == "ROLE_REQUIRED" and error.role is not None:
        return HTTPException(
            status_code=403,
            detail={"code": "ROLE_REQUIRED", "role": error.role},
        )
    if error.code == "STALE_ANALYSIS":
        return HTTPException(
            status_code=409,
            detail={
                "code": "STALE_ANALYSIS",
                "message": "Create a new Analysis Version before deciding.",
            },
        )
    if error.code == "OPTION_NOT_EXECUTABLE":
        return HTTPException(
            status_code=409,
            detail={
                "code": "OPTION_NOT_EXECUTABLE",
                "blocking_codes": list(error.blocking_codes),
            },
        )
    return HTTPException(
        status_code=409,
        detail={"code": error.code, "message": str(error)},
    )


@router.post(
    "/api/cases/{case_id}/decisions",
    response_model=DecisionResponse,
    status_code=201,
)
def record_decision(
    case_id: str,
    request: DecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(get_decision_identity),
) -> DecisionResponse:
    kind = DecisionKind(request.kind)
    command = RecordDecisionCommand(
        case_id=case_id,
        analysis_id=request.analysis_id,
        selected_option_id=request.selected_option_id,
        kind=kind,
        idempotency_key=idempotency_key,
        rejection_reason=request.rejection_reason,
    )

    try:
        decision = services.decision_service.record(command, actor)
    except IdempotencyKeyConflict:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_KEY_CONFLICT"},
        ) from None
    except RecordNotFound:
        _projection(services, case_id)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STALE_ANALYSIS",
                "message": "Create a new Analysis Version before deciding.",
            },
        ) from None
    except DecisionPolicyViolation as error:
        raise _policy_http_error(error) from None
    return decision_response(services, decision)


@router.get(
    "/api/decisions/{decision_id}",
    response_model=DecisionResponse,
)
def get_decision(
    decision_id: str,
    services: ApplicationServices = Depends(get_services),
) -> DecisionResponse:
    return decision_response(services, _decision(services, decision_id))


@router.post(
    "/api/decisions/{decision_id}/actions/retry",
    response_model=DecisionResponse,
)
def retry_action_planning(
    decision_id: str,
    request: ServerMutationRequest | None = Body(default=None),
    services: ApplicationServices = Depends(get_services),
    actor: IdentitySnapshot = Depends(get_decision_identity),
) -> DecisionResponse:
    del request
    _require_role(actor, "response_approver")
    decision = _decision(services, decision_id)
    if services.planning_status(decision_id, decision.kind) != "failed":
        raise HTTPException(
            status_code=409,
            detail={"code": "ACTION_PLANNING_RETRY_NOT_AVAILABLE"},
        )
    if not services.planning_worker.process_decision_outbox(decision_id):
        raise HTTPException(
            status_code=409,
            detail={"code": "ACTION_PLANNING_RETRY_NOT_AVAILABLE"},
        )
    return decision_response(services, decision)
