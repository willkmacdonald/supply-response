"""Signal agent: extract structured facts from a supplier communication.

Uses Azure OpenAI when ``AZURE_OPENAI_ENDPOINT`` is configured and an email body
is provided; falls back to deterministic extraction from the Disruption model
when the endpoint is absent or the call fails.

The JSON output contract mirrors ``agents/signal/prompt.md``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from data.schemas.models import Disruption

_logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
AGENT_VERSION = "1.0.0"


class SignalExtraction:
    """Structured output from the Signal agent."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.disruption_id: str = data.get("disruption_id", "")
        self.supplier_id: str = data.get("supplier_id", "")
        self.part_number: str = data.get("part_number", "")
        self.delayed_qty: Optional[int] = data.get("delayed_qty")
        self.original_date: Optional[str] = data.get("original_date")
        self.partial_qty: Optional[int] = data.get("partial_qty")
        self.partial_date: Optional[str] = data.get("partial_date")
        self.revised_date: Optional[str] = data.get("revised_date")
        self.recovery_date_confirmed: bool = data.get("recovery_date_confirmed", False)
        self.missing_information: list[str] = data.get("missing_information", [])
        self.citations: list[str] = data.get("citations", [])
        self.source: str = data.get("_source", "deterministic")
        self.agent_version: str = AGENT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "disruption_id": self.disruption_id,
            "supplier_id": self.supplier_id,
            "part_number": self.part_number,
            "delayed_qty": self.delayed_qty,
            "original_date": self.original_date,
            "partial_qty": self.partial_qty,
            "partial_date": self.partial_date,
            "revised_date": self.revised_date,
            "recovery_date_confirmed": self.recovery_date_confirmed,
            "missing_information": self.missing_information,
            "citations": self.citations,
            "source": self.source,
            "agent_version": self.agent_version,
        }


def _deterministic_extraction(disruption: Disruption) -> SignalExtraction:
    """Extract facts directly from the structured disruption model."""
    missing: list[str] = []
    if not disruption.recovery_date_confirmed:
        remaining = max(disruption.delayed_qty - (disruption.partial_qty or 0), 0)
        missing.append(
            f"Recovery date for the remaining {remaining} units is unconfirmed."
        )
    citations: list[str] = []
    if disruption.signal_reference:
        citations.append(f"{disruption.signal_source}:{disruption.signal_reference}")
    return SignalExtraction(
        {
            "disruption_id": disruption.disruption_id,
            "supplier_id": disruption.supplier_id,
            "part_number": disruption.part_id,
            "delayed_qty": disruption.delayed_qty,
            "original_date": disruption.original_date.isoformat(),
            "partial_qty": disruption.partial_qty or None,
            "partial_date": (
                disruption.partial_date.isoformat() if disruption.partial_date else None
            ),
            "revised_date": (
                disruption.revised_date.isoformat() if disruption.revised_date else None
            ),
            "recovery_date_confirmed": disruption.recovery_date_confirmed,
            "missing_information": missing,
            "citations": citations,
            "_source": "deterministic",
        }
    )


def _llm_extraction(disruption: Disruption, email_body: str) -> SignalExtraction:
    """Call Azure OpenAI to extract facts from a supplier email."""
    import openai  # deferred; only needed when LLM is configured

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_OPENAI_SIGNAL_DEPLOYMENT", "gpt-4o")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    client = openai.AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key if api_key else openai.NOT_GIVEN,
        api_version=api_version,
    )

    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    user_message = (
        f"Disruption reference: {disruption.disruption_id}\n"
        f"Supplier: {disruption.supplier_id}\n\n"
        f"Email body:\n{email_body}"
    )

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    data["_source"] = "azure_openai"
    return SignalExtraction(data)


def extract(
    disruption: Disruption,
    email_body: Optional[str] = None,
) -> SignalExtraction:
    """Extract confirmed facts from a disruption signal.

    Uses Azure OpenAI when ``AZURE_OPENAI_ENDPOINT`` is set and ``email_body``
    is provided.  Falls back to deterministic extraction in all other cases.
    """
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    if endpoint and email_body:
        try:
            return _llm_extraction(disruption, email_body)
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "Signal LLM call failed, falling back to deterministic: %s", exc
            )
    return _deterministic_extraction(disruption)


__all__ = ["AGENT_VERSION", "SignalExtraction", "extract"]
