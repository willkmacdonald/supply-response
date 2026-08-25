"""Context agent: retrieve quality constraints and policies for a disruption.

Reads from the local deterministic dataset in offline mode.  When
``WORK_IQ_ENDPOINT`` is configured in a future integration, this module
would call Work IQ through the MCP endpoint instead.

The output contract mirrors ``agents/context/prompt.md``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from data.schemas.models import Dataset, Disruption

_logger = logging.getLogger(__name__)
AGENT_VERSION = "1.0.0"


class ContextResult:
    """Structured output from the Context agent."""

    def __init__(
        self,
        constraints: list[dict[str, Any]],
        policies: list[dict[str, Any]],
        source: str,
    ) -> None:
        self.constraints = constraints
        self.policies = policies
        self.source = source
        self.agent_version = AGENT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraints": self.constraints,
            "policies": self.policies,
            "source": self.source,
            "agent_version": self.agent_version,
        }


def _deterministic_context(disruption: Disruption, dataset: Dataset) -> ContextResult:
    """Build context from the local synthetic dataset."""
    constraints: list[dict[str, Any]] = []
    for q in dataset.quality_qualifications:
        if q.part_id == disruption.part_id:
            constraints.append(
                {
                    "reference": q.qualification_id,
                    "type": "quality_qualification",
                    "supplier_id": q.supplier_id,
                    "part_number": q.part_id,
                    "status": q.status.value,
                    "expected_decision_date": (
                        q.expected_decision_date.isoformat()
                        if q.expected_decision_date
                        else None
                    ),
                    "formality": "formal",
                    "citation": f"erp:{q.qualification_id}",
                    "captured_at": disruption.signal_received_at.isoformat(),
                }
            )
    policies: list[dict[str, Any]] = [
        {
            "reference": "RL-POLICY-FREIGHT",
            "summary": "Premium freight above 25,000 requires finance approval.",
        }
    ]
    return ContextResult(
        constraints=constraints, policies=policies, source="deterministic"
    )


def retrieve(disruption: Disruption, dataset: Dataset) -> ContextResult:
    """Retrieve context (quality constraints, policies) for a disruption.

    In local mode this always uses the deterministic dataset.  When
    ``WORK_IQ_ENDPOINT`` is set, a log warning is emitted to signal that live
    retrieval is not yet wired and the deterministic fallback is used.
    """
    work_iq_endpoint = os.environ.get("WORK_IQ_ENDPOINT", "")
    if work_iq_endpoint:
        _logger.warning(
            "WORK_IQ_ENDPOINT is configured (%s) but live Work IQ retrieval is not "
            "yet implemented; falling back to deterministic context.",
            work_iq_endpoint,
        )
    return _deterministic_context(disruption, dataset)


__all__ = ["AGENT_VERSION", "ContextResult", "retrieve"]
