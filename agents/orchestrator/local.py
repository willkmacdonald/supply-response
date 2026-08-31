from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ExplanationAgent(Protocol):
    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class _LocalExtractionAgent:
    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        evidence = payload.get("evidence", ())
        return {
            "facts": [
                {
                    "evidence_id": item["evidence_id"],
                    "authority_scope": item["authority_scope"][0],
                    "source_span": item["claim"],
                }
                for item in evidence
            ],
            "uncertainties": [],
        }


class _LocalDecisionAgent:
    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        option_id = str(payload["recommended_option_id"])
        return {
            "recommended_option_id": option_id,
            "stage_references": [item["stage_reference"] for item in payload["stages"]],
        }


@dataclass(frozen=True, slots=True)
class LocalAgentSet:
    signal: ExplanationAgent
    context: ExplanationAgent
    decision: ExplanationAgent

    @classmethod
    def deterministic(cls) -> LocalAgentSet:
        return cls(
            signal=_LocalExtractionAgent(),
            context=_LocalExtractionAgent(),
            decision=_LocalDecisionAgent(),
        )
