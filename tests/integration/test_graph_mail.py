from __future__ import annotations

import pickle
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import pytest

from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.outbound_mail import SupplierEmailRevision
from integrations.graph_mail.client import (
    GraphMailClient,
    GraphMailError,
    GraphMailSubmissionUncertain,
)
from integrations.graph_mail.obo import (
    GRAPH_SCOPE,
    GraphAccessToken,
    GraphAuthenticationError,
    GraphOboExchange,
    build_graph_obo_exchange,
)
from tests.auth.test_token_authorization import API_CLIENT_ID, TENANT_ID
from tests.integration.test_workiq_contract import _authenticated_alex


class StubObo:
    def __init__(self) -> None:
        self.actors = []

    async def exchange(self, actor):
        self.actors.append(actor)
        return GraphAccessToken("fixture-graph-access-token")


class ConfidentialClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def acquire_token_on_behalf_of(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


@pytest.fixture
def reviewed_revision() -> SupplierEmailRevision:
    actor = IdentitySnapshot(
        tenant_id="11111111-1111-4111-8111-111111111111",
        object_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        persona_id="RL-PERSONA-ALEX",
        effective_roles=("material_planner", "response_approver"),
        identity_source=IdentitySource.ENTRA,
        source_id="RL-ENTRA-ALEX",
        user_principal_name="agent@willmacdonald.com",
    )
    now = datetime(2026, 9, 15, 18, 0, tzinfo=UTC)
    return SupplierEmailRevision(
        email_id="RL-EMAIL-1",
        decision_id="RL-DECISION-1",
        action_id="RL-ACTION-1",
        revision=2,
        subject="Reviewed supplier recovery request",
        body="Fictional demo body.",
        from_address="agent@willmacdonald.com",
        to_address="will@willmacdonald.com",
        edited_by=actor,
        edited_at=now,
        reviewed_by=actor,
        reviewed_at=now,
    )


def _message(revision: SupplierEmailRevision, *, sent: bool = False):
    return {
        "id": "immutable-message-id",
        "internetMessageId": "<fixture@willmacdonald.com>",
        "subject": revision.subject,
        "body": {"contentType": "text", "content": revision.body},
        "from": {"emailAddress": {"address": revision.from_address}},
        "sender": {"emailAddress": {"address": revision.from_address}},
        "toRecipients": [{"emailAddress": {"address": revision.to_address}}],
        "sentDateTime": "2026-09-15T18:02:00Z" if sent else None,
    }


@pytest.mark.anyio
async def test_adapter_creates_verifies_and_submits_exact_immutable_draft(
    reviewed_revision,
):
    requests: list[httpx.Request] = []

    async def graph(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer fixture-graph-access-token"
        assert request.headers["Prefer"] == 'IdType="ImmutableId"'
        if request.method == "POST" and request.url.path == "/v1.0/me/messages":
            assert request.headers["Content-Type"] == "application/json"
            assert request.content == (
                b'{"subject":"Reviewed supplier recovery request",'
                b'"body":{"contentType":"Text","content":"Fictional demo body."},'
                b'"toRecipients":[{"emailAddress":{"address":"will@willmacdonald.com"}}]}'
            )
            return httpx.Response(201, json={"id": "immutable-message-id"})
        if request.method == "GET":
            return httpx.Response(200, json=_message(reviewed_revision))
        if request.method == "POST" and request.url.path.endswith("/send"):
            assert request.content == b""
            return httpx.Response(202)
        raise AssertionError(
            f"unexpected Graph request: {request.method} {request.url}"
        )

    obo = StubObo()
    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(graph),
        follow_redirects=False,
    ) as http:
        client = GraphMailClient(
            http=http,
            obo=obo,
            mailbox_address="agent@willmacdonald.com",
        )
        draft = await client.create_draft(reviewed_revision, object())
        await client.send_draft(draft.provider_message_id, object())

    assert draft.provider_message_id == "immutable-message-id"
    assert draft.internet_message_id == "<fixture@willmacdonald.com>"
    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", "/v1.0/me/messages"),
        ("GET", "/v1.0/me/messages/immutable-message-id"),
        ("POST", "/v1.0/me/messages/immutable-message-id/send"),
    ]
    assert len(obo.actors) == 3


@pytest.mark.anyio
async def test_adapter_rejects_mismatch_before_any_send(reviewed_revision):
    methods: list[str] = []

    async def graph(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(201, json={"id": "immutable-message-id"})
        mismatched = _message(reviewed_revision)
        mismatched["toRecipients"] = [
            {"emailAddress": {"address": "attacker@example.com"}}
        ]
        return httpx.Response(200, json=mismatched)

    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(graph),
        follow_redirects=False,
    ) as http:
        client = GraphMailClient(
            http=http,
            obo=StubObo(),
            mailbox_address="agent@willmacdonald.com",
        )
        with pytest.raises(GraphMailError) as error:
            await client.create_draft(reviewed_revision, object())

    assert error.value.code == "graph_message_mismatch"
    assert methods == ["POST", "GET"]


@pytest.mark.anyio
async def test_adapter_rejects_mismatched_from_even_when_sender_matches(
    reviewed_revision,
):
    async def graph(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"id": "immutable-message-id"})
        mismatched = _message(reviewed_revision)
        mismatched["from"] = {"emailAddress": {"address": "attacker@example.com"}}
        return httpx.Response(200, json=mismatched)

    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(graph),
        follow_redirects=False,
    ) as http:
        client = GraphMailClient(
            http=http,
            obo=StubObo(),
            mailbox_address="agent@willmacdonald.com",
        )
        with pytest.raises(GraphMailError) as error:
            await client.create_draft(reviewed_revision, object())

    assert error.value.code == "graph_response_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["redirect", "non_json", "oversized"])
async def test_adapter_rejects_unsafe_graph_responses(reviewed_revision, kind):
    response = {
        "redirect": httpx.Response(
            302, headers={"location": "https://attacker.example/secret"}
        ),
        "non_json": httpx.Response(201, text="secret response"),
        "oversized": httpx.Response(201, content=b"x" * (1024 * 1024 + 1)),
    }[kind]

    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(lambda _: response),
        follow_redirects=False,
    ) as http:
        client = GraphMailClient(
            http=http,
            obo=StubObo(),
            mailbox_address="agent@willmacdonald.com",
        )
        with pytest.raises(GraphMailError) as error:
            await client.create_draft(reviewed_revision, object())

    assert error.value.code in {"graph_create_failed", "graph_response_invalid"}
    assert "secret" not in str(error.value)


@pytest.mark.anyio
async def test_send_timeout_is_explicitly_uncertain():
    async def graph(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret provider detail", request=request)

    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(graph),
        follow_redirects=False,
    ) as http:
        client = GraphMailClient(
            http=http,
            obo=StubObo(),
            mailbox_address="agent@willmacdonald.com",
        )
        with pytest.raises(GraphMailSubmissionUncertain) as error:
            await client.send_draft("immutable-message-id", object())

    assert error.value.code == "graph_send_uncertain"
    assert "secret" not in str(error.value)


@pytest.mark.anyio
async def test_capability_is_read_only_and_retrieves_the_exact_sent_item():
    requests: list[httpx.Request] = []

    async def graph(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1.0/me":
            return httpx.Response(
                200,
                json={
                    "id": "alex-object-id",
                    "mail": "agent@willmacdonald.com",
                    "userPrincipalName": "agent@willmacdonald.com",
                },
            )
        if request.url.path == "/v1.0/me/mailFolders/sentitems/messages":
            return httpx.Response(200, json={"value": [{"id": "sent-item-id"}]})
        return httpx.Response(200, json={"id": "sent-item-id"})

    async with httpx.AsyncClient(
        base_url="https://graph.microsoft.com",
        transport=httpx.MockTransport(graph),
        follow_redirects=False,
    ) as http:
        capability = await GraphMailClient(
            http=http,
            obo=StubObo(),
            mailbox_address="agent@willmacdonald.com",
        ).capability(object())

    assert capability.mailbox_address == "agent@willmacdonald.com"
    assert capability.sample_sent_message_id == "sent-item-id"
    assert [request.method for request in requests] == ["GET", "GET", "GET"]
    assert requests[1].url.params["$top"] == "1"
    assert requests[2].url.path == "/v1.0/me/messages/sent-item-id"
    assert all(
        request.headers["Prefer"] == 'IdType="ImmutableId"' for request in requests
    )


@pytest.mark.anyio
async def test_obo_uses_validated_assertion_and_only_graph_default_scope():
    auth_service, actor = _authenticated_alex()
    confidential = ConfidentialClient(
        {
            "access_token": "fixture-downstream-secret",
            "token_type": "Bearer",
            "scope": "Mail.ReadWrite Mail.Send",
        }
    )
    token = await GraphOboExchange(confidential, auth_service=auth_service).exchange(
        actor
    )

    assert token.reveal() == "fixture-downstream-secret"
    assert confidential.calls == [
        {
            "user_assertion": actor.downstream_user_assertion.reveal(),
            "scopes": [GRAPH_SCOPE],
        }
    ]
    assert "fixture-downstream-secret" not in repr(token)
    assert "fixture-downstream-secret" not in str(token)
    with pytest.raises(TypeError):
        pickle.dumps(token)


@pytest.mark.anyio
async def test_obo_rejects_foreign_actor_before_confidential_client_call():
    auth_service, _ = _authenticated_alex()
    _, foreign_actor = _authenticated_alex()
    confidential = ConfidentialClient({})

    with pytest.raises(GraphAuthenticationError):
        await GraphOboExchange(confidential, auth_service=auth_service).exchange(
            foreign_actor
        )

    assert confidential.calls == []


@pytest.mark.anyio
async def test_production_obo_builder_accepts_only_graph_mail_scopes(monkeypatch):
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    requests: list[httpx.Request] = []
    token_fields: list[dict[str, list[str]]] = []

    async def entra(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": f"{authority}/oauth2/v2.0/authorize",
                    "token_endpoint": f"{authority}/oauth2/v2.0/token",
                    "issuer": f"{authority}/v2.0",
                },
            )
        fields = parse_qs(request.content.decode())
        token_fields.append(fields)
        return httpx.Response(
            200,
            json={
                "access_token": "fixture-production-graph-token",
                "token_type": "Bearer",
                "scope": "Mail.ReadWrite Mail.Send",
                "expires_in": 3600,
            },
        )

    monkeypatch.setattr(
        httpx,
        "AsyncHTTPTransport",
        lambda **_: httpx.MockTransport(entra),
    )
    auth_service, actor = _authenticated_alex()

    token = await build_graph_obo_exchange(
        client_id=API_CLIENT_ID,
        client_secret="fixture-client-secret",
        tenant_id=TENANT_ID,
        auth_service=auth_service,
    ).exchange(actor)

    assert token.reveal() == "fixture-production-graph-token"
    assert [request.method for request in requests] == ["GET", "POST"]
    assert set(token_fields[0]["scope"][0].split()) == {
        GRAPH_SCOPE,
        "offline_access",
        "openid",
        "profile",
    }
    assert token_fields[0]["requested_token_use"] == ["on_behalf_of"]
