"""Offline field-status diagnostics: never retain or emit upstream values."""

import json
import logging

import httpx
import pytest

from integrations.workiq.errors import WorkIQProtocolError
from integrations.workiq.mcp import WorkIQMcpClient
from tests.integration.test_workiq_mcp_transport import INIT, reply


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("wrapper", ["structured", "text"])
@pytest.mark.parametrize(
    "payload,expected",
    [
        (
            {"answer": "", "conversationId": "private-id"},
            "response=missing conversation_id=valid answer=empty error=missing",
        ),
        (
            {"response": None, "conversationId": None, "error": "private-error"},
            "response=null conversation_id=null answer=missing error=valid",
        ),
        (
            {"response": "private-body"},
            "response=valid conversation_id=missing answer=missing error=missing",
        ),
        (
            {"response": " ", "conversationId": "private-id"},
            "response=empty conversation_id=valid answer=missing error=missing",
        ),
        (
            {"response": "private-body", "conversationId": "x" * 257},
            "response=valid conversation_id=oversize answer=missing error=missing",
        ),
        (
            {"response": {"private-key": "private-body"}, "conversationId": []},
            "response=object conversation_id=array answer=missing error=missing",
        ),
        (
            {"response": False, "conversationId": 42},
            "response=boolean conversation_id=number answer=missing error=missing",
        ),
        (
            {"response": 1.5, "conversationId": "", "answer": ""},
            "response=number conversation_id=empty answer=empty error=missing",
        ),
    ],
)
async def test_invalid_ask_logs_only_fixed_field_states(
    payload, expected, wrapper, caplog
):
    requests = []

    async def server(request):
        body = json.loads(request.content)
        requests.append(body)
        if body["method"] == "initialize":
            return reply(request, INIT)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        assert body["params"]["name"] == "ask"
        value = (
            {"structuredContent": payload}
            if wrapper == "structured"
            else {"content": [{"type": "text", "text": json.dumps(payload)}]}
        )
        return reply(request, value)

    with caplog.at_level(logging.WARNING, logger="integrations.workiq.mcp"):
        async with httpx.AsyncClient(transport=httpx.MockTransport(server)) as http:
            async with WorkIQMcpClient(http=http).session(
                access_token="private-token"
            ) as session:
                with pytest.raises(
                    WorkIQProtocolError, match="Work IQ discovery response is invalid"
                ):
                    await session.ask("private-question")
    records = [r for r in caplog.records if r.name == "integrations.workiq.mcp"]
    assert [r.getMessage() for r in records] == ["workiq_ask_shape " + expected]
    assert all(r.exc_info is None and r.stack_info is None for r in records)
    assert "private-" not in repr([r.__dict__ for r in records])
    assert (
        len(requests) == 3
    )  # Initialization, notification and one ask; no retry/fetch.


@pytest.mark.anyio
async def test_valid_ask_has_no_shape_log(caplog):
    from tests.integration.test_workiq_mcp_transport import ANSWER, Server

    with caplog.at_level(logging.WARNING, logger="integrations.workiq.mcp"):
        async with httpx.AsyncClient(transport=httpx.MockTransport(Server())) as http:
            async with WorkIQMcpClient(http=http).session(
                access_token="private-token"
            ) as session:
                assert await session.ask("private-question") == ANSWER
    assert not [r for r in caplog.records if r.name == "integrations.workiq.mcp"]


@pytest.mark.anyio
@pytest.mark.parametrize("wrapper", ["structured", "text"])
@pytest.mark.parametrize("field", ["answer", "response", "both"])
async def test_supported_answer_fields_normalize_without_logging(
    wrapper, field, caplog
):
    payload = {"conversationId": "private-id"}
    for key in ("answer", "response") if field == "both" else (field,):
        payload[key] = "private-body"

    async def server(request):
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return reply(request, INIT)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return reply(
            request,
            {"structuredContent": payload}
            if wrapper == "structured"
            else {"content": [{"type": "text", "text": json.dumps(payload)}]},
        )

    with caplog.at_level(logging.WARNING, logger="integrations.workiq.mcp"):
        async with httpx.AsyncClient(transport=httpx.MockTransport(server)) as http:
            async with WorkIQMcpClient(http=http).session(
                access_token="private-token"
            ) as session:
                result = await session.ask("private-question")
    assert result == {"response": "private-body", "conversationId": "private-id"}
    assert not [r for r in caplog.records if r.name == "integrations.workiq.mcp"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fields",
    [
        {"answer": "private-body", "response": "different-private-body"},
        {"answer": "private-body", "response": None},
        {"answer": "private-body", "response": ""},
        {"answer": None, "response": "private-body"},
        {"answer": "", "response": "private-body"},
        {"answer": {"private-key": "private-body"}},
        {"answer": False},
        {"answer": ["private-body"]},
        {"answer": 42},
        {"answer": "private-body", "conversationId": "x" * 257},
        {"answer": "private-body", "conversationId": None},
    ],
)
async def test_invalid_or_conflicting_aliases_never_fall_back(fields, caplog):
    payload = {"conversationId": "private-id", **fields}
    requests = []

    async def server(request):
        body = json.loads(request.content)
        requests.append(body)
        if body["method"] == "initialize":
            return reply(request, INIT)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return reply(request, {"structuredContent": payload})

    with caplog.at_level(logging.WARNING, logger="integrations.workiq.mcp"):
        async with httpx.AsyncClient(transport=httpx.MockTransport(server)) as http:
            async with WorkIQMcpClient(http=http).session(
                access_token="private-token"
            ) as session:
                with pytest.raises(
                    WorkIQProtocolError, match="discovery response is invalid"
                ):
                    await session.ask("private-question")
    assert len(requests) == 3
    records = [r for r in caplog.records if r.name == "integrations.workiq.mcp"]
    assert len(records) == 1
    assert "private-" not in repr([r.__dict__ for r in records])
