"""Local, deterministic stand-in for the Foundry hosted orchestrator.

The hosted orchestrator (Microsoft Agent Framework) is responsible for calling
the specialist agents and the deterministic tools. Locally we run the same
sequence without any model call so the demo is reproducible:

1. Signal   -> extract confirmed facts from the disruption record.
2. Context  -> attach policy and quality constraints plus evidence.
3. Tools    -> deterministic exposure and scenario calculations.
4. Decision -> rank scenarios, exclude infeasible ones, surface approvals.

Nothing here writes to the action ledger: consequential actions always require
explicit human approval through the API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from apps.api.services import (
    analyze,
    case_evidence,
    case_facts,
    case_uncertainties,
    recommended_scenario_id,
)
from data.schemas.models import Dataset, Disruption

ORCHESTRATOR_VERSION = "1.0.0"


def run_case(
    dataset: Dataset,
    disruption: Disruption,
    run_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Produce the full decision package for one disruption."""
    run_at = run_at or datetime.now(timezone.utc)
    exposure, evaluations = analyze(dataset, disruption, analyzed_at=run_at)
    executable = [e for e in evaluations if e.executable]
    blocked = [e for e in evaluations if not e.executable]

    return {
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "disruption_id": disruption.disruption_id,
        "run_at": run_at.isoformat(),
        "facts": case_facts(disruption),
        "uncertainties": case_uncertainties(disruption, dataset),
        "evidence": [item.model_dump() for item in case_evidence(disruption)],
        "exposure": exposure.model_dump(mode="json"),
        "scenarios": [e.model_dump(mode="json") for e in evaluations],
        "recommended_scenario_id": recommended_scenario_id(evaluations),
        "executable_scenario_ids": [e.scenario_id for e in executable],
        "conditional_scenario_ids": [e.scenario_id for e in blocked],
        "approval_required": True,
    }


__all__ = ["ORCHESTRATOR_VERSION", "run_case"]
