import asyncio
from threading import Event

import httpx
import pytest

from integrations.workiq.mcp_probe import (
    EXPECTED_SOURCE_LINK,
    ProbeUnavailable,
    WorkIQMcpProbe,
    _parse_response,
    _validate_entity,
)
from tests.integration.test_workiq_mcp_probe import FakeObo, authenticated_alex


@pytest.mark.parametrize(
    "url",
    [
        EXPECTED_SOURCE_LINK.replace("/l/message/", "/wrong/"),
        EXPECTED_SOURCE_LINK.replace("?", "suffix?"),
        EXPECTED_SOURCE_LINK.replace("teams.microsoft.com", "teams.microsoft.com:444"),
        EXPECTED_SOURCE_LINK.replace("parentMessageId=", "wrong="),
    ],
)
def test_link_requires_exact_identity(url):
    assert not _validate_entity({"webUrl": url})["expected_source_link"]


def test_sse_multiline_event():
    assert (
        _parse_response(
            "text/event-stream",
            b'data: {"jsonrpc":"2.0",\ndata: "id":2,"result":{}}\n\n',
            2,
        )["id"]
        == 2
    )


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["obo", "mcp"])
async def test_claim_owner_cleans_after_cancellation_and_worker_completion(phase):
    service, actor = authenticated_alex()
    started, finished = Event(), Event()

    class BlockingObo(FakeObo):
        def exchange(self, actor):
            if phase == "obo":
                started.set()
                assert finished.wait(3)
            return super().exchange(actor)

    async def handler(request):
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    probe = WorkIQMcpProbe(http=http, obo=BlockingObo())  # type: ignore[arg-type]
    task = asyncio.create_task(probe.run(actor, service))
    while not started.is_set():
        await asyncio.sleep(0.001)
    with pytest.raises(ProbeUnavailable):
        await probe.run(actor, service)
    assert not http.is_closed
    task.cancel()
    await asyncio.sleep(0.01)
    if phase == "obo":
        assert not task.done()
        assert not http.is_closed
    finished.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert http.is_closed
    assert probe._obo is None and probe._http is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,result,header",
    [
        (
            302,
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "serverInfo": {"name": "x", "version": "1"},
            },
            None,
        ),
        (
            200,
            {
                "protocolVersion": "wrong",
                "capabilities": {},
                "serverInfo": {"name": "x", "version": "1"},
            },
            "2025-03-26",
        ),
        (200, {"protocolVersion": "2025-03-26"}, None),
    ],
)
async def test_initialize_rejects_invalid_contract(status, result, header):
    service, actor = authenticated_alex()

    async def handler(request):
        return httpx.Response(
            status,
            json={"jsonrpc": "2.0", "id": 1, "result": result},
            headers={"mcp-protocol-version": header} if header else {},
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    outcome = await WorkIQMcpProbe(http=http, obo=FakeObo()).run(actor, service)  # type: ignore[arg-type]
    assert not outcome.mcp_initialized


def test_adapter_rejects_malformed_before_msal_can_log(caplog):
    from msal.oauth2cli.oauth2 import Client

    from integrations.workiq.probe_http import DiagnosticMsalHttp

    async def handler(request):
        return httpx.Response(200, text="sensitive-provider-response")

    adapter = DiagnosticMsalHttp(transport=httpx.MockTransport(handler))
    client = Client(
        {"token_endpoint": "https://login.microsoftonline.com/token"},
        "fixture-client",
        http_client=adapter,
    )
    with pytest.raises(ValueError):
        client.obtain_token_by_refresh_token("fixture")
    assert "sensitive-provider-response" not in caplog.text


@pytest.mark.parametrize("mode", ["oversize", "trickle"])
def test_adapter_enforces_transfer_bound(mode):
    from integrations.workiq.probe_http import DiagnosticMsalHttp

    closed = []

    class Stream(httpx.AsyncByteStream):
        async def aclose(self):
            closed.append(True)

        async def __aiter__(self):
            while True:
                if mode == "trickle":
                    await asyncio.sleep(0.01)
                yield b"x" * (65536 if mode == "oversize" else 1)

    async def handler(request):
        return httpx.Response(200, stream=Stream())

    adapter = DiagnosticMsalHttp(transport=httpx.MockTransport(handler), budget=0.05)
    with pytest.raises((ValueError, TimeoutError)):
        adapter.get("https://login.microsoftonline.com/metadata")
    assert closed == [True]


def test_adapter_deadline_is_shared_across_calls():
    from integrations.workiq.probe_http import DiagnosticMsalHttp

    calls = []

    async def handler(request):
        calls.append(request)
        await asyncio.sleep(0.035)
        return httpx.Response(200, json={})

    adapter = DiagnosticMsalHttp(transport=httpx.MockTransport(handler), budget=0.06)
    adapter.get("https://login.microsoftonline.com/metadata")
    with pytest.raises(TimeoutError):
        adapter.get("https://login.microsoftonline.com/metadata")
    with pytest.raises(TimeoutError):
        adapter.get("https://login.microsoftonline.com/metadata")
    assert len(calls) == 2
