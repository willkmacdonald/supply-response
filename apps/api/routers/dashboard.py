"""Dashboard summary endpoint (mirrors the Power BI Command Center page)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api import services
from apps.api.database import ActionRecord, CaseRecord, get_session
from apps.api.dataset import get_dataset
from apps.api.schemas import DashboardSummary
from services.exposure.calculator import CALCULATION_VERSION

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_CLOSED_STATUSES = {"approved", "rejected", "closed"}


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(session: Session = Depends(get_session)) -> DashboardSummary:
    cases = session.execute(select(CaseRecord).order_by(CaseRecord.case_id)).scalars().all()
    actions = session.execute(select(ActionRecord)).scalars().all()

    by_status = Counter(case.status for case in cases)
    by_severity = Counter(case.severity for case in cases)

    decision_minutes: list[float] = []
    for action in actions:
        case = next((c for c in cases if c.case_id == action.case_id), None)
        if case is None:
            continue
        delta = action.decided_at - case.signal_received_at
        decision_minutes.append(round(delta.total_seconds() / 60.0, 2))

    top_scenarios = []
    for case in cases:
        for record in sorted(case.scenarios, key=lambda r: r.rank)[:1]:
            top_scenarios.append(
                {
                    "case_id": case.case_id,
                    "scenario_id": record.scenario_id,
                    "rank": record.rank,
                    "executable": bool(record.executable),
                    "response_cost": record.response_cost,
                    "revenue_protected": record.revenue_protected,
                }
            )

    return DashboardSummary(
        generated_at=datetime.now(timezone.utc),
        calculation_version=CALCULATION_VERSION,
        active_cases=sum(1 for case in cases if case.status not in _CLOSED_STATUSES),
        cases_by_status=dict(sorted(by_status.items())),
        cases_by_severity=dict(sorted(by_severity.items())),
        total_revenue_at_risk=round(sum(case.revenue_at_risk for case in cases), 2),
        total_margin_at_risk=round(sum(case.margin_at_risk for case in cases), 2),
        total_otif_lines_at_risk=sum(case.otif_lines_at_risk for case in cases),
        approved_actions=sum(1 for action in actions if action.status == "approved"),
        rejected_actions=sum(1 for action in actions if action.status == "rejected"),
        average_minutes_to_decision=(
            round(sum(decision_minutes) / len(decision_minutes), 2)
            if decision_minutes
            else None
        ),
        dataset_row_counts=get_dataset().row_counts(),
        cases=[services.to_case_summary(case) for case in cases],
        top_scenarios=top_scenarios,
    )
