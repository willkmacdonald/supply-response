from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError
from sqlalchemy import Connection, Engine, insert, select, update
from sqlalchemy.exc import IntegrityError

from data.domain import CaseInstance, CasePurpose, RuntimeMode
from data.domain.analysis import AnalysisVersion
from data.synthetic.rl001 import OperationalSnapshot
from services.analysis.service import (
    analysis_material_hash,
    canonical_operational_snapshot,
)
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


class PersistenceIntegrityError(PersistenceError):
    """Raised when persisted state conflicts with its canonical domain record."""


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

    @staticmethod
    def _datetime_matches(stored: datetime, expected: datetime) -> bool:
        if stored.tzinfo is None and expected.tzinfo is not None:
            expected = expected.replace(tzinfo=None)
        return stored == expected

    @staticmethod
    def _decode_case(payload: str, *, record_name: str) -> CaseInstance:
        try:
            return CaseInstance.model_validate_json(payload)
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                f"{record_name} contains invalid Case Instance JSON"
            ) from error

    @staticmethod
    def _decode_snapshot(payload: str) -> OperationalSnapshot:
        try:
            return OperationalSnapshot.model_validate_json(payload)
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted Operational Snapshot contains invalid JSON"
            ) from error

    @staticmethod
    def _decode_analysis(payload: str) -> AnalysisVersion:
        try:
            return AnalysisVersion.model_validate_json(payload)
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted Analysis Version contains invalid JSON"
            ) from error

    def _stored_case(
        self,
        connection: Connection,
        case_id: str,
    ) -> CaseInstance:
        row = (
            connection.execute(
                select(case_instances).where(case_instances.c.case_id == case_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"case does not exist: {case_id}")
        case = self._decode_case(
            row["payload_json"],
            record_name="immutable case record",
        )
        if (
            case.case_id != row["case_id"]
            or case.template_id != row["template_id"]
            or case.purpose.value != row["purpose"]
            or case.runtime_mode.value != row["runtime_mode"]
            or case.status.value != row["status"]
            or not self._datetime_matches(
                row["scenario_effective_time"],
                case.scenario_effective_time,
            )
        ):
            raise PersistenceIntegrityError(
                "immutable case columns conflict with canonical Case Instance JSON"
            )
        return case

    def _stored_snapshot(
        self,
        connection: Connection,
        case_id: str,
    ) -> OperationalSnapshot:
        row = (
            connection.execute(
                select(operational_snapshots).where(
                    operational_snapshots.c.case_id == case_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise PersistenceIntegrityError(
                f"persisted Operational Snapshot is missing for case {case_id}"
            )
        snapshot = self._decode_snapshot(row["payload_json"])
        if (
            snapshot.case_id != row["case_id"]
            or snapshot.runtime_mode.value != row["runtime_mode"]
            or not self._datetime_matches(
                row["scenario_effective_time"],
                snapshot.scenario_effective_time,
            )
            or not self._datetime_matches(
                row["analysis_horizon_start"],
                snapshot.analysis_horizon_start,
            )
            or snapshot.analysis_horizon_end.isoformat() != row["analysis_horizon_end"]
        ):
            raise PersistenceIntegrityError(
                "persisted Operational Snapshot columns conflict with canonical JSON"
            )
        return snapshot

    def _require_case_runtime(
        self,
        connection: Connection,
        *,
        case_id: str,
        runtime_mode: RuntimeMode,
    ) -> CaseInstance:
        self._require_configured_mode(runtime_mode)
        stored_case = self._stored_case(connection, case_id)
        if stored_case.runtime_mode is not runtime_mode:
            raise RuntimeModeConflict(
                f"case {case_id} is {stored_case.runtime_mode.value}, "
                f"not {runtime_mode.value}"
            )
        return stored_case

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
        connection: Connection,
        analysis: AnalysisVersion,
    ) -> None:
        expected_hash = analysis_material_hash(analysis.material)
        if analysis.material_hash != expected_hash:
            raise PersistenceIntegrityError(
                "Analysis Version material_hash does not match canonical material"
            )

        runtime_mode = analysis.material.runtime_mode
        stored_case = self._require_case_runtime(
            connection,
            case_id=analysis.case_id,
            runtime_mode=runtime_mode,
        )
        stored_snapshot = self._stored_snapshot(connection, analysis.case_id)
        material = analysis.material
        if material.case_id != analysis.case_id:
            raise ValueError("analysis material case_id must match Analysis Version")
        if (
            material.template_id != stored_case.template_id
            or material.case_purpose is not stored_case.purpose
            or material.scenario_effective_time != stored_case.scenario_effective_time
        ):
            raise ValueError(
                "Analysis Version provenance must match its immutable Case Instance"
            )
        if material.operational_snapshot_json != canonical_operational_snapshot(
            stored_snapshot
        ):
            raise PersistenceIntegrityError(
                "Analysis Version Operational Snapshot does not match the "
                "persisted Operational Snapshot"
            )

        for evidence in analysis.evidence_items:
            if evidence.case_id != analysis.case_id:
                raise ValueError("Evidence Item case_id must match Analysis Version")
            if evidence.retrieved_for_analysis_id != analysis.analysis_id:
                raise ValueError(
                    "Evidence Item retrieval provenance must match Analysis Version"
                )
            self._require_matching_runtime(
                evidence.runtime_mode,
                runtime_mode,
                record_name="Evidence Item",
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

    def _require_analysis_row_integrity(
        self,
        row,
        analysis: AnalysisVersion,
    ) -> None:
        if (
            analysis.analysis_id != row["analysis_id"]
            or analysis.case_id != row["case_id"]
            or analysis.material_hash != row["material_hash"]
            or analysis.material.runtime_mode.value != row["runtime_mode"]
            or not self._datetime_matches(
                row["analysis_started_at"],
                analysis.analysis_started_at,
            )
            or not self._datetime_matches(
                row["retrieval_window_ends_at"],
                analysis.retrieval_window_ends_at,
            )
            or not self._datetime_matches(row["created_at"], analysis.created_at)
        ):
            raise PersistenceIntegrityError(
                "analysis columns conflict with canonical Analysis Version JSON"
            )

    def _require_case_projection_integrity(
        self,
        row,
        case: CaseInstance,
        stored_case: CaseInstance,
    ) -> None:
        if (
            case.case_id != row["case_id"]
            or case.purpose.value != row["purpose"]
            or case.runtime_mode.value != row["runtime_mode"]
            or case.status.value != row["status"]
            or not self._datetime_matches(
                row["scenario_effective_time"],
                case.scenario_effective_time,
            )
            or case.template_id != stored_case.template_id
            or case.purpose is not stored_case.purpose
            or case.runtime_mode is not stored_case.runtime_mode
            or case.scenario_effective_time != stored_case.scenario_effective_time
            or case.scenario_timezone != stored_case.scenario_timezone
        ):
            raise PersistenceIntegrityError(
                "case projection conflicts with immutable Case Instance provenance"
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
            row = (
                connection.execute(
                    select(case_projection).where(case_projection.c.case_id == case_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise RecordNotFound(f"case does not exist: {case_id}")
            case = self._decode_case(
                row["payload_json"],
                record_name="case projection",
            )
            stored_case = self._stored_case(connection, case_id)
            self._require_case_projection_integrity(row, case, stored_case)
            self._require_configured_mode(case.runtime_mode)
            return case

    def save_analysis(self, analysis: AnalysisVersion) -> None:
        runtime_mode = analysis.material.runtime_mode

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
                        updated_at=datetime.now(UTC),
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
            row = (
                connection.execute(
                    select(analysis_versions).where(
                        analysis_versions.c.analysis_id == analysis_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise RecordNotFound(f"analysis does not exist: {analysis_id}")
            analysis = self._decode_analysis(row["payload_json"])
            self._require_analysis_row_integrity(row, analysis)
            try:
                self._require_analysis_provenance(connection, analysis)
            except PersistenceIntegrityError:
                raise
            except (RuntimeModeConflict, ValueError) as error:
                raise PersistenceIntegrityError(
                    "persisted Analysis Version provenance is inconsistent"
                ) from error
            return analysis

    def save_case_projection(self, case: CaseInstance) -> None:
        with self.engine.begin() as connection:
            stored_case = self._require_case_runtime(
                connection,
                case_id=case.case_id,
                runtime_mode=case.runtime_mode,
            )
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
                    updated_at=datetime.now(UTC),
                )
            )
            if result.rowcount != 1:
                raise RecordNotFound(f"case projection does not exist: {case.case_id}")

    def list_cases(
        self,
        *,
        purpose: CasePurpose | None = None,
    ) -> tuple[CaseInstance, ...]:
        statement = select(case_projection).order_by(case_projection.c.case_id)
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
            cases: list[CaseInstance] = []
            for row in rows:
                case = self._decode_case(
                    row["payload_json"],
                    record_name="case projection",
                )
                stored_case = self._stored_case(connection, case.case_id)
                self._require_case_projection_integrity(row, case, stored_case)
                if case.runtime_mode is not self.runtime_mode:
                    continue
                if purpose is not None and case.purpose is not purpose:
                    continue
                cases.append(case)
            return tuple(cases)


def build_store(settings: Settings) -> CaseStore:
    from services.persistence.sqlite import sqlite_store

    return sqlite_store(
        settings.database_url,
        runtime_mode=settings.runtime_mode,
    )
