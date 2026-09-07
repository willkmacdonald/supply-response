from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from threading import Lock
from typing import Final

_APPROVED_FIELDS: Final = (
    "result",
    "task",
    "artifacts",
    "parts",
    "data",
    "facts",
    "citation",
    "citations",
    "citationMap",
    "references",
    "reference",
    "sources",
    "source",
    "sourceId",
    "sourceType",
    "excerpt",
    "targetLink",
    "webUrl",
    "content",
    "text",
    "claim",
    "factId",
    "artifactId",
    "sourceTimestamp",
    "effectiveAt",
    "expiresAt",
    "authorityScope",
    "isCitedInResponse",
    "id",
    "contextId",
    "status",
    "state",
    "message",
    "name",
    "description",
    "metadata",
    "mediaType",
    "url",
    "raw",
    "filename",
    "type",
    "value",
    "index",
    "title",
)
_APPROVED_FIELD_SET: Final = frozenset(_APPROVED_FIELDS)
_SOURCE_KINDS: Final = frozenset({"supplier", "quality", "other"})
_MAX_DEPTH: Final = 12
_MAX_NODES: Final = 128
_MAX_EXAMPLES: Final = 2
_MAX_SERIALIZED_CHARS: Final = 8_192
_TRUNCATED: Final = {"type": "truncated"}

_logger = logging.getLogger(__name__)
_emitted_source_kinds: set[str] = set()
_emitted_source_kinds_lock = Lock()


def _shape(value: object, *, depth: int, remaining_nodes: list[int]) -> object:
    if depth >= _MAX_DEPTH or remaining_nodes[0] <= 0:
        return _TRUNCATED
    remaining_nodes[0] -= 1

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        approved_children: dict[str, object] = {}
        fields: dict[str, object] = {}
        unknown_children: list[object] = []
        unknown_count = 0
        for key, child in value.items():
            if isinstance(key, str) and key in _APPROVED_FIELD_SET:
                approved_children[key] = child
            else:
                unknown_count += 1
                if len(unknown_children) < _MAX_EXAMPLES:
                    unknown_children.append(child)
        for key in _APPROVED_FIELDS:
            if key in approved_children:
                fields[key] = _shape(
                    approved_children[key],
                    depth=depth + 1,
                    remaining_nodes=remaining_nodes,
                )
        unknown = [
            _shape(
                child,
                depth=depth + 1,
                remaining_nodes=remaining_nodes,
            )
            for child in unknown_children
        ]
        result: dict[str, object] = {"type": "object", "count": len(value)}
        if fields:
            result["fields"] = fields
        if unknown:
            result["unknown"] = unknown
        if unknown_count > len(unknown):
            result["truncated"] = True
        return result
    if isinstance(value, list):
        items = [
            _shape(child, depth=depth + 1, remaining_nodes=remaining_nodes)
            for child in value[:_MAX_EXAMPLES]
        ]
        result = {"type": "array", "count": len(value), "items": items}
        if len(value) > len(items):
            result["truncated"] = True
        return result
    return "other"


def response_shape(payload: object) -> str:
    shape = _shape(payload, depth=0, remaining_nodes=[_MAX_NODES])
    serialized = json.dumps(shape, separators=(",", ":"))
    if len(serialized) > _MAX_SERIALIZED_CHARS:
        return '{"type":"truncated"}'
    return serialized


def log_response_shape(payload: object, source_kind: str) -> None:
    sanitized_source_kind = source_kind if source_kind in _SOURCE_KINDS else "other"
    with _emitted_source_kinds_lock:
        if sanitized_source_kind in _emitted_source_kinds:
            return
        _emitted_source_kinds.add(sanitized_source_kind)
    shape = response_shape(payload)
    _logger.warning(
        "workiq_response_shape source=%s shape=%s",
        sanitized_source_kind,
        shape,
    )
