from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response

from apps.api.app.dependencies import ApplicationServices, get_services
from data.domain import CasePurpose
from services.persistence.store import RecordNotFound


router = APIRouter(prefix="/api/test", tags=["automated-test-support"])


@router.post(
    "/cases/{case_id}/faults/{fault}",
    status_code=204,
    response_class=Response,
)
def arm_case_fault(
    case_id: str,
    fault: Literal["planning_failure", "first_action_failure"],
    services: ApplicationServices = Depends(get_services),
) -> Response:
    try:
        case = services.store.get_projection(case_id).case
    except RecordNotFound:
        raise HTTPException(
            status_code=404,
            detail={"code": "CASE_NOT_FOUND", "case_id": case_id},
        ) from None
    if case.purpose is not CasePurpose.AUTOMATED_TEST:
        raise HTTPException(
            status_code=403,
            detail={"code": "AUTOMATED_TEST_CASE_REQUIRED"},
        )
    services.test_faults.arm(case_id, fault)
    return Response(status_code=204)
