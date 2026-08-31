from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents.orchestrator.local import LocalAgentSet
from agents.orchestrator.workflow import Orchestrator
from apps.api.app.dependencies import build_composition, get_actor
from apps.api.app.live import LiveAnalysisApplicationService, LiveSourceUnavailable
from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import CasePurpose, RuntimeMode
from data.domain.evidence import (
    AuthorityScope,
    EvidenceItem,
    EvidenceKind,
    EvidenceRequirement,
    EvidenceSourceSystem,
    RetrievalHealth,
    UncertaintyState,
)
from data.synthetic.rl001 import instantiate_rl001
from integrations.workiq.models import WorkIQRetrieval, WorkIQRetrievalLineage
from services.analysis.service import analyze_case
from services.execution.playback import ImmediateClock
from services.persistence.sqlite import sqlite_store
from tests.integration.test_workiq_trust_boundaries import _actor_and_service

NOW = datetime(2026, 8, 31, 18, 0, tzinfo=UTC)


class FakeWorkIQ:
    async def retrieve_supplier_signal(
        self, *, actor, source_id, case_id, analysis_id, retrieved_at
    ):
        del actor, retrieved_at
        return self._retrieval(
            {"source_id": source_id, "case_id": case_id, "analysis_id": analysis_id},
            "ALPHA",
            AuthorityScope.SUPPLIER_STATEMENT,
        )

    async def retrieve_quality_context(
        self, *, actor, source_id, case_id, analysis_id, retrieved_at
    ):
        del actor, retrieved_at
        return self._retrieval(
            {"source_id": source_id, "case_id": case_id, "analysis_id": analysis_id},
            "QUALITY",
            AuthorityScope.COLLABORATION_STATEMENT,
        )

    @staticmethod
    def _retrieval(kwargs, suffix, scope):
        item = EvidenceItem(
            evidence_id=f"RL-E-WORKIQ-{suffix}",
            case_id=kwargs["case_id"],
            kind=EvidenceKind.SOURCE_STATEMENT,
            authority_scope=(scope,),
            source_system=EvidenceSourceSystem.WORK_IQ,
            source_id=kwargs["source_id"],
            source_timestamp=NOW,
            retrieved_at=NOW,
            retrieved_for_analysis_id=kwargs["analysis_id"],
            retrieval_health=RetrievalHealth.HEALTHY,
            effective_at=NOW,
            expires_at=None,
            claim=f"Authoritative {suffix.lower()} evidence.",
            excerpt=f"Distinctive {suffix.lower()} excerpt.",
            citation_url=f"https://teams.microsoft.com/l/entity/{suffix.lower()}",
            runtime_mode=RuntimeMode.LIVE,
            synthetic=False,
            requirement=EvidenceRequirement.REQUIRED_AUTHORITATIVE,
            uncertainty_state=UncertaintyState.CERTAIN,
        )
        return WorkIQRetrieval(
            evidence=(item,),
            lineage=WorkIQRetrievalLineage(
                context_id=f"context-{suffix}",
                task_id=f"task-{suffix}",
                artifact_ids=(f"artifact-{suffix}",),
                source_ids=(kwargs["source_id"],),
            ),
        )


class BrokenWorkIQ(FakeWorkIQ):
    async def retrieve_supplier_signal(
        self, *, actor, source_id, case_id, analysis_id, retrieved_at
    ):
        del actor, source_id, case_id, analysis_id, retrieved_at
        raise TimeoutError("credential-bearing internal endpoint detail")


@pytest.fixture
def live_store(tmp_path):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'live-contract.db'}", runtime_mode=RuntimeMode.LIVE
    )
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-LIVE",
        purpose=CasePurpose.SHOWCASE,
        runtime_mode=RuntimeMode.LIVE,
    )
    store.create_case(case, snapshot)
    return store


@pytest.mark.anyio
async def test_live_analysis_uses_only_fabric_and_work_iq_provenance(live_store):
    captured_lineage = []

    class CapturingOrchestrator:
        async def analyze(self, command):
            captured_lineage.extend(command.retrieval_lineage)
            return await Orchestrator(
                LocalAgentSet.deterministic, analyze_case
            ).analyze(command)

    service = LiveAnalysisApplicationService(
        store=live_store,
        work_iq=FakeWorkIQ(),
        orchestrator=CapturingOrchestrator(),  # type: ignore[arg-type]
        supplier_source_id="source-alpha",
        quality_source_id="source-quality",
        fabric_citation_base_url="https://app.powerbi.com/groups/demo/reports/report",
        clock=lambda: NOW,
    )

    analysis = await service.create("RL-CASE-LIVE", actor=_actor_and_service()[1])

    assert analysis.material.runtime_mode is RuntimeMode.LIVE
    assert {item.source_system for item in analysis.evidence_items} == {
        EvidenceSourceSystem.FABRIC,
        EvidenceSourceSystem.WORK_IQ,
    }
    assert all(not item.synthetic for item in analysis.evidence_items)
    assert all(item.citation_url for item in analysis.evidence_items)
    assert {item.task_id for item in captured_lineage} == {
        "task-ALPHA",
        "task-QUALITY",
    }


@pytest.mark.anyio
async def test_live_source_failure_is_bounded_and_never_falls_back(live_store):
    service = LiveAnalysisApplicationService(
        store=live_store,
        work_iq=BrokenWorkIQ(),
        orchestrator=Orchestrator(LocalAgentSet.deterministic, analyze_case),
        supplier_source_id="source-alpha",
        quality_source_id="source-quality",
        fabric_citation_base_url="https://app.powerbi.com/groups/demo/reports/report",
        clock=lambda: NOW,
    )

    with pytest.raises(LiveSourceUnavailable) as caught:
        await service.create("RL-CASE-LIVE", actor=_actor_and_service()[1])

    assert caught.value.code == "LIVE_SOURCE_UNAVAILABLE"
    assert caught.value.new_fallback_case_allowed is True
    assert "credential" not in str(caught.value).lower()


@pytest.mark.anyio
async def test_concurrent_live_analysis_reuses_one_immutable_version(live_store):
    service = LiveAnalysisApplicationService(
        store=live_store,
        work_iq=FakeWorkIQ(),
        orchestrator=Orchestrator(LocalAgentSet.deterministic, analyze_case),
        supplier_source_id="source-alpha",
        quality_source_id="source-quality",
        fabric_citation_base_url="https://app.powerbi.com/groups/demo/reports/report",
        clock=lambda: NOW,
    )
    actor = _actor_and_service()[1]

    first, second = await asyncio.gather(
        service.create("RL-CASE-LIVE", actor=actor),
        service.create("RL-CASE-LIVE", actor=actor),
    )

    assert first.analysis_id == second.analysis_id


def _live_app(tmp_path, work_iq):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'live-api.db'}", runtime_mode=RuntimeMode.LIVE
    )
    auth_service, actor = _actor_and_service()
    clock = ImmediateClock(NOW)
    analysis_service = LiveAnalysisApplicationService(
        store=store,
        work_iq=work_iq,
        orchestrator=Orchestrator(LocalAgentSet.deterministic, analyze_case),
        supplier_source_id="source-alpha",
        quality_source_id="source-quality",
        fabric_citation_base_url="https://app.powerbi.com/groups/demo/reports/report",
        clock=clock.now,
    )
    settings = Settings(
        runtime_mode=RuntimeMode.LIVE,
        allowed_tenant_id="11111111-1111-4111-8111-111111111111",
        fabric_sql_server="fixture.database.fabric.microsoft.com",
        fabric_sql_database="fixture",
        credential_mode="managed_identity",
    )
    services = build_composition(
        settings,
        clock=clock.now,
        playback_clock=clock,
        live_components={
            "store": store,
            "analysis_service": analysis_service,
            "auth_service": auth_service,
            "power_bi_url": "https://app.powerbi.com/groups/demo/reports/report",
        },
    )
    app = create_app(services=services)
    app.dependency_overrides[get_actor] = lambda: actor
    return app


def test_composed_live_api_reaches_decision_actions_and_observations(tmp_path):
    app = _live_app(tmp_path, FakeWorkIQ())
    with TestClient(app) as client:
        created = client.post(
            "/api/cases",
            json={"template_id": "RL-001", "purpose": "showcase"},
        )
        case_id = created.json()["case_id"]
        analysis = client.post(f"/api/cases/{case_id}/analysis")
        assert analysis.status_code == 201
        decision = client.post(
            f"/api/cases/{case_id}/decisions",
            headers={"Idempotency-Key": "RL-LIVE-CONTRACT"},
            json={
                "analysis_id": analysis.json()["analysis_id"],
                "kind": "approved",
                "selected_option_id": "RL-OPTION-COMBINED",
            },
        )
        assert decision.status_code == 201
        app.state.services.run_worker_until_idle()
        decision_id = decision.json()["decision_id"]
        actions = client.get(f"/api/decisions/{decision_id}/actions")
        assert len(actions.json()) == 5
        playback = client.post(f"/api/decisions/{decision_id}/playback")
        assert playback.status_code == 201, playback.json()
        app.state.services.playback_service.run_to_completion(
            playback.json()["playback_id"], clock=app.state.services.playback_clock
        )
        observations = client.get(f"/api/decisions/{decision_id}/observations")
        assert observations.status_code == 200
        assert all(item["kind"] == "simulated" for item in observations.json())


def test_composed_live_api_maps_source_failure_without_secret_detail(tmp_path):
    app = _live_app(tmp_path, BrokenWorkIQ())
    with TestClient(app) as client:
        case_id = client.post(
            "/api/cases",
            json={"template_id": "RL-001", "purpose": "showcase"},
        ).json()["case_id"]
        response = client.post(f"/api/cases/{case_id}/analysis")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "LIVE_SOURCE_UNAVAILABLE",
        "new_fallback_case_allowed": True,
    }


def test_live_browser_project_disables_credential_bearing_artifacts():
    root = Path(__file__).resolve().parents[2]
    config = (root / "apps/web/playwright.config.ts").read_text()
    live_spec = (root / "apps/web/e2e/live-demo.spec.ts").read_text()

    assert 'name: "live"' in config
    assert 'trace: "off"' in config
    assert 'screenshot: "off"' in config
    assert 'video: "off"' in config
    assert "Authorization" not in live_spec
    assert "SUPPLY_RESPONSE_ALEX_STORAGE_STATE" in live_spec
    assert "SUPPLY_RESPONSE_EXPECTED_CORPUS_VERSION" in live_spec
