from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from opentelemetry.context import _SUPPRESS_INSTRUMENTATION_KEY, get_value

from integrations.workiq.errors import WorkIQProtocolError


@pytest.fixture
def anyio_backend():
    return "asyncio"


def client(http):
    from integrations.workiq.mcp import WorkIQMcpClient

    return WorkIQMcpClient(http=http)


def reply(request, result=None, **envelope):
    body = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": body["id"],
            "result": result,
            **envelope,
        },
    )


INIT = {
    "protocolVersion": "2025-03-26",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "Work IQ", "version": "1.0"},
}
ANSWER = {
    "response": "fixture source location",
    "conversationId": "fixture-conversation",
}
FETCH = {"results": [{"data": {"id": "fixture-message"}, "statusCode": 200}]}


class Server:
    def __init__(self, *, mode="json", session_id=None):
        self.requests: list[httpx.Request] = []
        self.mode = mode
        self.session_id = session_id

    async def __call__(self, request):
        assert get_value(_SUPPRESS_INSTRUMENTATION_KEY) is True
        self.requests.append(request)
        body = json.loads(request.content)
        if body["method"] == "initialize":
            assert body["params"]["protocolVersion"] == "2025-03-26"
            response = reply(request, INIT)
            if self.session_id is not None:
                response.headers["Mcp-Session-Id"] = self.session_id
            return response
        if body["method"] == "notifications/initialized":
            assert "id" not in body
            return httpx.Response(202)
        assert body["method"] == "tools/call"
        name = body["params"]["name"]
        assert name in {"ask", "fetch"}
        result = ANSWER if name == "ask" else FETCH
        if self.mode == "structured":
            return reply(request, {"structuredContent": result})
        wrapped = {"content": [{"type": "text", "text": json.dumps(result)}]}
        response = reply(request, wrapped)
        if self.mode == "sse":
            payload = json.dumps(json.loads(response.content), indent=2)
            return httpx.Response(
                200,
                text=": heartbeat\r\nevent: message\r\n"
                + "\r\n".join("data: " + line for line in payload.splitlines())
                + "\r\n\r\n",
                headers={"content-type": "text/event-stream"},
            )
        return response


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["json", "structured", "sse"])
@pytest.mark.parametrize("session_id", [None, "fixture-session"])
async def test_initialize_ask_fetch_and_optional_session_headers(mode, session_id):
    server = Server(mode=mode, session_id=session_id)
    async with httpx.AsyncClient(transport=httpx.MockTransport(server)) as http:
        async with client(http).session(access_token="fixture-token") as session:
            assert (
                await session.ask("Find the fictional supplier disruption email")
                == ANSWER
            )
            assert await session.fetch("/me/messages/fixture-message") == FETCH
            ids = session.request_ids
        with pytest.raises(WorkIQProtocolError):
            await session.ask("closed")
        assert http.is_closed is False
    assert len(ids) == len(set(ids)) == 3
    assert [r.method for r in server.requests] == ["POST"] * 4
    assert all(
        str(r.url) == "https://workiq.svc.cloud.microsoft/mcp" for r in server.requests
    )
    for request in server.requests[1:]:
        assert request.headers.get("mcp-session-id") == session_id
        assert request.headers["mcp-protocol-version"] == "2025-03-26"
    assert json.loads(server.requests[2].content)["params"] == {
        "name": "ask",
        "arguments": {"question": "Find the fictional supplier disruption email"},
    }
    assert json.loads(server.requests[3].content)["params"] == {
        "name": "fetch",
        "arguments": {"entityUrls": ["/me/messages/fixture-message"]},
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "bad",
    [
        "tool_error",
        "rpc_error",
        "wrong_id",
        "redirect",
        "malformed",
        "oversize",
        "deep",
        "wrong_content_type",
        "missing_conversation",
        "empty_response",
        "bad_entity",
        "bool_status",
        "multiple_results",
        "bad_sse",
        "duplicate_json_keys",
    ],
)
async def test_untrusted_responses_fail_closed_without_body_or_token_leaks(bad, caplog):
    server = Server()

    async def handler(request):
        body = json.loads(request.content)
        if body["method"] != "tools/call":
            return await server(request)
        if bad == "tool_error":
            return reply(
                request,
                {
                    "isError": True,
                    "content": [{"type": "text", "text": "private-body"}],
                },
            )
        if bad == "rpc_error":
            return reply(request, None, error={"code": -1, "message": "private-body"})
        if bad == "wrong_id":
            return reply(request, {"structuredContent": ANSWER}, id="wrong")
        if bad == "redirect":
            return httpx.Response(
                307, headers={"location": "https://example.com/private-body"}
            )
        if bad == "malformed":
            return httpx.Response(
                200, text="private-body", headers={"content-type": "application/json"}
            )
        if bad == "oversize":
            return httpx.Response(
                200,
                content=b" " * (1024 * 1024 + 1),
                headers={"content-type": "application/json"},
            )
        if bad == "deep":
            return httpx.Response(
                200,
                content=b"[" * 1000 + b"0" + b"]" * 1000,
                headers={"content-type": "application/json"},
            )
        if bad == "wrong_content_type":
            return httpx.Response(
                200,
                content=reply(request, ANSWER).content,
                headers={"content-type": "text/html"},
            )
        if bad == "bad_sse":
            return httpx.Response(
                200,
                text="data: private-body\n\n",
                headers={"content-type": "text/event-stream"},
            )
        if bad == "duplicate_json_keys":
            return httpx.Response(
                200,
                content=b'{"id":1,"id":2}',
                headers={"content-type": "application/json"},
            )
        result: dict[str, Any] = {
            "missing_conversation": {"response": "private-body"},
            "empty_response": {**ANSWER, "response": ""},
            "bad_entity": {
                "results": [{"statusCode": 404, "data": {"body": "private-body"}}]
            },
            "bool_status": {"results": [{"statusCode": True, "data": {}}]},
            "multiple_results": {"results": FETCH["results"] * 2},
        }[bad]
        return reply(request, {"structuredContent": result})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as http:
        with pytest.raises(WorkIQProtocolError) as caught:
            async with client(http).session(access_token="private-token") as session:
                if bad in {"bad_entity", "bool_status", "multiple_results"}:
                    await session.fetch("/me/messages/fixture-message")
                else:
                    await session.ask("private-question")
    for secret in ("private-body", "private-token", "private-question"):
        assert secret not in caplog.text + str(caught.value)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutation",
    [
        {"protocolVersion": "wrong"},
        {"capabilities": {}},
        {"serverInfo": {}},
        {"serverInfo": {"name": "x" * 300, "version": "1"}},
    ],
)
async def test_initialization_contract_is_validated(mutation):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: reply(request, {**INIT, **mutation})
        )
    ) as http:
        with pytest.raises(WorkIQProtocolError):
            async with client(http).session(access_token="fixture-token"):
                pytest.fail("invalid initialization accepted")


@pytest.mark.anyio
@pytest.mark.parametrize("session_id", ["x" * 129, "invalid session"])
async def test_invalid_session_headers_are_rejected(session_id):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(Server(session_id=session_id))
    ) as http:
        with pytest.raises(WorkIQProtocolError):
            async with client(http).session(access_token="fixture-token"):
                pytest.fail("invalid session accepted")


@pytest.mark.anyio
async def test_two_concurrent_sessions_keep_tokens_and_headers_isolated():
    barrier = asyncio.Event()
    requests = []

    async def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        token = request.headers["authorization"].removeprefix("Bearer ")
        if body["method"] == "initialize":
            if len(requests) == 2:
                barrier.set()
            await barrier.wait()
            result = reply(request, INIT)
            result.headers["mcp-session-id"] = token
            return result
        assert request.headers["mcp-session-id"] == token
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return reply(
            request, {"structuredContent": {**ANSWER, "conversationId": token}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        shared = client(http)

        async def ask(token):
            async with shared.session(access_token=token) as session:
                return await session.ask("fixture question")

        results = await asyncio.gather(ask("actor-one"), ask("actor-two"))
        assert [r["conversationId"] for r in results] == ["actor-one", "actor-two"]
        assert "authorization" not in http.headers


@pytest.mark.anyio
async def test_cancelled_stream_is_closed_and_session_cannot_be_reused():
    entered = asyncio.Event()
    closed = asyncio.Event()
    sessions = []

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b""

        async def aclose(self):
            closed.set()

    server = Server()

    async def handler(request):
        if json.loads(request.content)["method"] == "tools/call":
            return httpx.Response(
                200, stream=Stream(), headers={"content-type": "application/json"}
            )
        return await server(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        shared = client(http)

        async def run():
            async with shared.session(access_token="fixture-token") as session:
                sessions.append(session)
                await session.ask("fixture")

        task = asyncio.create_task(run())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed.is_set()
        with pytest.raises(WorkIQProtocolError):
            await sessions[0].ask("closed")
