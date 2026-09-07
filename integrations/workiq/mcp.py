"""Bounded, read-only Work IQ MCP sessions; no actor state on the shared client."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Final
from uuid import uuid4

import httpx
from opentelemetry.instrumentation.utils import suppress_instrumentation

from .errors import WorkIQProtocolError, WorkIQResponseLimitError

ENDPOINT: Final = "https://workiq.svc.cloud.microsoft/mcp"
PROTOCOL_VERSION: Final = "2025-03-26"
MAX_RESPONSE_BYTES: Final = 1024 * 1024
MAX_JSON_DEPTH: Final = 20


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WorkIQProtocolError("Work IQ JSON contains duplicate keys")
        result[key] = value
    return result


def _reject_constant(_: str) -> Any:
    raise WorkIQProtocolError("Work IQ JSON contains an invalid number")


def bounded_json(body: bytes | str) -> Any:
    """Check nesting before parsing, including JSON inside tool text wrappers."""
    try:
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        if len(text.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise WorkIQResponseLimitError("Work IQ response exceeds size limit")
        depth, quoted, escaped = 0, False, False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > MAX_JSON_DEPTH:
                    raise WorkIQResponseLimitError(
                        "Work IQ response exceeds depth limit"
                    )
            elif char in "]}":
                depth -= 1
        return json.loads(
            text, object_pairs_hook=_pairs, parse_constant=_reject_constant
        )
    except (ValueError, UnicodeError, RecursionError):
        raise WorkIQProtocolError("Work IQ response contains malformed JSON") from None


def _rpc_body(body: bytes, content_type: str) -> Any:
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "application/json":
        return bounded_json(body)
    if media_type != "text/event-stream":
        raise WorkIQProtocolError("Work IQ response has unsupported content type")
    try:
        text = body.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeError:
        raise WorkIQProtocolError("Work IQ event stream is malformed") from None
    messages = []
    for event in text.split("\n\n"):
        data = []
        for line in event.splitlines():
            if line.startswith("data:"):
                value = line[5:]
                data.append(value.removeprefix(" "))
            elif line and not line.startswith((":", "event:", "id:", "retry:")):
                raise WorkIQProtocolError("Work IQ event stream is malformed")
        if data:
            messages.append(bounded_json("\n".join(data)))
    if len(messages) != 1:
        raise WorkIQProtocolError("Work IQ event stream has ambiguous responses")
    return messages[0]


def _bounded_string(value: Any, maximum: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


class _BorrowedTransport(httpx.AsyncBaseTransport):
    """Share only the fixed endpoint's connection pool, never HTTP client state."""

    def __init__(self, owner: httpx.AsyncClient) -> None:
        # httpx exposes transport injection but no public accessor for an existing
        # client's pool. Keep this dependency in one place and test pool ownership.
        self._transport = owner._transport_for_url(httpx.URL(ENDPOINT))

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self._transport.handle_async_request(request)

    async def aclose(self) -> None:
        """The injected client retains ownership of the underlying transport."""


class WorkIQMcpClient:
    def __init__(self, *, http: httpx.AsyncClient) -> None:
        self._http = http

    @asynccontextmanager
    async def session(self, *, access_token: str) -> AsyncIterator[WorkIQMcpSession]:
        if self._http.is_closed:
            raise WorkIQProtocolError("Work IQ connection pool is closed")
        async with httpx.AsyncClient(
            transport=_BorrowedTransport(self._http),
            trust_env=False,
            follow_redirects=False,
        ) as http:
            session = WorkIQMcpSession(http=http, access_token=access_token)
            try:
                await session._initialize()
                yield session
            finally:
                session._headers.clear()
                http.cookies.clear()
                session._closed = True


class WorkIQMcpSession:
    def __init__(self, *, http: httpx.AsyncClient, access_token: str) -> None:
        if not _bounded_string(access_token, 32768) or any(
            ord(char) < 33 or ord(char) > 126 for char in access_token
        ):
            raise WorkIQProtocolError("Work IQ access token is malformed")
        self._http = http
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        self._request_ids: list[str] = []
        self._closed = False

    @property
    def request_ids(self) -> tuple[str, ...]:
        return tuple(self._request_ids)

    async def _initialize(self) -> None:
        result = await self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "supply-response", "version": "1.0"},
            },
        )
        capabilities, server = result.get("capabilities"), result.get("serverInfo")
        if (
            result.get("protocolVersion") != PROTOCOL_VERSION
            or not isinstance(capabilities, dict)
            or not isinstance(capabilities.get("tools"), dict)
            or not isinstance(server, dict)
            or not all(
                _bounded_string(server.get(key), 256) for key in ("name", "version")
            )
        ):
            raise WorkIQProtocolError("Work IQ initialization is invalid")
        self._headers["MCP-Protocol-Version"] = PROTOCOL_VERSION
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def _send(self, payload: dict[str, Any]) -> Any:
        if self._closed:
            raise WorkIQProtocolError("Work IQ session is closed")
        notification = "id" not in payload
        try:
            with suppress_instrumentation():
                async with asyncio.timeout(120):
                    async with self._http.stream(
                        "POST",
                        ENDPOINT,
                        json=payload,
                        headers=self._headers,
                        follow_redirects=False,
                        auth=None,
                        timeout=120,
                    ) as response:
                        if response.status_code != (202 if notification else 200):
                            raise WorkIQProtocolError(
                                f"Work IQ HTTP {response.status_code}"
                            )
                        session_id = response.headers.get("mcp-session-id")
                        protocol = response.headers.get("mcp-protocol-version")
                        if protocol is not None and protocol != PROTOCOL_VERSION:
                            raise WorkIQProtocolError(
                                "Work IQ protocol header is invalid"
                            )
                        if session_id is not None:
                            if not re.fullmatch(r"[!-~]{1,128}", session_id):
                                raise WorkIQProtocolError(
                                    "Work IQ session header is invalid"
                                )
                            previous = self._headers.get("Mcp-Session-Id")
                            if (
                                payload.get("method") != "initialize"
                                and session_id != previous
                            ):
                                raise WorkIQProtocolError(
                                    "Work IQ session header changed"
                                )
                            self._headers["Mcp-Session-Id"] = session_id
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise WorkIQResponseLimitError(
                                    "Work IQ response exceeds size limit"
                                )
                            body.extend(chunk)
                        if notification:
                            if body:
                                raise WorkIQProtocolError(
                                    "Work IQ notification response is not empty"
                                )
                            return None
                        return _rpc_body(
                            bytes(body), response.headers.get("content-type", "")
                        )
        except (httpx.HTTPError, TimeoutError):
            raise WorkIQProtocolError("Work IQ request unavailable") from None

    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = str(uuid4())
        self._request_ids.append(request_id)
        envelope = await self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        if (
            not isinstance(envelope, dict)
            or envelope.get("jsonrpc") != "2.0"
            or envelope.get("id") != request_id
            or "error" in envelope
            or not isinstance(envelope.get("result"), dict)
        ):
            raise WorkIQProtocolError("Work IQ RPC response is invalid")
        return envelope["result"]

    async def _tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError", False) is not False:
            raise WorkIQProtocolError("Work IQ tool failed")
        value = result.get("structuredContent")
        if value is None:
            content = result.get("content")
            if (
                not isinstance(content, list)
                or len(content) != 1
                or not isinstance(content[0], dict)
                or content[0].get("type") != "text"
                or not isinstance(content[0].get("text"), str)
            ):
                raise WorkIQProtocolError("Work IQ tool response is invalid")
            value = bounded_json(content[0]["text"])
        if not isinstance(value, dict):
            raise WorkIQProtocolError("Work IQ tool response is invalid")
        return value

    async def ask(self, question: str) -> dict[str, Any]:
        if not _bounded_string(question, 16000):
            raise WorkIQProtocolError("Work IQ question is invalid")
        result = await self._tool("ask", {"question": question})
        if not _bounded_string(
            result.get("response"), MAX_RESPONSE_BYTES
        ) or not _bounded_string(result.get("conversationId"), 256):
            raise WorkIQProtocolError("Work IQ discovery response is invalid")
        return result

    async def fetch(self, entity_url: str) -> dict[str, Any]:
        if not _bounded_string(entity_url, 8192):
            raise WorkIQProtocolError("Work IQ entity location is invalid")
        result = await self._tool("fetch", {"entityUrls": [entity_url]})
        rows = result.get("results")
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], dict)
            or type(rows[0].get("statusCode")) is not int
            or rows[0]["statusCode"] != 200
            or not isinstance(rows[0].get("data"), dict)
        ):
            raise WorkIQProtocolError("Work IQ entity retrieval failed")
        return result
