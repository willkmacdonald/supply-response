import asyncio
import json
from copy import deepcopy
from dataclasses import replace

import httpx
import pytest

from integrations.workiq.mcp import WorkIQMcpClient
from tests.integration.test_workiq_async_obo import Entra, exchange
from tests.integration.test_workiq_contract import _authenticated_alex
from tests.integration.test_workiq_mcp_transport import INIT, reply
from tests.integration.test_workiq_message_evidence import (
    BINDING,
    MAIL,
    MAIL_LINK,
    NOW,
    QUALITY,
    TEAMS_LINK,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("An offline evidence test attempted network access")

    monkeypatch.setattr("socket.getaddrinfo", forbidden)


class Server:
    def __init__(self, kind="supplier", answer=None, entity=None, fail_fetch=False):
        self.requests = []
        self.kind = kind
        self.answer = (
            answer
            if answer is not None
            else (MAIL_LINK if kind == "supplier" else TEAMS_LINK)
        )
        self.entity = deepcopy(
            entity if entity is not None else (MAIL if kind == "supplier" else QUALITY)
        )
        self.fail_fetch = fail_fetch
        self.block_stage = None
        self.entered = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def __call__(self, request):
        self.requests.append(json.loads(request.content))
        body = self.requests[-1]
        if body["method"] == "initialize":
            return reply(request, INIT)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        name = body["params"]["name"]
        if name == self.block_stage:
            self.entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled.set()
        if name == "ask":
            result = {
                "response": self.answer,
                "conversationId": "fixture-discovery-conversation",
            }
        else:
            assert name == "fetch"
            result = {
                "results": [
                    {"statusCode": 404 if self.fail_fetch else 200, "data": self.entity}
                ]
            }
        return reply(request, {"structuredContent": result})

    def calls(self, name):
        return [
            r["params"]["arguments"]
            for r in self.requests
            if r["method"] == "tools/call" and r["params"]["name"] == name
        ]


async def retrieve(monkeypatch, server, binding=BINDING, actor=None, source_id=None):
    from integrations.workiq.mcp_evidence import WorkIQMcpEvidencePort

    service, validated = _authenticated_alex()
    entra = Entra()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", entra.transport)
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
            actor=validated if actor is None else actor,
            source_id=source_id
            or (
                binding.supplier_source_id
                if server.kind == "supplier"
                else binding.quality_source_id
            ),
            case_id="case-fixture",
            analysis_id="analysis-fixture",
            retrieved_at=NOW,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["supplier", "quality"])
async def test_real_auth_obo_discovery_fetch_and_source_statement(monkeypatch, kind):
    server = Server(kind)
    result = await retrieve(monkeypatch, server)
    assert len(result.evidence) == 1
    assert result.evidence[0].source_id == server.entity["id"]
    assert (
        "73 units" in result.evidence[0].claim
        if kind == "supplier"
        else "Z-47" in result.evidence[0].claim
    )
    assert result.lineage.context_id == "fixture-discovery-conversation"
    assert result.lineage.protocol == "mcp"
    assert result.lineage.task_id == "" and result.lineage.artifact_ids == ()
    assert result.lineage.source_ids == (server.entity["id"],)
    assert result.lineage.request_ids == tuple(
        r["id"] for r in server.requests if "id" in r
    )
    assert len(server.calls("ask")) == len(server.calls("fetch")) == 1
    ask = str(server.calls("ask"))
    for forbidden in (
        BINDING.supplier_source_id,
        BINDING.quality_source_id,
        BINDING.team_id,
        BINDING.alex_object_id,
        "73",
        "Z-47",
        "2026",
        "http",
    ):
        assert forbidden not in ask


@pytest.mark.anyio
@pytest.mark.parametrize(
    "answer",
    [
        "Only prose claiming Alpha has 73 units.",
        "https://teams.microsoft.com/l/channel/ch/general",
        "{invalid JSON}",
        "/me/messages",
        "/users/other/messages/mail-fixture",
        "https://evil.example/message",
    ],
)
async def test_missing_or_untrusted_discovery_causes_zero_fetch(monkeypatch, answer):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    server = Server(answer=answer)
    with pytest.raises(WorkIQSourceError) as caught:
        await retrieve(monkeypatch, server)
    assert caught.value.stage == "discovery" and caught.value.source_kind == "supplier"
    assert server.calls("fetch") == []


@pytest.mark.anyio
async def test_changed_expected_ids_cannot_supply_or_alter_locations(monkeypatch):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    baseline = Server()
    await retrieve(monkeypatch, baseline)
    changed = Server()
    with pytest.raises(WorkIQSourceError):
        await retrieve(
            monkeypatch,
            changed,
            replace(BINDING, supplier_source_id="configured-but-not-discovered"),
        )
    assert changed.calls("ask") == baseline.calls("ask")
    assert changed.calls("fetch") == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure,stage", [("fetch", "fetch"), ("author", "validation")]
)
async def test_ask_facts_never_promoted_on_fetch_or_validation_failure(
    monkeypatch, failure, stage, caplog
):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    server = Server(
        answer=f"private-body 73 units [source]({MAIL_LINK})",
        fail_fetch=failure == "fetch",
    )
    if failure == "author":
        server.entity["sender"]["emailAddress"]["address"] = "private-body@example.com"
    with pytest.raises(WorkIQSourceError) as caught:
        await retrieve(monkeypatch, server)
    assert caught.value.stage == stage
    assert caught.value.__context__ is None
    assert "private-body" not in str(caught.value) + caplog.text
    trace = caught.value.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code.co_name == "_retrieve":
            assert trace.tb_frame.f_locals.get("answer") is None
            assert trace.tb_frame.f_locals.get("payload") is None
            assert trace.tb_frame.f_locals.get("token") is None
            assert trace.tb_frame.f_locals.get("session") is None
        trace = trace.tb_next
    assert len(server.calls("ask")) == len(server.calls("fetch")) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("bad", ["tenant", "object", "source", "unvalidated"])
async def test_cross_user_and_mismatched_source_inputs_rejected_before_network(
    monkeypatch, bad
):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    binding = replace(
        BINDING,
        **(
            {"tenant_id": "other"}
            if bad == "tenant"
            else {"alex_object_id": "other"}
            if bad == "object"
            else {}
        ),
    )
    server = Server()
    with pytest.raises(WorkIQSourceError):
        await retrieve(
            monkeypatch,
            server,
            binding,
            actor=object() if bad == "unvalidated" else None,
            source_id="wrong" if bad == "source" else None,
        )
    assert server.requests == []


@pytest.mark.anyio
@pytest.mark.parametrize("stage", ["ask", "fetch"])
@pytest.mark.parametrize("cancel", [False, True])
async def test_aggregate_deadline_and_cancellation_close_active_work(
    monkeypatch, stage, cancel
):
    from integrations.workiq import mcp_evidence

    assert mcp_evidence.SOURCE_TIMEOUT_SECONDS == 120
    monkeypatch.setattr(mcp_evidence, "SOURCE_TIMEOUT_SECONDS", 0.2)
    server = Server()
    server.block_stage = stage
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
    assert len(server.calls("ask")) == 1


@pytest.mark.anyio
async def test_ambiguous_matching_entities_are_rejected(monkeypatch):
    from integrations.workiq.mcp_evidence import WorkIQSourceError

    server = Server(
        answer=json.dumps(
            {
                "locations": [
                    "/me/messages/mail-fixture",
                    f"/users/{BINDING.alex_object_id}/messages/mail-fixture",
                ]
            }
        )
    )
    with pytest.raises(WorkIQSourceError) as caught:
        await retrieve(monkeypatch, server)
    assert caught.value.stage == "validation"
    assert len(server.calls("fetch")) == 2
