from __future__ import annotations

import logging

import msal
import pytest

from integrations.graph_mail.obo import (
    GRAPH_SCOPES,
    GraphAuthenticationError,
    GraphOboExchange,
    build_graph_obo_exchange,
)
from tests.auth.test_token_authorization import API_CLIENT_ID, TENANT_ID
from tests.integration.test_graph_mail import ConfidentialClient
from tests.integration.test_workiq_contract import _authenticated_alex

SECRET = "privatecredential123"
LOGGER_NAME = "integrations.graph_mail.obo"


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            {"error": "invalid_client", "error_codes": [7000215]},
            ("outcome=remote_error", "oauth_error=invalid_client", "aad_code=7000215"),
        ),
        (
            {"error": "invalid_grant", "error_codes": [65001]},
            ("outcome=remote_error", "oauth_error=invalid_grant", "aad_code=65001"),
        ),
        (
            {
                "access_token": SECRET,
                "token_type": "AppOnly",
                "scope": " ".join(GRAPH_SCOPES),
            },
            (
                "outcome=response_rejected",
                "token_present=True",
                "bearer_type=False",
                "mail_readwrite=True",
                "mail_send=True",
            ),
        ),
        (
            {"access_token": SECRET, "token_type": "Bearer"},
            (
                "outcome=response_rejected",
                "mail_readwrite=False",
                "mail_send=False",
            ),
        ),
        (
            {"error": SECRET, "error_codes": [123456789012345, SECRET]},
            ("outcome=remote_error", "oauth_error=unknown", "aad_code=unknown"),
        ),
        ({}, ("outcome=response_rejected", "token_present=False")),
    ],
)
@pytest.mark.anyio
async def test_obo_logs_only_categorical_response_diagnostics(
    caplog: pytest.LogCaptureFixture,
    response: dict[str, object],
    expected: tuple[str, ...],
) -> None:
    response = {
        **response,
        "error_description": SECRET,
        "claims": SECRET,
        "correlation_id": SECRET,
        "refresh_token": SECRET,
    }
    service, actor = _authenticated_alex()

    with (
        caplog.at_level(logging.WARNING, logger=LOGGER_NAME),
        pytest.raises(GraphAuthenticationError) as caught,
    ):
        await GraphOboExchange(
            ConfidentialClient(response), auth_service=service
        ).exchange(actor)

    records = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert len(records) == 1
    assert "graph_obo_failed" in records[0].getMessage()
    for item in expected:
        assert item in records[0].getMessage()
    assert SECRET not in repr(records[0].__dict__)
    assert actor.downstream_user_assertion.reveal() not in repr(records[0].__dict__)
    assert SECRET not in str(caught.value)
    assert records[0].exc_info is None


@pytest.mark.anyio
async def test_valid_obo_response_does_not_emit_diagnostic(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, actor = _authenticated_alex()
    response = {
        "access_token": SECRET,
        "token_type": "Bearer",
        "scope": " ".join(GRAPH_SCOPES),
    }

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        token = await GraphOboExchange(
            ConfidentialClient(response), auth_service=service
        ).exchange(actor)

    assert token.reveal() == SECRET
    assert not [record for record in caplog.records if record.name == LOGGER_NAME]


@pytest.mark.anyio
async def test_production_obo_preserves_bounded_numeric_aad_code(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = {
        "error": "invalid_grant",
        "error_codes": [9002313],
        "error_description": SECRET,
        "correlation_id": SECRET,
    }
    monkeypatch.setattr(
        msal,
        "ConfidentialClientApplication",
        lambda **_: ConfidentialClient(response),
    )
    service, actor = _authenticated_alex()

    with (
        caplog.at_level(logging.WARNING, logger=LOGGER_NAME),
        pytest.raises(GraphAuthenticationError),
    ):
        await build_graph_obo_exchange(
            client_id=API_CLIENT_ID,
            client_secret="fixture-client-secret",
            tenant_id=TENANT_ID,
            auth_service=service,
        ).exchange(actor)

    records = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert len(records) == 1
    assert "oauth_error=invalid_grant" in records[0].getMessage()
    assert "aad_code=9002313" in records[0].getMessage()
    assert SECRET not in repr(records[0].__dict__)
