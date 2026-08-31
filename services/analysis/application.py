from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from data.domain import CaseStatus
from data.domain.analysis import AnalysisVersion
from data.domain.decisions import CorpusScope, StandingAuthorization
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.persistence.store import SqlAlchemyStore


class FallbackAnalysisApplicationService:
    """Compose fallback acquisition, canonical analysis, and persistence."""

    def __init__(
        self,
        store: SqlAlchemyStore,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._clock = clock

    def create(self, case_id: str) -> AnalysisVersion:
        projection = self._store.get_projection(case_id)
        case = projection.case
        _, snapshot = instantiate_rl001(
            case_id=case.case_id,
            purpose=case.purpose,
            runtime_mode=case.runtime_mode,
        )
        analysis_id = f"RL-ANALYSIS-{uuid4()}"
        started_at = self._clock()
        created_at = max(self._clock(), started_at)
        analysis = analyze_case(
            AnalyzeCaseCommand(
                analysis_id=analysis_id,
                case=case,
                corpus=CorpusScope.DEMO_CORPUS,
                operational_snapshot=snapshot,
                evidence_items=build_rl001_evidence(
                    snapshot,
                    analysis_id=analysis_id,
                    retrieved_at=started_at,
                ),
                standing_authorizations=(StandingAuthorization.taylor_rl001(),),
                analysis_started_at=started_at,
                created_at=created_at,
                calculation_version="rl001-options-v1",
            )
        )
        self._store.save_analysis(analysis)
        self._store.save_case_projection(
            case.model_copy(update={"status": CaseStatus.AWAITING_DECISION})
        )
        return analysis
