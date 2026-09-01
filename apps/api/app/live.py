from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from agents.orchestrator.contracts import (
    AgentExplanationUnavailable,
    AnalyzeCommand,
    RetrievalLineage,
)
from agents.orchestrator.workflow import Orchestrator
from apps.api.app.auth import AuthenticatedActor
from data.domain import CaseInstance, CasePurpose, CaseStatus, RuntimeMode
from data.domain.analysis import (
    AnalysisExplanation,
    AnalysisRetrievalLineage,
    AnalysisVersion,
)
from data.domain.decisions import CorpusScope, StandingAuthorization
from data.domain.evidence import (
    AuthorityScope,
    EvidenceItem,
    EvidenceRequirement,
    EvidenceSourceSystem,
    RetrievalHealth,
)
from data.synthetic.rl001 import OperationalSnapshot
from integrations.workiq.models import WorkIQRetrieval
from services.analysis.service import AnalyzeCaseCommand, canonical_operational_snapshot
from services.persistence.store import (
    AnalysisClaimBusy,
    RuntimeModeConflict,
    SqlAlchemyStore,
)


class LiveSourceUnavailable(RuntimeError):
    code = "LIVE_SOURCE_UNAVAILABLE"
    new_fallback_case_allowed = True

    def __init__(self) -> None:
        super().__init__("A required live source is unavailable.")


class WorkIQPort(Protocol):
    async def retrieve_supplier_signal(
        self,
        *,
        actor: AuthenticatedActor,
        source_id: str,
        case_id: str,
        analysis_id: str,
        retrieved_at: Any,
    ) -> WorkIQRetrieval: ...
    async def retrieve_quality_context(
        self,
        *,
        actor: AuthenticatedActor,
        source_id: str,
        case_id: str,
        analysis_id: str,
        retrieved_at: Any,
    ) -> WorkIQRetrieval: ...


@dataclass(frozen=True, slots=True)
class LiveOperationalRetrieval:
    case: CaseInstance
    snapshot: OperationalSnapshot
    evidence: tuple[EvidenceItem, ...]
    source_snapshot_id: str
    retrieved_at: datetime


class LiveOperationalDataPort(Protocol):
    async def retrieve(
        self,
        *,
        case_id: str,
        purpose: CasePurpose,
        analysis_id: str,
        retrieved_at: datetime,
    ) -> LiveOperationalRetrieval: ...


def validate_live_https_url(value: str, *, allowed_hosts: set[str]) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("live URL is invalid") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("live URL is outside the trusted policy")
    return value


def validate_live_citation_url(value: str, *, allowed_hosts: set[str]) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("live citation URL is invalid") from error
    sensitive = {"access_token", "assertion", "client_secret", "code", "sig", "token"}
    query_names = {
        unquote(item.partition("=")[0]).lower()
        for item in parsed.query.split("&")
        if item
    }
    decoded_query = unquote(parsed.query).lower()
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or not parsed.path.startswith("/")
        or query_names & sensitive
        or any(f"{name}=" in decoded_query for name in sensitive)
    ):
        raise ValueError("live citation URL is outside the trusted policy")
    return value


def _require_item(
    items: tuple[EvidenceItem, ...],
    *,
    system: EvidenceSourceSystem,
    scope: AuthorityScope,
    source_id: str | None,
    analysis_id: str,
    case_id: str,
    started_at: datetime,
    citation_hosts: set[str],
) -> None:
    matches = [
        item
        for item in items
        if item.source_system is system
        and scope in item.authority_scope
        and (source_id is None or item.source_id == source_id)
    ]
    if not matches:
        raise ValueError("required authoritative live evidence is missing")
    for item in matches:
        if (
            item.case_id != case_id
            or item.retrieved_for_analysis_id != analysis_id
            or item.runtime_mode is not RuntimeMode.LIVE
            or item.synthetic
            or item.requirement is not EvidenceRequirement.REQUIRED_AUTHORITATIVE
            or item.retrieval_health is not RetrievalHealth.HEALTHY
            or item.source_timestamp is None
            or item.retrieved_at is None
            or not item.source_id.strip()
            or not (item.excerpt or "").strip()
            or not item.citation_url
            or abs(started_at - item.source_timestamp) > timedelta(hours=24)
        ):
            raise ValueError("required authoritative live evidence is incomplete")
        validate_live_citation_url(item.citation_url, allowed_hosts=citation_hosts)


class LiveAnalysisApplicationService:
    def __init__(
        self,
        *,
        store: SqlAlchemyStore,
        operational_data: LiveOperationalDataPort,
        work_iq: WorkIQPort,
        orchestrator: Orchestrator,
        supplier_source_id: str,
        quality_source_id: str,
        clock,
        tenant_sharepoint_host: str = "tenant.sharepoint.com",
        **legacy: Any,
    ) -> None:
        del legacy
        if store.runtime_mode is not RuntimeMode.LIVE:
            raise ValueError("live analysis requires a live store")
        self._store = store
        self._operational_data = operational_data
        self._work_iq = work_iq
        self._orchestrator = orchestrator
        self._supplier_source_id = supplier_source_id
        self._quality_source_id = quality_source_id
        self._citation_hosts = {
            "app.powerbi.com",
            "outlook.office.com",
            "outlook.office365.com",
            "teams.microsoft.com",
            tenant_sharepoint_host,
        }
        self._clock = clock

    async def create(
        self, case_id: str, *, actor: AuthenticatedActor
    ) -> AnalysisVersion:
        claim_id: str | None = None
        material_version: str | None = None
        try:
            case = self._store.get_case(case_id)
            if case.runtime_mode is not RuntimeMode.LIVE:
                raise RuntimeModeConflict("live analysis cannot access a fallback Case")
            projection = self._store.get_projection(case_id)
            if projection.current_analysis_id is not None:
                return self._store.get_analysis(projection.current_analysis_id)
            started_at = self._clock()
            material_version = canonical_operational_snapshot(
                self._store.get_operational_snapshot(case_id)
            )
            claim_id = str(uuid4())
            if not self._store.try_claim_analysis(
                case_id=case_id,
                material_version=material_version,
                claim_id=claim_id,
                claimed_at=started_at,
            ):
                return await self._wait_for_winner(case_id)
            analysis_id = f"RL-ANALYSIS-{uuid4()}"
            operational, supplier, quality = await asyncio.gather(
                self._operational_data.retrieve(
                    case_id=case_id,
                    purpose=case.purpose,
                    analysis_id=analysis_id,
                    retrieved_at=started_at,
                ),
                self._work_iq.retrieve_supplier_signal(
                    actor=actor,
                    source_id=self._supplier_source_id,
                    case_id=case_id,
                    analysis_id=analysis_id,
                    retrieved_at=started_at,
                ),
                self._work_iq.retrieve_quality_context(
                    actor=actor,
                    source_id=self._quality_source_id,
                    case_id=case_id,
                    analysis_id=analysis_id,
                    retrieved_at=started_at,
                ),
            )
            if (
                operational.case.case_id != case.case_id
                or operational.case.purpose is not case.purpose
                or operational.case.runtime_mode is not RuntimeMode.LIVE
                or canonical_operational_snapshot(operational.snapshot)
                != material_version
                or not operational.source_snapshot_id.strip()
            ):
                raise ValueError("live operational snapshot changed or is incomplete")
            evidence = (*operational.evidence, *supplier.evidence, *quality.evidence)
            for scope in (
                AuthorityScope.OPERATIONAL_QUANTITY,
                AuthorityScope.OPERATIONAL_DATE,
                AuthorityScope.QUALIFICATION_STATE,
            ):
                _require_item(
                    evidence,
                    system=EvidenceSourceSystem.FABRIC,
                    scope=scope,
                    source_id=None,
                    analysis_id=analysis_id,
                    case_id=case_id,
                    started_at=started_at,
                    citation_hosts=self._citation_hosts,
                )
            for scope, source_id in (
                (AuthorityScope.SUPPLIER_STATEMENT, self._supplier_source_id),
                (AuthorityScope.COLLABORATION_STATEMENT, self._quality_source_id),
            ):
                _require_item(
                    evidence,
                    system=EvidenceSourceSystem.WORK_IQ,
                    scope=scope,
                    source_id=source_id,
                    analysis_id=analysis_id,
                    case_id=case_id,
                    started_at=started_at,
                    citation_hosts=self._citation_hosts,
                )
            evidence = tuple(
                item.model_copy(
                    update={
                        "citation_classification": "fabric"
                        if item.source_system is EvidenceSourceSystem.FABRIC
                        else "work_iq",
                        "navigable_citation_url": item.citation_url,
                        "citation_trusted_host": urlsplit(
                            item.citation_url or ""
                        ).hostname,
                    }
                )
                for item in evidence
            )
            lineage = (
                AnalysisRetrievalLineage(
                    source_kind="supplier",
                    context_id=supplier.lineage.context_id,
                    task_id=supplier.lineage.task_id,
                    artifact_ids=supplier.lineage.artifact_ids,
                    source_ids=supplier.lineage.source_ids,
                ),
                AnalysisRetrievalLineage(
                    source_kind="quality",
                    context_id=quality.lineage.context_id,
                    task_id=quality.lineage.task_id,
                    artifact_ids=quality.lineage.artifact_ids,
                    source_ids=quality.lineage.source_ids,
                ),
            )
            command = AnalyzeCaseCommand(
                analysis_id=analysis_id,
                case=case,
                corpus=CorpusScope.DEMO_CORPUS,
                operational_snapshot=operational.snapshot,
                evidence_items=evidence,
                standing_authorizations=(StandingAuthorization.taylor_rl001(),),
                analysis_started_at=started_at,
                created_at=max(self._clock(), started_at),
                calculation_version="rl001-options-v1",
            )
            try:
                result = await self._orchestrator.analyze(
                    AnalyzeCommand(
                        deterministic=command,
                        retrieval_lineage=tuple(
                            RetrievalLineage(
                                context_id=item.context_id,
                                task_id=item.task_id,
                                artifact_ids=item.artifact_ids,
                                source_ids=item.source_ids,
                            )
                            for item in lineage
                        ),
                    )
                )
                explanation = AnalysisExplanation(
                    status=result.explanation_status,
                    signal_json=result.signal_extraction.model_dump_json()
                    if result.signal_extraction is not None
                    else None,
                    context_json=result.context_extraction.model_dump_json()
                    if result.context_extraction is not None
                    else None,
                    decision_json=result.decision_explanation.model_dump_json()
                    if result.decision_explanation is not None
                    else None,
                )
                analysis = result.analysis_version
            except AgentExplanationUnavailable as unavailable:
                analysis = unavailable.partial_result.analysis_version
                explanation = AnalysisExplanation(status="unavailable")
            analysis = analysis.model_copy(
                update={"retrieval_lineage": lineage, "explanation": explanation}
            )
            return self._store.complete_analysis_claim(
                analysis=analysis,
                projected_case=case.model_copy(
                    update={"status": CaseStatus.AWAITING_DECISION}
                ),
                material_version=material_version,
                claim_id=claim_id,
            )
        except RuntimeModeConflict:
            raise
        except AnalysisClaimBusy:
            return await self._wait_for_winner(case_id)
        except Exception:  # noqa: BLE001 - public boundary maps all source failures
            try:
                if claim_id is not None and material_version is not None:
                    self._store.release_analysis_claim(
                        case_id=case_id,
                        material_version=material_version,
                        claim_id=claim_id,
                    )
            except Exception:  # noqa: BLE001,S110 - lease expires safely
                pass
            raise LiveSourceUnavailable() from None

    async def _wait_for_winner(self, case_id: str) -> AnalysisVersion:
        for _ in range(100):
            try:
                projection = self._store.get_projection(case_id)
                if projection.current_analysis_id is not None:
                    return self._store.get_analysis(projection.current_analysis_id)
            except Exception:  # noqa: BLE001 - persistence detail must remain bounded
                raise LiveSourceUnavailable() from None
            await asyncio.sleep(0.01)
        raise LiveSourceUnavailable()
