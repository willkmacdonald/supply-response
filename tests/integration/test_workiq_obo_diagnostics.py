from __future__ import annotations

import logging

import pytest

from integrations.workiq.obo import (
    WORK_IQ_SCOPE,
    WorkIQAuthenticationError,
    WorkIQOboExchange,
)
from tests.integration.test_workiq_contract import (
    ConfidentialClientFixture,
    _authenticated_alex,
)

SECRET = "privatecredential123"


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
            {"access_token": SECRET, "token_type": "Bearer", "scope": WORK_IQ_SCOPE},
            (
                "outcome=response_rejected",
                "token_present=True",
                "bearer_type=True",
                "scope_unqualified=False",
                "scope_qualified=True",
            ),
        ),
        (
            {"access_token": SECRET, "token_type": "Bearer"},
            (
                "outcome=response_rejected",
                "scope_unqualified=False",
                "scope_qualified=False",
            ),
        ),
        (
            {"error": SECRET, "error_codes": [123456789012345, SECRET]},
            ("outcome=remote_error", "oauth_error=unknown", "aad_code=unknown"),
        ),
        ({}, ("outcome=response_rejected", "token_present=False")),
    ],
)
def test_obo_logs_only_categorical_response_diagnostics(caplog, response, expected):
    response = {
        **response,
        "error_description": SECRET,
        "claims": SECRET,
        "correlation_id": SECRET,
        "refresh_token": SECRET,
    }
    service, actor = _authenticated_alex()
    with (
        caplog.at_level(logging.WARNING, logger="integrations.workiq.obo"),
        pytest.raises(WorkIQAuthenticationError) as caught,
    ):
        WorkIQOboExchange(
            ConfidentialClientFixture(response), auth_service=service
        ).exchange(actor)

    records = [r for r in caplog.records if r.name == "integrations.workiq.obo"]
    assert len(records) == 1
    assert "workiq_obo_failed" in records[0].getMessage()
    for item in expected:
        assert item in records[0].getMessage()
    assert SECRET not in repr(records[0].__dict__)
    assert actor.downstream_user_assertion.reveal() not in repr(records[0].__dict__)
    assert SECRET not in str(caught.value)
    assert records[0].exc_info is None


def test_valid_obo_response_does_not_emit_diagnostic(caplog):
    service, actor = _authenticated_alex()
    response = {
        "access_token": SECRET,
        "token_type": "Bearer",
        "scope": "WorkIQAgent.Ask",
    }
    with caplog.at_level(logging.WARNING, logger="integrations.workiq.obo"):
        token = WorkIQOboExchange(
            ConfidentialClientFixture(response), auth_service=service
        ).exchange(actor)
    assert token.reveal() == SECRET
    assert not [r for r in caplog.records if r.name == "integrations.workiq.obo"]
