from __future__ import annotations

import logging
from types import SimpleNamespace

import httpx
import pytest

from integrations.graph_mail.client import GraphMailClient, GraphMailError
from integrations.graph_mail.obo import GraphAccessToken

LOGGER_NAME = "supply_response.graph_mail"
TOKEN_SECRET = "fixture-capability-token-secret"
PROVIDER_SECRET = "fixture-provider-response-secret"
MESSAGE_ID = "fixture-private-message-id"
MAILBOX_ADDRESS = "agent@willmacdonald.com"
ACTOR_TENANT_ID = "11111111-1111-4111-8111-111111111111"
ACTOR_OBJECT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class SequencedObo:
    def __init__(self, *results: GraphAccessToken | Exception) -> None:
        self._results = iter(results)
        self.calls = 0

    async def exchange(self, actor: object) -> GraphAccessToken:
        del actor
        self.calls += 1
        result = next(self._results)
        if isinstance(result, Exception):
            raise result
        return result


class InvalidGzipStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"invalid-gzip-" + PROVIDER_SECRET.encode()


def _token() -> GraphAccessToken:
    return GraphAccessToken(TOKEN_SECRET)


def _sent_list() -> httpx.Response:
    return httpx.Response(200, json={"value": [{"id": MESSAGE_ID}]})


def _exact_message(*, address: str = MAILBOX_ADDRESS) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": MESSAGE_ID,
            "sender": {"emailAddress": {"address": address}},
            "from": {"emailAddress": {"address": address}},
        },
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("case", "expected_stage", "expected_outcome", "obo_calls", "http_calls"),
    [
        ("sent_list_obo", "sent_list_obo", "non_success", 1, 0),
        ("sent_list_http", "sent_list_http", "non_success", 1, 1),
        ("sent_list_shape", "sent_list_shape", "invalid_shape", 1, 1),
        ("exact_get_obo", "exact_get_obo", "non_success", 2, 1),
        ("exact_get_http", "exact_get_http", "transport", 2, 2),
        ("exact_get_shape", "exact_get_shape", "invalid_shape", 2, 2),
        ("sender_binding", "sender_binding", "mismatch", 2, 2),
    ],
)
async def test_capability_failure_emits_one_bounded_stage_diagnostic(
    case: str,
    expected_stage: str,
    expected_outcome: str,
    obo_calls: int,
    http_calls: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    obo_results: list[GraphAccessToken | Exception] = [_token(), _token()]
    if case == "sent_list_obo":
        obo_results[0] = RuntimeError(PROVIDER_SECRET)
    elif case == "exact_get_obo":
        obo_results[1] = RuntimeError(PROVIDER_SECRET)
    obo = SequencedObo(*obo_results)
    requests: list[httpx.Request] = []

    def graph(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            if case == "sent_list_http":
                return httpx.Response(503, text=PROVIDER_SECRET)
            if case == "sent_list_shape":
                return httpx.Response(200, json={"value": []})
            return _sent_list()
        if case == "exact_get_http":
            raise httpx.RemoteProtocolError(PROVIDER_SECRET, request=request)
        if case == "exact_get_shape":
            return httpx.Response(
                200,
                json={
                    "id": f"wrong-{MESSAGE_ID}",
                    "sender": {
                        "emailAddress": {"address": "private-sender@example.com"}
                    },
                    "from": {"emailAddress": {"address": "private-sender@example.com"}},
                },
            )
        if case == "sender_binding":
            return _exact_message(address="private-sender@example.com")
        return _exact_message()

    actor = SimpleNamespace(
        tenant_id=ACTOR_TENANT_ID,
        object_id=ACTOR_OBJECT_ID,
    )
    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(graph),
        follow_redirects=False,
    ) as http:
        client = GraphMailClient(
            http=http,
            obo=obo,
            mailbox_address=MAILBOX_ADDRESS,
        )
        with (
            caplog.at_level(logging.WARNING, logger=LOGGER_NAME),
            pytest.raises(GraphMailError) as caught,
        ):
            await client.capability(actor)

    records = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].getMessage() == (
        "graph_mail_capability_failed "
        f"stage={expected_stage} outcome={expected_outcome} "
        "code=graph_capability_failed"
    )
    assert records[0].exc_info is None
    assert caught.value.code == "graph_capability_failed"
    assert obo.calls == obo_calls
    assert len(requests) == http_calls

    observable = caplog.text + str(caught.value) + repr(caught.value)
    for sensitive in (
        TOKEN_SECRET,
        PROVIDER_SECRET,
        MESSAGE_ID,
        MAILBOX_ADDRESS,
        "private-sender@example.com",
        ACTOR_TENANT_ID,
        ACTOR_OBJECT_ID,
        "/me/mailFolders/sentitems/messages",
        "$select",
    ):
        assert sensitive not in observable


@pytest.mark.anyio
async def test_capability_timeout_has_bounded_http_outcome(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def graph(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(PROVIDER_SECRET, request=request)

    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(graph),
        follow_redirects=False,
    ) as http:
        with (
            caplog.at_level(logging.WARNING, logger=LOGGER_NAME),
            pytest.raises(GraphMailError),
        ):
            await GraphMailClient(
                http=http,
                obo=SequencedObo(_token()),
                mailbox_address=MAILBOX_ADDRESS,
            ).capability(object())

    records = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert len(records) == 1
    assert "stage=sent_list_http outcome=timeout" in records[0].getMessage()
    assert PROVIDER_SECRET not in caplog.text


@pytest.mark.anyio
async def test_capability_decoding_error_is_a_bounded_shape_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def graph(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "content-encoding": "gzip",
            },
            stream=InvalidGzipStream(),
        )

    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(graph),
        follow_redirects=False,
    ) as http:
        with (
            caplog.at_level(logging.WARNING, logger=LOGGER_NAME),
            pytest.raises(GraphMailError) as caught,
        ):
            await GraphMailClient(
                http=http,
                obo=SequencedObo(_token()),
                mailbox_address=MAILBOX_ADDRESS,
            ).capability(object())

    records = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert len(records) == 1
    assert records[0].getMessage() == (
        "graph_mail_capability_failed "
        "stage=sent_list_shape outcome=invalid_shape "
        "code=graph_capability_failed"
    )
    observable = caplog.text + str(caught.value) + repr(caught.value)
    assert PROVIDER_SECRET not in observable


@pytest.mark.anyio
async def test_successful_capability_is_read_only_and_emits_no_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    requests: list[httpx.Request] = []

    def graph(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _sent_list() if len(requests) == 1 else _exact_message()

    obo = SequencedObo(_token(), _token())
    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(graph),
        follow_redirects=False,
    ) as http:
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            capability = await GraphMailClient(
                http=http,
                obo=obo,
                mailbox_address=MAILBOX_ADDRESS,
            ).capability(object())

    assert capability.mailbox_address == MAILBOX_ADDRESS
    assert capability.sample_sent_message_id == MESSAGE_ID
    assert [request.method for request in requests] == ["GET", "GET"]
    assert obo.calls == 2
    assert not [record for record in caplog.records if record.name == LOGGER_NAME]
