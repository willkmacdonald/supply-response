"""Typed retrieval of current operational source material from Fabric SQL."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from sqlalchemy import Engine, text

from apps.api.app.live import LiveOperationalRetrieval
from data.domain import CaseInstance, CasePurpose, CaseStatus, RuntimeMode
from data.domain.evidence import EvidenceItem
from data.synthetic.rl001 import OperationalSnapshot


class FabricLiveOperationalDataPort:
    """Read the one verified current RL-001 source bundle; never generate fixtures."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    async def retrieve(
        self,
        *,
        case_id: str,
        purpose: CasePurpose,
        analysis_id: str,
        retrieved_at: datetime,
    ) -> LiveOperationalRetrieval:
        return await asyncio.to_thread(
            self._retrieve,
            case_id=case_id,
            purpose=purpose,
            analysis_id=analysis_id,
            retrieved_at=retrieved_at,
        )

    def _retrieve(
        self,
        *,
        case_id: str,
        purpose: CasePurpose,
        analysis_id: str,
        retrieved_at: datetime,
    ) -> LiveOperationalRetrieval:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT TOP (1) source_snapshot_id, snapshot_payload_json, "
                        "evidence_payload_json FROM app.live_operational_sources "
                        "WHERE template_id = :template_id AND is_verified = 1 "
                        "AND effective_at <= :retrieved_at "
                        "ORDER BY effective_at DESC"
                    ),
                    {"template_id": "RL-001", "retrieved_at": retrieved_at},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise LookupError("verified live operational source is unavailable")
        snapshot = OperationalSnapshot.model_validate_json(
            row["snapshot_payload_json"]
        ).model_copy(update={"case_id": case_id, "runtime_mode": RuntimeMode.LIVE})
        case = CaseInstance(
            case_id=case_id,
            template_id="RL-001",
            purpose=purpose,
            runtime_mode=RuntimeMode.LIVE,
            scenario_effective_time=snapshot.scenario_effective_time,
            status=CaseStatus.OPEN,
        )
        raw_evidence = json.loads(row["evidence_payload_json"])
        if not isinstance(raw_evidence, list):
            raise TypeError("Fabric operational evidence bundle is invalid")
        evidence = tuple(
            EvidenceItem.model_validate(item).model_copy(
                update={
                    "case_id": case_id,
                    "retrieved_for_analysis_id": analysis_id,
                    "retrieved_at": retrieved_at,
                    "runtime_mode": RuntimeMode.LIVE,
                }
            )
            for item in raw_evidence
        )
        return LiveOperationalRetrieval(
            case=case,
            snapshot=snapshot,
            evidence=evidence,
            source_snapshot_id=row["source_snapshot_id"],
            retrieved_at=retrieved_at,
        )
