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
_PROJECT_ENDPOINT = re.compile(
    r"^https://"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"\.services\.ai\.azure\.com/api/projects/"
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"
)


def _trusted_project_endpoint(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return bool(
        _PROJECT_ENDPOINT.fullmatch(value)
        and parsed.scheme == "https"
        and parsed.hostname
        and parsed.hostname == parsed.hostname.lower()
        and parsed.username is None
        and parsed.password is None
        and port is None
        and not parsed.query
        and not parsed.fragment
    )


@dataclass(frozen=True, slots=True)
class FoundryAgentBinding:
    project_endpoint: str
    agent_name: str
    agent_version: str

    def __post_init__(self) -> None:
        if (
            not _trusted_project_endpoint(self.project_endpoint)
            or not _NAME.fullmatch(self.agent_name)
            or not _VERSION.fullmatch(self.agent_version)
        ):
            raise ValueError(
                "Foundry agent binding is not an exact trusted configuration"
            )


def validate_project_endpoint(value: str) -> str:
    if not _trusted_project_endpoint(value):
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
        messages = getattr(response, "messages", None)
        if not isinstance(messages, list) or not messages:
            raise RuntimeError("Foundry response must contain plain text only")
        text_parts: list[str] = []
        for message in messages:
            if getattr(message, "role", None) != "assistant":
                raise RuntimeError("Foundry response must contain plain text only")
            contents = getattr(message, "contents", None)
            if not isinstance(contents, list) or not contents:
                raise RuntimeError("Foundry response must contain plain text only")
            for content in contents:
                if getattr(content, "type", None) != "text":
                    raise RuntimeError("Foundry response must contain plain text only")
                item = getattr(content, "text", None)
                if not isinstance(item, str):
                    raise TypeError("Foundry response must contain plain text only")
                text_parts.append(item)
        if getattr(response, "finish_reason", None) == "tool_calls":
            raise RuntimeError("Foundry response must contain plain text only")
        text = " ".join(text_parts)
        if not isinstance(text, str) or len(text.encode("utf-8")) > 16_000:
            raise RuntimeError(
                "Foundry response did not satisfy the bounded JSON contract"
            )
        try:
            value = json.loads(text)
        except (json.JSONDecodeError, UnicodeError):
            raise RuntimeError(
                "Foundry response did not satisfy the bounded JSON contract"
            ) from None
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
