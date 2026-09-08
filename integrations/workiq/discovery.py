"""Topic-only discovery prompts and bounded extraction of untrusted locators."""

import re
from collections.abc import Iterator, Mapping
from typing import Any

from .errors import WorkIQProtocolError
from .locations import MessageLocation, parse_location
from .mcp import bounded_json
from .models import DiscoveryTopic, SourceKind


def question_for(topic: DiscoveryTopic) -> str:
    if topic.case_reference != "RL-001":
        raise ValueError("Unsupported discovery topic")
    if topic.source_kind == "supplier":
        return (
            "Find the fictional RL-001 Alpha supplier disruption email in the user's mailbox. "
            "Return complete individual message locations or source links for retrieval."
        )
    if topic.source_kind == "quality":
        return (
            "Find Jordan's fictional RL-001 Beta qualification post in the "
            "Supply Response Demo team, General channel. "
            "Return complete individual channel-message locations for retrieval: "
            "a Teams message link containing groupId and tenantId, or a JSON array "
            "of complete /teams/{teamId}/channels/{channelId}/messages/{messageId} "
            "resource paths from the discovered sources. "
            "Do not return personal or group chat links, channel-only links, or "
            "search pages. Do not invent missing identifiers."
        )
    raise ValueError("Unsupported discovery topic")


def _strings(value: Any, depth: int = 0) -> Iterator[str]:
    if depth > 20:
        return
    if isinstance(value, str):
        yield value
        if value.lstrip().startswith(("{", "[")):
            try:
                decoded = bounded_json(value)
            except WorkIQProtocolError:
                return
            yield from _strings(decoded, depth + 1)
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _strings(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, depth + 1)


def discover_locations(
    payload: Mapping[str, Any], *, source_kind: SourceKind
) -> tuple[MessageLocation, ...]:
    found: dict[str, MessageLocation] = {}
    # Complete JSON string values may hold resource paths. In prose, only explicit
    # HTTPS links qualify; instructions mentioning a path do not become fetches.
    for text in _strings(
        {key: value for key, value in payload.items() if key != "conversationId"}
    ):
        candidates = [text, *re.findall(r"https://[^\s<>\"'\[\]()]+", text)]
        for candidate in candidates:
            location = parse_location(candidate)
            if location is not None and location.source_kind == source_kind:
                found.setdefault(location.fetch_path, location)
                if len(found) == 5:
                    return tuple(found.values())
    return tuple(found.values())
