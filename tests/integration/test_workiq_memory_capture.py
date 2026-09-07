from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
from datetime import UTC, datetime

import pytest


def capture_module():
    name = "integrations.workiq.memory_capture"
    assert importlib.util.find_spec(name) is not None, "memory-only capture is missing"
    return importlib.import_module(name)


def payload(text="final answer"):
    return {
        "headers": {"Authorization": "SECRET"},
        "result": {
            "task": {
                "status": {"message": {"parts": [{"text": "PRIVATE STATUS"}]}},
                "artifacts": [
                    {
                        "parts": [
                            {"text": text},
                            {
                                "mediaType": "application/vnd.ms-workiq-reference",
                                "data": {
                                    "ref1": {
                                        "targetLink": "https://example.com/doc",
                                        "isCitedInResponse": True,
                                        "sourceTimestamp": "2026-09-01T00:00:00Z",
                                        "token": "SECRET",
                                    }
                                },
                            },
                            {"mediaType": "unknown", "data": {"private": "SECRET"}},
                        ]
                    }
                ],
            }
        },
    }


def test_disabled_until_armed_and_same_analysis_one_pair_only():
    c = capture_module().MemoryCapture()
    assert c.reserve("supplier", "case", "analysis") is None
    assert c.command("arm")["state"] == "armed"
    ticket = c.reserve("supplier", "case", "analysis")
    assert ticket is not None
    assert c.reserve("supplier", "case", "analysis") is None
    assert c.reserve("quality", "different", "analysis") is None
    assert c.reserve("quality", "case", "other") is None
    quality = c.reserve("quality", "case", "analysis")
    c.record(ticket, payload())
    c.record(quality, payload())
    assert c.command("status")["state"] == "ready"
    result = c.command("take")
    assert set(result["responses"]) == {"supplier", "quality"}
    assert c.command("take")["state"] == "spent"
    assert c.command("arm")["state"] == "spent"


def test_only_final_answers_and_known_citation_fields_no_log(caplog):
    c = capture_module().MemoryCapture()
    c.command("arm")
    for source in ("supplier", "quality"):
        c.record(c.reserve(source, "c", "a"), payload())
    output = json.dumps(c.command("take"))
    assert "final answer" in output and "targetLink" in output
    assert "sourceTimestamp" in output
    assert "SECRET" not in output and "PRIVATE STATUS" not in output
    assert "Authorization" not in output and "private" not in output
    assert not caplog.records


def test_unknown_metadata_is_not_treated_as_citations():
    result = capture_module().project_answer(payload())
    assert result["uninspected_data_parts"] == 1
    assert result["citations"][0]["ref1"]["targetLink"] == "https://example.com/doc"


def test_expiry_clears_and_never_rearms():
    now = [0.0]
    c = capture_module().MemoryCapture(now=lambda: now[0])
    c.command("arm")
    ticket = c.reserve("supplier", "c", "a")
    c.record(ticket, payload())
    now[0] = 601
    c.expire()
    assert c.command("take") == {"state": "spent"}
    assert c.command("arm") == {"state": "spent"}
    c.record(ticket, payload())
    assert c.command("take") == {"state": "spent"}


def test_arming_expiry_and_partial_take_and_failure():
    now = [0.0]
    c = capture_module().MemoryCapture(now=lambda: now[0])
    c.command("arm")
    now[0] = 1801
    assert c.command("status")["state"] == "spent"
    c = capture_module().MemoryCapture()
    c.command("arm")
    c.record(c.reserve("supplier", "c", "a"), payload())
    assert c.command("take")["state"] == "collecting"
    c.failed(c.reserve("quality", "c", "a"))
    assert c.command("take")["responses"]["quality"] == {"outcome": "unavailable"}


def test_discard_and_unknown_commands_do_not_reveal_content():
    c = capture_module().MemoryCapture()
    c.command("arm")
    c.record(c.reserve("supplier", "c", "a"), payload())
    assert "responses" not in c.command("status")
    assert c.command("nonsense") == {"state": "invalid_command"}
    assert c.command("discard") == {"state": "spent"}


def test_projection_is_bounded_and_redacts_token_like_text():
    m = capture_module()
    p = payload(
        "Bearer abcdefsecret https://example.com/?access_token=SECRET " + "x" * 100000
    )
    result = json.dumps(m.project_answer(p))
    assert "abcdefsecret" not in result and "access_token=SECRET" not in result
    assert len(result.encode()) <= 65536
    assert "truncated" in result


def test_peer_access_requires_same_uid_and_linux_abstract_socket():
    m = capture_module()
    assert m.SOCKET_ADDRESS.startswith("\0")
    assert m.peer_allowed(10001, 10001)
    assert not m.peer_allowed(10002, 10001)


@pytest.mark.parametrize("value", [None, {}, {"result": []}])
def test_malformed_projection_is_bounded(value):
    assert capture_module().project_answer(value) == {"outcome": "invalid_artifacts"}


def test_real_port_captures_before_normalization_failure(monkeypatch, caplog):
    import httpx

    from integrations.workiq.client import WorkIQClient, WorkIQEvidencePort
    from integrations.workiq.errors import WorkIQProtocolError
    from integrations.workiq.obo import WorkIQOboExchange
    from tests.integration.test_workiq_contract import (
        ConfidentialClientFixture,
        _authenticated_alex,
    )

    m = capture_module()
    c = m.MemoryCapture()
    monkeypatch.setattr(m, "capture", c)
    c.command("arm")
    auth, actor = _authenticated_alex()
    obo = WorkIQOboExchange(
        ConfidentialClientFixture(
            {
                "access_token": "test-secret",
                "token_type": "Bearer",
                "scope": "WorkIQAgent.Ask",
            }
        ),
        auth_service=auth,
    )

    def handler(request):
        body = payload()
        body.update(jsonrpc="2.0", id=json.loads(request.content)["id"])
        body["result"]["task"].update(id="task", contextId="context")
        body["result"]["task"]["artifacts"][0]["artifactId"] = "artifact"
        body["result"]["task"]["status"]["state"] = "TASK_STATE_COMPLETED"
        return httpx.Response(200, json=body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            port = WorkIQEvidencePort(
                client=WorkIQClient(http=http),
                obo=obo,
                tenant_sharepoint_host="tenant.sharepoint.com",
            )
            for retrieve in (
                port.retrieve_supplier_signal,
                port.retrieve_quality_context,
            ):
                with pytest.raises(WorkIQProtocolError, match="facts are malformed"):
                    await retrieve(
                        actor=actor,
                        source_id="source",
                        case_id="case",
                        analysis_id="analysis",
                        retrieved_at=datetime.now(UTC),
                    )

    asyncio.run(run())
    assert c.command("status")["state"] == "ready"
    assert "final answer" in json.dumps(c.command("take"))
    assert "final answer" not in caplog.text
    assert "SECRET" not in caplog.text
