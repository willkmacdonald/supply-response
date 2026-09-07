from __future__ import annotations

import asyncio
import logging
import threading
import time
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from opentelemetry.context import _SUPPRESS_INSTRUMENTATION_KEY, get_value

from apps.api.app.auth import AuthenticationError, AuthorizationError
from integrations.workiq.obo import WORK_IQ_SCOPE, WorkIQAuthenticationError
from tests.auth.test_token_authorization import API_CLIENT_ID, PRIVATE_KEY, TENANT_ID
from tests.integration.test_workiq_contract import _authenticated_alex

SECRET = "fixture-private-upstream-data"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
METADATA = {
    "authorization_endpoint": f"{AUTHORITY}/oauth2/v2.0/authorize",
    "token_endpoint": f"{AUTHORITY}/oauth2/v2.0/token",
    "issuer": f"{AUTHORITY}/v2.0",
}
TOKEN = {
    "access_token": SECRET,
    "token_type": "Bearer",
    "scope": WORK_IQ_SCOPE,
    "expires_in": 3600,
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("An offline OBO test attempted real network access")

    monkeypatch.setattr("socket.getaddrinfo", forbidden)


def exchange(service):
    from integrations.workiq.async_obo import AsyncWorkIQOboExchange

    return AsyncWorkIQOboExchange(
        client_id=API_CLIENT_ID,
        client_secret="fixture-app-secret",
        tenant_id=TENANT_ID,
        auth_service=service,
    )


class Entra:
    def __init__(self, response=None):
        self.requests = []
        self.transports = []
        self.closed = []
        self.response = response

    def transport(self, **kwargs):
        owner = self

        class Transport(httpx.MockTransport):
            async def aclose(self):
                owner.closed.append(self)
                await super().aclose()

        result = Transport(self.handle)
        self.transports.append(result)
        return result

    async def handle(self, request):
        assert get_value(_SUPPRESS_INSTRUMENTATION_KEY) is True
        self.requests.append(request)
        if request.method == "GET":
            assert (
                str(request.url) == f"{AUTHORITY}/v2.0/.well-known/openid-configuration"
            )
            return httpx.Response(200, json=METADATA)
        assert str(request.url) == METADATA["token_endpoint"]
        if self.response is not None:
            return self.response
        return httpx.Response(200, json=TOKEN)


@pytest.mark.anyio
async def test_real_builder_and_msal_exchange_validated_alex_with_isolated_clients(
    monkeypatch, caplog
):
    service, actor = _authenticated_alex()
    entra = Entra()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", entra.transport)
    obo = exchange(service)
    with caplog.at_level(logging.DEBUG):
        tokens = await asyncio.gather(obo.exchange(actor), obo.exchange(actor))
    assert [token.reveal() for token in tokens] == [SECRET, SECRET]
    assert len(entra.requests) == 4
    assert len(entra.transports) == len(entra.closed) == 2
    for request in entra.requests:
        assert request.url.host == "login.microsoftonline.com"
        if request.method == "POST":
            fields = parse_qs(request.content.decode())
            assert fields["assertion"] == [actor.downstream_user_assertion.reveal()]
            assert fields["client_id"] == [API_CLIENT_ID]
            assert fields["client_secret"] == ["fixture-app-secret"]
            assert WORK_IQ_SCOPE in fields["scope"][0].split()
            assert fields["requested_token_use"] == ["on_behalf_of"]
    for secret in (
        SECRET,
        "fixture-app-secret",
        actor.downstream_user_assertion.reveal(),
    ):
        assert secret not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutation",
    [
        {"oid": "cccccccc-cccc-4ccc-8ccc-cccccccccccc"},
        {"roles": ["quality_approver"]},
        {"aud": "wrong-api"},
        {"scp": "wrong_scope"},
    ],
)
async def test_invalid_signed_actor_claims_never_reach_token_endpoint(
    monkeypatch, mutation
):
    service, valid_actor = _authenticated_alex()
    entra = Entra()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", entra.transport)
    obo = exchange(service)
    claims = jwt.decode(
        valid_actor.downstream_user_assertion.reveal(),
        options={"verify_signature": False},
    )
    token = jwt.encode(
        {**claims, **mutation},
        PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "fixture-key"},
    )
    with pytest.raises(
        (AuthenticationError, AuthorizationError, WorkIQAuthenticationError)
    ):
        await obo.exchange(service.authenticate(token))
    assert entra.requests == []


@pytest.mark.anyio
async def test_actor_from_other_authservice_is_rejected_before_http(monkeypatch):
    service, _ = _authenticated_alex()
    _, other_actor = _authenticated_alex()
    entra = Entra()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", entra.transport)
    with pytest.raises(WorkIQAuthenticationError):
        await exchange(service).exchange(other_actor)
    assert entra.requests == []
    assert entra.closed == entra.transports


@pytest.mark.anyio
@pytest.mark.parametrize(
    "bad",
    [
        "malformed",
        "oversized",
        "deep",
        "redirect",
        "error",
        "error_and_token",
        "wrong_scope",
        "wrong_type",
        "missing_token",
        "oversized_token",
    ],
)
async def test_token_boundary_sanitizes_failures_before_msal_can_log_raw_data(
    monkeypatch, caplog, bad
):
    service, actor = _authenticated_alex()
    payload = {
        "error": {
            "error": SECRET,
            "error_description": SECRET,
            "error_codes": [SECRET],
            "claims": SECRET,
        },
        "error_and_token": {
            **TOKEN,
            "error": "invalid_grant",
            "error_description": SECRET,
        },
        "wrong_scope": {**TOKEN, "scope": SECRET},
        "wrong_type": {**TOKEN, "token_type": SECRET},
        "missing_token": {
            "token_type": "Bearer",
            "scope": WORK_IQ_SCOPE,
            "unknown": SECRET,
        },
        "oversized_token": {**TOKEN, "access_token": "x" * 32769},
    }.get(bad)
    response = httpx.Response(200, json=payload)
    if bad == "malformed":
        response = httpx.Response(200, text=SECRET)
    elif bad == "oversized":
        response = httpx.Response(200, content=b"x" * (1024 * 1024 + 1))
    elif bad == "deep":
        response = httpx.Response(200, content=b"[" * 1000 + b"0" + b"]" * 1000)
    elif bad == "redirect":
        response = httpx.Response(
            302, headers={"location": "https://example.com/" + SECRET}
        )
    entra = Entra(response)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", entra.transport)
    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(WorkIQAuthenticationError) as caught,
    ):
        await exchange(service).exchange(actor)
    assert SECRET not in caplog.text + str(caught.value)
    assert caught.value.__context__ is None
    assert actor.downstream_user_assertion.reveal() not in caplog.text
    assert "fixture-app-secret" not in caplog.text
    assert len(entra.requests) == 2
    assert entra.closed == entra.transports


@pytest.mark.anyio
async def test_untrusted_metadata_cannot_redirect_obo_credentials(monkeypatch, caplog):
    service, actor = _authenticated_alex()
    requests = []

    async def handle(request):
        requests.append(request)
        return httpx.Response(
            200, json={**METADATA, "token_endpoint": "https://example.com/" + SECRET}
        )

    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **_: httpx.MockTransport(handle)
    )
    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(WorkIQAuthenticationError) as caught,
    ):
        await exchange(service).exchange(actor)
    assert len(requests) == 1
    assert SECRET not in caplog.text + str(caught.value)


@pytest.mark.anyio
@pytest.mark.parametrize("cancel", [True, False])
async def test_cancellation_and_12_second_deadline_join_worker_and_close_stream(
    monkeypatch, cancel
):
    service, actor = _authenticated_alex()
    entered, stream_closed = asyncio.Event(), asyncio.Event()
    entra = Entra()

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b""

        async def aclose(self):
            stream_closed.set()

    entra.response = httpx.Response(200, stream=Stream())
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", entra.transport)
    obo = exchange(service)
    started = time.monotonic()
    task = asyncio.create_task(obo.exchange(actor))
    await asyncio.wait_for(entered.wait(), 2)
    # This must progress while the actual MSAL worker is waiting on token HTTP.
    await asyncio.sleep(0.02)
    assert not task.done()
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert time.monotonic() - started < 1
    else:
        with pytest.raises(WorkIQAuthenticationError):
            await asyncio.wait_for(task, 13)
        assert 11.5 <= time.monotonic() - started < 13
    assert stream_closed.is_set()
    assert entra.closed == entra.transports
    assert not [t for t in threading.enumerate() if t.name.startswith("workiq-obo")]
