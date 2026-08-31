from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jwt
import pytest

from apps.api.app.auth import (
    AuthService,
    AuthenticatedActor,
    PersonaBinding,
    UserAssertion,
)
from data.domain.evidence import AuthorityScope, EvidenceRequirement, UncertaintyState
from integrations.workiq.citations import (
    CitationExpectation,
    CitationNavigationError,
    PlaywrightCitationVerifier,
)
from integrations.workiq.client import WorkIQEvidencePort
from integrations.workiq.errors import WorkIQProtocolError
from integrations.workiq.normalizer import normalize_a2a_evidence
from integrations.workiq.obo import WorkIQAuthenticationError, WorkIQOboExchange
from tests.auth.test_token_authorization import (
    ALEX_OID,
    API_CLIENT_ID,
    FixtureHttp,
    JORDAN_OID,
    NOW,
    PRIVATE_KEY,
    TENANT_ID,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "fixtures" / "workiq"
RETRIEVED_AT = datetime(2026, 8, 31, 18, 0, tzinfo=UTC)
TAYLOR_OID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


class ConfidentialClientFixture:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def acquire_token_on_behalf_of(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "access_token": "downstream-secret",
            "token_type": "Bearer",
            "scope": "WorkIQAgent.Ask",
        }


def _actor(*, persona: str = "alex", **claims: Any) -> AuthenticatedActor:
    _, actor = _actor_and_service(persona=persona, **claims)
    return actor


def _actor_and_service(
    *, persona: str = "alex", **claims: Any
) -> tuple[AuthService, AuthenticatedActor]:
    fixture_http = FixtureHttp()
    bindings = (
        PersonaBinding.alex(TENANT_ID, ALEX_OID),
        PersonaBinding(
            tenant_id=TENANT_ID,
            object_id=JORDAN_OID,
            persona_id="RL-PERSONA-JORDAN",
            allowed_roles=("quality_approver",),
            source_id="RL-ENTRA-JORDAN",
        ),
        PersonaBinding(
            tenant_id=TENANT_ID,
            object_id=TAYLOR_OID,
            persona_id="RL-PERSONA-TAYLOR",
            allowed_roles=("finance_approver",),
            source_id="RL-ENTRA-TAYLOR",
        ),
    )
    service = AuthService(
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        bindings=bindings,
        http_get=fixture_http,
        now=lambda: NOW.timestamp(),
    )
    default_claims: dict[str, Any] = {
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "aud": API_CLIENT_ID,
        "iat": int(NOW.timestamp()) - 5,
        "nbf": int(NOW.timestamp()) - 5,
        "exp": int(NOW.timestamp()) + 300,
        "tid": TENANT_ID,
        "oid": {
            "alex": ALEX_OID,
            "jordan": JORDAN_OID,
            "taylor": TAYLOR_OID,
        }[persona],
        "roles": (
            ["material_planner", "response_approver"]
            if persona == "alex"
            else ["quality_approver"]
            if persona == "jordan"
            else ["finance_approver"]
        ),
        "scp": "access_as_user",
    }
    default_claims.update(claims)
    token = jwt.encode(
        default_claims,
        PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "fixture-key", "typ": "JWT"},
    )
    return service, service.authenticate(token)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def _normalize(
    payload: dict[str, Any],
    *,
    source_id: str = "fixture-source-alpha",
    scope: AuthorityScope = AuthorityScope.SUPPLIER_STATEMENT,
    tenant_host: str = "tenant.sharepoint.com",
):
    return normalize_a2a_evidence(
        payload,
        case_id="case",
        analysis_id="analysis",
        retrieved_at=RETRIEVED_AT,
        expected_source_id=source_id,
        expected_authority_scope=scope,
        tenant_sharepoint_host=tenant_host,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda fact: fact["citation"].update({"sourceId": "wrong-source"}),
        lambda fact: fact.update({"authorityScope": "collaboration_statement"}),
        lambda fact: fact["citation"].update(
            {"url": "https://other-tenant.sharepoint.com/sites/demo/item"}
        ),
    ],
)
def test_authority_is_bound_to_requested_source_purpose_and_tenant(mutation) -> None:
    payload = _fixture("supplier-alpha-a2a.json")
    fact = payload["result"]["artifacts"][0]["parts"][0]["data"]["facts"][0]
    mutation(fact)

    item = _normalize(payload).evidence[0]

    assert item.requirement is EvidenceRequirement.CONTEXTUAL
    assert item.uncertainty_state is UncertaintyState.UNCERTAIN


@pytest.mark.anyio
async def test_application_port_returns_typed_evidence_and_lineage() -> None:
    class Obo:
        def exchange(self, actor):
            assert actor.persona_id == "RL-PERSONA-ALEX"

            class Token:
                def reveal(self) -> str:
                    return "token"

            return Token()

    class Client:
        async def send_message(self, prompt: str, *, access_token: str):
            return _fixture("supplier-alpha-a2a.json")

    port = WorkIQEvidencePort(
        client=Client(),  # type: ignore[arg-type]
        obo=Obo(),  # type: ignore[arg-type]
        tenant_sharepoint_host="tenant.sharepoint.com",
    )
    retrieval = await port.retrieve_supplier_signal(
        actor=_actor(),
        source_id="fixture-source-alpha",
        case_id="case",
        analysis_id="analysis",
        retrieved_at=RETRIEVED_AT,
    )

    assert retrieval.lineage.context_id == "fixture-context-alpha"
    assert retrieval.lineage.task_id == "fixture-task-alpha"
    assert retrieval.lineage.artifact_ids == ("fixture-artifact-alpha",)
    assert retrieval.lineage.source_ids == ("fixture-source-alpha",)
    assert retrieval.evidence[0].evidence_id == "RL-E-WORKIQ-ALPHA-1"
    assert "token" not in repr(retrieval)


def test_user_assertion_cannot_be_constructed_outside_authentication() -> None:
    with pytest.raises(TypeError):
        UserAssertion("forged")

    with pytest.raises(TypeError):
        AuthenticatedActor(
            tenant_id=TENANT_ID,
            object_id=ALEX_OID,
            persona_id="RL-PERSONA-ALEX",
            effective_roles=("material_planner", "response_approver"),
            display_name="Alex",
            user_principal_name="alex@example.invalid",
            source_id="RL-ENTRA-ALEX",
            bearer_assertion="forged",
        )


def test_obo_accepts_only_authenticated_alex_with_exact_lineage() -> None:
    client = ConfidentialClientFixture()
    service, alex = _actor_and_service()
    token = WorkIQOboExchange(client, auth_service=service).exchange(alex)

    assert token.reveal() == "downstream-secret"
    assert len(client.calls) == 1

    for actor in (
        _actor(persona="jordan"),
        _actor(persona="taylor"),
        object(),
    ):
        with pytest.raises(WorkIQAuthenticationError):
            WorkIQOboExchange(client, auth_service=service).exchange(actor)  # type: ignore[arg-type]
    assert len(client.calls) == 1


def test_obo_rejects_actor_authenticated_by_a_different_auth_service() -> None:
    client = ConfidentialClientFixture()
    expected_service, _ = _actor_and_service()
    _, other_actor = _actor_and_service()

    with pytest.raises(WorkIQAuthenticationError):
        WorkIQOboExchange(client, auth_service=expected_service).exchange(other_actor)

    assert client.calls == []


def test_imported_or_caller_supplied_proofs_cannot_fabricate_obo_actor() -> None:
    import apps.api.app.auth as auth_module

    client = ConfidentialClientFixture()
    service, _ = _actor_and_service()
    assert not hasattr(auth_module, "_AUTHENTICATION_PROOF")

    with pytest.raises(TypeError):
        AuthenticatedActor(
            tenant_id=TENANT_ID,
            object_id=ALEX_OID,
            persona_id="RL-PERSONA-ALEX",
            effective_roles=("material_planner", "response_approver"),
            display_name="Alex",
            user_principal_name="alex@example.invalid",
            source_id="RL-ENTRA-ALEX",
            bearer_assertion="forged",
            _proof=object(),
        )

    fabricated = AuthenticatedActor._from_auth_service(
        tenant_id=TENANT_ID,
        object_id=ALEX_OID,
        persona_id="RL-PERSONA-ALEX",
        effective_roles=("material_planner", "response_approver"),
        display_name="Alex",
        user_principal_name="alex@example.invalid",
        source_id="RL-ENTRA-ALEX",
        bearer_assertion="forged",
        auth_service_capability=object(),
    )
    with pytest.raises(WorkIQAuthenticationError):
        WorkIQOboExchange(client, auth_service=service).exchange(fabricated)

    assert client.calls == []


@pytest.mark.parametrize("bad_claims", [{"tid": "wrong"}, {"scp": None}])
def test_untrusted_assertions_never_reach_confidential_client(bad_claims) -> None:
    client = ConfidentialClientFixture()
    with pytest.raises(Exception):
        _actor(**bad_claims)
    assert client.calls == []


def test_authenticated_actor_cannot_be_mutated_into_alex() -> None:
    jordan = _actor(persona="jordan")
    with pytest.raises(AttributeError):
        jordan.persona_id = "RL-PERSONA-ALEX"


def test_actor_fields_cannot_replace_auth_service_bound_authorization() -> None:
    client = ConfidentialClientFixture()
    service, jordan = _actor_and_service(persona="jordan")
    object.__setattr__(jordan, "persona_id", "RL-PERSONA-ALEX")
    object.__setattr__(jordan, "source_id", "RL-ENTRA-ALEX")
    object.__setattr__(
        jordan,
        "effective_roles",
        ("material_planner", "response_approver"),
    )

    with pytest.raises(WorkIQAuthenticationError):
        WorkIQOboExchange(client, auth_service=service).exchange(jordan)

    assert client.calls == []


def test_obo_rejects_authenticated_actor_from_another_tenant() -> None:
    client = ConfidentialClientFixture()
    service, _ = _actor_and_service()
    with pytest.raises(WorkIQAuthenticationError):
        WorkIQOboExchange(
            client,
            auth_service=service,
        ).exchange(_actor())
    assert client.calls == []


@pytest.mark.parametrize(
    "attack", ["application-only", "wrong-tenant", "bad-signature"]
)
def test_live_style_authentication_gate_blocks_untrusted_tokens_before_obo(
    attack: str,
) -> None:
    fixture_http = FixtureHttp()
    service = AuthService(
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        bindings=(PersonaBinding.alex(TENANT_ID, ALEX_OID),),
        http_get=fixture_http,
        now=lambda: NOW.timestamp(),
    )
    claims: dict[str, Any] = {
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "aud": API_CLIENT_ID,
        "iat": int(NOW.timestamp()) - 5,
        "nbf": int(NOW.timestamp()) - 5,
        "exp": int(NOW.timestamp()) + 300,
        "tid": TENANT_ID,
        "oid": ALEX_OID,
        "roles": ["material_planner", "response_approver"],
        "scp": "access_as_user",
    }
    if attack == "application-only":
        claims.pop("scp")
    elif attack == "wrong-tenant":
        claims["tid"] = "33333333-3333-4333-8333-333333333333"
    token = jwt.encode(
        claims,
        PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "fixture-key", "typ": "JWT"},
    )
    if attack == "bad-signature":
        header, payload, signature = token.split(".")
        token = ".".join((header, payload, f"A{signature[1:]}"))
    client = ConfidentialClientFixture()
    obo = WorkIQOboExchange(client, auth_service=service)

    with pytest.raises(Exception):
        obo.exchange(service.authenticate(token))
    assert client.calls == []


def test_generated_ids_include_part_and_fact_indexes() -> None:
    payload = _fixture("supplier-alpha-a2a.json")
    artifact = payload["result"]["artifacts"][0]
    first = artifact["parts"][0]["data"]["facts"][0]
    first.pop("factId")
    artifact["parts"].append({"data": {"facts": [dict(first)]}})

    retrieval = _normalize(payload)

    assert [item.evidence_id for item in retrieval.evidence] == [
        "fixture-artifact-alpha:part:0:fact:0",
        "fixture-artifact-alpha:part:1:fact:0",
    ]


@pytest.mark.parametrize("duplicate_kind", ["artifact", "fact", "source-conflict"])
def test_ambiguous_duplicate_response_ids_are_rejected(duplicate_kind: str) -> None:
    payload = _fixture("supplier-alpha-a2a.json")
    artifact = payload["result"]["artifacts"][0]
    if duplicate_kind == "artifact":
        payload["result"]["artifacts"].append(json.loads(json.dumps(artifact)))
    else:
        duplicate = json.loads(json.dumps(artifact["parts"][0]["data"]["facts"][0]))
        if duplicate_kind == "source-conflict":
            duplicate["factId"] = "RL-E-WORKIQ-ALPHA-2"
            duplicate["citation"]["url"] = "https://outlook.office.com/other"
        artifact["parts"][0]["data"]["facts"].append(duplicate)

    with pytest.raises(WorkIQProtocolError, match="duplicate|ambiguous"):
        _normalize(payload)


def test_final_evidence_ids_cannot_collide_across_text_and_fact_parts() -> None:
    payload = _fixture("supplier-alpha-a2a.json")
    artifact = payload["result"]["artifacts"][0]
    artifact["parts"].append(
        {
            "text": "context",
            "data": {
                "facts": [
                    {
                        "factId": "fixture-artifact-alpha:text:1",
                        "claim": "collision",
                    }
                ]
            },
        }
    )

    with pytest.raises(WorkIQProtocolError, match="duplicate"):
        _normalize(payload)


@pytest.mark.anyio
async def test_playwright_verifier_rejects_broken_login_and_off_host_results() -> None:
    outcomes = [
        {"ok": False, "reason": "status", "status": 404},
        {"ok": False, "reason": "off_host", "url": "https://login.microsoftonline.com"},
        {"ok": False, "reason": "off_host", "url": "https://evil.example"},
    ]

    async def runner(*args: str, input_text: str) -> str:
        del args, input_text
        return json.dumps(outcomes.pop(0))

    verifier = PlaywrightCitationVerifier(
        storage_state_path=Path("/private/tmp/alex-state.json"),
        tenant_sharepoint_host="tenant.sharepoint.com",
        runner=runner,
    )
    for url in (
        "https://teams.microsoft.com/l/message/x/y",
        "https://outlook.office.com/mail/x",
        "https://tenant.sharepoint.com/sites/x",
    ):
        with pytest.raises(CitationNavigationError):
            await verifier.verify(
                (
                    CitationExpectation(
                        url=url,
                        expected_excerpt=(
                            "Qualification remains pending and the audit is incomplete."
                        ),
                        source_identity="fixture-source",
                    ),
                )
            )


def test_javascript_citation_policy_exercises_real_security_and_content_checks() -> (
    None
):
    result = subprocess.run(
        [
            "node",
            "--test",
            str(
                ROOT
                / "apps"
                / "web"
                / "scripts"
                / "citation-verification-policy.test.mjs"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
