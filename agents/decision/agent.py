"""Decision agent: produce a narrative explanation for a disruption case.

Uses Azure OpenAI when ``AZURE_OPENAI_ENDPOINT`` is configured; falls back to
a deterministic template-based narrative when the endpoint is absent or the
call fails.

The system prompt lives in ``agents/decision/prompt.md``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from services.exposure.calculator import ExposureResult
from services.scenarios.evaluator import ScenarioEvaluation

_logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
AGENT_VERSION = "1.0.0"


def _deterministic_narrative(
    facts: list[str],
    uncertainties: list[str],
    exposure: ExposureResult,
    evaluations: list[ScenarioEvaluation],
    recommended_scenario_id: Optional[str],
) -> str:
    """Build a Markdown narrative from the deterministic data without an LLM."""
    lines: list[str] = ["## Situation"]
    for fact in facts:
        lines.append(f"- {fact}")

    if uncertainties:
        lines.append("\n## Open questions")
        for item in uncertainties:
            lines.append(f"- {item}")

    lines.append("\n## Exposure")
    lines.append(
        f"First projected stockout: "
        f"**{exposure.first_stockout_date or 'none within horizon'}**. "
        f"Maximum shortage: **{exposure.max_shortage_qty:,} units**. "
        f"Revenue at risk: **${exposure.revenue_at_risk:,.0f}**. "
        f"OTIF lines at risk: **{exposure.otif_lines_at_risk}**."
    )

    executable = [e for e in evaluations if e.executable]
    blocked = [e for e in evaluations if not e.executable]
    recommended = next(
        (e for e in evaluations if e.scenario_id == recommended_scenario_id), None
    ) or next((e for e in evaluations if e.recommended), None)

    lines.append("\n## Scenario trade-offs")
    for ev in executable:
        marker = " *(recommended)*" if ev.recommended else ""
        lines.append(
            f"- **{ev.scenario_id}** {ev.title}{marker}: "
            f"cost ${ev.response_cost:,.0f}, "
            f"revenue protected ${ev.revenue_protected:,.0f}, "
            f"net benefit ${ev.net_benefit:,.0f}."
        )
    for ev in blocked:
        lines.append(
            f"- **{ev.scenario_id}** {ev.title} — "
            f"**not executable**: {ev.blocking_constraint}. "
            f"Conditional future option."
        )

    if recommended:
        lines.append("\n## Recommendation")
        lines.append(
            f"**{recommended.scenario_id} — {recommended.title}** is the recommended "
            f"immediate action. "
            f"Net benefit: ${recommended.net_benefit:,.0f}. "
            f"Response cost: ${recommended.response_cost:,.0f}. "
            f"Revenue protected: ${recommended.revenue_protected:,.0f}. "
        )
        if recommended.assumptions:
            lines.append("\nAssumptions:")
            for assumption in recommended.assumptions:
                lines.append(f"- {assumption}")

    lines.append("\n## Required approval")
    lines.append(
        "Explicit human approval is required before any commitment is made. "
        "No purchase order or financial commitment has been created."
    )
    if uncertainties:
        lines.append("\nUnresolved questions that must be tracked:")
        for item in uncertainties:
            lines.append(f"- {item}")

    lines.append(
        "\n*Numbers are from the deterministic calculation engine — "
        "no LLM arithmetic was used.*"
    )
    return "\n".join(lines)


def _llm_narrative(
    facts: list[str],
    uncertainties: list[str],
    exposure: ExposureResult,
    evaluations: list[ScenarioEvaluation],
    recommended_scenario_id: Optional[str],
) -> str:
    """Call Azure OpenAI to produce a narrative explanation."""
    import json as _json

    import openai  # deferred; only needed when LLM is configured

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_OPENAI_DECISION_DEPLOYMENT", "gpt-4o")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    client = openai.AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key if api_key else openai.NOT_GIVEN,
        api_version=api_version,
    )

    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "facts": facts,
        "uncertainties": uncertainties,
        "recommended_scenario_id": recommended_scenario_id,
        "exposure": exposure.model_dump(mode="json"),
        "scenarios": [e.model_dump(mode="json") for e in evaluations],
    }
    user_message = (
        "Produce a clear, concise recommendation narrative in Markdown for the "
        "material planner based on the following JSON decision package. "
        "Follow the system prompt rules exactly — use all numbers verbatim.\n\n"
        + _json.dumps(payload, indent=2, default=str)
    )

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


def narrate(
    facts: list[str],
    uncertainties: list[str],
    exposure: ExposureResult,
    evaluations: list[ScenarioEvaluation],
    recommended_scenario_id: Optional[str] = None,
) -> tuple[str, str]:
    """Produce a narrative explanation for a disruption case.

    Returns ``(narrative_text, source)`` where ``source`` is
    ``"azure_openai"`` or ``"deterministic"``.
    """
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    if endpoint:
        try:
            text = _llm_narrative(
                facts, uncertainties, exposure, evaluations, recommended_scenario_id
            )
            return text, "azure_openai"
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "Decision LLM call failed, falling back to deterministic: %s", exc
            )
    text = _deterministic_narrative(
        facts, uncertainties, exposure, evaluations, recommended_scenario_id
    )
    return text, "deterministic"


__all__ = ["AGENT_VERSION", "narrate"]
