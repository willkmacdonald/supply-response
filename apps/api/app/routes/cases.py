# FastAPI dependency markers are intentionally declared in signature defaults.
# ruff: noqa: B008

from __future__ import annotations

import inspect
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from apps.api.app.auth import AuthenticatedActor
from apps.api.app.contracts import (
    AnalysisResponse,
    CaseControls,
    CaseResponse,
    CreateCaseRequest,
)
from apps.api.app.dependencies import ApplicationServices, get_actor, get_services
from apps.api.app.live import LiveSourceUnavailable
from data.domain import CaseStatus, RuntimeMode
from data.synthetic.rl001 import instantiate_rl001
from services.persistence.store import RecordNotFound

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _projection(services: ApplicationServices, case_id: str):
    try:
        return services.store.get_projection(case_id)
    except RecordNotFound:
        raise HTTPException(
            status_code=404,
            detail={"code": "CASE_NOT_FOUND", "case_id": case_id},
        ) from None


def case_response(
    services: ApplicationServices,
    case_id: str,
) -> CaseResponse:
    projection = _projection(services, case_id)
    case = projection.case
    planning_failed = projection.display_status is not None
    return CaseResponse(
        **case.model_dump(),
        current_analysis_id=projection.current_analysis_id,
        current_decision_id=projection.current_decision_id,
        display_status=projection.display_status,
        recorded_at=services.case_recorded_at(case_id),
        projection_updated_at=services.projection_updated_at(case_id),
        controls=CaseControls(
            new_analysis=case.status
            in {
                CaseStatus.OPEN,
                CaseStatus.DECISION_REJECTED,
                CaseStatus.REANALYSIS_REQUIRED,
            },
            decide=case.status is CaseStatus.AWAITING_DECISION,
            retry_action_planning=planning_failed,
            start_playback=case.status is CaseStatus.EXECUTING,
        ),
    )


def analysis_response(analysis) -> AnalysisResponse:
    recommended = next(
        (
            option
            for option in analysis.response_options
            if option.option_id == analysis.ranking.recommended_option_id
        ),
        None,
    )
    return AnalysisResponse(
        **analysis.model_dump(),
        runtime_mode=analysis.material.runtime_mode,
        scenario_effective_time=analysis.material.scenario_effective_time,
        recommendation=recommended,
    )


@router.post("", response_model=CaseResponse, status_code=201)
async def create_case(
    request: CreateCaseRequest,
    services: ApplicationServices = Depends(get_services),
) -> CaseResponse:
    case_id = f"RL-CASE-{uuid4()}"
    if services.settings.runtime_mode is RuntimeMode.LIVE:
        if services.live_operational_data is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "LIVE_SOURCE_UNAVAILABLE",
                    "new_fallback_case_allowed": True,
                },
            )
        try:
            live = await services.live_operational_data.retrieve(
                case_id=case_id,
                purpose=request.purpose,
                analysis_id=f"case-bootstrap-{case_id}",
                retrieved_at=services.clock(),
            )
            case, snapshot = live.case, live.snapshot
        except Exception:  # noqa: BLE001 - live source errors are intentionally bounded
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "LIVE_SOURCE_UNAVAILABLE",
                    "new_fallback_case_allowed": True,
                },
            ) from None
    else:
        case, snapshot = instantiate_rl001(
            case_id=case_id,
            purpose=request.purpose,
            runtime_mode=services.settings.runtime_mode,
        )
    services.store.create_case(case, snapshot)
    return case_response(services, case_id)


@router.get("", response_model=list[CaseResponse])
def list_cases(
    services: ApplicationServices = Depends(get_services),
) -> list[CaseResponse]:
    return [
        case_response(services, case.case_id) for case in services.store.list_cases()
    ]


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    services: ApplicationServices = Depends(get_services),
) -> CaseResponse:
    return case_response(services, case_id)


@router.post("/{case_id}/analysis", response_model=AnalysisResponse, status_code=201)
async def create_analysis(
    case_id: str,
    services: ApplicationServices = Depends(get_services),
    actor: AuthenticatedActor | None = Depends(get_actor),
) -> AnalysisResponse:
    try:
        pending = (
            services.analysis_service.create(case_id)
            if actor is None
            else services.analysis_service.create(case_id, actor=actor)
        )
        analysis = await pending if inspect.isawaitable(pending) else pending
    except RecordNotFound:
        raise HTTPException(
            status_code=404,
            detail={"code": "CASE_NOT_FOUND", "case_id": case_id},
        ) from None
    except LiveSourceUnavailable as error:
        detail = {
            "code": error.code,
            "new_fallback_case_allowed": error.new_fallback_case_allowed,
        }
        if error.source_kind is not None and error.stage is not None:
            detail.update(source_kind=error.source_kind, stage=error.stage)
        raise HTTPException(
            status_code=503,
            detail=detail,
        ) from None
    return analysis_response(analysis)


@router.get("/{case_id}/analysis", response_model=AnalysisResponse)
def get_current_analysis(
    case_id: str,
    services: ApplicationServices = Depends(get_services),
) -> AnalysisResponse:
    projection = _projection(services, case_id)
    if projection.current_analysis_id is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "ANALYSIS_REQUIRED"},
        )
    return analysis_response(
        services.store.get_analysis(projection.current_analysis_id)
    )
