"""Temporary probe HTTP boundary tests using real signed-token authorization."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from opentelemetry.context import _SUPPRESS_INSTRUMENTATION_KEY, get_value

from apps.api.app.auth import AuthService, PersonaBinding
from apps.api.app.main import create_app
from apps.api.app.routes import workiq_probe
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from integrations.workiq.obo import WorkIQOboExchange
from integrations.workiq.probe_binding import ALEX_OBJECT_ID, TENANT_ID
from tests.auth.test_token_authorization import API_CLIENT_ID, PRIVATE_KEY, _jwk

NOW = datetime(2026, 9, 7, 18, tzinfo=UTC)
ENDPOINT = "/api/diagnostics/workiq-fetch"


def _token(**overrides: Any) -> str:
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "aud": API_CLIENT_ID,
        "iat": int(NOW.timestamp()) - 5,
        "nbf": int(NOW.timestamp()) - 5,
        "exp": int(NOW.timestamp()) + 300,
        "tid": TENANT_ID,
        "oid": ALEX_OBJECT_ID,
        "roles": ["material_planner", "response_approver"],
        "scp": "access_as_user",
    }
    claims.update(overrides)
    return jwt.encode(
        claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": "fixture-key"}
    )


def _identity_metadata(url: str) -> dict[str, Any]:
    issuer = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
    keys = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
    if url == f"{issuer}/.well-known/openid-configuration":
        return {"issuer": issuer, "jwks_uri": keys}
    assert url == keys
    return {"keys": [_jwk()]}


class RejectedTokenProvider:
    """Stand in only for Entra's remote token response, not actor validation."""

    calls = 0

    def acquire_token_on_behalf_of(
        self, *, user_assertion: str, scopes: list[str]
    ) -> dict[str, Any]:
        assert user_assertion
        assert scopes == ["api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask"]
        assert get_value(_SUPPRESS_INSTRUMENTATION_KEY) is True
        self.calls += 1
        return {"error": "invalid_grant", "error_description": "must-never-leak"}


@pytest.fixture
def authorized_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, RejectedTokenProvider]]:
    app = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'probe-auth.db'}",
        ),
        clock=lambda: NOW,
    )
    services = app.state.services
    services.settings = services.settings.model_copy(
        update={
            "runtime_mode": RuntimeMode.LIVE,
            "api_client_id": API_CLIENT_ID,
            "allowed_tenant_id": TENANT_ID,
            "entra_client_secret": "fixture-only-not-a-real-secret",
        }
    )
    service = AuthService(
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        bindings=(PersonaBinding.alex(TENANT_ID, ALEX_OBJECT_ID),),
        http_get=_identity_metadata,
        now=lambda: NOW.timestamp(),
    )
    services.auth_service = service
    provider = RejectedTokenProvider()

    def build_exchange(**kwargs: Any) -> WorkIQOboExchange:
        assert kwargs["auth_service"] is service
        assert kwargs["client_id"] == API_CLIENT_ID
        assert kwargs["tenant_id"] == TENANT_ID
        assert kwargs["client_secret"] == "fixture-only-not-a-real-secret"
        return WorkIQOboExchange(provider, auth_service=service)

    monkeypatch.setattr(workiq_probe, "build_obo_exchange", build_exchange)
    monkeypatch.setattr(workiq_probe, "PROBE_START_UTC", NOW - timedelta(minutes=1))
    monkeypatch.setattr(workiq_probe, "PROBE_END_UTC", NOW + timedelta(minutes=29))
    with TestClient(app) as client:
        yield client, provider


@pytest.mark.parametrize("authorization", [None, "Basic invalid", "Bearer invalid"])
def test_missing_or_malformed_auth_cannot_consume_attempt(
    authorized_client, authorization
):
    client, provider = authorized_client
    headers = {} if authorization is None else {"Authorization": authorization}
    assert client.post(ENDPOINT, headers=headers).status_code == 401
    assert provider.calls == 0
    assert (
        client.post(ENDPOINT, headers={"Authorization": f"Bearer {_token()}"}).json()[
            "authenticated_alex"
        ]
        is True
    )
    assert provider.calls == 1


@pytest.mark.parametrize(
    ("mutation", "status"),
    [
        ({"tid": "11111111-1111-4111-8111-111111111111"}, 401),
        ({"oid": "1ff5eea4-5056-4868-b3bb-339ba87f9e2e"}, 403),
        ({"roles": ["material_planner"]}, 403),
        ({"roles": ["material_planner", "response_approver", "admin"]}, 403),
        ({"scp": "other_scope"}, 403),
        ({"aud": "wrong-audience"}, 401),
        ({"exp": int(NOW.timestamp()) - 300}, 401),
    ],
)
def test_wrong_identity_claims_rejected_before_obo(authorized_client, mutation, status):
    client, provider = authorized_client
    response = client.post(
        ENDPOINT, headers={"Authorization": f"Bearer {_token(**mutation)}"}
    )
    assert response.status_code == status
    assert provider.calls == 0


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (None, None),
        (NOW - timedelta(minutes=31), NOW - timedelta(minutes=1)),
        (NOW + timedelta(minutes=1), NOW + timedelta(minutes=30)),
        (NOW - timedelta(minutes=1), NOW + timedelta(minutes=30)),
        (NOW.replace(tzinfo=None), NOW + timedelta(minutes=1)),
    ],
)
def test_invalid_window_blocks_before_obo(authorized_client, monkeypatch, start, end):
    client, provider = authorized_client
    monkeypatch.setattr(workiq_probe, "PROBE_START_UTC", start)
    monkeypatch.setattr(workiq_probe, "PROBE_END_UTC", end)
    assert (
        client.post(
            ENDPOINT, headers={"Authorization": f"Bearer {_token()}"}
        ).status_code
        == 404
    )
    assert provider.calls == 0


def test_fallback_cannot_use_probe_even_with_valid_bearer(authorized_client):
    client, provider = authorized_client
    services = client.app.state.services
    services.settings = services.settings.model_copy(
        update={"runtime_mode": RuntimeMode.FALLBACK}
    )
    assert (
        client.post(
            ENDPOINT, headers={"Authorization": f"Bearer {_token()}"}
        ).status_code
        == 404
    )
    assert provider.calls == 0


def test_explicit_bodyless_post_only_and_spent_attempt(authorized_client):
    client, provider = authorized_client
    headers = {"Authorization": f"Bearer {_token()}"}
    assert client.get(ENDPOINT, headers=headers).status_code == 405
    assert (
        client.post(ENDPOINT + "?entityUrls=wrong", headers=headers).status_code == 400
    )
    assert client.post(ENDPOINT, headers=headers, json={}).status_code == 400
    assert provider.calls == 0
    response = client.post(ENDPOINT, headers=headers)
    assert response.status_code == 200
    assert response.json()["stage"] == "obo_failed"
    assert "must-never-leak" not in response.text
    assert client.post(ENDPOINT, headers=headers).status_code == 409
    assert provider.calls == 1
