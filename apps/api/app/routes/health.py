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
    readiness = services.readiness.check()
    schema_version = readiness.fabric_schema_version
    if schema_version is not None:
        result.update(
            operational_store=services.operational_store,
            schema_version=schema_version,
        )
    return result


@router.get("/api/runtime", response_model=RuntimeResponse)
def runtime(
    services: ApplicationServices = Depends(get_services),
) -> RuntimeResponse:
    readiness = services.readiness.check()
    power_bi_available = (
        services.settings.runtime_mode.value == "live"
        and readiness.power_bi_verified
        and readiness.capability_health.get("power_bi") == "ready"
    )
    return RuntimeResponse(
        runtime_mode=services.settings.runtime_mode,
        work_iq=(
            "work_iq" if services.settings.runtime_mode.value == "live" else "synthetic"
        ),
        operational_store=services.operational_store,
        agent_runtime=(
            "foundry" if services.settings.runtime_mode.value == "live" else "local"
        ),
        power_bi_available=power_bi_available,
        power_bi_url=services.power_bi_url if power_bi_available else None,
        capability_health=readiness.capability_health,
        deployment_contract=(
            {
                "scenario_effective_time": services.settings.scenario_effective_time.isoformat(),
                "corpus_version": services.settings.workiq_corpus_version or "",
                "supplier_source_id": services.settings.workiq_supplier_source_id or "",
                "quality_source_id": services.settings.workiq_quality_source_id or "",
                "signal_agent_version": services.settings.foundry_signal_agent_version
                or "",
                "context_agent_version": services.settings.foundry_context_agent_version
                or "",
                "decision_agent_version": services.settings.foundry_decision_agent_version
                or "",
            }
            if services.settings.runtime_mode.value == "live"
            else None
        ),
    )
