from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth import AuthService, PersonaBinding
from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from integrations.workiq.mcp_probe import (
    EXPECTED_ENTITY_URL,
    EXPECTED_SOURCE_LINK,
    ProbeUnavailable,
    WorkIQMcpProbe,
    _bounded,
    _extract_entity,
    _parse_response,
)
from integrations.workiq.obo import WorkIQAccessToken
from integrations.workiq.probe_binding import ALEX_OBJECT_ID, TENANT_ID
from tests.auth.test_token_authorization import API_CLIENT_ID, PRIVATE_KEY, _jwk


def test_probe_post_route_is_wired(tmp_path) -> None:
    app = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'probe.db'}",
        )
    )
    with TestClient(app) as client:
        document = client.get("/openapi.json").json()
    assert "/api/diagnostics/workiq-fetch" in document["paths"]


def test_probe_binding_is_disabled_or_has_a_fixed_bounded_utc_window() -> None:
    from integrations.workiq.probe_binding import PROBE_END_UTC, PROBE_START_UTC

    if PROBE_START_UTC is None:
        assert PROBE_END_UTC is None
    else:
        assert PROBE_END_UTC is not None
        assert PROBE_START_UTC.tzinfo is UTC
        assert PROBE_END_UTC.tzinfo is UTC
        assert 0 < (PROBE_END_UTC - PROBE_START_UTC).total_seconds() <= 1800


def test_probe_rejects_caller_supplied_query_and_body(tmp_path) -> None:
    app = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'request.db'}",
        )
    )
    with TestClient(app) as client:
        assert (
            client.post("/api/diagnostics/workiq-fetch?entityUrl=wrong").status_code
            == 400
        )
        assert (
            client.post(
                "/api/diagnostics/workiq-fetch", json={"tool": "ask"}
            ).status_code
            == 400
        )


class FixedIdentityHttp:
    def __call__(self, url: str) -> dict[str, Any]:
        issuer = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
        keys = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
        if url.endswith("openid-configuration"):
            return {"issuer": issuer, "jwks_uri": keys}
        if url == keys:
            return {"keys": [_jwk()]}
        raise AssertionError("unexpected identity URL")


def authenticated_alex():
    now = datetime(2026, 9, 7, 18, tzinfo=UTC)
    service = AuthService(
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        bindings=(PersonaBinding.alex(TENANT_ID, ALEX_OBJECT_ID),),
        http_get=FixedIdentityHttp(),
        now=lambda: now.timestamp(),
    )
    token = jwt.encode(
        {
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "aud": API_CLIENT_ID,
            "iat": int(now.timestamp()) - 5,
            "nbf": int(now.timestamp()) - 5,
            "exp": int(now.timestamp()) + 300,
            "tid": TENANT_ID,
            "oid": ALEX_OBJECT_ID,
            "roles": ["material_planner", "response_approver"],
            "scp": "access_as_user",
        },
        PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "fixture-key", "typ": "JWT"},
    )
    return service, service.authenticate(token)


class FakeObo:
    def exchange(self, actor):
        del actor
        return WorkIQAccessToken("downstream-secret")


@pytest.mark.anyio
async def test_probe_uses_only_fixed_mcp_sequence_and_returns_safe_checks() -> None:
    service, actor = authenticated_alex()
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        if payload.get("method") == "initialize":
            return httpx.Response(
                200,
                request=request,
                headers={
                    "content-type": "application/json",
                    "mcp-session-id": "fixed-session",
                    "mcp-protocol-version": "2025-03-26",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "serverInfo": {"name": "fixture", "version": "1"},
                    },
                },
            )
        if payload.get("method") == "notifications/initialized":
            return httpx.Response(202, request=request)
        entity = {
            "id": "1788577543694",
            "from": {"user": {"id": "fed4348d-b983-4757-ab9f-0146ed52bfcd"}},
            "channelIdentity": {
                "channelId": "19:2ROXbDFk-xAzLDwt8NJAsRozD1zhz1XtG5QXqzGppsw1@thread.tacv2",
                "teamId": "6cbd1c71-8a78-49eb-9d47-aef266fb55da",
            },
            "body": {"content": "present"},
            "createdDateTime": "2026-09-01T12:00:00Z",
            "webUrl": EXPECTED_SOURCE_LINK,
        }
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "structuredContent": {
                        "results": [{"data": entity, "statusCode": 200}]
                    }
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        result = await WorkIQMcpProbe(http=http, obo=FakeObo()).run(actor, service)  # type: ignore[arg-type]
    assert result.stage == "complete"
    assert all(
        value is True
        for key, value in result.safe_dict().items()
        if key not in {"stage", "http_status"}
    )
    assert [json.loads(r.content).get("method") for r in requests] == [
        "initialize",
        "notifications/initialized",
        "tools/call",
    ]
    assert json.loads(requests[2].content)["params"] == {
        "name": "fetch",
        "arguments": {"entityUrls": [EXPECTED_ENTITY_URL]},
    }
    assert "present" not in json.dumps(result.safe_dict())


@pytest.mark.anyio
async def test_failed_attempt_consumes_latch_and_redacts_exception() -> None:
    service, actor = authenticated_alex()

    class BrokenObo:
        def exchange(self, actor):
            del actor
            raise RuntimeError("sensitive assertion")

    probe = WorkIQMcpProbe(http=httpx.AsyncClient(), obo=BrokenObo())  # type: ignore[arg-type]
    first = await probe.run(actor, service)
    assert first.stage == "obo_failed"
    assert "sensitive" not in json.dumps(first.safe_dict())
    with pytest.raises(ProbeUnavailable):
        await probe.run(actor, service)
    assert probe._http is None


def test_release_retains_only_spent_latch_not_clients() -> None:
    probe = WorkIQMcpProbe(http=object(), obo=FakeObo())  # type: ignore[arg-type]
    probe._claim()
    probe.release_sensitive_clients()
    assert probe._attempted is True
    assert probe._http is None
    assert probe._obo is None
    with pytest.raises(ProbeUnavailable):
        probe._claim()


def test_concurrent_claim_allows_exactly_one_attempt() -> None:
    probe = WorkIQMcpProbe(http=object(), obo=FakeObo())  # type: ignore[arg-type]

    def claim() -> bool:
        try:
            probe._claim()
            return True
        except ProbeUnavailable:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: claim(), range(16)))
    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 15


def test_protocol_parser_accepts_sse_notifications_before_matching_response() -> None:
    body = b'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\ndata: {"jsonrpc":"2.0","id":2,"result":{}}\n\n'
    assert _parse_response("text/event-stream", body, 2)["id"] == 2


def test_protocol_parser_rejects_ambiguous_and_deep_responses() -> None:
    duplicate = b'data: {"jsonrpc":"2.0","id":2,"result":{}}\n\ndata: {"jsonrpc":"2.0","id":2,"result":{}}\n\n'
    with pytest.raises(ValueError):
        _parse_response("text/event-stream", duplicate, 2)
    value: dict[str, Any] = {}
    cursor = value
    for _ in range(22):
        child: dict[str, Any] = {}
        cursor["child"] = child
        cursor = child
    with pytest.raises(ValueError):
        _bounded(value)
    with pytest.raises(ValueError):
        _bounded("x" * (1024 * 1024 + 1))


def test_fetch_requires_one_successful_nested_result() -> None:
    assert _extract_entity(
        {
            "structuredContent": {
                "results": [{"statusCode": 403, "data": {"id": "wrong"}}]
            }
        }
    ) == ({"id": "wrong"}, 403)
    assert _extract_entity({"structuredContent": {"results": []}}) == (None, None)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failed_method", "stage"),
    [("initialize", "initialize_failed"), ("tools/call", "fetch_failed")],
)
async def test_http_failure_status_is_preserved_without_retry(
    failed_method: str, stage: str
) -> None:
    service, actor = authenticated_alex()
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content).get("method")
        calls.append(method)
        if method == failed_method:
            return httpx.Response(
                403, request=request, json={"secret": "must-not-leak"}
            )
        if method == "initialize":
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "serverInfo": {"name": "fixture", "version": "1"},
                    },
                },
            )
        return httpx.Response(202, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        result = await WorkIQMcpProbe(http=http, obo=FakeObo()).run(actor, service)  # type: ignore[arg-type]
    assert result.stage == stage
    assert result.http_status == 403
    assert calls.count(failed_method) == 1
    assert "must-not-leak" not in json.dumps(result.safe_dict())
