# FastAPI dependency markers are intentionally declared in signature defaults.
# ruff: noqa: B008

from fastapi import APIRouter, Depends

from apps.api.app.contracts import RuntimeResponse
from apps.api.app.dependencies import ApplicationServices, get_services

router = APIRouter()


@router.get("/health")
def health(
    services: ApplicationServices = Depends(get_services),
) -> dict[str, str | int]:
    result: dict[str, str | int] = {
        "status": "ok",
        "runtime_mode": services.settings.runtime_mode.value,
    }
    if services.fabric_schema_version is not None:
        result.update(
            operational_store=services.operational_store,
            schema_version=services.fabric_schema_version,
        )
    return result


@router.get("/api/runtime", response_model=RuntimeResponse)
def runtime(
    services: ApplicationServices = Depends(get_services),
) -> RuntimeResponse:
    return RuntimeResponse(
        runtime_mode=services.settings.runtime_mode,
        work_iq=(
            "work_iq" if services.settings.runtime_mode.value == "live" else "synthetic"
        ),
        operational_store=services.operational_store,
        agent_runtime=(
            "foundry" if services.settings.runtime_mode.value == "live" else "local"
        ),
        power_bi_available=services.power_bi_available,
        power_bi_url=services.power_bi_url,
        capability_health={
            "operational_store": "ready",
            "work_iq": "ready",
            "agent_runtime": "ready",
            "power_bi": "ready" if services.power_bi_available else "unavailable",
        },
    )
