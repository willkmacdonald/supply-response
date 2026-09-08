from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agents.orchestrator.contracts import RetrievalLineage
from agents.orchestrator.local import LocalAgentSet
from agents.orchestrator.workflow import Orchestrator
from apps.api.app.dependencies import build_composition, build_live_components
from apps.api.app.live import LiveAnalysisApplicationService
from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from data.domain.analysis import AnalysisRetrievalLineage
from integrations.workiq.mcp import WorkIQMcpClient
from integrations.workiq.mcp_evidence import WorkIQMcpEvidencePort
from services.analysis.service import analyze_case
from services.persistence.sqlite import sqlite_store
from services.persistence.tables import analysis_claims
from tests.auth.test_token_authorization import ALEX_OID, API_CLIENT_ID, TENANT_ID
from tests.integration.test_live_hardening import ExplicitLiveOperationalPort
from tests.integration.test_workiq_async_obo import Entra, exchange
from tests.integration.test_workiq_contract import _authenticated_alex
from tests.integration.test_workiq_mcp_transport import INIT, reply
from tests.integration.test_workiq_message_evidence import (
    BINDING,
    MAIL,
    MAIL_LINK,
    QUALITY,
    TEAMS_LINK,
)

NOW = datetime(2026, 8, 31, 18, tzinfo=UTC)


def _live_settings(tmp_path, **updates: object) -> Settings:
    values: dict[str, object] = {
        "runtime_mode": RuntimeMode.LIVE,
        "allowed_tenant_id": TENANT_ID,
        "api_client_id": API_CLIENT_ID,
        "alex_object_id": ALEX_OID,
        "entra_client_secret": "fixture-secret",
        "fabric_sql_server": "fixture.database.fabric.microsoft.com",
        "fabric_sql_database": "fixture",
        "credential_mode": "managed_identity",
        "tenant_sharepoint_host": "tenant.sharepoint.com",
        "workiq_supplier_source_id": "mail-fixture",
        "workiq_quality_source_id": "1770000000000",
        "workiq_corpus_version": "fixture-corpus-v1",
        "workiq_supplier_sender": "dispatch@alpha.example",
        "workiq_quality_author_object_id": ("44444444-4444-4444-8444-444444444444"),
        "workiq_team_id": "55555555-5555-4555-8555-555555555555",
        "workiq_channel_id": "19:channel-fixture@thread.tacv2",
        "foundry_project_endpoint": (
            "https://fixture.services.ai.azure.com/api/projects/supply-response"
        ),
        "foundry_signal_agent_name": "signal-agent",
        "foundry_signal_agent_version": "1",
        "foundry_context_agent_name": "context-agent",
        "foundry_context_agent_version": "1",
        "foundry_decision_agent_name": "decision-agent",
        "foundry_decision_agent_version": "1",
        "power_bi_report_url": "https://app.powerbi.com/groups/demo/reports/report",
        "fabric_citation_base_url": (
            "https://app.powerbi.com/groups/demo/reports/report"
        ),
        "power_bi_deployment_receipt": hashlib.sha256(
            b"https://app.powerbi.com/groups/demo/reports/report"
        ).hexdigest(),
    }
    values.update(updates)
    receipt_parts = (
        "workiq-binding-v2",
        str(values["workiq_corpus_version"]),
        str(values["workiq_supplier_source_id"]),
        str(values["workiq_quality_source_id"]),
        str(values["workiq_supplier_sender"]),
        str(values["workiq_quality_author_object_id"]),
        str(values["workiq_team_id"]),
        str(values["workiq_channel_id"]),
    )
    values.setdefault(
        "workiq_deployment_receipt",
        hashlib.sha256("\n".join(receipt_parts).encode()).hexdigest(),
    )
    values.setdefault("database_url", f"sqlite:///{tmp_path / 'unused.db'}")
    return Settings.model_validate(values)


def _offline_fabric(monkeypatch, tmp_path):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'composition.db'}", runtime_mode=RuntimeMode.LIVE
    )
    monkeypatch.setattr(
        "services.persistence.fabric_sql.build_credential", lambda settings: object()
    )
    monkeypatch.setattr(
        "services.persistence.fabric_sql.fabric_store",
        lambda settings, credential: store,
    )
    return store


def _forbid_live_resource_construction(monkeypatch) -> list[str]:
    started: list[str] = []

    def forbidden(name: str):
        def fail(*args, **kwargs):
            started.append(name)
            raise AssertionError(f"{name} constructed before receipt validation")

        return fail

    for path, name in (
        ("services.persistence.fabric_sql.build_credential", "fabric credential"),
        ("apps.api.app.dependencies.fabric_store", "fabric store"),
        (
            "integrations.fabric.operational.FabricLiveOperationalDataPort",
            "fabric source",
        ),
        ("integrations.workiq.async_obo.AsyncWorkIQOboExchange", "OBO exchange"),
        ("integrations.workiq.mcp.WorkIQMcpClient", "MCP client"),
        ("integrations.workiq.mcp_evidence.WorkIQMcpEvidencePort", "MCP source"),
    ):
        monkeypatch.setattr(path, forbidden(name))
    return started


def test_live_composition_uses_mcp_evidence_with_all_trusted_bindings(
    monkeypatch, tmp_path
):
    store = _offline_fabric(monkeypatch, tmp_path)
    components = build_live_components(
        _live_settings(tmp_path), clock=lambda: datetime.now(UTC)
    )
    try:
        port = components["analysis_service"]._work_iq
        assert isinstance(port, WorkIQMcpEvidencePort)
        assert port._binding.supplier_sender == "dispatch@alpha.example"
        assert port._binding.quality_author_object_id == (
            "44444444-4444-4444-8444-444444444444"
        )
        assert port._binding.team_id == "55555555-5555-4555-8555-555555555555"
        assert port._binding.channel_id == "19:channel-fixture@thread.tacv2"
        assert components["readiness"].check().capability_health["work_iq"] == "ready"
    finally:
        import asyncio

        asyncio.run(components["async_resources"][0].aclose())
        store.engine.dispose()


@pytest.mark.parametrize(
    "receipt",
    [
        None,
        hashlib.sha256(b"fixture-corpus-v1\nmail-fixture\n1770000000000").hexdigest(),
        "0" * 64,
    ],
    ids=("missing", "legacy-v1", "mismatched-v2"),
)
def test_live_composition_rejects_invalid_workiq_receipt_before_resources_begin(
    monkeypatch, tmp_path, receipt
):
    started = _forbid_live_resource_construction(monkeypatch)

    with pytest.raises(
        RuntimeError,
        match="^live dependency binding receipt is invalid: workiq$",
    ):
        build_live_components(
            _live_settings(tmp_path, workiq_deployment_receipt=receipt),
            clock=lambda: datetime.now(UTC),
        )

    assert started == []


def test_fallback_composition_does_not_require_workiq_receipt(monkeypatch, tmp_path):
    started = _forbid_live_resource_construction(monkeypatch)

    services = build_composition(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'fallback.db'}",
        ),
        clock=lambda: NOW,
    )

    assert services.settings.runtime_mode is RuntimeMode.FALLBACK
    assert started == []
    services.store.engine.dispose()


@pytest.mark.parametrize(
    "missing",
    [
        "workiq_supplier_sender",
        "workiq_quality_author_object_id",
        "workiq_team_id",
        "workiq_channel_id",
    ],
)
def test_live_composition_rejects_missing_discovery_binding_before_store_access(
    monkeypatch, tmp_path, missing
):
    accessed = False

    def forbidden_store(*args, **kwargs):
        nonlocal accessed
        accessed = True
        raise AssertionError("live store opened before binding validation")

    monkeypatch.setattr("services.persistence.fabric_sql.fabric_store", forbidden_store)
    with pytest.raises(RuntimeError, match=f"setting is missing: {missing}"):
        build_live_components(
            _live_settings(tmp_path, **{missing: ""}),
            clock=lambda: datetime.now(UTC),
        )
    assert accessed is False


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("workiq_supplier_sender", "not-an-email"),
        ("workiq_quality_author_object_id", "not-a-uuid"),
        ("workiq_team_id", "not-a-uuid"),
        ("workiq_channel_id", "channel-only"),
    ],
)
def test_live_composition_rejects_malformed_discovery_binding_before_store_access(
    monkeypatch, tmp_path, name, value
):
    accessed = False

    def forbidden_store(*args, **kwargs):
        nonlocal accessed
        accessed = True
        raise AssertionError("live store opened before binding validation")

    monkeypatch.setattr("services.persistence.fabric_sql.fabric_store", forbidden_store)
    with pytest.raises(RuntimeError, match=f"setting is invalid: {name}"):
        build_live_components(
            _live_settings(tmp_path, **{name: value}),
            clock=lambda: datetime.now(UTC),
        )
    assert accessed is False


def test_new_mcp_and_old_a2a_lineage_are_both_accepted():
    old_domain = AnalysisRetrievalLineage.model_validate(
        {
            "source_kind": "supplier",
            "context_id": "context",
            "task_id": "task",
            "artifact_ids": ["artifact"],
            "source_ids": ["source"],
        }
    )
    old_agent = RetrievalLineage.model_validate(
        old_domain.model_dump(exclude={"source_kind"})
    )
    assert old_domain.protocol == old_agent.protocol == "a2a"
    assert old_domain.request_ids == old_agent.request_ids == ()

    new_domain = AnalysisRetrievalLineage(
        source_kind="quality",
        context_id="conversation",
        task_id="",
        artifact_ids=(),
        source_ids=("message",),
        protocol="mcp",
        request_ids=("initialize", "ask", "fetch"),
    )
    new_agent = RetrievalLineage.model_validate(
        new_domain.model_dump(exclude={"source_kind"})
    )
    assert new_agent.protocol == "mcp"
    assert new_agent.task_id == "" and new_agent.artifact_ids == ()
    assert new_agent.request_ids == ("initialize", "ask", "fetch")


class _McpServer:
    def __init__(self, *, fail_kind: str | None = None) -> None:
        self.requests: list[dict[str, Any]] = []
        self.fail_kind = fail_kind
        self.mail = deepcopy(MAIL)
        self.mail["receivedDateTime"] = "2026-08-31T12:00:00Z"
        self.quality = deepcopy(QUALITY)
        self.quality["createdDateTime"] = "2026-08-31T12:05:00Z"

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        if body["method"] == "initialize":
            return reply(request, INIT)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        arguments = body["params"]["arguments"]
        if body["params"]["name"] == "ask":
            quality = "Jordan" in arguments["question"]
            result = {
                "answer": TEAMS_LINK if quality else MAIL_LINK,
                "conversationId": (
                    "quality-conversation" if quality else "supplier-conversation"
                ),
            }
        else:
            path = arguments["entityUrls"][0]
            quality = path.startswith("/teams/")
            kind = "quality" if quality else "supplier"
            result = {
                "results": [
                    {
                        "statusCode": 404 if kind == self.fail_kind else 200,
                        "data": (
                            {"diagnostic": "private-upstream-body"}
                            if kind == self.fail_kind
                            else self.quality
                            if quality
                            else self.mail
                        ),
                    }
                ]
            }
        return reply(request, {"structuredContent": result})

    def tool_calls(self, name: str) -> list[dict[str, Any]]:
        return [
            request["params"]["arguments"]
            for request in self.requests
            if request["method"] == "tools/call" and request["params"]["name"] == name
        ]


def _mcp_live_app(monkeypatch, tmp_path, *, fail_kind: str | None = None):
    def forbidden(*args, **kwargs):
        pytest.fail("normal live Analyze attempted an unmocked network request")

    monkeypatch.setattr("socket.getaddrinfo", forbidden)
    auth_service, actor = _authenticated_alex()
    entra = Entra()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", entra.transport)
    server = _McpServer(fail_kind=fail_kind)
    mcp_http = httpx.AsyncClient(transport=httpx.MockTransport(server))
    port = WorkIQMcpEvidencePort(
        client=WorkIQMcpClient(http=mcp_http),
        obo=exchange(auth_service),
        binding=BINDING,
    )
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'mcp-live.db'}", runtime_mode=RuntimeMode.LIVE
    )
    operational = ExplicitLiveOperationalPort()
    analysis_service = LiveAnalysisApplicationService(
        store=store,
        operational_data=operational,
        work_iq=port,
        orchestrator=Orchestrator(LocalAgentSet.deterministic, analyze_case),
        supplier_source_id=BINDING.supplier_source_id,
        quality_source_id=BINDING.quality_source_id,
        tenant_sharepoint_host="tenant.sharepoint.com",
        clock=lambda: NOW,
    )
    services = build_composition(
        _live_settings(tmp_path),
        clock=lambda: NOW,
        live_components={
            "store": store,
            "analysis_service": analysis_service,
            "auth_service": auth_service,
            "power_bi_url": "https://app.powerbi.com/groups/demo/reports/report",
            "operational_data": operational,
            "async_resources": (mcp_http,),
        },
    )
    return create_app(services=services), actor, server, entra, store


def test_signed_alex_normal_live_analyze_discovers_and_fetches_both_sources(
    monkeypatch, tmp_path
):
    app, actor, server, entra, store = _mcp_live_app(monkeypatch, tmp_path)
    headers = {"Authorization": f"Bearer {actor.downstream_user_assertion.reveal()}"}
    with TestClient(app) as client:
        case = client.post(
            "/api/cases",
            json={"template_id": "RL-001", "purpose": "showcase"},
            headers=headers,
        )
        response = client.post(
            f"/api/cases/{case.json()['case_id']}/analysis", headers=headers
        )

    assert response.status_code == 201, response.json()
    workiq = [
        item
        for item in response.json()["evidence_items"]
        if item["source_system"] == "work_iq"
    ]
    assert {item["claim"] for item in workiq} == {
        "Alpha can dispatch 73 units. Arrival remains unconfirmed & provisional.",
        "Beta evaluation covers lot Z-47 only. Further review remains open.",
    }
    assert all(item["citation_classification"] == "work_iq" for item in workiq)
    assert {item["authority_scope"][0] for item in workiq} == {
        "supplier_statement",
        "collaboration_statement",
    }
    analysis = store.get_analysis(response.json()["analysis_id"])
    assert {item.protocol for item in analysis.retrieval_lineage} == {"mcp"}
    assert all(
        not item.task_id and not item.artifact_ids
        for item in analysis.retrieval_lineage
    )
    assert all(len(item.request_ids) == 3 for item in analysis.retrieval_lineage)
    asks = server.tool_calls("ask")
    assert len(asks) == 2 and len(server.tool_calls("fetch")) == 2
    for forbidden_value in (
        BINDING.supplier_source_id,
        BINDING.quality_source_id,
        BINDING.alex_object_id,
        BINDING.team_id,
        "73",
        "Z-47",
    ):
        assert forbidden_value not in str(asks)
    assert all(
        request.url.host == "login.microsoftonline.com" for request in entra.requests
    )


def test_mcp_source_stage_survives_safe_503_and_releases_analysis_claim(
    monkeypatch, tmp_path
):
    app, actor, _server, _entra, store = _mcp_live_app(
        monkeypatch, tmp_path, fail_kind="quality"
    )
    headers = {"Authorization": f"Bearer {actor.downstream_user_assertion.reveal()}"}
    with TestClient(app) as client:
        case_id = client.post(
            "/api/cases",
            json={"template_id": "RL-001", "purpose": "showcase"},
            headers=headers,
        ).json()["case_id"]
        response = client.post(f"/api/cases/{case_id}/analysis", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "LIVE_SOURCE_UNAVAILABLE",
        "new_fallback_case_allowed": True,
        "source_kind": "quality",
        "stage": "fetch",
    }
    assert "private-upstream-body" not in response.text
    with store.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(analysis_claims)) == 0
