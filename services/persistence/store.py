from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import Engine, insert, select, update
from sqlalchemy.exc import IntegrityError

from data.domain import CaseInstance, CasePurpose, RuntimeMode
from data.domain.analysis import AnalysisVersion
from data.synthetic.rl001 import OperationalSnapshot
from services.persistence.ports import CaseStore
from services.persistence.tables import (
    analysis_versions,
    approval_satisfactions,
    case_instances,
    case_projection,
    evidence_items,
    operational_snapshots,
)

if TYPE_CHECKING:
    from apps.api.app.settings import Settings


class PersistenceError(RuntimeError):
    """Base error for persistence boundary failures."""


class RecordNotFound(PersistenceError):
    """Raised when a requested immutable record does not exist."""


class ImmutableRecordConflict(PersistenceError):
    """Raised when an insert-only record would be overwritten."""


class RuntimeModeConflict(PersistenceError):
    """Raised when state crosses a Case Instance runtime boundary."""


def serialize_model(value: BaseModel) -> str:
    return value.model_dump_json(exclude_none=False, by_alias=True)


class SqlAlchemyStore:
    def __init__(
        self,
        engine: Engine,
        *,
        runtime_mode: RuntimeMode,
    ) -> None:
        self.engine = engine
        self.runtime_mode = runtime_mode

    def _require_configured_mode(self, runtime_mode: RuntimeMode) -> None:
        if runtime_mode is not self.runtime_mode:
            raise RuntimeModeConflict(
                f"store is configured for {self.runtime_mode.value}, "
                f"not {runtime_mode.value}"
            )

    def _stored_runtime_mode(self, connection, case_id: str) -> RuntimeMode:
        value = connection.execute(
            select(case_instances.c.runtime_mode).where(
                case_instances.c.case_id == case_id
            )
        ).scalar_one_or_none()
        if value is None:
            raise RecordNotFound(f"case does not exist: {case_id}")
        return RuntimeMode(value)

    def _stored_case(self, connection, case_id: str) -> CaseInstance:
        payload = connection.execute(
            select(case_instances.c.payload_json).where(
                case_instances.c.case_id == case_id
            )
        ).scalar_one_or_none()
        if payload is None:
            raise RecordNotFound(f"case does not exist: {case_id}")
        return CaseInstance.model_validate_json(payload)

    def _require_case_runtime(
        self,
        connection,
        *,
        case_id: str,
        runtime_mode: RuntimeMode,
    ) -> None:
        self._require_configured_mode(runtime_mode)
        stored_mode = self._stored_runtime_mode(connection, case_id)
        if stored_mode is not runtime_mode:
            raise RuntimeModeConflict(
                f"case {case_id} is {stored_mode.value}, not {runtime_mode.value}"
            )

    @staticmethod
    def _require_matching_runtime(
        runtime_mode: RuntimeMode,
        expected: RuntimeMode,
        *,
        record_name: str,
    ) -> None:
        if runtime_mode is not expected:
            raise RuntimeModeConflict(
                f"{record_name} runtime_mode must match Analysis Version"
            )

    def _require_analysis_provenance(
        self,
        connection,
        analysis: AnalysisVersion,
    ) -> None:
        runtime_mode = analysis.material.runtime_mode
        self._require_case_runtime(
            connection,
            case_id=analysis.case_id,
            runtime_mode=runtime_mode,
        )
        stored_case = self._stored_case(connection, analysis.case_id)
        material = analysis.material
        if (
            material.template_id != stored_case.template_id
            or material.case_purpose is not stored_case.purpose
            or material.scenario_effective_time != stored_case.scenario_effective_time
        ):
            raise ValueError(
                "Analysis Version provenance must match its immutable Case Instance"
            )

        for item in material.evidence:
            if item.case_id != analysis.case_id:
                raise ValueError(
                    "analysis material Evidence Item case_id must match "
                    "Analysis Version"
                )
            self._require_matching_runtime(
                item.runtime_mode,
                runtime_mode,
                record_name="analysis material Evidence Item",
            )
        for item in material.conflicts:
            if item.case_id != analysis.case_id:
                raise ValueError(
                    "analysis material conflict case_id must match Analysis Version"
                )
        for item in material.approval_satisfactions:
            if item.target.case_id != analysis.case_id:
                raise ValueError(
                    "analysis material Approval Satisfaction case_id must match "
                    "Analysis Version"
                )
            self._require_matching_runtime(
                item.target.runtime_mode,
                runtime_mode,
                record_name="analysis material Approval Satisfaction",
            )
        for item in analysis.approval_satisfactions:
            target_case = item.target.case
            if item.analysis_id != analysis.analysis_id:
                raise ValueError(
                    "Approval Satisfaction analysis_id must match Analysis Version"
                )
            if target_case.case_id != analysis.case_id:
                raise ValueError(
                    "Approval Satisfaction case_id must match Analysis Version"
                )
            self._require_matching_runtime(
                target_case.runtime_mode,
                runtime_mode,
                record_name="Approval Satisfaction",
            )

    def create_case(
        self,
        case: CaseInstance,
        snapshot: OperationalSnapshot,
    ) -> None:
        self._require_configured_mode(case.runtime_mode)
        if snapshot.case_id != case.case_id:
            raise ValueError("operational snapshot case_id must match Case Instance")
        if snapshot.runtime_mode is not case.runtime_mode:
            raise RuntimeModeConflict(
                "operational snapshot runtime_mode must match Case Instance"
            )
        if snapshot.scenario_effective_time != case.scenario_effective_time:
            raise ValueError(
                "operational snapshot Scenario Effective Time must match Case Instance"
            )

        try:
            with self.engine.begin() as connection:
                connection.execute(
                    insert(case_instances).values(
                        case_id=case.case_id,
                        template_id=case.template_id,
                        purpose=case.purpose.value,
                        runtime_mode=case.runtime_mode.value,
                        status=case.status.value,
                        scenario_effective_time=case.scenario_effective_time,
                        payload_json=serialize_model(case),
                    )
                )
                connection.execute(
                    insert(operational_snapshots).values(
                        case_id=snapshot.case_id,
                        runtime_mode=snapshot.runtime_mode.value,
                        scenario_effective_time=snapshot.scenario_effective_time,
                        analysis_horizon_start=snapshot.analysis_horizon_start,
                        analysis_horizon_end=snapshot.analysis_horizon_end.isoformat(),
                        payload_json=serialize_model(snapshot),
                    )
                )
                connection.execute(
                    insert(case_projection).values(
                        case_id=case.case_id,
                        purpose=case.purpose.value,
                        runtime_mode=case.runtime_mode.value,
                        status=case.status.value,
                        scenario_effective_time=case.scenario_effective_time,
                        payload_json=serialize_model(case),
                    )
                )
        except IntegrityError as error:
            raise ImmutableRecordConflict(
                f"case already exists: {case.case_id}"
            ) from error

    def get_case(self, case_id: str) -> CaseInstance:
        with self.engine.connect() as connection:
            payload = connection.execute(
                select(case_projection.c.payload_json).where(
                    case_projection.c.case_id == case_id
                )
            ).scalar_one_or_none()
        if payload is None:
            raise RecordNotFound(f"case does not exist: {case_id}")
        case = CaseInstance.model_validate_json(payload)
        self._require_configured_mode(case.runtime_mode)
        return case

    def save_analysis(self, analysis: AnalysisVersion) -> None:
        runtime_mode = analysis.material.runtime_mode
        if analysis.material.case_id != analysis.case_id:
            raise ValueError("analysis material case_id must match Analysis Version")

        for evidence in analysis.evidence_items:
            if evidence.case_id != analysis.case_id:
                raise ValueError("Evidence Item case_id must match Analysis Version")
            if evidence.retrieved_for_analysis_id != analysis.analysis_id:
                raise ValueError(
                    "Evidence Item retrieval provenance must match Analysis Version"
                )
            if evidence.runtime_mode is not runtime_mode:
                raise RuntimeModeConflict(
                    "Evidence Item runtime_mode must match Analysis Version"
                )

        try:
            with self.engine.begin() as connection:
                self._require_analysis_provenance(connection, analysis)
                connection.execute(
                    insert(analysis_versions).values(
                        analysis_id=analysis.analysis_id,
                        case_id=analysis.case_id,
                        material_hash=analysis.material_hash,
                        runtime_mode=runtime_mode.value,
                        analysis_started_at=analysis.analysis_started_at,
                        retrieval_window_ends_at=analysis.retrieval_window_ends_at,
                        created_at=analysis.created_at,
                        payload_json=serialize_model(analysis),
                    )
                )
                if analysis.evidence_items:
                    connection.execute(
                        insert(evidence_items),
                        [
                            {
                                "evidence_id": item.evidence_id,
                                "analysis_id": analysis.analysis_id,
                                "case_id": item.case_id,
                                "kind": item.kind.value,
                                "runtime_mode": item.runtime_mode.value,
                                "source_system": item.source_system.value,
                                "source_timestamp": item.source_timestamp,
                                "retrieved_at": item.retrieved_at,
                                "effective_at": item.effective_at,
                                "expires_at": item.expires_at,
                                "payload_json": serialize_model(item),
                            }
                            for item in analysis.evidence_items
                        ],
                    )
                if analysis.approval_satisfactions:
                    connection.execute(
                        insert(approval_satisfactions),
                        [
                            {
                                "analysis_id": analysis.analysis_id,
                                "decision_id": None,
                                "option_id": item.option_id,
                                "authorization_id": item.authorization_id,
                                "persona_id": item.persona_id,
                                "role": item.role,
                                "satisfied": item.satisfied,
                                "payload_json": serialize_model(item),
                            }
                            for item in analysis.approval_satisfactions
                        ],
                    )
                result = connection.execute(
                    update(case_projection)
                    .where(case_projection.c.case_id == analysis.case_id)
                    .values(
                        current_analysis_id=analysis.analysis_id,
                        current_analysis_hash=analysis.material_hash,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                if result.rowcount != 1:
                    raise RecordNotFound(
                        f"case projection does not exist: {analysis.case_id}"
                    )
        except IntegrityError as error:
            raise ImmutableRecordConflict(
                f"analysis or nested immutable record already exists: "
                f"{analysis.analysis_id}"
            ) from error

    def get_analysis(self, analysis_id: str) -> AnalysisVersion:
        with self.engine.connect() as connection:
            payload = connection.execute(
                select(analysis_versions.c.payload_json).where(
                    analysis_versions.c.analysis_id == analysis_id
                )
            ).scalar_one_or_none()
        if payload is None:
            raise RecordNotFound(f"analysis does not exist: {analysis_id}")
        analysis = AnalysisVersion.model_validate_json(payload)
        self._require_configured_mode(analysis.material.runtime_mode)
        return analysis

    def save_case_projection(self, case: CaseInstance) -> None:
        with self.engine.begin() as connection:
            self._require_case_runtime(
                connection,
                case_id=case.case_id,
                runtime_mode=case.runtime_mode,
            )
            stored_case = self._stored_case(connection, case.case_id)
            if (
                case.template_id != stored_case.template_id
                or case.purpose is not stored_case.purpose
                or case.scenario_effective_time != stored_case.scenario_effective_time
                or case.scenario_timezone != stored_case.scenario_timezone
            ):
                raise ImmutableRecordConflict(
                    "case projection cannot change immutable provenance"
                )
            result = connection.execute(
                update(case_projection)
                .where(case_projection.c.case_id == case.case_id)
                .values(
                    purpose=case.purpose.value,
                    runtime_mode=case.runtime_mode.value,
                    status=case.status.value,
                    scenario_effective_time=case.scenario_effective_time,
                    payload_json=serialize_model(case),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            if result.rowcount != 1:
                raise RecordNotFound(f"case projection does not exist: {case.case_id}")

    def list_cases(
        self,
        *,
        purpose: CasePurpose | None = None,
    ) -> tuple[CaseInstance, ...]:
        statement = select(case_projection.c.payload_json).where(
            case_projection.c.runtime_mode == self.runtime_mode.value
        )
        if purpose is not None:
            statement = statement.where(case_projection.c.purpose == purpose.value)
        statement = statement.order_by(case_projection.c.case_id)
        with self.engine.connect() as connection:
            payloads = connection.execute(statement).scalars().all()
        return tuple(CaseInstance.model_validate_json(item) for item in payloads)


def build_store(settings: Settings) -> CaseStore:
    from services.persistence.sqlite import sqlite_store

    return sqlite_store(
        settings.database_url,
        runtime_mode=settings.runtime_mode,
    )
