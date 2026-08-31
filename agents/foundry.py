from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from agent_framework_foundry import FoundryAgent

from agents.orchestrator.local import LocalAgentSet

_NAME = re.compile(r"^[a-z][a-z0-9-]{2,62}$")
_VERSION = re.compile(r"^[1-9][0-9]{0,9}$")


@dataclass(frozen=True, slots=True)
class FoundryAgentBinding:
    project_endpoint: str
    agent_name: str
    agent_version: str

    def __post_init__(self) -> None:
        parsed = urlsplit(self.project_endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".services.ai.azure.com")
            or parsed.query
            or parsed.fragment
            or not _NAME.fullmatch(self.agent_name)
            or not _VERSION.fullmatch(self.agent_version)
        ):
            raise ValueError(
                "Foundry agent binding is not an exact trusted configuration"
            )


def validate_project_endpoint(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".services.ai.azure.com")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Foundry project endpoint is outside the trusted policy")
    return value


def build_foundry_agent(
    binding: FoundryAgentBinding,
    *,
    credential: object,
    constructor: Callable[..., Any] = FoundryAgent,
) -> Any:
    """Construct an existing pinned prompt agent without resolving latest."""

    return constructor(
        project_endpoint=binding.project_endpoint,
        agent_name=binding.agent_name,
        agent_version=binding.agent_version,
        credential=credential,
        tools=[],
        timeout=30.0,
    )


class FoundryJsonAgent:
    """Keep SDK response parsing behind the orchestration's small JSON port."""

    def __init__(self, agent: Any) -> None:
        self._agent = agent

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._agent.run(json.dumps(payload, separators=(",", ":")))
        text = getattr(response, "text", None)
        if not isinstance(text, str) or len(text.encode("utf-8")) > 16_000:
            raise RuntimeError(
                "Foundry response did not satisfy the bounded JSON contract"
            )
        value = json.loads(text)
        if not isinstance(value, dict):
            raise TypeError("Foundry response must be a JSON object")
        return value


def build_foundry_agent_set(
    *,
    bindings: dict[str, FoundryAgentBinding],
    credential: object,
    constructor: Callable[..., Any] = FoundryAgent,
) -> LocalAgentSet:
    """Build exactly three pinned, tool-free server-managed prompt agents."""

    if set(bindings) != {"signal", "context", "decision"}:
        raise ValueError("exact signal, context, and decision bindings are required")
    endpoints = {item.project_endpoint for item in bindings.values()}
    if len(endpoints) != 1:
        raise ValueError("all prompt agents must use one trusted Foundry project")
    return LocalAgentSet(
        signal=FoundryJsonAgent(
            build_foundry_agent(
                bindings["signal"], credential=credential, constructor=constructor
            )
        ),
        context=FoundryJsonAgent(
            build_foundry_agent(
                bindings["context"], credential=credential, constructor=constructor
            )
        ),
        decision=FoundryJsonAgent(
            build_foundry_agent(
                bindings["decision"], credential=credential, constructor=constructor
            )
        ),
    )
