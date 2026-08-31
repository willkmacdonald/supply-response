from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from apps.api.app.contracts import DecisionRequest, DecisionResponse
from apps.api.app.dependencies import (
    ApplicationServices,
    get_server_identity,
    get_services,
)
from apps.api.app.routes.cases import _projection
from data.domain.decisions import (
    Decision,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
)
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
    )


def _require_role(actor: IdentitySnapshot, role: str) -> None:
    if role not in actor.effective_roles:
        raise HTTPException(
            status_code=403,
            detail={"code": "ROLE_REQUIRED", "role": role},
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
    actor: IdentitySnapshot = Depends(get_server_identity),
) -> DecisionResponse:
    projection = _projection(services, case_id)
    _require_role(actor, "response_approver")
    kind = DecisionKind(request.kind)
    if kind is DecisionKind.APPROVED:
        _require_role(actor, "material_planner")

    if projection.current_analysis_id != request.analysis_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STALE_ANALYSIS",
                "message": "Create a new Analysis Version before deciding.",
            },
        )
    analysis = services.store.get_analysis(request.analysis_id)
    if kind is DecisionKind.APPROVED:
        option = next(
            (
                item
                for item in analysis.response_options
                if item.option_id == request.selected_option_id
            ),
            None,
        )
        if option is None:
            raise HTTPException(
                status_code=409,
                detail={"code": "OPTION_NOT_IN_ANALYSIS"},
            )
        if not option.executable or option.predicted is None or option.blocking_codes:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OPTION_NOT_EXECUTABLE",
                    "blocking_codes": list(option.blocking_codes),
                },
            )

    try:
        decision = services.decision_service.record(
            RecordDecisionCommand(
                case_id=case_id,
                analysis_id=request.analysis_id,
                selected_option_id=request.selected_option_id,
                kind=kind,
                idempotency_key=idempotency_key,
                rejection_reason=request.rejection_reason,
            ),
            actor,
        )
    except IdempotencyKeyConflict:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_KEY_CONFLICT"},
        ) from None
    except DecisionPolicyViolation as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "DECISION_POLICY_VIOLATION", "message": str(error)},
        ) from None
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
    services: ApplicationServices = Depends(get_services),
) -> DecisionResponse:
    decision = _decision(services, decision_id)
    if services.planning_status(decision_id, decision.kind) != "failed":
        raise HTTPException(
            status_code=409,
            detail={"code": "ACTION_PLANNING_RETRY_NOT_AVAILABLE"},
        )
    services.planning_worker.process_next_outbox()
    return decision_response(services, decision)
