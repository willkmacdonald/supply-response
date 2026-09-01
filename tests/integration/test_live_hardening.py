from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from agents.orchestrator.local import LocalAgentSet
from agents.orchestrator.workflow import AgentExplanationUnavailable, Orchestrator
from apps.api.app.live import (
    LiveAnalysisApplicationService,
    LiveOperationalRetrieval,
    LiveSourceUnavailable,
)
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
from services.persistence.sqlite import sqlite_store
from tests.integration.test_workiq_trust_boundaries import _actor_and_service

NOW = datetime(2026, 8, 31, 18, 0, tzinfo=UTC)


def _evidence(
    *,
    evidence_id: str,
    case_id: str,
    analysis_id: str,
    source_system: EvidenceSourceSystem,
    source_id: str,
    scope: AuthorityScope,
    citation: str,
    source_timestamp: datetime = NOW,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        case_id=case_id,
        kind=(
            EvidenceKind.OPERATIONAL_FACT
            if source_system is EvidenceSourceSystem.FABRIC
            else EvidenceKind.SOURCE_STATEMENT
        ),
        authority_scope=(scope,),
        source_system=source_system,
        source_id=source_id,
        source_timestamp=source_timestamp,
        retrieved_at=NOW,
        retrieved_for_analysis_id=analysis_id,
        retrieval_health=RetrievalHealth.HEALTHY,
        effective_at=NOW,
        expires_at=NOW + timedelta(days=1),
        claim=f"Authoritative {evidence_id}",
        excerpt=f"Verified {evidence_id}",
        citation_url=citation,
        runtime_mode=RuntimeMode.LIVE,
        synthetic=False,
        requirement=EvidenceRequirement.REQUIRED_AUTHORITATIVE,
        uncertainty_state=UncertaintyState.CERTAIN,
    )


class ExplicitLiveOperationalPort:
    def __init__(self, *, incomplete: bool = False) -> None:
        self.incomplete = incomplete

    async def retrieve(
        self, *, case_id: str, purpose: CasePurpose, analysis_id: str, retrieved_at
    ) -> LiveOperationalRetrieval:
        case, snapshot = instantiate_rl001(
            case_id=case_id, purpose=purpose, runtime_mode=RuntimeMode.LIVE
        )
        items = (
            _evidence(
                evidence_id="RL-ALPHA-OPTIONAL-3000",
                case_id=case_id,
                analysis_id=analysis_id,
                source_system=EvidenceSourceSystem.FABRIC,
                source_id="fabric.inventory_position/RL-INV-DEMO-CHI",
                scope=AuthorityScope.OPERATIONAL_QUANTITY,
                citation="https://app.powerbi.com/groups/demo/reports/report/evidence/quantity",
            ).model_copy(
                update={
                    "authority_scope": (
                        AuthorityScope.OPERATIONAL_QUANTITY,
                        AuthorityScope.OPERATIONAL_DATE,
                    )
                }
            ),
            _evidence(
                evidence_id="RL-TRANSFER-DAL-CHI-1500",
                case_id=case_id,
                analysis_id=analysis_id,
                source_system=EvidenceSourceSystem.FABRIC,
                source_id="fabric.disruption/RL-DISRUPTION-001",
                scope=AuthorityScope.OPERATIONAL_QUANTITY,
                citation="https://app.powerbi.com/groups/demo/reports/report/evidence/date",
            ).model_copy(
                update={
                    "authority_scope": (
                        AuthorityScope.OPERATIONAL_QUANTITY,
                        AuthorityScope.OPERATIONAL_DATE,
                    )
                }
            ),
            _evidence(
                evidence_id="RL-QUALITY-001",
                case_id=case_id,
                analysis_id=analysis_id,
                source_system=EvidenceSourceSystem.FABRIC,
                source_id="fabric.qualification/RL-QUAL-BETA",
                scope=AuthorityScope.QUALIFICATION_STATE,
                citation="https://app.powerbi.com/groups/demo/reports/report/evidence/quality",
            ),
        )
        return LiveOperationalRetrieval(
            case=case,
            snapshot=snapshot,
            evidence=items[:-1] if self.incomplete else items,
            source_snapshot_id="fabric-snapshot-2026-09-01",
            retrieved_at=retrieved_at,
        )


class ExactWorkIQ:
    def __init__(self, *, empty_supplier: bool = False, stale: bool = False) -> None:
        self.empty_supplier = empty_supplier
        self.stale = stale

    async def retrieve_supplier_signal(self, **kwargs):
        if self.empty_supplier:
            evidence = ()
        else:
            evidence = (
                _evidence(
                    evidence_id="WORKIQ-SUPPLIER",
                    case_id=kwargs["case_id"],
                    analysis_id=kwargs["analysis_id"],
                    source_system=EvidenceSourceSystem.WORK_IQ,
                    source_id=kwargs["source_id"],
                    scope=AuthorityScope.SUPPLIER_STATEMENT,
                    citation="https://teams.microsoft.com/l/entity/supplier",
                    source_timestamp=NOW
                    - (timedelta(days=2) if self.stale else timedelta()),
                ),
            )
        return WorkIQRetrieval(
            evidence=evidence,
            lineage=WorkIQRetrievalLineage(
                context_id="supplier-context",
                task_id="supplier-task",
                artifact_ids=("supplier-artifact",),
                source_ids=(kwargs["source_id"],),
            ),
        )

    async def retrieve_quality_context(self, **kwargs):
        return WorkIQRetrieval(
            evidence=(
                _evidence(
                    evidence_id="WORKIQ-QUALITY",
                    case_id=kwargs["case_id"],
                    analysis_id=kwargs["analysis_id"],
                    source_system=EvidenceSourceSystem.WORK_IQ,
                    source_id=kwargs["source_id"],
                    scope=AuthorityScope.COLLABORATION_STATEMENT,
                    citation="https://tenant.sharepoint.com/sites/quality/item",
                ),
            ),
            lineage=WorkIQRetrievalLineage(
                context_id="quality-context",
                task_id="quality-task",
                artifact_ids=("quality-artifact",),
                source_ids=(kwargs["source_id"],),
            ),
        )


def _service(store, *, operational=None, work_iq=None, orchestrator=None):
    return LiveAnalysisApplicationService(
        store=store,
        operational_data=operational or ExplicitLiveOperationalPort(),
        work_iq=work_iq or ExactWorkIQ(),
        orchestrator=orchestrator
        or Orchestrator(LocalAgentSet.deterministic, analyze_case),
        supplier_source_id="supplier-source",
        quality_source_id="quality-source",
        clock=lambda: NOW,
        tenant_sharepoint_host="tenant.sharepoint.com",
    )


async def _seed(store, operational=None):
    port = operational or ExplicitLiveOperationalPort()
    retrieval = await port.retrieve(
        case_id="RL-CASE-LIVE",
        purpose=CasePurpose.SHOWCASE,
        analysis_id="case-bootstrap",
        retrieved_at=NOW,
    )
    store.create_case(retrieval.case, retrieval.snapshot)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("operational", "work_iq"),
    [
        (ExplicitLiveOperationalPort(incomplete=True), ExactWorkIQ()),
        (ExplicitLiveOperationalPort(), ExactWorkIQ(empty_supplier=True)),
        (ExplicitLiveOperationalPort(), ExactWorkIQ(stale=True)),
    ],
)
async def test_live_analysis_fails_closed_for_incomplete_or_stale_sources(
    tmp_path, operational, work_iq
):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'strict-live.db'}", runtime_mode=RuntimeMode.LIVE
    )
    await _seed(store)
    with pytest.raises(LiveSourceUnavailable):
        await _service(store, operational=operational, work_iq=work_iq).create(
            "RL-CASE-LIVE", actor=_actor_and_service()[1]
        )
    assert store.get_projection("RL-CASE-LIVE").current_analysis_id is None


@pytest.mark.anyio
async def test_explanation_failure_persists_partial_and_workiq_lineage(tmp_path):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'lineage.db'}", runtime_mode=RuntimeMode.LIVE
    )
    await _seed(store)

    class Unavailable:
        async def analyze(self, command):
            partial = analyze_case(command.deterministic)
            from agents.orchestrator.contracts import PartialDeterministicResult

            raise AgentExplanationUnavailable(
                PartialDeterministicResult(
                    analysis_version=partial, evidence_items=partial.evidence_items
                )
            )

    analysis = await _service(store, orchestrator=Unavailable()).create(
        "RL-CASE-LIVE", actor=_actor_and_service()[1]
    )
    reloaded = store.get_analysis(analysis.analysis_id)
    assert reloaded.explanation.status == "unavailable"
    assert {item.task_id for item in reloaded.retrieval_lineage} == {
        "supplier-task",
        "quality-task",
    }
    assert "token" not in reloaded.model_dump_json().lower()


@pytest.mark.anyio
async def test_two_service_instances_share_one_database_analysis_claim(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'claims.db'}"
    first_store = sqlite_store(database_url, runtime_mode=RuntimeMode.LIVE)
    second_store = sqlite_store(database_url, runtime_mode=RuntimeMode.LIVE)
    await _seed(first_store)
    first = _service(first_store)
    second = _service(second_store)
    actor = _actor_and_service()[1]

    one, two = await asyncio.gather(
        first.create("RL-CASE-LIVE", actor=actor),
        second.create("RL-CASE-LIVE", actor=actor),
    )

    assert one.analysis_id == two.analysis_id
    assert (
        first_store.get_projection("RL-CASE-LIVE").current_analysis_id
        == one.analysis_id
    )
