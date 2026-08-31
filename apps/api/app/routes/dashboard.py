from fastapi import APIRouter, Depends

from apps.api.app.contracts import DashboardCaseResponse
from apps.api.app.dependencies import ApplicationServices, get_services
from apps.api.app.routes.cases import case_response


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/cases", response_model=list[DashboardCaseResponse])
def dashboard_cases(
    services: ApplicationServices = Depends(get_services),
) -> list[DashboardCaseResponse]:
    rows: list[DashboardCaseResponse] = []
    for case in services.store.list_cases():
        projection = services.store.get_projection(case.case_id)
        analysis = (
            services.store.get_analysis(projection.current_analysis_id)
            if projection.current_analysis_id is not None
            else None
        )
        decision = None
        actions = ()
        observations = ()
        if projection.current_decision_id is not None:
            with services.uow_factory() as uow:
                decision = uow.decisions.get(projection.current_decision_id)
                actions = uow.execution.list_actions(
                    decision_id=projection.current_decision_id
                )
                observations = uow.execution.list_observations(
                    projection.current_decision_id
                )
        summary = case_response(services, case.case_id)
        rows.append(
            DashboardCaseResponse(
                **summary.model_dump(),
                analysis_created_at=analysis.created_at if analysis else None,
                decision_decided_at=decision.decided_at if decision else None,
                recommended_option_id=(
                    analysis.ranking.recommended_option_id if analysis else None
                ),
                selected_option_id=(decision.selected_option_id if decision else None),
                action_count=len(actions),
                observation_count=len(observations),
            )
        )
    return rows
