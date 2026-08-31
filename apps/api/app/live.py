from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

from agents.orchestrator.contracts import AnalyzeCommand, RetrievalLineage
from agents.orchestrator.workflow import Orchestrator
from apps.api.app.auth import AuthenticatedActor
from data.domain import CaseStatus, RuntimeMode
from data.domain.analysis import AnalysisVersion
from data.domain.decisions import CorpusScope, StandingAuthorization
from data.domain.evidence import EvidenceSourceSystem
from data.synthetic.rl001 import build_rl001_evidence
from integrations.workiq.models import WorkIQRetrieval
from services.analysis.service import AnalyzeCaseCommand
from services.persistence.store import RuntimeModeConflict, SqlAlchemyStore


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
    sensitive_query_names = {
        "access_token",
        "assertion",
        "client_secret",
        "code",
        "sig",
        "token",
    }
    query_names = {
        item.partition("=")[0].lower() for item in parsed.query.split("&") if item
    }
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or not parsed.path.startswith("/")
        or query_names & sensitive_query_names
    ):
        raise ValueError("live citation URL is outside the trusted policy")
    return value


class LiveAnalysisApplicationService:
    """Join Fabric facts and delegated Work IQ evidence without fallback."""

    def __init__(
        self,
        *,
        store: SqlAlchemyStore,
        work_iq: WorkIQPort,
        orchestrator: Orchestrator,
        supplier_source_id: str,
        quality_source_id: str,
        fabric_citation_base_url: str,
        clock: Callable[[], datetime],
        tenant_sharepoint_host: str = "tenant.sharepoint.com",
    ) -> None:
        if store.runtime_mode is not RuntimeMode.LIVE:
            raise ValueError("live analysis requires a live store")
        self._store = store
        self._work_iq = work_iq
        self._orchestrator = orchestrator
        self._supplier_source_id = supplier_source_id
        self._quality_source_id = quality_source_id
        self._fabric_citation_base_url = validate_live_https_url(
            fabric_citation_base_url,
            allowed_hosts={"app.powerbi.com"},
        )
        self._citation_hosts = {
            "app.powerbi.com",
            "outlook.office.com",
            "outlook.office365.com",
            "teams.microsoft.com",
            tenant_sharepoint_host,
        }
        self._clock = clock
        self._locks: dict[str, asyncio.Lock] = {}

    async def create(
        self, case_id: str, *, actor: AuthenticatedActor
    ) -> AnalysisVersion:
        lock = self._locks.setdefault(case_id, asyncio.Lock())
        async with lock:
            case = self._store.get_case(case_id)
            if case.runtime_mode is not RuntimeMode.LIVE:
                raise RuntimeModeConflict("live analysis cannot access a fallback Case")
            projection = self._store.get_projection(case_id)
            if projection.current_analysis_id is not None:
                return self._store.get_analysis(projection.current_analysis_id)
            snapshot = self._store.get_operational_snapshot(case_id)
            analysis_id = f"RL-ANALYSIS-{uuid4()}"
            started_at = self._clock()
            try:
                supplier, quality = await asyncio.gather(
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
                fabric = tuple(
                    item.model_copy(
                        update={
                            "source_system": EvidenceSourceSystem.FABRIC,
                            "source_id": f"FABRIC-{item.source_id}",
                            "citation_url": (
                                f"{self._fabric_citation_base_url}/evidence/"
                                f"{item.evidence_id}"
                            ),
                            "synthetic": False,
                        }
                    )
                    for item in build_rl001_evidence(
                        snapshot,
                        analysis_id=analysis_id,
                        retrieved_at=started_at,
                    )
                )
                evidence = (*fabric, *supplier.evidence, *quality.evidence)
                if any(
                    item.runtime_mode is not RuntimeMode.LIVE
                    or item.synthetic
                    or item.source_system
                    not in {EvidenceSourceSystem.FABRIC, EvidenceSourceSystem.WORK_IQ}
                    or not item.citation_url
                    for item in evidence
                ):
                    raise ValueError("live evidence provenance is incomplete")
                for item in evidence:
                    validate_live_citation_url(
                        item.citation_url or "", allowed_hosts=self._citation_hosts
                    )
                command = AnalyzeCaseCommand(
                    analysis_id=analysis_id,
                    case=case,
                    corpus=CorpusScope.DEMO_CORPUS,
                    operational_snapshot=snapshot,
                    evidence_items=evidence,
                    standing_authorizations=(StandingAuthorization.taylor_rl001(),),
                    analysis_started_at=started_at,
                    created_at=max(self._clock(), started_at),
                    calculation_version="rl001-options-v1",
                )
                result = await self._orchestrator.analyze(
                    AnalyzeCommand(
                        deterministic=command,
                        retrieval_lineage=tuple(
                            RetrievalLineage(
                                context_id=retrieval.lineage.context_id,
                                task_id=retrieval.lineage.task_id,
                                artifact_ids=retrieval.lineage.artifact_ids,
                                source_ids=retrieval.lineage.source_ids,
                            )
                            for retrieval in (supplier, quality)
                        ),
                    )
                )
                analysis = result.analysis_version
            except Exception as error:
                if isinstance(error, RuntimeModeConflict):
                    raise
                raise LiveSourceUnavailable() from None
            self._store.save_analysis(analysis)
            self._store.save_case_projection(
                case.model_copy(update={"status": CaseStatus.AWAITING_DECISION})
            )
            return analysis
