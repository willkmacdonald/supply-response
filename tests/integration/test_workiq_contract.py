from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest

from apps.api.app.auth import AuthService, PersonaBinding
from data.domain.common import RuntimeMode
from data.domain.evidence import AuthorityScope, EvidenceKind, EvidenceRequirement
from integrations.workiq.client import (
    WorkIQProtocolError,
    WorkIQResponseLimitError,
    WorkIQClient,
)
from integrations.workiq.normalizer import normalize_a2a_evidence
from integrations.workiq.obo import (
    WORK_IQ_SCOPE,
    WorkIQAuthenticationError,
    WorkIQOboExchange,
)
from integrations.workiq.prompts import quality_context_prompt, supplier_signal_prompt
from tests.auth.test_token_authorization import (
    ALEX_OID,
    API_CLIENT_ID,
    FixtureHttp,
    NOW as AUTH_NOW,
    PRIVATE_KEY,
    TENANT_ID,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "fixtures" / "workiq"
NOW = datetime(2026, 8, 31, 18, 0, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ConfidentialClientFixture:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def acquire_token_on_behalf_of(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.result


def _authenticated_alex():
    service = AuthService(
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        bindings=(PersonaBinding.alex(TENANT_ID, ALEX_OID),),
        http_get=FixtureHttp(),
        now=lambda: AUTH_NOW.timestamp(),
    )
    assertion = jwt.encode(
        {
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "aud": API_CLIENT_ID,
            "iat": int(AUTH_NOW.timestamp()) - 5,
            "nbf": int(AUTH_NOW.timestamp()) - 5,
            "exp": int(AUTH_NOW.timestamp()) + 300,
            "tid": TENANT_ID,
            "oid": ALEX_OID,
            "roles": ["material_planner", "response_approver"],
            "scp": "access_as_user",
        },
        PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "fixture-key", "typ": "JWT"},
    )
    return service, service.authenticate(assertion)


def test_obo_requests_only_explicit_delegated_scope_and_redacts_secrets() -> None:
    raw_assertion = "validated-api-bearer-secret"
    downstream = "downstream-work-iq-secret"
    confidential = ConfidentialClientFixture(
        {
            "access_token": downstream,
            "token_type": "Bearer",
            "scope": "WorkIQAgent.Ask",
        }
    )

    service, actor = _authenticated_alex()
    raw_assertion = actor.downstream_user_assertion.reveal()
    token = WorkIQOboExchange(confidential, auth_service=service).exchange(actor)

    assert token.reveal() == downstream
    assert confidential.calls == [
        {"user_assertion": raw_assertion, "scopes": [WORK_IQ_SCOPE]}
    ]
    assert raw_assertion not in repr(token)
    assert downstream not in repr(token)
    assert downstream not in str(token)
    with pytest.raises(TypeError):
        pickle.dumps(token)


@pytest.mark.parametrize(
    "result",
    [
        {},
        {"error": "invalid_grant", "error_description": "secret details"},
        {"access_token": "downstream-secret-literal", "token_type": "Bearer"},
        {
            "access_token": "downstream-secret-literal",
            "token_type": "Bearer",
            "scope": ".default",
        },
        {
            "access_token": "downstream-secret-literal",
            "token_type": "AppOnly",
            "scope": "WorkIQAgent.Ask",
        },
    ],
)
def test_obo_rejects_missing_error_or_application_only_results(
    result: dict[str, Any],
) -> None:
    with pytest.raises(WorkIQAuthenticationError) as error:
        service, actor = _authenticated_alex()
        WorkIQOboExchange(
            ConfidentialClientFixture(result), auth_service=service
        ).exchange(actor)

    message = str(error.value)
    assert "api-secret" not in message
    access_token = result.get("access_token")
    if isinstance(access_token, str):
        assert access_token not in message
    assert "secret details" not in message


def _completed_payload(request_id: str = "request-1") -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "contextId": "context-opaque",
            "taskId": "task-opaque",
            "status": {"state": "TASK_STATE_COMPLETED"},
            "artifacts": [],
        },
    }


@pytest.mark.anyio
async def test_client_sends_exact_a2a_v1_request() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=_completed_payload(captured["payload"]["id"]),
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        payload = await WorkIQClient(http=http).send_message(
            "constrained prompt", access_token="downstream-secret"
        )

    assert captured["url"] == "https://workiq.svc.cloud.microsoft/a2a/"
    assert captured["headers"]["a2a-version"] == "1.0"
    assert captured["headers"]["authorization"] == "Bearer downstream-secret"
    assert captured["payload"]["jsonrpc"] == "2.0"
    assert captured["payload"]["method"] == "SendMessage"
    assert captured["payload"]["params"]["message"]["role"] == "ROLE_USER"
    assert captured["payload"]["params"]["message"]["parts"] == [
        {"text": "constrained prompt"}
    ]
    assert captured["payload"]["params"]["message"]["metadata"] == {
        "Location": {
            "timeZoneOffset": -300,
            "timeZone": "America/Chicago",
        }
    }
    assert payload["result"]["contextId"] == "context-opaque"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mutate", "error_type"),
    [
        (lambda body: body.update({"jsonrpc": "1.0"}), WorkIQProtocolError),
        (lambda body: body.update({"id": "wrong"}), WorkIQProtocolError),
        (
            lambda body: body["result"]["status"].update(
                {"state": "TASK_STATE_FAILED"}
            ),
            WorkIQProtocolError,
        ),
        (lambda body: body.update({"error": {"code": -1}}), WorkIQProtocolError),
    ],
)
async def test_client_rejects_malformed_wrong_id_failed_or_error_responses(
    mutate: Any, error_type: type[Exception]
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        request_id = json.loads(request.content)["id"]
        body = _completed_payload(request_id)
        mutate(body)
        return httpx.Response(200, json=body, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(error_type):
            await WorkIQClient(http=http).send_message(
                "prompt", access_token="redacted"
            )


@pytest.mark.anyio
async def test_client_bounds_response_bytes_json_depth_artifacts_and_parts() -> None:
    nested: dict[str, Any] = {"leaf": 1}
    for index in range(14):
        nested = {f"level-{index}": nested}
    bodies = [
        b"{" + b'"padding":"' + (b"x" * 1_048_576) + b'"}',
        json.dumps(nested).encode(),
        json.dumps(_completed_payload()).encode(),
    ]
    too_many = _completed_payload()
    too_many["result"]["artifacts"] = [
        {"artifactId": str(index), "parts": []} for index in range(65)
    ]
    bodies[2] = json.dumps(too_many).encode()

    for body in bodies:

        async def handler(request: httpx.Request, body: bytes = body) -> httpx.Response:
            if b'"jsonrpc"' in body:
                document = json.loads(body)
                document["id"] = json.loads(request.content)["id"]
                body = json.dumps(document).encode()
            return httpx.Response(200, content=body, request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(WorkIQResponseLimitError):
                await WorkIQClient(http=http).send_message(
                    "prompt", access_token="redacted"
                )


@pytest.mark.parametrize(
    "fixture_name",
    ["supplier-alpha-a2a.json", "supplier-beta-quality-a2a.json"],
)
def test_a2a_response_normalizes_to_cited_evidence(fixture_name: str) -> None:
    payload = json.loads((FIXTURES / fixture_name).read_text())
    expected_source_id = (
        "fixture-source-alpha"
        if fixture_name.startswith("supplier-alpha")
        else "fixture-source-beta-quality"
    )
    expected_scope = (
        AuthorityScope.SUPPLIER_STATEMENT
        if fixture_name.startswith("supplier-alpha")
        else AuthorityScope.COLLABORATION_STATEMENT
    )
    retrieval = normalize_a2a_evidence(
        payload,
        case_id="RL-CASE-WORKIQ-1",
        analysis_id="RL-ANALYSIS-WORKIQ-1",
        retrieved_at=NOW,
        expected_source_id=expected_source_id,
        expected_authority_scope=expected_scope,
        tenant_sharepoint_host="tenant.sharepoint.com",
    )
    items = retrieval.evidence

    assert items
    assert all(item.source_system == "work_iq" for item in items)
    assert all(item.source_id and item.source_timestamp for item in items)
    assert all(item.excerpt and item.citation_url for item in items)
    assert all(
        item.runtime_mode is RuntimeMode.LIVE and not item.synthetic for item in items
    )
    assert all(
        item.requirement is EvidenceRequirement.REQUIRED_AUTHORITATIVE for item in items
    )


@pytest.mark.parametrize(
    "citation",
    [
        None,
        {"sourceId": "x", "url": "https://example.com/x", "excerpt": "x"},
        {"sourceId": "x", "url": "javascript:alert(1)", "excerpt": "x"},
        {"sourceId": "x", "url": "https://localhost/x", "excerpt": "x"},
        {
            "sourceId": "x",
            "url": "https://user:pass@teams.microsoft.com/x",
            "excerpt": "x",
        },
    ],
)
def test_normalizer_never_upgrades_missing_or_untrusted_citations(
    citation: dict[str, str] | None,
) -> None:
    payload = _completed_payload()
    payload["result"]["artifacts"] = [
        {
            "artifactId": "artifact-1",
            "parts": [
                {
                    "data": {
                        "facts": [
                            {
                                "factId": "fact-1",
                                "claim": "Untrusted claim",
                                "sourceTimestamp": "2026-08-30T17:00:00Z",
                                "authorityScope": "supplier_statement",
                                "citation": citation,
                            }
                        ]
                    }
                }
            ],
        }
    ]

    item = normalize_a2a_evidence(
        payload,
        case_id="RL-CASE-WORKIQ-2",
        analysis_id="RL-ANALYSIS-WORKIQ-2",
        retrieved_at=NOW,
        expected_source_id="x",
        expected_authority_scope=AuthorityScope.SUPPLIER_STATEMENT,
        tenant_sharepoint_host="tenant.sharepoint.com",
    ).evidence[0]

    assert item.citation_url is None
    assert item.kind is EvidenceKind.CONTEXTUAL_EVIDENCE
    assert item.requirement is EvidenceRequirement.CONTEXTUAL
    assert item.authority_scope == ()


def test_normalizer_rejects_oversized_text_and_part_bounds() -> None:
    payload = _completed_payload()
    payload["result"]["artifacts"] = [
        {
            "artifactId": "artifact-1",
            "parts": [{"text": "x" * 32_769}],
        }
    ]
    with pytest.raises(WorkIQResponseLimitError):
        normalize_a2a_evidence(
            payload,
            case_id="case",
            analysis_id="analysis",
            retrieved_at=NOW,
            expected_source_id="source",
            expected_authority_scope=AuthorityScope.SUPPLIER_STATEMENT,
            tenant_sharepoint_host="tenant.sharepoint.com",
        )


def test_free_text_is_contextual_and_never_authoritative() -> None:
    payload = _completed_payload()
    payload["result"]["artifacts"] = [
        {
            "artifactId": "artifact-free-text",
            "parts": [{"text": "A response without a tenant citation."}],
        }
    ]

    item = normalize_a2a_evidence(
        payload,
        case_id="case",
        analysis_id="analysis",
        retrieved_at=NOW,
        expected_source_id="source",
        expected_authority_scope=AuthorityScope.SUPPLIER_STATEMENT,
        tenant_sharepoint_host="tenant.sharepoint.com",
    ).evidence[0]

    assert item.kind is EvidenceKind.CONTEXTUAL_EVIDENCE
    assert item.requirement is EvidenceRequirement.CONTEXTUAL
    assert item.authority_scope == ()
    assert item.citation_url is None


def test_normalizer_rejects_excessive_part_count() -> None:
    payload = _completed_payload()
    payload["result"]["artifacts"] = [
        {
            "artifactId": "artifact-many-parts",
            "parts": [{"text": "context"} for _ in range(33)],
        }
    ]

    with pytest.raises(WorkIQResponseLimitError):
        normalize_a2a_evidence(
            payload,
            case_id="case",
            analysis_id="analysis",
            retrieved_at=NOW,
            expected_source_id="source",
            expected_authority_scope=AuthorityScope.SUPPLIER_STATEMENT,
            tenant_sharepoint_host="tenant.sharepoint.com",
        )


def test_prompts_pin_fictional_sources_and_prohibit_inference_and_web_grounding() -> (
    None
):
    supplier = supplier_signal_prompt("opaque-alpha-source")
    quality = quality_context_prompt("opaque-beta-source")

    for prompt, source in (
        (supplier, "opaque-alpha-source"),
        (quality, "opaque-beta-source"),
    ):
        assert source in prompt
        assert "DEMO CORPUS — FICTIONAL" in prompt
        assert "JSON" in prompt
        assert "citation" in prompt.lower()
        assert "do not infer" in prompt.lower()
        assert "web grounding" in prompt.lower()
    assert "supplier signal" in supplier.lower()
    assert "quality context" in quality.lower()


def test_demo_corpus_is_exact_fictional_and_contains_no_tenant_binding() -> None:
    alpha = (ROOT / "data/demo-corpus/supplier-alpha-message.md").read_text()
    beta = (ROOT / "data/demo-corpus/supplier-beta-quality-message.md").read_text()
    runbook = (ROOT / "docs/deployment/demo-corpus.md").read_text()

    assert "DEMO CORPUS — FICTIONAL" in alpha
    assert "cannot deliver 8,000 units on Scenario Day 2" in alpha
    assert "3,000 units by air on September 6 at $7.50 per unit" in alpha
    assert "no confirmed date for the remaining 5,000 units" in alpha
    assert "DEMO CORPUS — FICTIONAL" in beta
    assert "qualification is pending" in beta
    assert "audit and first article are incomplete" in beta
    assert "September 15 is the next fictional-scenario review date" in beta
    assert "Scenario Effective Time" in runbook
    assert "does not require regeneration" in runbook
    assert "Copilot Credits" in runbook
    assert "Microsoft 365 Copilot license is not required" in runbook
    assert "@willmacdonald.com" not in alpha + beta + runbook


def test_runtime_dependencies_include_httpx_and_msal() -> None:
    project_text = (ROOT / "pyproject.toml").read_text()
    project = tomllib.loads(project_text)
    dependencies = project["project"]["dependencies"]
    dev = project["project"]["optional-dependencies"]["dev"]

    assert "httpx>=0.28,<1" in dependencies
    assert "msal>=1.32,<2" in dependencies
    assert "httpx>=0.28,<1" not in dev
    assert any(
        marker.startswith("workiq_live:")
        for marker in project["tool"]["pytest"]["ini_options"]["markers"]
    )


LIVE_SETTINGS = (
    "SUPPLY_RESPONSE_WORKIQ_LIVE",
    "SUPPLY_RESPONSE_ALLOWED_TENANT_ID",
    "SUPPLY_RESPONSE_API_CLIENT_ID",
    "SUPPLY_RESPONSE_API_CLIENT_SECRET",
    "SUPPLY_RESPONSE_ALEX_OBJECT_ID",
    "SUPPLY_RESPONSE_WORKIQ_ALEX_ASSERTION_FILE",
    "SUPPLY_RESPONSE_WORKIQ_ALPHA_SOURCE_ID",
    "SUPPLY_RESPONSE_WORKIQ_BETA_SOURCE_ID",
    "SUPPLY_RESPONSE_WORKIQ_TENANT_SHAREPOINT_HOST",
    "SUPPLY_RESPONSE_WORKIQ_ALEX_STORAGE_STATE_FILE",
)


def _run_live_probe(overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    for name in LIVE_SETTINGS:
        environment.pop(name, None)
    environment.update(overrides)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_workiq_live.py",
            "-q",
            "-m",
            "workiq_live",
            "-rs",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_workiq_live_test_skips_when_unconfigured() -> None:
    result = _run_live_probe({})

    assert result.returncode == 0
    assert "SKIPPED" in result.stdout
    assert "not configured" in result.stdout


def test_workiq_live_test_fails_closed_on_partial_configuration() -> None:
    result = _run_live_probe({"SUPPLY_RESPONSE_WORKIQ_LIVE": "1"})

    assert result.returncode != 0
    assert "Work IQ live settings must be configured together" in (
        result.stdout + result.stderr
    )
