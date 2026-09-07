"""Single-use, content-redacting Work IQ MCP probe."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from threading import Lock
from typing import Any, Final
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

import httpx

from apps.api.app.auth import AuthenticatedActor, AuthService
from integrations.workiq.obo import WorkIQOboExchange

from .probe_binding import (
    ALEX_OBJECT_ID,
    CHANNEL_ID,
    JORDAN_OBJECT_ID,
    MESSAGE_ID,
    TEAM_ID,
    TENANT_ID,
)

ENDPOINT: Final = "https://workiq.svc.cloud.microsoft/mcp"
MAX_RESPONSE_BYTES: Final = 1024 * 1024
MAX_JSON_DEPTH: Final = 20
TOTAL_TIMEOUT_SECONDS: Final = 60
EXPECTED_ENTITY_URL: Final = (
    f"/teams/{TEAM_ID}/channels/{quote(CHANNEL_ID, safe='')}/messages/{MESSAGE_ID}"
)
EXPECTED_SOURCE_LINK: Final = (
    f"https://teams.microsoft.com/l/message/{quote(CHANNEL_ID, safe='')}/{MESSAGE_ID}?"
    + urlencode(
        {"tenantId": TENANT_ID, "groupId": TEAM_ID, "parentMessageId": MESSAGE_ID}
    )
)


@dataclass(frozen=True)
class ProbeResult:
    stage: str
    http_status: int | None = None
    authenticated_alex: bool = False
    obo_succeeded: bool = False
    mcp_initialized: bool = False
    fetch_succeeded: bool = False
    exact_message_identity: bool = False
    expected_author: bool = False
    valid_source_timestamp: bool = False
    nonempty_body: bool = False
    expected_channel_identity: bool = False
    expected_source_link: bool = False

    def safe_dict(self) -> dict[str, str | int | bool | None]:
        return asdict(self)


class ProbeUnavailable(RuntimeError):
    pass


class _ProbeHttpError(RuntimeError):
    def __init__(self, status: int) -> None:
        self.status = status


class WorkIQMcpProbe:
    def __init__(self, *, http: httpx.AsyncClient, obo: WorkIQOboExchange) -> None:
        self._http = http
        self._obo = obo
        self._lock = Lock()
        self._attempted = False

    def release_sensitive_clients(self) -> None:
        """Retain only the spent latch after the request completes."""
        self._http = None  # type: ignore[assignment]
        self._obo = None  # type: ignore[assignment]

    def _claim(self) -> None:
        with self._lock:
            if self._attempted:
                raise ProbeUnavailable("probe attempt is unavailable")
            self._attempted = True

    async def run(
        self, actor: AuthenticatedActor, auth_service: AuthService
    ) -> ProbeResult:
        authenticated = (
            actor.tenant_id == TENANT_ID
            and actor.object_id == ALEX_OBJECT_ID
            and actor.persona_id == "RL-PERSONA-ALEX"
            and actor.source_id == "RL-ENTRA-ALEX"
            and actor.effective_roles == ("material_planner", "response_approver")
        )
        if not authenticated:
            raise ProbeUnavailable("probe actor is unavailable")
        try:
            auth_service._validated_user_assertion(actor)
        except Exception as error:
            raise ProbeUnavailable("probe actor is unavailable") from error
        self._claim()
        try:
            async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
                return await self._run_claimed(actor)
        except TimeoutError:
            return ProbeResult(stage="timed_out", authenticated_alex=True)
        finally:
            http = self._http
            self.release_sensitive_clients()
            if http is not None:
                cleanup = asyncio.create_task(http.aclose())
                await _finish_even_if_cancelled(cleanup)

    async def _run_claimed(self, actor: AuthenticatedActor) -> ProbeResult:
        base = ProbeResult(stage="authenticated", authenticated_alex=True)
        try:
            obo = self._obo
            assert obo is not None
            worker = asyncio.create_task(asyncio.to_thread(obo.exchange, actor))
            token = await _finish_even_if_cancelled(worker)
        except Exception:  # noqa: BLE001 - boundary deliberately redacts every provider error
            return ProbeResult(**{**base.safe_dict(), "stage": "obo_failed"})
        base = ProbeResult(
            stage="obo_succeeded", authenticated_alex=True, obo_succeeded=True
        )
        headers = {
            "Authorization": f"Bearer {token.reveal()}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        phase = "initialize"
        try:
            initialized, init_status, session, protocol = await self._rpc(
                headers,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "supply-response-diagnostic",
                            "version": "1.0",
                        },
                    },
                },
                expected_id=1,
            )
            server = initialized.get("serverInfo")
            if (
                protocol != "2025-03-26"
                or initialized.get("protocolVersion") != protocol
                or not isinstance(initialized.get("capabilities"), dict)
                or not isinstance(server, dict)
                or not all(
                    isinstance(server.get(key), str) and server[key]
                    for key in ("name", "version")
                )
                or (session is not None and not _valid_session(session))
            ):
                return ProbeResult(
                    **{
                        **base.safe_dict(),
                        "stage": "initialize_failed",
                        "http_status": init_status,
                    }
                )
            base = ProbeResult(
                stage="mcp_initialized",
                http_status=init_status,
                authenticated_alex=True,
                obo_succeeded=True,
                mcp_initialized=True,
            )
            phase = "fetch"
            rpc_headers = {**headers, "MCP-Protocol-Version": protocol}
            if session:
                rpc_headers["Mcp-Session-Id"] = session
            await self._notify(rpc_headers)
            fetched, _, _, _ = await self._rpc(
                rpc_headers,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "fetch",
                        "arguments": {"entityUrls": [EXPECTED_ENTITY_URL]},
                    },
                },
                expected_id=2,
            )
            entity, nested_status = _extract_entity(fetched)
            checks = _validate_entity(entity)
            if nested_status != 200:
                return ProbeResult(
                    **{
                        **base.safe_dict(),
                        "stage": "fetch_failed",
                        "http_status": nested_status,
                    }
                )
            return ProbeResult(
                stage="complete",
                http_status=nested_status,
                authenticated_alex=True,
                obo_succeeded=True,
                mcp_initialized=bool(initialized),
                fetch_succeeded=nested_status == 200 and entity is not None,
                **checks,
            )
        except _ProbeHttpError as error:
            return ProbeResult(
                **{
                    **base.safe_dict(),
                    "stage": f"{phase}_failed",
                    "http_status": error.status,
                }
            )
        except Exception:  # noqa: BLE001 - boundary deliberately redacts every transport/parser error
            return ProbeResult(**{**base.safe_dict(), "stage": "mcp_failed"})

    async def _notify(self, headers: dict[str, str]) -> None:
        http = self._http
        assert http is not None
        request = http.build_request(
            "POST",
            ENDPOINT,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        response = await http.send(request, stream=True)
        size = 0
        try:
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise ValueError("MCP notification failed")
        finally:
            await response.aclose()
        if response.status_code != 202 or size != 0:
            raise ValueError("MCP notification failed")

    async def _rpc(
        self, headers: dict[str, str], payload: dict[str, Any], *, expected_id: int
    ) -> tuple[dict[str, Any], int, str | None, str | None]:
        http = self._http
        assert http is not None
        request = http.build_request("POST", ENDPOINT, headers=headers, json=payload)
        response = await http.send(request, stream=True)
        body = bytearray()
        try:
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("MCP transport failed")
        finally:
            await response.aclose()
        if response.status_code != 200:
            raise _ProbeHttpError(response.status_code)
        envelope = _parse_response(
            response.headers.get("content-type", ""), bytes(body), expected_id
        )
        if envelope.get("jsonrpc") != "2.0" or envelope.get("id") != expected_id:
            raise ValueError("MCP envelope failed")
        result = envelope.get("result")
        if not isinstance(result, dict) or "error" in envelope:
            raise ValueError("MCP result failed")
        _bounded(result)
        return (
            result,
            response.status_code,
            response.headers.get("mcp-session-id"),
            response.headers.get("mcp-protocol-version")
            or result.get("protocolVersion"),
        )


def _parse_response(
    content_type_header: str, body: bytes, expected_id: int
) -> dict[str, Any]:
    content_type = content_type_header.split(";", 1)[0]
    if content_type == "text/event-stream":
        text = body.decode("utf-8")
        values = []
        data = []
        for line in text.splitlines():
            if not line:
                if data:
                    values.append("\n".join(data))
                    data = []
            elif line.startswith("data:"):
                field = line[5:]
                data.append(field.removeprefix(" "))
        decoded = [json.loads(item) for item in values]
        matches = [
            item
            for item in decoded
            if isinstance(item, dict) and item.get("id") == expected_id
        ]
        if len(matches) != 1:
            raise ValueError("MCP event stream failed")
        value = matches[0]
    elif content_type in {"application/json", ""}:
        value = json.loads(body)
    else:
        raise ValueError("MCP content type failed")
    if not isinstance(value, dict):
        raise TypeError("MCP response failed")
    return value


def _valid_session(value: str) -> bool:
    return bool(value) and all(0x21 <= ord(character) <= 0x7E for character in value)


def _bounded(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError("MCP response failed")
    if isinstance(value, dict):
        if len(value) > 1000:
            raise ValueError("MCP response failed")
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("MCP response failed")
            _bounded(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 1000:
            raise ValueError("MCP response failed")
        for item in value:
            _bounded(item, depth + 1)
    elif isinstance(value, str) and len(value.encode()) > MAX_RESPONSE_BYTES:
        raise ValueError("MCP response failed")


def _extract_entity(result: dict[str, Any]) -> tuple[dict[str, Any] | None, int | None]:
    if result.get("isError") is True:
        return None, None
    candidates: list[Any] = [result.get("structuredContent")]
    content = result.get("content")
    if isinstance(content, list):
        for part in content:
            if (
                isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            ):
                try:
                    candidates.append(json.loads(part["text"]))
                except json.JSONDecodeError:
                    continue
    for candidate in candidates:
        if isinstance(candidate, dict):
            _bounded(candidate)
            results = candidate.get("results")
            if (
                isinstance(results, list)
                and len(results) == 1
                and isinstance(results[0], dict)
            ):
                item = results[0]
                status = item.get("statusCode")
                data = item.get("data")
                if isinstance(status, int) and isinstance(data, dict):
                    return data, status
    return None, None


def _validate_entity(entity: dict[str, Any] | None) -> dict[str, bool]:
    if entity is None:
        return {
            key: False
            for key in (
                "exact_message_identity",
                "expected_author",
                "valid_source_timestamp",
                "nonempty_body",
                "expected_channel_identity",
                "expected_source_link",
            )
        }
    sender = entity.get("from")
    user = sender.get("user") if isinstance(sender, dict) else None
    author_id = user.get("id") if isinstance(user, dict) else None
    body = entity.get("body")
    if isinstance(body, dict):
        body = body.get("content")
    timestamp = entity.get("sourceTimestamp") or entity.get("createdDateTime")
    valid_timestamp = False
    if isinstance(timestamp, str):
        try:
            valid_timestamp = datetime.fromisoformat(timestamp).tzinfo is not None
        except ValueError:
            pass
    source_url = entity.get("sourceUrl") or entity.get("webUrl")
    channel_identity = entity.get("channelIdentity")
    parsed = urlparse(source_url) if isinstance(source_url, str) else None
    query = parse_qs(parsed.query) if parsed else {}
    return {
        "exact_message_identity": str(entity.get("id")) == MESSAGE_ID,
        "expected_author": author_id == JORDAN_OBJECT_ID,
        "valid_source_timestamp": valid_timestamp,
        "nonempty_body": isinstance(body, str) and bool(body.strip()),
        "expected_channel_identity": isinstance(channel_identity, dict)
        and channel_identity.get("channelId") == CHANNEL_ID
        and channel_identity.get("teamId") == TEAM_ID,
        "expected_source_link": bool(
            parsed
            and parsed.scheme == "https"
            and parsed.hostname == "teams.microsoft.com"
            and parsed.netloc in {"teams.microsoft.com", "teams.microsoft.com:443"}
            and not parsed.fragment
            and not parsed.params
            and [unquote(segment) for segment in parsed.path.split("/")]
            == ["", "l", "message", CHANNEL_ID, MESSAGE_ID]
            and query.get("tenantId") == [TENANT_ID]
            and query.get("groupId") == [TEAM_ID]
            and query.get("parentMessageId") == [MESSAGE_ID]
        ),
    }


async def _finish_even_if_cancelled(task: asyncio.Task[Any]) -> Any:
    """Keep cleanup/worker ownership until completion, then propagate cancellation."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:  # noqa: BLE001 - retrieve the worker exception below
            break
    if cancelled:
        if not task.cancelled():
            task.exception()  # retrieve any worker error without retaining its traceback
        raise asyncio.CancelledError
    return task.result()
