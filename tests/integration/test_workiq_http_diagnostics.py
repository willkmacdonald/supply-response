from __future__ import annotations

import json
import logging

import httpx
import pytest

from integrations.workiq.client import WorkIQClient
from integrations.workiq.errors import WorkIQProtocolError


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("status", [302, 400, 401, 403, 404, 429, 500, 503])
async def test_http_rejection_logs_only_numeric_status(
    status: int, caplog: pytest.LogCaptureFixture
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            text="private-response-body",
            headers={"WWW-Authenticate": "private-challenge"},
            request=request,
        )

    with caplog.at_level(logging.WARNING, logger="integrations.workiq.client"):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(WorkIQProtocolError, match=f"HTTP {status}"):
                await WorkIQClient(http=http).send_message(
                    "private-prompt", access_token="private-access-token"
                )

    records = [r for r in caplog.records if r.name == "integrations.workiq.client"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    assert record.getMessage() == f"workiq_http_failed status={status}"
    assert record.args == (status,)
    assert record.exc_info is None
    assert record.stack_info is None
    for secret in (
        "private-response-body",
        "private-challenge",
        "private-prompt",
        "private-access-token",
    ):
        assert secret not in caplog.text


@pytest.mark.anyio
async def test_success_does_not_emit_http_failure_diagnostic(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": json.loads(request.content)["id"],
                "result": {
                    "task": {
                        "status": {"state": "TASK_STATE_COMPLETED"},
                        "artifacts": [],
                    },
                },
            },
            request=request,
        )

    with caplog.at_level(logging.WARNING, logger="integrations.workiq.client"):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            await WorkIQClient(http=http).send_message(
                "private-prompt", access_token="private-access-token"
            )

    assert not [r for r in caplog.records if r.name == "integrations.workiq.client"]
