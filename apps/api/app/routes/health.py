from fastapi import APIRouter, Depends

from apps.api.app.contracts import RuntimeResponse
from apps.api.app.dependencies import ApplicationServices, get_services


router = APIRouter()


@router.get("/health")
def health(services: ApplicationServices = Depends(get_services)) -> dict[str, str]:
    return {"status": "ok", "runtime_mode": services.settings.runtime_mode.value}


@router.get("/api/runtime", response_model=RuntimeResponse)
def runtime(
    services: ApplicationServices = Depends(get_services),
) -> RuntimeResponse:
    return RuntimeResponse(
        runtime_mode=services.settings.runtime_mode,
        work_iq="synthetic",
        operational_store="sqlite",
        agent_runtime="local",
        power_bi_available=False,
    )
