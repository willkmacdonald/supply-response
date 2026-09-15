from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from agents.orchestrator.local import LocalAgentSet
from agents.orchestrator.workflow import Orchestrator
from apps.api.app.auth import AuthService, PersonaBinding
from apps.api.app.dependencies import build_composition
from apps.api.app.live import LiveAnalysisApplicationService
from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.synthetic.rl001 import instantiate_rl001
from services.analysis.service import analyze_case
from services.persistence.sqlite import sqlite_store
from tests.auth.test_token_authorization import PRIVATE_KEY
from tests.integration.test_live_case_contract import FakeWorkIQ
from tests.integration.test_live_hardening import NOW as LIVE_NOW
from tests.integration.test_live_hardening import ExplicitLiveOperationalPort

TENANT = "11111111-1111-4111-8111-111111111111"
CLIENT = "22222222-2222-4222-8222-222222222222"
ALEX = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TAYLOR = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
NOW = datetime(2026, 9, 13, 15, tzinfo=UTC)


def _auth() -> AuthService:
    private = serialization.load_pem_private_key(PRIVATE_KEY, password=None)
    assert isinstance(private, rsa.RSAPrivateKey)
    jwk: dict[str, Any] = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid="fixture-key", use="sig", alg="RS256")
    issuer = f"https://login.microsoftonline.com/{TENANT}/v2.0"
    jwks = f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys"

    def get(url: str):
        if url.endswith("openid-configuration"):
            return {"issuer": issuer, "jwks_uri": jwks}
        return {"keys": [jwk]}

    return AuthService(
        tenant_id=TENANT,
        audience=CLIENT,
        bindings=(
            PersonaBinding.alex(TENANT, ALEX),
            PersonaBinding.taylor(TENANT, TAYLOR),
        ),
        http_get=get,
        now=lambda: NOW.timestamp(),
    )


def _token(*, taylor: bool = False) -> str:
    issuer = f"https://login.microsoftonline.com/{TENANT}/v2.0"
    return jwt.encode(
        {
            "iss": issuer,
            "aud": CLIENT,
            "iat": int(NOW.timestamp()) - 1,
            "nbf": int(NOW.timestamp()) - 1,
            "exp": int(NOW.timestamp()) + 300,
            "tid": TENANT,
            "oid": TAYLOR if taylor else ALEX,
            "roles": ["finance_approver"]
            if taylor
            else ["material_planner", "response_approver"],
            "scp": "access_as_user",
            "name": "Taylor" if taylor else "Alex",
        },
        PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "fixture-key"},
    )


def test_verified_session_and_planner_boundary(tmp_path):
    settings = Settings(
        runtime_mode=RuntimeMode.LIVE,
        allowed_tenant_id=TENANT,
        credential_mode="managed_identity",
        fabric_sql_server="fixture",
        fabric_sql_database="fixture",
        api_client_id=CLIENT,
        alex_object_id=ALEX.upper(),
        taylor_object_id=TAYLOR,
        independent_finance_enabled=True,
        automated_test_faults_enabled=True,
    )
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'journey.db'}", runtime_mode=RuntimeMode.LIVE
    )
    services = build_composition(
        settings,
        clock=lambda: LIVE_NOW,
        live_components={
            "store": store,
            "analysis_service": object(),
            "auth_service": _auth(),
            "power_bi_url": "https://app.powerbi.com/fixture",
        },
    )
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-HTTP",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.LIVE,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    store.create_case(case, snapshot)
    live_analysis = LiveAnalysisApplicationService(
        store=store,
        operational_data=ExplicitLiveOperationalPort(),
        work_iq=FakeWorkIQ(),
        orchestrator=Orchestrator(LocalAgentSet.deterministic, analyze_case),
        supplier_source_id="source-alpha",
        quality_source_id="source-quality",
        fabric_citation_base_url="https://app.powerbi.com/groups/demo/reports/report",
        clock=lambda: LIVE_NOW,
    )
    asyncio.run(
        live_analysis.create(case.case_id, actor=_auth().authenticate(_token()))
    )
    with TestClient(create_app(services=services)) as client:
        alex = {"Authorization": f"Bearer {_token()}"}
        taylor = {"Authorization": f"Bearer {_token(taylor=True)}"}
        assert client.get("/api/me", headers=alex).json() == {
            "mode": "entra",
            "persona_id": "RL-PERSONA-ALEX",
            "display_name": "Alex",
            "independent_finance_enabled": True,
        }
        planner_routes = (
            (
                "POST",
                "/api/cases",
                {"template_id": "RL-001", "purpose": "automated_test"},
            ),
            ("GET", "/api/cases", None),
            ("GET", "/api/cases/missing", None),
            ("POST", "/api/cases/missing/analysis", None),
            ("GET", "/api/cases/missing/analysis", None),
            (
                "POST",
                "/api/cases/missing/decisions",
                {
                    "analysis_id": "missing",
                    "kind": "approved",
                    "selected_option_id": "missing",
                },
            ),
            ("GET", "/api/decisions/missing", None),
            ("POST", "/api/decisions/missing/actions/retry", {}),
            ("GET", "/api/decisions/missing/actions", None),
            ("POST", "/api/decisions/missing/actions/missing/retry", None),
            ("GET", "/api/decisions/missing/drafts", None),
            ("POST", "/api/decisions/missing/playback", None),
            ("GET", "/api/decisions/missing/playback", None),
            ("GET", "/api/decisions/missing/observations", None),
            ("GET", "/api/dashboard/cases", None),
            ("POST", "/api/test/cases/missing/faults/planning_failure", None),
        )
        for method, url, body in planner_routes:
            denied = client.request(
                method,
                url,
                headers={**taylor, "Idempotency-Key": "boundary"},
                json=body,
            )
            assert denied.status_code == 403, (method, url, denied.text)
            assert denied.json()["detail"]["code"] == "PLANNER_ACCESS_REQUIRED"

        assert client.get("/api/finance/reviews", headers=alex).status_code == 403

        state = client.get("/api/cases/RL-CASE-HTTP/proposal", headers=alex).json()
        first = client.post(
            "/api/cases/RL-CASE-HTTP/proposals",
            headers={**alex, "Idempotency-Key": "submit-1"},
            json={"option_id": "RL-OPTION-COMBINED", "expected": state["token"]},
        )
        assert first.status_code == 201, first.text
        review = first.json()["review"]
        rejected = client.post(
            f"/api/finance/reviews/{review['review_id']}/resolutions",
            headers={**taylor, "Idempotency-Key": "reject-1"},
            json={
                "expected": client.get(
                    "/api/cases/RL-CASE-HTTP/proposal", headers=alex
                ).json()["token"],
                "expected_review_revision": 1,
                "approved": False,
                "reason": "Revise the mitigation package.",
            },
        )
        assert rejected.status_code == 201
        state = client.get("/api/cases/RL-CASE-HTTP/proposal", headers=alex).json()
        second = client.post(
            "/api/cases/RL-CASE-HTTP/proposals",
            headers={**alex, "Idempotency-Key": "submit-2"},
            json={"option_id": "RL-OPTION-EXPEDITE", "expected": state["token"]},
        )
        assert second.status_code == 201
        review = second.json()["review"]
        finance_reviews = client.get("/api/finance/reviews", headers=taylor)
        assert finance_reviews.status_code == 200, finance_reviews.text
        finance_list_analysis = finance_reviews.json()[0]["analysis"]
        state = client.get("/api/cases/RL-CASE-HTTP/proposal", headers=alex).json()
        approved = client.post(
            f"/api/finance/reviews/{review['review_id']}/resolutions",
            headers={**taylor, "Idempotency-Key": "approve-1"},
            json={
                "expected": state["token"],
                "expected_review_revision": 1,
                "approved": True,
            },
        )
        assert approved.status_code == 201
        finance_detail = client.get(
            f"/api/finance/reviews/{review['review_id']}", headers=taylor
        )
        assert finance_detail.status_code == 200, finance_detail.text
        finance_detail_analysis = finance_detail.json()["analysis"]
        for analysis in (finance_list_analysis, finance_detail_analysis):
            assert analysis["runtime_mode"] == "live"
            assert analysis["runtime_mode"] == analysis["material"]["runtime_mode"]
            assert (
                analysis["scenario_effective_time"]
                == analysis["material"]["scenario_effective_time"]
            )
            assert (
                analysis["recommendation"]["option_id"]
                == analysis["ranking"]["recommended_option_id"]
            )
        armed = client.post(
            "/api/test/cases/RL-CASE-HTTP/faults/planning_failure",
            headers=alex,
        )
        assert armed.status_code == 204
        state = client.get("/api/cases/RL-CASE-HTTP/proposal", headers=alex).json()
        final = client.post(
            "/api/cases/RL-CASE-HTTP/proposal-decisions",
            headers={**alex, "Idempotency-Key": "final-1"},
            json={"expected": state["token"], "kind": "approved"},
        )
        assert final.status_code == 201
        assert final.json()["action_planning_status"] == "pending"
        assert (
            final.json()["proposal_approval_evidence"]["review"]["status"] == "approved"
        )
        decision_id = final.json()["decision_id"]
        assert (
            client.get(f"/api/decisions/{decision_id}/actions", headers=alex).json()
            == []
        )
        assert services.planning_worker.process_next_unattempted_outbox() is True
        failed = client.get(f"/api/decisions/{decision_id}", headers=alex)
        assert failed.json()["action_planning_status"] == "failed"
        controls = client.get("/api/cases/RL-CASE-HTTP", headers=alex).json()[
            "controls"
        ]
        assert controls["retry_action_planning"] is True
        assert controls["start_playback"] is False
        retry = client.post(
            f"/api/decisions/{decision_id}/actions/retry", headers=alex, json={}
        )
        assert retry.status_code == 200
        assert retry.json()["action_planning_status"] == "complete"
        actions = client.get(
            f"/api/decisions/{decision_id}/actions", headers=alex
        ).json()
        assert [action["kind"] for action in actions] == [
            "prepare_alpha_recovery_draft",
            "coordinate_alpha_expedited_partial",
            "update_disruption_status",
        ]
        action_retry = client.post(
            f"/api/decisions/{decision_id}/actions/{actions[0]['action_id']}/retry",
            headers=alex,
        )
        assert action_retry.status_code == 409
        assert action_retry.json()["detail"]["code"] == "INDEPENDENT_EXECUTION_DEFERRED"
        playback = client.post(f"/api/decisions/{decision_id}/playback", headers=alex)
        assert playback.status_code == 409
        assert playback.json()["detail"]["code"] == "INDEPENDENT_EXECUTION_DEFERRED"
