import asyncio
import json
import logging
from copy import deepcopy
from dataclasses import replace

import httpx
import pytest

from integrations.workiq.mcp import WorkIQMcpClient
from tests.integration.test_workiq_async_obo import Entra, exchange
from tests.integration.test_workiq_contract import _authenticated_alex
from tests.integration.test_workiq_mcp_transport import INIT, reply
from tests.integration.test_workiq_message_evidence import BINDING, MAIL, NOW, QUALITY


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Server:
    def __init__(self, kind="supplier", *, fail_entity=False):
        self.kind, self.fail_entity, self.requests = kind, fail_entity, []
        self.entity = deepcopy(QUALITY if kind == "quality" else MAIL)
        self.block_path: str | None = None
        self.entered, self.cancelled = asyncio.Event(), asyncio.Event()

    def _collection(self, path):
        if self.kind == "supplier":
            return {
                "value": [
                    {
                        "id": BINDING.supplier_source_id,
                        "subject": "RL-Supplier Alpha",
                        "from": {"emailAddress": {"address": BINDING.supplier_sender}},
                        "receivedDateTime": "2026-09-06T14:45:00Z",
                    }
                ]
            }
        if path == "/me/joinedTeams":
            return {
                "value": [
                    {"id": BINDING.team_id, "displayName": "Supply Response Demo"}
                ]
            }
        if path == f"/teams/{BINDING.team_id}/channels":
            return {"value": [{"id": BINDING.channel_id, "displayName": "General"}]}
        return {
            "value": [
                {
                    "id": BINDING.quality_source_id,
                    "from": {"user": {"id": BINDING.quality_author_object_id}},
                    "body": {
                        "contentType": "text",
                        "content": "RL-Supplier Beta qualification is pending.",
                    },
                }
            ]
        }

    async def __call__(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        if body["method"] == "initialize":
            return reply(request, INIT)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        assert body["params"]["name"] == "fetch"
        path = body["params"]["arguments"]["entityUrls"][0]
        if path == self.block_path:
            self.entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled.set()
        entity_path = "/messages/" in path and "?$top=" not in path
        data = deepcopy(self.entity) if entity_path else self._collection(path)
        result = {
            "results": [
                {
                    "statusCode": 404 if entity_path and self.fail_entity else 200,
                    "data": data,
                }
            ]
        }
        return reply(request, {"structuredContent": result})

    def calls(self):
        return [
            r["params"]["arguments"]["entityUrls"][0]
            for r in self.requests
            if r["method"] == "tools/call"
        ]


async def retrieve(
    monkeypatch, server, *, source_id=None, actor_override=None, binding=BINDING
):
    from integrations.workiq.mcp_evidence import WorkIQMcpEvidencePort

    service, actor = _authenticated_alex()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", Entra().transport)
    async with httpx.AsyncClient(transport=httpx.MockTransport(server)) as http:
        port = WorkIQMcpEvidencePort(
            client=WorkIQMcpClient(http=http), obo=exchange(service), binding=binding
        )
        method = (
            port.retrieve_supplier_signal
            if server.kind == "supplier"
            else port.retrieve_quality_context
        )
        return await method(
            actor=actor if actor_override is None else actor_override,
            source_id=source_id
            or (
                BINDING.supplier_source_id
                if server.kind == "supplier"
                else BINDING.quality_source_id
            ),
            case_id="case",
            analysis_id="analysis",
            retrieved_at=NOW,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("kind,fetches", [("supplier", 2), ("quality", 4)])
async def test_real_obo_structured_discovery_and_authoritative_fetch(
    monkeypatch, kind, fetches
):
    server = Server(kind)
    result = await retrieve(monkeypatch, server)
    assert len(result.evidence) == 1
    assert result.lineage.context_id == "" and result.lineage.protocol == "mcp"
    assert result.lineage.request_ids == tuple(
        r["id"] for r in server.requests if "id" in r
    )
    assert len(server.calls()) == fetches
    assert all(r.get("params", {}).get("name") != "ask" for r in server.requests)


@pytest.mark.anyio
async def test_source_input_rejected_before_auth_or_network(monkeypatch):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    server = Server()
    with pytest.raises(WorkIQSourceError) as caught:
        await retrieve(monkeypatch, server, source_id="wrong")
    assert caught.value.stage == "validation" and server.requests == []


@pytest.mark.anyio
@pytest.mark.parametrize("bad", ["tenant", "object", "unvalidated"])
async def test_invalid_actor_rejected_before_obo_or_network(monkeypatch, bad):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    _service, actor = _authenticated_alex()
    invalid = object() if bad == "unvalidated" else actor
    server = Server()
    binding = replace(
        BINDING,
        **(
            {"tenant_id": "wrong"}
            if bad == "tenant"
            else {"alex_object_id": "wrong"}
            if bad == "object"
            else {}
        ),
    )
    with pytest.raises(WorkIQSourceError) as caught:
        await retrieve(monkeypatch, server, actor_override=invalid, binding=binding)
    assert caught.value.stage == "authentication"
    assert server.requests == []


@pytest.mark.anyio
async def test_individual_fetch_failure_is_sanitized(monkeypatch, caplog):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    server = Server(fail_entity=True)
    with (
        caplog.at_level(logging.WARNING, logger="integrations.workiq.mcp_evidence"),
        pytest.raises(WorkIQSourceError) as caught,
    ):
        await retrieve(monkeypatch, server)
    assert caught.value.stage == "fetch" and caught.value.__context__ is None
    assert "mail-fixture" not in caplog.text


@pytest.mark.anyio
async def test_validation_failure_clears_payload_and_never_logs_upstream_data(
    monkeypatch, caplog
):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    server = Server()
    server.entity["sender"] = {
        "emailAddress": {"address": "private-attacker@example.com"}
    }
    with (
        caplog.at_level(logging.WARNING, logger="integrations.workiq.mcp_evidence"),
        pytest.raises(WorkIQSourceError) as caught,
    ):
        await retrieve(monkeypatch, server)
    assert caught.value.stage == "validation" and caught.value.__context__ is None
    assert "private-attacker" not in caplog.text
    trace = caught.value.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code.co_name == "_retrieve":
            assert trace.tb_frame.f_locals.get("payload") is None
            assert trace.tb_frame.f_locals.get("token") is None
            assert trace.tb_frame.f_locals.get("session") is None
        trace = trace.tb_next


@pytest.mark.anyio
@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("blocked", ["discovery", "entity"])
async def test_aggregate_deadline_and_cancellation(monkeypatch, cancel, blocked):
    from integrations.workiq import mcp_evidence
    from integrations.workiq.structured_discovery import MAIL_QUERY

    server = Server()
    server.block_path = (
        MAIL_QUERY
        if blocked == "discovery"
        else f"/me/messages/{BINDING.supplier_source_id}"
    )
    monkeypatch.setattr(mcp_evidence, "SOURCE_TIMEOUT_SECONDS", 0.1)
    task = asyncio.create_task(retrieve(monkeypatch, server))
    await asyncio.wait_for(server.entered.wait(), 1)
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(mcp_evidence.WorkIQSourceError) as caught:
            await task
        assert caught.value.stage == "timeout"
    assert server.cancelled.is_set()


@pytest.mark.anyio
async def test_discovery_binding_mismatch_never_falls_back_to_saved_id(monkeypatch):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    server = Server()
    server._collection = lambda path: {
        "value": [
            {
                "id": "other",
                "subject": "RL-Supplier Alpha",
                "from": {"emailAddress": {"address": BINDING.supplier_sender}},
                "receivedDateTime": "2026-09-06T14:45:00Z",
            }
        ]
    }
    with pytest.raises(WorkIQSourceError) as caught:
        await retrieve(monkeypatch, server)
    assert caught.value.stage == "discovery"
    assert all(
        path != f"/me/messages/{BINDING.supplier_source_id}" for path in server.calls()
    )
