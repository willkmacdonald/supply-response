# Existing concrete unit-of-work context manager intentionally uses its class type.
# ruff: noqa: PYI034

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, ValidationError
from sqlalchemy import Connection, Engine, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from data.domain import CaseInstance, CasePurpose, CaseStatus, RuntimeMode
from data.domain.analysis import AnalysisVersion
from data.domain.cases import WorkflowVersion
from data.domain.decisions import (
    ApprovalSatisfaction,
    CaseProjection,
    Decision,
    DecisionKind,
)
from data.domain.execution import (
    ALLOWED_TRANSITIONS,
    ActionPlanningRequested,
    DraftArtifact,
    ExecutionAction,
    ExecutionActionKind,
    ExecutionAttempt,
    ExecutionStatus,
    ExecutionStatusEvent,
    ObservationKind,
    OutboxClaim,
    OutboxClaimStatus,
    OutboxProcessingState,
    OutcomeObservation,
    Playback,
    PlaybackStatus,
)
from data.synthetic.rl001 import OperationalSnapshot
from services.analysis.service import (
    analysis_material_hash,
    canonical_operational_snapshot,
)
from services.persistence.ports import EXECUTION_PROPOSAL_STALE_ERROR, CaseStore
from services.persistence.tables import (
    action_projection,
    analysis_claims,
    analysis_versions,
    approval_satisfactions,
    case_instances,
    case_projection,
    decisions,
    draft_artifacts,
    evidence_items,
    execution_actions,
    execution_attempts,
    execution_events,
    operational_snapshots,
    outbox_events,
    outcome_observations,
    playbacks,
)
from services.policy.workflow import approval_policy_for

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


class AnalysisClaimBusy(PersistenceError):
    """Another process owns the bounded analysis material claim."""


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

    def _insert_playback_if_absent(
        self,
        connection: Connection,
        playback: Playback,
    ) -> bool:
        """Perform the physical database's atomic insert-if-absent operation."""
        raise NotImplementedError

    @staticmethod
    def _datetime_matches(stored: datetime, expected: datetime) -> bool:
        if stored.tzinfo is None and expected.tzinfo is not None:
            expected = expected.replace(tzinfo=None)
        return stored == expected

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )

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
        if material.approval_policy_version != approval_policy_for(stored_case):
            raise PersistenceIntegrityError(
                "Analysis approval policy must match its immutable Case Instance"
            )
        if (
            stored_case.effective_workflow_version
            is WorkflowVersion.INDEPENDENT_FINANCE
            and (
                any(
                    item.role == "finance_approver"
                    for item in material.standing_authorizations
                )
                or any(
                    item.role == "finance_approver"
                    for item in material.approval_satisfactions
                )
                or any(
                    item.role == "finance_approver"
                    for item in analysis.approval_satisfactions
                )
            )
        ):
            raise PersistenceIntegrityError(
                "Independent Finance approval policy cannot contain Finance standing evidence"
            )
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
            if (
                target_case.effective_workflow_version
                is not stored_case.effective_workflow_version
            ):
                raise PersistenceIntegrityError(
                    "Approval Satisfaction case policy must match its immutable Case Instance"
                )
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
            or case.effective_workflow_version
            is not stored_case.effective_workflow_version
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

    def get_operational_snapshot(self, case_id: str) -> OperationalSnapshot:
        """Load the immutable snapshot after re-checking its Case runtime."""
        with self.engine.connect() as connection:
            case = self._stored_case(connection, case_id)
            self._require_configured_mode(case.runtime_mode)
            snapshot = self._stored_snapshot(connection, case_id)
            if snapshot.runtime_mode is not case.runtime_mode:
                raise RuntimeModeConflict(
                    "Operational Snapshot runtime does not match Case Instance"
                )
            return snapshot

    def save_analysis(
        self,
        analysis: AnalysisVersion,
        *,
        projected_case: CaseInstance | None = None,
    ) -> None:
        try:
            with self.engine.begin() as connection:
                self._save_analysis_connection(connection, analysis, projected_case)
        except IntegrityError as error:
            raise ImmutableRecordConflict(
                f"analysis or nested immutable record already exists: "
                f"{analysis.analysis_id}"
            ) from error

    def _save_analysis_connection(
        self,
        connection: Connection,
        analysis: AnalysisVersion,
        projected_case: CaseInstance | None,
    ) -> None:
        """Insert an Analysis and advance its Case projection on one connection."""
        runtime_mode = analysis.material.runtime_mode
        self._require_analysis_provenance(connection, analysis)
        stored_case = self._stored_case(connection, analysis.case_id)
        proposal_state = None
        if (
            stored_case.effective_workflow_version
            is WorkflowVersion.INDEPENDENT_FINANCE
        ):
            from services.persistence.proposals import SqlAlchemyProposalRepository

            proposal_state = SqlAlchemyProposalRepository(self, connection).get_state(
                analysis.case_id
            )
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
        projection = (
            connection.execute(
                select(case_projection)
                .where(case_projection.c.case_id == analysis.case_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if projection is None:
            raise RecordNotFound(f"case projection does not exist: {analysis.case_id}")
        now = datetime.now(UTC)
        values = {
            "current_analysis_id": analysis.analysis_id,
            "current_analysis_hash": analysis.material_hash,
            "updated_at": now,
        }
        if projected_case is not None:
            self._require_case_projection_integrity(
                {
                    **projection,
                    "status": projected_case.status.value,
                    "payload_json": serialize_model(projected_case),
                },
                projected_case,
                stored_case,
            )
            values.update(
                status=projected_case.status.value,
                payload_json=serialize_model(projected_case),
            )
        if (
            projection["current_decision_id"] is not None
            and projection["current_analysis_hash"] is not None
            and (
                projection["current_analysis_hash"] != analysis.material_hash
                or stored_case.effective_workflow_version
                is WorkflowVersion.INDEPENDENT_FINANCE
            )
        ):
            changed_case = self._decode_case(
                projection["payload_json"], record_name="case projection"
            ).model_copy(update={"status": CaseStatus.REANALYSIS_REQUIRED})
            values.update(
                status=CaseStatus.REANALYSIS_REQUIRED.value,
                payload_json=serialize_model(changed_case),
            )
        if proposal_state is None:
            result = connection.execute(
                update(case_projection)
                .where(case_projection.c.case_id == analysis.case_id)
                .values(**values)
            )
            if result.rowcount != 1:
                raise RecordNotFound(
                    f"case projection does not exist: {analysis.case_id}"
                )
        else:
            from services.persistence.proposals import (
                SqlAlchemyProposalRepository,
                _cas_projection,
            )

            values["current_selection_id"] = None
            _cas_projection(
                connection,
                case_id=analysis.case_id,
                expected=proposal_state.token,
                values=values,
            )
            SqlAlchemyProposalRepository(self, connection)._supersede(
                proposal_state,
                now=now,
                key=f"analysis-supersede:{analysis.analysis_id}",
                operation="analysis-supersede",
            )

    def try_claim_analysis(
        self,
        *,
        case_id: str,
        material_version: str,
        claim_id: str,
        claimed_at: datetime,
        lease: timedelta = timedelta(minutes=5),
    ) -> bool:
        """Atomically claim material across workers, taking over only expired leases."""
        import hashlib

        version = hashlib.sha256(material_version.encode()).hexdigest()
        expires_at = claimed_at + lease
        try:
            with self.engine.begin() as connection:
                self._require_case_runtime(
                    connection, case_id=case_id, runtime_mode=self.runtime_mode
                )
                connection.execute(
                    insert(analysis_claims).values(
                        case_id=case_id,
                        material_version=version,
                        claim_id=claim_id,
                        claimed_at=claimed_at,
                        claim_expires_at=expires_at,
                    )
                )
            return True
        except IntegrityError:
            with self.engine.begin() as connection:
                result = connection.execute(
                    update(analysis_claims)
                    .where(
                        analysis_claims.c.case_id == case_id,
                        analysis_claims.c.material_version == version,
                        analysis_claims.c.claim_expires_at < claimed_at,
                    )
                    .values(
                        claim_id=claim_id,
                        claimed_at=claimed_at,
                        claim_expires_at=expires_at,
                    )
                )
                return result.rowcount == 1

    def release_analysis_claim(
        self, *, case_id: str, material_version: str, claim_id: str
    ) -> None:
        import hashlib

        version = hashlib.sha256(material_version.encode()).hexdigest()
        with self.engine.begin() as connection:
            connection.execute(
                analysis_claims.delete().where(
                    analysis_claims.c.case_id == case_id,
                    analysis_claims.c.material_version == version,
                    analysis_claims.c.claim_id == claim_id,
                )
            )

    def complete_analysis_claim(
        self,
        *,
        analysis: AnalysisVersion,
        projected_case: CaseInstance,
        material_version: str,
        claim_id: str,
        completed_at: datetime,
    ) -> AnalysisVersion:
        """Persist immutable analysis and projection in the existing one transaction."""
        import hashlib

        version = hashlib.sha256(material_version.encode()).hexdigest()
        try:
            with self.engine.begin() as connection:
                claim = (
                    connection.execute(
                        select(analysis_claims)
                        .where(
                            analysis_claims.c.case_id == analysis.case_id,
                            analysis_claims.c.material_version == version,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if (
                    claim is None
                    or claim["claim_id"] != claim_id
                    or self._normalize_datetime(claim["claim_expires_at"])
                    < self._normalize_datetime(completed_at)
                ):
                    raise AnalysisClaimBusy(
                        "analysis material claim is expired or owned elsewhere"
                    )
                self._save_analysis_connection(connection, analysis, projected_case)
                deleted = connection.execute(
                    analysis_claims.delete().where(
                        analysis_claims.c.case_id == analysis.case_id,
                        analysis_claims.c.material_version == version,
                        analysis_claims.c.claim_id == claim_id,
                    )
                )
                if deleted.rowcount != 1:
                    raise AnalysisClaimBusy("analysis material claim changed")
        except IntegrityError as error:
            raise AnalysisClaimBusy(
                "analysis completion lost its claim race"
            ) from error
        return analysis

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
                case.effective_workflow_version
                is not stored_case.effective_workflow_version
            ):
                raise PersistenceIntegrityError(
                    "case projection conflicts with immutable Case Instance policy"
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

    def uow_factory(
        self,
        *,
        before_decision_insert: Callable[[], None] | None = None,
        before_outbox_insert: Callable[[], None] | None = None,
    ) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(
            self,
            before_decision_insert=before_decision_insert,
            before_outbox_insert=before_outbox_insert,
        )

    def get_projection(self, case_id: str) -> CaseProjection:
        with self.uow_factory() as uow:
            return uow.cases.get_projection(case_id)

    def set_current_decision(self, case_id: str, decision_id: str) -> None:
        with self.uow_factory() as uow:
            uow.cases.set_current_decision(case_id, decision_id)
            uow.commit()

    def mark_rejected(self, case_id: str, decision_id: str) -> None:
        with self.uow_factory() as uow:
            uow.cases.mark_rejected(case_id, decision_id)
            uow.commit()

    def mark_action_planning_complete(self, case_id: str) -> None:
        with self.uow_factory() as uow:
            uow.cases.mark_action_planning_complete(case_id)
            uow.commit()

    def mark_action_planning_failed(self, case_id: str) -> None:
        with self.uow_factory() as uow:
            uow.cases.mark_action_planning_failed(case_id)
            uow.commit()


class SqlAlchemyCaseRepository:
    def __init__(self, store: SqlAlchemyStore, connection: Connection) -> None:
        self._store = store
        self._connection = connection

    def get_case(self, case_id: str) -> CaseInstance:
        return self.get_projection(case_id).case

    def get_analysis(self, analysis_id: str) -> AnalysisVersion:
        row = (
            self._connection.execute(
                select(analysis_versions).where(
                    analysis_versions.c.analysis_id == analysis_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"analysis does not exist: {analysis_id}")
        analysis = self._store._decode_analysis(row["payload_json"])
        self._store._require_analysis_row_integrity(row, analysis)
        try:
            self._store._require_analysis_provenance(self._connection, analysis)
        except PersistenceIntegrityError:
            raise
        except (RuntimeModeConflict, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted Analysis Version provenance is inconsistent"
            ) from error
        return analysis

    def get_projection(self, case_id: str) -> CaseProjection:
        row = (
            self._connection.execute(
                select(case_projection).where(case_projection.c.case_id == case_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"case does not exist: {case_id}")
        case = self._store._decode_case(
            row["payload_json"],
            record_name="case projection",
        )
        stored_case = self._store._stored_case(self._connection, case_id)
        self._store._require_case_projection_integrity(row, case, stored_case)
        self._store._require_configured_mode(case.runtime_mode)
        display_status = None
        if (
            case.status is CaseStatus.ACTION_PLANNING
            and row["current_decision_id"] is not None
        ):
            last_error = self._connection.scalar(
                select(outbox_events.c.last_error).where(
                    outbox_events.c.decision_id == row["current_decision_id"],
                    outbox_events.c.event_type == "ActionPlanningRequested",
                    outbox_events.c.processed_at.is_(None),
                )
            )
            if last_error is not None:
                display_status = "Approved — action planning failed"
        return CaseProjection(
            case=case,
            current_analysis_id=row["current_analysis_id"],
            current_analysis_hash=row["current_analysis_hash"],
            current_decision_id=row["current_decision_id"],
            display_status=display_status,
        )

    def _set_decision_projection(
        self,
        case_id: str,
        decision_id: str,
        *,
        status: CaseStatus,
    ) -> None:
        projection = self.get_projection(case_id)
        changed = projection.case.model_copy(update={"status": status})
        result = self._connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == case_id)
            .values(
                status=status.value,
                current_decision_id=decision_id,
                updated_at=datetime.now(UTC),
                payload_json=serialize_model(changed),
            )
        )
        if result.rowcount != 1:
            raise RecordNotFound(f"case projection does not exist: {case_id}")

    def set_current_decision(self, case_id: str, decision_id: str) -> None:
        self._set_decision_projection(
            case_id,
            decision_id,
            status=CaseStatus.ACTION_PLANNING,
        )

    def mark_rejected(self, case_id: str, decision_id: str) -> None:
        self._set_decision_projection(
            case_id,
            decision_id,
            status=CaseStatus.DECISION_REJECTED,
        )

    def _set_case_status(self, case_id: str, status: CaseStatus) -> None:
        projection = self.get_projection(case_id)
        changed = projection.case.model_copy(update={"status": status})
        result = self._connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == case_id)
            .values(
                status=status.value,
                updated_at=datetime.now(UTC),
                payload_json=serialize_model(changed),
            )
        )
        if result.rowcount != 1:
            raise RecordNotFound(f"case projection does not exist: {case_id}")

    def mark_action_planning_complete(self, case_id: str) -> None:
        self._set_case_status(case_id, CaseStatus.EXECUTING)

    def mark_action_planning_failed(self, case_id: str) -> None:
        self._set_case_status(case_id, CaseStatus.ACTION_PLANNING)


class SqlAlchemyDecisionRepository:
    def __init__(
        self,
        store: SqlAlchemyStore,
        connection: Connection,
        *,
        before_decision_insert: Callable[[], None] | None = None,
    ) -> None:
        self._store = store
        self._connection = connection
        self._before_decision_insert = before_decision_insert

    @staticmethod
    def _decode_decision(payload: str) -> Decision:
        try:
            return Decision.model_validate_json(payload)
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted Decision contains invalid JSON"
            ) from error

    def _decision_from_row(
        self,
        row,
        *,
        validate_outbox_cardinality: bool = True,
    ) -> Decision:
        decision = self._decode_decision(row["payload_json"])
        if (
            decision.decision_id != row["decision_id"]
            or decision.case_id != row["case_id"]
            or decision.analysis_id != row["analysis_id"]
            or decision.idempotency_key != row["idempotency_key"]
            or decision.kind.value != row["kind"]
            or decision.runtime_mode.value != row["runtime_mode"]
            or not self._store._datetime_matches(row["decided_at"], decision.decided_at)
        ):
            raise PersistenceIntegrityError(
                "decision columns conflict with canonical Decision JSON"
            )
        self._store._require_configured_mode(decision.runtime_mode)
        self._require_analysis_lineage(decision)
        self._require_bound_satisfactions(decision)
        if validate_outbox_cardinality:
            self._require_outbox_cardinality(decision)
        return decision

    def _require_analysis_lineage(self, decision: Decision) -> None:
        analysis = SqlAlchemyCaseRepository(self._store, self._connection).get_analysis(
            decision.analysis_id
        )
        if (
            analysis.case_id != decision.case_id
            or analysis.material_hash != decision.analysis_material_hash
            or analysis.material.runtime_mode is not decision.runtime_mode
            or analysis.material.scenario_effective_time
            != decision.scenario_effective_time
            or analysis.material.calculation_version != decision.calculation_version
            or analysis.material.evidence_policy_version
            != decision.evidence_policy_version
            or analysis.material.approval_policy_version
            != decision.approval_policy_version
            or analysis.ranking.policy_version != decision.ranking_policy_version
        ):
            raise PersistenceIntegrityError(
                "Decision analysis lineage conflicts with its immutable Analysis Version"
            )
        if analysis.ranking != decision.comparator_trace:
            raise PersistenceIntegrityError(
                "Decision comparator trace conflicts with its immutable Analysis Version"
            )
        self._require_proposal_lineage(decision)
        if decision.kind.value == "rejected":
            return
        option = next(
            (
                item
                for item in analysis.response_options
                if item.option_id == decision.selected_option_id
            ),
            None,
        )
        if (
            option is None
            or option != decision.selected_option
            or option.evidence_ids != decision.evidence_ids
            or option.assumptions != decision.assumptions
            or option.blocking_codes != decision.constraints
            or option.prerequisite_roles != decision.prerequisite_roles
        ):
            raise PersistenceIntegrityError(
                "Decision selected option conflicts with its immutable Analysis Version"
            )
        self._require_derived_satisfactions(decision, analysis, option)

    def _require_proposal_lineage(self, decision: Decision) -> None:
        evidence = decision.proposal_approval
        independent = (
            decision.approval_policy_version
            == WorkflowVersion.INDEPENDENT_FINANCE.value
        )
        if decision.kind is DecisionKind.REJECTED:
            if evidence is not None:
                raise PersistenceIntegrityError(
                    "Rejected Decision has proposal evidence"
                )
            return
        if independent != (evidence is not None):
            raise PersistenceIntegrityError(
                "Decision proposal evidence conflicts with policy"
            )
        if evidence is None:
            return
        from services.persistence.finance_reviews import (
            SqlAlchemyFinanceReviewRepository,
        )
        from services.persistence.proposals import SqlAlchemyProposalRepository

        try:
            selection = SqlAlchemyProposalRepository(
                self._store, self._connection
            ).get_selection(evidence.selection.selection_id)
        except RecordNotFound as error:
            raise PersistenceIntegrityError(
                "Decision proposal selection is absent from journal"
            ) from error
        if selection != evidence.selection:
            raise PersistenceIntegrityError(
                "Decision selection snapshot differs from journal"
            )
        if evidence.review is None:
            if evidence.review_revision is not None:
                raise PersistenceIntegrityError("Low-cost evidence has review revision")
            return
        if evidence.review_revision is None:
            raise PersistenceIntegrityError("Finance evidence lacks revision")
        try:
            review = SqlAlchemyFinanceReviewRepository(
                self._store, self._connection
            ).get_revision(evidence.review.review_id, evidence.review_revision)
        except RecordNotFound as error:
            raise PersistenceIntegrityError(
                "Decision Finance revision is absent from journal"
            ) from error
        if review != evidence.review:
            raise PersistenceIntegrityError(
                "Decision Finance snapshot differs from revision"
            )

    def _require_outbox_cardinality(self, decision: Decision) -> None:
        event_types = (
            self._connection.execute(
                select(outbox_events.c.event_type)
                .where(outbox_events.c.decision_id == decision.decision_id)
                .order_by(outbox_events.c.event_id)
            )
            .scalars()
            .all()
        )
        if decision.kind.value == "approved":
            if event_types != ["ActionPlanningRequested"]:
                raise PersistenceIntegrityError(
                    "approved Decision requires exactly one ActionPlanningRequested event"
                )
        elif event_types:
            raise PersistenceIntegrityError(
                "rejected Decision cannot have outbox events"
            )

    @staticmethod
    def _require_material_planner_satisfaction(
        satisfaction: ApprovalSatisfaction,
        *,
        decision: Decision,
        analysis: AnalysisVersion,
        option,
    ) -> bool:
        predicted = option.predicted
        conditions = satisfaction.authorization_conditions
        target = satisfaction.target
        return bool(
            predicted is not None
            and decision.actor.persona_id == "RL-PERSONA-ALEX"
            and decision.actor.source_id == "RL-ENTRA-ALEX"
            and decision.actor.identity_source.value == "entra"
            and "material_planner" in decision.actor.effective_roles
            and "response_approver" in decision.actor.effective_roles
            and satisfaction.role == "material_planner"
            and satisfaction.persona_id == decision.actor.persona_id
            and satisfaction.authorization_id == "RL-AUTH-ALEX-MATERIAL-DECISION"
            and satisfaction.analysis_id == decision.analysis_id
            and satisfaction.option_id == decision.selected_option_id
            and satisfaction.satisfied
            and target.case.case_id == decision.case_id
            and target.case.template_id == analysis.material.template_id
            and target.case.purpose is analysis.material.case_purpose
            and target.case.runtime_mode is decision.runtime_mode
            and target.scenario_effective_time == decision.scenario_effective_time
            and target.corpus is analysis.material.corpus
            and target.total_response_cost == predicted.response_cost
            and target.requested_side_effects == option.requested_side_effects
            and conditions.allowed_option_kinds == (option.option_kind,)
            and conditions.maximum_response_cost == predicted.response_cost
            and conditions.allowed_corpora == (analysis.material.corpus,)
            and conditions.allowed_template_ids == (analysis.material.template_id,)
            and conditions.allowed_case_purposes == (analysis.material.case_purpose,)
            and conditions.valid_from == decision.scenario_effective_time
            and conditions.valid_through == decision.scenario_effective_time
            and conditions.forbidden_external_side_effects == ()
        )

    def _require_derived_satisfactions(
        self,
        decision: Decision,
        analysis: AnalysisVersion,
        option,
    ) -> None:
        required_roles = set(option.prerequisite_roles) - {"response_approver"}
        if (
            decision.approval_policy_version
            == WorkflowVersion.INDEPENDENT_FINANCE.value
        ):
            required_roles.discard("finance_approver")
        actual_by_role = {item.role: item for item in decision.approval_satisfactions}
        if set(actual_by_role) != required_roles:
            raise PersistenceIntegrityError(
                "Decision required satisfaction roles conflict with Analysis Version"
            )
        for role in required_roles:
            actual = actual_by_role[role]
            if role == "material_planner":
                if not self._require_material_planner_satisfaction(
                    actual,
                    decision=decision,
                    analysis=analysis,
                    option=option,
                ):
                    raise PersistenceIntegrityError(
                        "Decision required satisfaction conflicts with Alex material approval"
                    )
                continue
            expected = tuple(
                item
                for item in analysis.approval_satisfactions
                if item.option_id == option.option_id and item.role == role
            )
            expected_personas = {
                "finance_approver": "RL-PERSONA-TAYLOR",
                "quality_approver": "RL-PERSONA-JORDAN",
            }
            if (
                len(expected) != 1
                or actual != expected[0]
                or (
                    role in expected_personas
                    and expected[0].persona_id != expected_personas[role]
                )
            ):
                raise PersistenceIntegrityError(
                    "Decision required satisfaction conflicts with Analysis Version"
                )

    def _require_bound_satisfactions(self, decision: Decision) -> None:
        rows = self._list_approval_satisfactions(decision.decision_id)
        expected = tuple(
            sorted(
                decision.approval_satisfactions,
                key=lambda item: (item.role, item.persona_id, item.authorization_id),
            )
        )
        actual = tuple(
            sorted(
                rows,
                key=lambda item: (item.role, item.persona_id, item.authorization_id),
            )
        )
        if actual != expected:
            raise PersistenceIntegrityError(
                "Decision Approval Satisfaction rows conflict with canonical JSON"
            )

    def get(self, decision_id: str) -> Decision:
        row = (
            self._connection.execute(
                select(decisions).where(decisions.c.decision_id == decision_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"decision does not exist: {decision_id}")
        return self._decision_from_row(row)

    def get_for_outbox_insert(self, decision_id: str) -> Decision:
        """Validate a Decision before its same-transaction outbox insert.

        The aggregate cardinality invariant deliberately waits until the
        transaction is committed; this call occurs between Decision and outbox
        inserts, when an approved Decision has no event yet.
        """
        row = (
            self._connection.execute(
                select(decisions).where(decisions.c.decision_id == decision_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"decision does not exist: {decision_id}")
        return self._decision_from_row(row, validate_outbox_cardinality=False)

    def get_by_idempotency_key(self, idempotency_key: str) -> Decision | None:
        row = (
            self._connection.execute(
                select(decisions).where(decisions.c.idempotency_key == idempotency_key)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else self._decision_from_row(row)

    def list_for_case(self, case_id: str) -> tuple[Decision, ...]:
        rows = (
            self._connection.execute(
                select(decisions)
                .where(decisions.c.case_id == case_id)
                .order_by(decisions.c.decided_at, decisions.c.decision_id)
            )
            .mappings()
            .all()
        )
        return tuple(self._decision_from_row(row) for row in rows)

    def insert(self, decision: Decision) -> None:
        if self._before_decision_insert is not None:
            self._before_decision_insert()
        self._store._require_configured_mode(decision.runtime_mode)
        stored_case = self._store._stored_case(self._connection, decision.case_id)
        if stored_case.runtime_mode is not decision.runtime_mode:
            raise RuntimeModeConflict(
                "Decision runtime_mode must match its immutable Case Instance"
            )
        self._require_analysis_lineage(decision)
        self._connection.execute(
            insert(decisions).values(
                decision_id=decision.decision_id,
                case_id=decision.case_id,
                analysis_id=decision.analysis_id,
                idempotency_key=decision.idempotency_key,
                kind=decision.kind.value,
                runtime_mode=decision.runtime_mode.value,
                decided_at=decision.decided_at,
                payload_json=serialize_model(decision),
            )
        )

    def insert_satisfactions(
        self,
        decision_id: str,
        satisfactions: tuple[ApprovalSatisfaction, ...],
    ) -> None:
        row = (
            self._connection.execute(
                select(decisions.c.payload_json).where(
                    decisions.c.decision_id == decision_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"decision does not exist: {decision_id}")
        decision = self._decode_decision(row["payload_json"])
        if not satisfactions:
            return
        for item in satisfactions:
            if (
                item.analysis_id != decision.analysis_id
                or item.option_id != decision.selected_option_id
            ):
                raise PersistenceIntegrityError(
                    "Decision Approval Satisfaction provenance is inconsistent"
                )
        self._connection.execute(
            insert(approval_satisfactions),
            [
                {
                    "analysis_id": item.analysis_id,
                    "decision_id": decision_id,
                    "option_id": item.option_id,
                    "authorization_id": item.authorization_id,
                    "persona_id": item.persona_id,
                    "role": item.role,
                    "satisfied": item.satisfied,
                    "payload_json": serialize_model(item),
                }
                for item in satisfactions
            ],
        )

    def list_approval_satisfactions(
        self,
        decision_id: str,
    ) -> tuple[ApprovalSatisfaction, ...]:
        return self._list_approval_satisfactions(decision_id)

    def _list_approval_satisfactions(
        self,
        decision_id: str,
    ) -> tuple[ApprovalSatisfaction, ...]:
        rows = (
            self._connection.execute(
                select(approval_satisfactions)
                .where(approval_satisfactions.c.decision_id == decision_id)
                .order_by(
                    approval_satisfactions.c.role,
                    approval_satisfactions.c.persona_id,
                )
            )
            .mappings()
            .all()
        )
        result: list[ApprovalSatisfaction] = []
        for row in rows:
            try:
                item = ApprovalSatisfaction.model_validate_json(row["payload_json"])
            except (ValidationError, ValueError) as error:
                raise PersistenceIntegrityError(
                    "persisted Approval Satisfaction contains invalid JSON"
                ) from error
            if (
                item.analysis_id != row["analysis_id"]
                or item.option_id != row["option_id"]
                or item.authorization_id != row["authorization_id"]
                or item.persona_id != row["persona_id"]
                or item.role != row["role"]
                or item.satisfied is not row["satisfied"]
            ):
                raise PersistenceIntegrityError(
                    "approval satisfaction columns conflict with canonical JSON"
                )
            result.append(item)
        return tuple(result)


class SqlAlchemyExecutionRepository:
    def __init__(
        self,
        store: SqlAlchemyStore,
        connection: Connection,
        *,
        before_outbox_insert: Callable[[], None] | None = None,
    ) -> None:
        self._store = store
        self._connection = connection
        self._before_outbox_insert = before_outbox_insert

    def insert_outbox(self, event: ActionPlanningRequested) -> None:
        decision = SqlAlchemyDecisionRepository(
            self._store,
            self._connection,
        ).get_for_outbox_insert(event.decision_id)
        if decision.kind.value != "approved":
            raise PersistenceIntegrityError(
                "outbox event requires an approved Decision"
            )
        if event.case_id != decision.case_id:
            raise PersistenceIntegrityError(
                "outbox case_id conflicts with its Decision"
            )
        if event.analysis_id != decision.analysis_id:
            raise PersistenceIntegrityError(
                "outbox analysis_id conflicts with its Decision"
            )
        if event.event_type != "ActionPlanningRequested":
            raise PersistenceIntegrityError("outbox event_type is invalid")
        if self._before_outbox_insert is not None:
            self._before_outbox_insert()
        self._connection.execute(
            insert(outbox_events).values(
                event_id=event.event_id,
                decision_id=event.decision_id,
                event_type=event.event_type,
                created_at=event.created_at,
                available_at=event.available_at,
                claim_status=event.claim_status.value,
                payload_json=serialize_model(event),
            )
        )

    def list_outbox(
        self,
        *,
        decision_id: str,
    ) -> tuple[ActionPlanningRequested, ...]:
        decision = SqlAlchemyDecisionRepository(self._store, self._connection).get(
            decision_id
        )
        rows = (
            self._connection.execute(
                select(outbox_events)
                .where(outbox_events.c.decision_id == decision_id)
                .order_by(outbox_events.c.created_at, outbox_events.c.event_id)
            )
            .mappings()
            .all()
        )
        events: list[ActionPlanningRequested] = []
        for row in rows:
            try:
                event = ActionPlanningRequested.model_validate_json(row["payload_json"])
            except (ValidationError, ValueError) as error:
                raise PersistenceIntegrityError(
                    "persisted outbox event contains invalid JSON"
                ) from error
            if (
                event.event_id != row["event_id"]
                or event.decision_id != row["decision_id"]
                or event.event_type != row["event_type"]
                or not self._store._datetime_matches(
                    row["created_at"], event.created_at
                )
                or not self._store._datetime_matches(
                    row["available_at"], event.available_at
                )
            ):
                raise PersistenceIntegrityError(
                    "outbox columns conflict with canonical event JSON"
                )
            if event.case_id != decision.case_id:
                raise PersistenceIntegrityError(
                    "outbox case_id conflicts with its Decision"
                )
            if event.analysis_id != decision.analysis_id:
                raise PersistenceIntegrityError(
                    "outbox analysis_id conflicts with its Decision"
                )
            if event.event_type != "ActionPlanningRequested":
                raise PersistenceIntegrityError("outbox event_type is invalid")
            if decision.kind.value != "approved":
                raise PersistenceIntegrityError(
                    "outbox event requires an approved Decision"
                )
            events.append(event)
        if decision.kind.value == "approved" and len(events) != 1:
            raise PersistenceIntegrityError(
                "approved Decision requires exactly one ActionPlanningRequested event"
            )
        if decision.kind.value == "rejected" and events:
            raise PersistenceIntegrityError(
                "rejected Decision cannot have outbox events"
            )
        return tuple(events)

    @staticmethod
    def _decode_outbox_event(row) -> ActionPlanningRequested:
        try:
            event = ActionPlanningRequested.model_validate_json(row["payload_json"])
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted outbox event contains invalid JSON"
            ) from error
        if (
            event.event_id != row["event_id"]
            or event.decision_id != row["decision_id"]
            or event.event_type != row["event_type"]
        ):
            raise PersistenceIntegrityError(
                "outbox columns conflict with canonical event JSON"
            )
        return event

    def claim_next_outbox(
        self,
        event_type: str,
        *,
        workflow_versions: tuple[WorkflowVersion, ...] | None = None,
    ) -> OutboxClaim | None:
        return self._claim_outbox(
            event_type,
            decision_id=None,
            include_failed=True,
            workflow_versions=workflow_versions,
        )

    def claim_next_unattempted_outbox(
        self,
        event_type: str,
        *,
        workflow_versions: tuple[WorkflowVersion, ...] | None = None,
    ) -> OutboxClaim | None:
        return self._claim_outbox(
            event_type,
            decision_id=None,
            include_failed=False,
            workflow_versions=workflow_versions,
        )

    def claim_outbox_for_decision(
        self,
        event_type: str,
        decision_id: str,
        *,
        workflow_versions: tuple[WorkflowVersion, ...] | None = None,
    ) -> OutboxClaim | None:
        return self._claim_outbox(
            event_type,
            decision_id=decision_id,
            include_failed=True,
            workflow_versions=workflow_versions,
        )

    def _claim_outbox(
        self,
        event_type: str,
        *,
        decision_id: str | None,
        include_failed: bool,
        workflow_versions: tuple[WorkflowVersion, ...] | None,
    ) -> OutboxClaim | None:
        if event_type != "ActionPlanningRequested":
            raise ValueError("unsupported outbox event type")
        now = datetime.now(UTC)
        claim_expires_at = now + timedelta(minutes=5)
        ready_to_claim = or_(
            outbox_events.c.claim_status == OutboxClaimStatus.PENDING.value,
            (
                (outbox_events.c.claim_status == OutboxClaimStatus.CLAIMED.value)
                & (outbox_events.c.claim_expires_at < now)
            ),
        )
        filters = [
            outbox_events.c.event_type == event_type,
            outbox_events.c.available_at <= now,
            outbox_events.c.processed_at.is_(None),
            ready_to_claim,
            or_(
                outbox_events.c.last_error.is_(None),
                outbox_events.c.last_error != EXECUTION_PROPOSAL_STALE_ERROR,
            ),
        ]
        if decision_id is not None:
            filters.append(outbox_events.c.decision_id == decision_id)
        if not include_failed:
            filters.append(outbox_events.c.last_error.is_(None))
        candidates = self._connection.execute(
            select(
                outbox_events.c.event_id,
                outbox_events.c.decision_id,
                outbox_events.c.event_type,
                decisions.c.case_id,
                decisions.c.analysis_id,
                case_instances.c.payload_json.label("case_payload_json"),
            )
            .join(decisions, decisions.c.decision_id == outbox_events.c.decision_id)
            .join(case_instances, case_instances.c.case_id == decisions.c.case_id)
            .where(*filters)
            .order_by(outbox_events.c.available_at, outbox_events.c.event_id)
        ).mappings()
        try:
            candidate = next(
                (
                    row
                    for row in candidates
                    if workflow_versions is None
                    or self._store._decode_case(
                        row["case_payload_json"], record_name="outbox Case"
                    ).effective_workflow_version
                    in workflow_versions
                ),
                None,
            )
        finally:
            candidates.close()
        if candidate is None:
            return None
        row = (
            self._connection.execute(
                update(outbox_events)
                .where(
                    outbox_events.c.event_id == candidate["event_id"],
                    *filters,
                )
                .values(
                    claim_status=OutboxClaimStatus.CLAIMED.value,
                    claimed_by="RL-EXECUTION-PLANNER",
                    claimed_at=now,
                    claim_expires_at=claim_expires_at,
                )
                .returning(outbox_events.c.event_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return OutboxClaim(
            event_id=candidate["event_id"],
            decision_id=candidate["decision_id"],
            case_id=candidate["case_id"],
            analysis_id=candidate["analysis_id"],
            event_type=candidate["event_type"],
        )

    def validate_claimed_outbox(
        self,
        claim: OutboxClaim,
    ) -> ActionPlanningRequested:
        row = (
            self._connection.execute(
                select(outbox_events).where(outbox_events.c.event_id == claim.event_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(
                f"claimed outbox event does not exist: {claim.event_id}"
            )
        event = self._decode_outbox_event(row)
        if (
            row["claim_status"] != OutboxClaimStatus.CLAIMED.value
            or row["processed_at"] is not None
            or event.event_id != claim.event_id
            or event.decision_id != claim.decision_id
            or event.case_id != claim.case_id
            or event.analysis_id != claim.analysis_id
            or event.event_type != claim.event_type
            or not self._store._datetime_matches(row["created_at"], event.created_at)
            or not self._store._datetime_matches(
                row["available_at"], event.available_at
            )
        ):
            raise PersistenceIntegrityError(
                "claimed outbox event conflicts with its canonical payload"
            )
        return event

    def mark_outbox_processed(self, event_id: str) -> None:
        result = self._connection.execute(
            update(outbox_events)
            .where(
                outbox_events.c.event_id == event_id,
                outbox_events.c.claim_status == OutboxClaimStatus.CLAIMED.value,
                outbox_events.c.processed_at.is_(None),
            )
            .values(
                claim_status=OutboxClaimStatus.PROCESSED.value,
                processed_at=datetime.now(UTC),
                claim_expires_at=None,
                last_error=None,
            )
        )
        if result.rowcount != 1:
            raise RecordNotFound(f"claimed outbox event does not exist: {event_id}")

    def record_outbox_failure(self, event_id: str, error_code: str) -> None:
        result = self._connection.execute(
            update(outbox_events)
            .where(
                outbox_events.c.event_id == event_id,
                outbox_events.c.processed_at.is_(None),
                or_(
                    outbox_events.c.last_error.is_(None),
                    outbox_events.c.last_error != EXECUTION_PROPOSAL_STALE_ERROR,
                ),
            )
            .values(
                claim_status=OutboxClaimStatus.PENDING.value,
                claimed_by=None,
                claimed_at=None,
                claim_expires_at=None,
                attempt_count=outbox_events.c.attempt_count + 1,
                last_error=error_code,
            )
        )
        if result.rowcount != 1:
            raise RecordNotFound(f"outbox event does not exist: {event_id}")

    def record_outbox_failure_if_current(
        self,
        event_id: str,
        *,
        expected: OutboxProcessingState,
        error_code: str,
    ) -> bool:
        if expected.event_id != event_id or not error_code.strip():
            raise ValueError("event identity and nonblank error code are required")
        if (
            expected.processed_at is not None
            or expected.last_error == EXECUTION_PROPOSAL_STALE_ERROR
        ):
            return False
        now = datetime.now(UTC)
        prior_error = (
            outbox_events.c.last_error.is_(None)
            if expected.last_error is None
            else outbox_events.c.last_error == expected.last_error
        )
        available = or_(
            outbox_events.c.claim_status == OutboxClaimStatus.PENDING.value,
            (outbox_events.c.claim_status == OutboxClaimStatus.CLAIMED.value)
            & (outbox_events.c.claim_expires_at < now),
        )
        result = self._connection.execute(
            update(outbox_events)
            .where(
                outbox_events.c.event_id == event_id,
                outbox_events.c.processed_at.is_(None),
                outbox_events.c.claim_status == expected.claim_status.value,
                outbox_events.c.attempt_count == expected.attempt_count,
                prior_error,
                available,
                or_(
                    outbox_events.c.last_error.is_(None),
                    outbox_events.c.last_error != EXECUTION_PROPOSAL_STALE_ERROR,
                ),
            )
            .values(
                claim_status=OutboxClaimStatus.PENDING.value,
                claimed_by=None,
                claimed_at=None,
                claim_expires_at=None,
                attempt_count=outbox_events.c.attempt_count + 1,
                last_error=error_code,
            )
        )
        return result.rowcount == 1

    def get_outbox_state(self, event_id: str) -> OutboxProcessingState:
        row = (
            self._connection.execute(
                select(outbox_events).where(outbox_events.c.event_id == event_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"outbox event does not exist: {event_id}")
        return OutboxProcessingState(
            event_id=row["event_id"],
            claim_status=OutboxClaimStatus(row["claim_status"]),
            processed_at=row["processed_at"],
            attempt_count=row["attempt_count"],
            last_error=row["last_error"],
        )

    @staticmethod
    def _decode_action(payload: str, *, record_name: str) -> ExecutionAction:
        try:
            return ExecutionAction.model_validate_json(payload)
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                f"{record_name} contains invalid Execution Action JSON"
            ) from error

    def _immutable_action(self, action_id: str) -> ExecutionAction:
        row = (
            self._connection.execute(
                select(execution_actions).where(
                    execution_actions.c.action_id == action_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"execution action does not exist: {action_id}")
        action = self._decode_action(
            row["payload_json"],
            record_name="immutable action record",
        )
        if (
            action.action_id != row["action_id"]
            or action.case_id != row["case_id"]
            or action.decision_id != row["decision_id"]
            or action.kind.value != row["action_kind"]
            or action.status.value != row["status"]
            or action.status is not ExecutionStatus.PLANNED
            or not self._store._datetime_matches(row["created_at"], action.created_at)
        ):
            raise PersistenceIntegrityError(
                "action columns conflict with canonical immutable JSON"
            )
        return action

    def insert_action_if_absent(self, action: ExecutionAction) -> bool:
        if action.status is not ExecutionStatus.PLANNED:
            raise ValueError("new execution actions must be planned")
        decision = SqlAlchemyDecisionRepository(self._store, self._connection).get(
            action.decision_id
        )
        if decision.kind.value != "approved" or action.case_id != decision.case_id:
            raise PersistenceIntegrityError(
                "Execution Action must match an approved Decision"
            )
        existing = self._connection.scalar(
            select(execution_actions.c.action_id).where(
                execution_actions.c.action_id == action.action_id
            )
        )
        if existing is not None:
            if self._immutable_action(action.action_id) != action:
                raise ImmutableRecordConflict(
                    f"execution action ID conflicts: {action.action_id}"
                )
            return False

        self._connection.execute(
            insert(execution_actions).values(
                action_id=action.action_id,
                case_id=action.case_id,
                decision_id=action.decision_id,
                action_kind=action.kind.value,
                status=action.status.value,
                created_at=action.created_at,
                payload_json=serialize_model(action),
            )
        )
        self._connection.execute(
            insert(action_projection).values(
                action_id=action.action_id,
                case_id=action.case_id,
                decision_id=action.decision_id,
                status=action.status.value,
                current_attempt=0,
                payload_json=serialize_model(action),
            )
        )
        initial_event = ExecutionStatusEvent(
            execution_event_id=f"RL-EXECUTION-EVENT-{uuid4()}",
            action_id=action.action_id,
            decision_id=action.decision_id,
            sequence_number=1,
            from_status=None,
            to_status=ExecutionStatus.PLANNED,
            occurred_at=action.created_at,
        )
        self.append_status_event(initial_event)
        if action.draft_artifact_id is not None:
            artifact = DraftArtifact(
                artifact_id=action.draft_artifact_id,
                action_id=action.action_id,
                decision_id=action.decision_id,
                created_at=action.created_at,
            )
            self._connection.execute(
                insert(draft_artifacts).values(
                    artifact_id=artifact.artifact_id,
                    action_id=artifact.action_id,
                    decision_id=artifact.decision_id,
                    artifact_kind=artifact.artifact_kind,
                    created_at=artifact.created_at,
                    payload_json=serialize_model(artifact),
                )
            )
        return True

    def get_action(self, action_id: str) -> ExecutionAction:
        immutable = self._immutable_action(action_id)
        row = (
            self._connection.execute(
                select(action_projection).where(
                    action_projection.c.action_id == action_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise PersistenceIntegrityError(
                f"action projection is missing: {action_id}"
            )
        projected = self._decode_action(
            row["payload_json"],
            record_name="action projection",
        )
        if (
            projected.action_id != row["action_id"]
            or projected.case_id != row["case_id"]
            or projected.decision_id != row["decision_id"]
            or projected.status.value != row["status"]
            or projected.model_copy(update={"status": ExecutionStatus.PLANNED})
            != immutable
        ):
            raise PersistenceIntegrityError(
                "action projection conflicts with its immutable Action"
            )
        return projected

    def list_actions(self, *, decision_id: str) -> tuple[ExecutionAction, ...]:
        action_ids = (
            self._connection.execute(
                select(execution_actions.c.action_id).where(
                    execution_actions.c.decision_id == decision_id
                )
            )
            .scalars()
            .all()
        )
        actions = [self.get_action(action_id) for action_id in action_ids]
        order = {kind.value: index for index, kind in enumerate(ExecutionActionKind)}
        return tuple(sorted(actions, key=lambda action: order[action.kind.value]))

    def get_draft_artifact(self, action_id: str) -> DraftArtifact:
        row = (
            self._connection.execute(
                select(draft_artifacts).where(draft_artifacts.c.action_id == action_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(
                f"Draft Artifact does not exist for action: {action_id}"
            )
        try:
            artifact = DraftArtifact.model_validate_json(row["payload_json"])
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted Draft Artifact contains invalid JSON"
            ) from error
        if (
            artifact.artifact_id != row["artifact_id"]
            or artifact.action_id != row["action_id"]
            or artifact.decision_id != row["decision_id"]
            or artifact.artifact_kind != row["artifact_kind"]
            or not self._store._datetime_matches(row["created_at"], artifact.created_at)
            or artifact.sent is not False
        ):
            raise PersistenceIntegrityError(
                "Draft Artifact columns conflict with canonical unsent JSON"
            )
        return artifact

    def fill_draft_artifact(self, artifact: DraftArtifact) -> None:
        previous = self.get_draft_artifact(artifact.action_id)
        if previous.artifact_id != artifact.artifact_id:
            raise ImmutableRecordConflict("Draft Artifact ID cannot be changed")
        if artifact.sent is not False:
            raise ImmutableRecordConflict("Draft Artifact must remain unsent")
        if previous.subject is not None:
            if previous != artifact:
                raise ImmutableRecordConflict("Draft Artifact content is insert-only")
            return
        if artifact.subject is None or artifact.body is None:
            raise ValueError("Draft Artifact content is required")
        if artifact.model_copy(update={"subject": None, "body": None}) != previous:
            raise ImmutableRecordConflict(
                "Draft Artifact fill cannot change immutable fields"
            )
        self._connection.execute(
            update(draft_artifacts)
            .where(draft_artifacts.c.artifact_id == artifact.artifact_id)
            .values(payload_json=serialize_model(artifact))
        )

    @staticmethod
    def _decode_attempt(payload: str) -> ExecutionAttempt:
        try:
            return ExecutionAttempt.model_validate_json(payload)
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted Execution Attempt contains invalid JSON"
            ) from error

    def _attempt_from_row(self, row) -> ExecutionAttempt:
        attempt = self._decode_attempt(row["payload_json"])
        if (
            attempt.attempt_id != row["attempt_id"]
            or attempt.action_id != row["action_id"]
            or attempt.decision_id != row["decision_id"]
            or attempt.attempt_number != row["attempt_number"]
            or attempt.status.value != row["status"]
            or not self._store._datetime_matches(row["started_at"], attempt.started_at)
            or (attempt.completed_at is None and row["completed_at"] is not None)
            or (
                attempt.completed_at is not None
                and (
                    row["completed_at"] is None
                    or not self._store._datetime_matches(
                        row["completed_at"], attempt.completed_at
                    )
                )
            )
        ):
            raise PersistenceIntegrityError(
                "Execution Attempt columns conflict with canonical JSON"
            )
        return attempt

    def insert_attempt(self, attempt: ExecutionAttempt) -> None:
        action = self.get_action(attempt.action_id)
        existing = self.list_attempts(attempt.action_id)
        if (
            attempt.decision_id != action.decision_id
            or attempt.attempt_number != len(existing) + 1
            or attempt.status is not ExecutionStatus.IN_PROGRESS
            or attempt.completed_at is not None
        ):
            raise PersistenceIntegrityError("Execution Attempt is inconsistent")
        self._connection.execute(
            insert(execution_attempts).values(
                attempt_id=attempt.attempt_id,
                action_id=attempt.action_id,
                decision_id=attempt.decision_id,
                attempt_number=attempt.attempt_number,
                status=attempt.status.value,
                started_at=attempt.started_at,
                completed_at=attempt.completed_at,
                payload_json=serialize_model(attempt),
            )
        )
        self._connection.execute(
            update(action_projection)
            .where(action_projection.c.action_id == attempt.action_id)
            .values(current_attempt=attempt.attempt_number)
        )

    def update_attempt(self, attempt: ExecutionAttempt) -> None:
        previous = self.get_attempt(attempt.attempt_id)
        if (
            previous.status is not ExecutionStatus.IN_PROGRESS
            or attempt.action_id != previous.action_id
            or attempt.decision_id != previous.decision_id
            or attempt.attempt_number != previous.attempt_number
            or attempt.started_at != previous.started_at
            or attempt.status
            not in {
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
            }
            or attempt.completed_at is None
        ):
            raise PersistenceIntegrityError(
                "Execution Attempt update would rewrite immutable attempt history"
            )
        self._connection.execute(
            update(execution_attempts)
            .where(execution_attempts.c.attempt_id == attempt.attempt_id)
            .values(
                status=attempt.status.value,
                completed_at=attempt.completed_at,
                payload_json=serialize_model(attempt),
            )
        )

    def get_attempt(self, attempt_id: str) -> ExecutionAttempt:
        row = (
            self._connection.execute(
                select(execution_attempts).where(
                    execution_attempts.c.attempt_id == attempt_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"Execution Attempt does not exist: {attempt_id}")
        return self._attempt_from_row(row)

    def list_attempts(self, action_id: str) -> tuple[ExecutionAttempt, ...]:
        rows = (
            self._connection.execute(
                select(execution_attempts)
                .where(execution_attempts.c.action_id == action_id)
                .order_by(execution_attempts.c.attempt_number)
            )
            .mappings()
            .all()
        )
        return tuple(self._attempt_from_row(row) for row in rows)

    def update_action_projection(self, action: ExecutionAction) -> None:
        immutable = self._immutable_action(action.action_id)
        if action.model_copy(update={"status": ExecutionStatus.PLANNED}) != immutable:
            raise ImmutableRecordConflict(
                "action projection cannot change immutable Action fields"
            )
        result = self._connection.execute(
            update(action_projection)
            .where(action_projection.c.action_id == action.action_id)
            .values(
                status=action.status.value,
                updated_at=datetime.now(UTC),
                payload_json=serialize_model(action),
            )
        )
        if result.rowcount != 1:
            raise RecordNotFound(
                f"action projection does not exist: {action.action_id}"
            )

    def append_status_event(self, event: ExecutionStatusEvent) -> None:
        action = self._immutable_action(event.action_id)
        existing = self.list_status_events(event.action_id)
        if (
            event.decision_id != action.decision_id
            or event.sequence_number != len(existing) + 1
        ):
            raise PersistenceIntegrityError(
                "Execution Status Event sequence or lineage is inconsistent"
            )
        if not existing:
            if (
                event.from_status is not None
                or event.to_status is not ExecutionStatus.PLANNED
            ):
                raise PersistenceIntegrityError(
                    "first Execution Status Event must establish planned state"
                )
        else:
            from_status = event.from_status
            if (
                from_status is None
                or from_status is not existing[-1].to_status
                or event.to_status not in ALLOWED_TRANSITIONS[from_status]
            ):
                raise PersistenceIntegrityError(
                    "Execution Status Event violates the transition graph"
                )
        self._connection.execute(
            insert(execution_events).values(
                execution_event_id=event.execution_event_id,
                action_id=event.action_id,
                decision_id=event.decision_id,
                event_type="ExecutionStatusChanged",
                occurred_at=event.occurred_at,
                payload_json=serialize_model(event),
            )
        )

    def list_status_events(
        self,
        action_id: str,
    ) -> tuple[ExecutionStatusEvent, ...]:
        rows = (
            self._connection.execute(
                select(execution_events).where(
                    execution_events.c.action_id == action_id
                )
            )
            .mappings()
            .all()
        )
        events: list[ExecutionStatusEvent] = []
        for row in rows:
            try:
                event = ExecutionStatusEvent.model_validate_json(row["payload_json"])
            except (ValidationError, ValueError) as error:
                raise PersistenceIntegrityError(
                    "persisted Execution Status Event contains invalid JSON"
                ) from error
            if (
                event.execution_event_id != row["execution_event_id"]
                or event.action_id != row["action_id"]
                or event.decision_id != row["decision_id"]
                or row["event_type"] != "ExecutionStatusChanged"
                or not self._store._datetime_matches(
                    row["occurred_at"], event.occurred_at
                )
            ):
                raise PersistenceIntegrityError(
                    "Execution Status Event columns conflict with canonical JSON"
                )
            events.append(event)
        ordered = tuple(sorted(events, key=lambda event: event.sequence_number))
        if [event.sequence_number for event in ordered] != list(
            range(1, len(ordered) + 1)
        ):
            raise PersistenceIntegrityError("Execution Status Event history has gaps")
        return ordered

    @staticmethod
    def _decode_playback(payload: str) -> Playback:
        try:
            return Playback.model_validate_json(payload)
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted Playback contains invalid JSON"
            ) from error

    def _playback_from_row(self, row) -> Playback:
        playback = self._decode_playback(row["payload_json"])
        if (
            playback.playback_id != row["playback_id"]
            or playback.case_id != row["case_id"]
            or playback.decision_id != row["decision_id"]
            or playback.status.value != row["status"]
            or not self._store._datetime_matches(row["started_at"], playback.started_at)
            or (playback.completed_at is None and row["completed_at"] is not None)
            or (
                playback.completed_at is not None
                and (
                    row["completed_at"] is None
                    or not self._store._datetime_matches(
                        row["completed_at"], playback.completed_at
                    )
                )
            )
            or (playback.failed_at is None and row["failed_at"] is not None)
            or (
                playback.failed_at is not None
                and (
                    row["failed_at"] is None
                    or not self._store._datetime_matches(
                        row["failed_at"], playback.failed_at
                    )
                )
            )
            or playback.error_code != row["error_code"]
        ):
            raise PersistenceIntegrityError(
                "Playback columns conflict with canonical JSON"
            )
        return playback

    def insert_playback_if_absent(self, playback: Playback) -> bool:
        if (
            playback.status is not PlaybackStatus.IN_PROGRESS
            or playback.completed_at is not None
        ):
            raise ValueError("new Playback must be in progress")
        decision = SqlAlchemyDecisionRepository(self._store, self._connection).get(
            playback.decision_id
        )
        if (
            decision.kind.value != "approved"
            or decision.case_id != playback.case_id
            or decision.actor != playback.actor
        ):
            raise PersistenceIntegrityError(
                "Playback must retain its approved Decision and actor lineage"
            )
        existing = self.get_playback_for_decision(playback.decision_id)
        if existing is not None:
            if existing.playback_id != playback.playback_id:
                raise ImmutableRecordConflict(
                    "Decision already has a different Playback"
                )
            return False
        inserted = self._store._insert_playback_if_absent(
            self._connection,
            playback,
        )
        canonical = self.get_playback_for_decision(playback.decision_id)
        if canonical is None:
            raise PersistenceIntegrityError(
                "Playback insert did not persist a canonical record"
            )
        if canonical.playback_id != playback.playback_id:
            raise ImmutableRecordConflict("Decision already has a different Playback")
        return inserted

    def get_playback(self, playback_id: str) -> Playback:
        row = (
            self._connection.execute(
                select(playbacks).where(playbacks.c.playback_id == playback_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"Playback does not exist: {playback_id}")
        return self._playback_from_row(row)

    def get_playback_for_decision(self, decision_id: str) -> Playback | None:
        row = (
            self._connection.execute(
                select(playbacks).where(playbacks.c.decision_id == decision_id)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else self._playback_from_row(row)

    def update_playback(self, playback: Playback) -> None:
        previous = self.get_playback(playback.playback_id)
        restored = playback.model_copy(
            update={
                "status": PlaybackStatus.IN_PROGRESS,
                "completed_at": None,
                "failed_at": None,
                "error_code": None,
            }
        )
        if (
            previous.status is not PlaybackStatus.IN_PROGRESS
            or playback.status not in {PlaybackStatus.COMPLETED, PlaybackStatus.FAILED}
            or restored != previous
        ):
            raise ImmutableRecordConflict(
                "Playback update may only record one terminal result"
            )
        result = self._connection.execute(
            update(playbacks)
            .where(
                playbacks.c.playback_id == playback.playback_id,
                playbacks.c.status == PlaybackStatus.IN_PROGRESS.value,
            )
            .values(
                status=playback.status.value,
                completed_at=playback.completed_at,
                failed_at=playback.failed_at,
                error_code=playback.error_code,
                payload_json=serialize_model(playback),
            )
        )
        if result.rowcount != 1:
            raise ImmutableRecordConflict("Playback already has a terminal result")

    @staticmethod
    def _decode_observation(payload: str) -> OutcomeObservation:
        try:
            return OutcomeObservation.model_validate_json(payload)
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted Outcome Observation contains invalid JSON"
            ) from error

    def _observation_from_row(self, row) -> OutcomeObservation:
        observation = self._decode_observation(row["payload_json"])
        if (
            observation.observation_id != row["observation_id"]
            or observation.case_id != row["case_id"]
            or observation.decision_id != row["decision_id"]
            or observation.playback_id != row["playback_id"]
            or observation.action_id != row["action_id"]
            or observation.metric != row["metric"]
            or observation.observed_value != row["observed_value"]
            or observation.unit != row["unit"]
            or observation.predicted_value != row["predicted_value"]
            or not self._store._datetime_matches(
                row["scenario_effective_time"],
                observation.scenario_effective_time,
            )
            or observation.scenario_timezone != row["scenario_timezone"]
            or not self._store._datetime_matches(
                row["recorded_at"], observation.recorded_at
            )
            or observation.source_reference != row["source_reference"]
            or observation.kind.value != row["kind"]
            or observation.synthetic is not bool(row["synthetic"])
        ):
            raise PersistenceIntegrityError(
                "Outcome Observation columns conflict with canonical JSON"
            )
        return observation

    def insert_observation(self, observation: OutcomeObservation) -> None:
        decision = SqlAlchemyDecisionRepository(self._store, self._connection).get(
            observation.decision_id
        )
        case = self._store._stored_case(self._connection, decision.case_id)
        if (
            observation.case_id != decision.case_id
            or observation.scenario_effective_time != decision.scenario_effective_time
            or observation.scenario_timezone != case.scenario_timezone
        ):
            raise PersistenceIntegrityError(
                "Outcome Observation conflicts with its Decision or Case lineage"
            )
        if observation.playback_id is not None:
            playback = self.get_playback(observation.playback_id)
            if (
                playback.decision_id != observation.decision_id
                or observation.kind is not ObservationKind.SIMULATED
                or not observation.synthetic
            ):
                raise PersistenceIntegrityError(
                    "Playback observation provenance must remain simulated"
                )
        if observation.action_id is not None:
            action = self.get_action(observation.action_id)
            if action.decision_id != observation.decision_id:
                raise PersistenceIntegrityError(
                    "Outcome Observation action lineage is inconsistent"
                )
        existing = (
            self._connection.execute(
                select(outcome_observations).where(
                    outcome_observations.c.observation_id == observation.observation_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            raise ImmutableRecordConflict(
                f"Outcome Observation is append-only: {observation.observation_id}"
            )
        self._connection.execute(
            insert(outcome_observations).values(
                observation_id=observation.observation_id,
                case_id=observation.case_id,
                decision_id=observation.decision_id,
                playback_id=observation.playback_id,
                action_id=observation.action_id,
                metric=observation.metric,
                observed_value=observation.observed_value,
                unit=observation.unit,
                predicted_value=observation.predicted_value,
                scenario_effective_time=observation.scenario_effective_time,
                scenario_timezone=observation.scenario_timezone,
                recorded_at=observation.recorded_at,
                source_reference=observation.source_reference,
                kind=observation.kind.value,
                synthetic=observation.synthetic,
                payload_json=serialize_model(observation),
            )
        )

    def list_observations(
        self,
        decision_id: str,
    ) -> tuple[OutcomeObservation, ...]:
        rows = (
            self._connection.execute(
                select(outcome_observations)
                .where(outcome_observations.c.decision_id == decision_id)
                .order_by(
                    outcome_observations.c.recorded_at,
                    outcome_observations.c.observation_id,
                )
            )
            .mappings()
            .all()
        )
        return tuple(self._observation_from_row(row) for row in rows)


class SqlAlchemyUnitOfWork:
    def __init__(
        self,
        store: SqlAlchemyStore,
        *,
        before_decision_insert: Callable[[], None] | None = None,
        before_outbox_insert: Callable[[], None] | None = None,
    ) -> None:
        self._store = store
        self._before_decision_insert = before_decision_insert
        self._before_outbox_insert = before_outbox_insert
        self._connection: Connection | None = None
        self._transaction = None

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        from services.persistence.finance_reviews import (
            SqlAlchemyFinanceReviewRepository,
        )
        from services.persistence.proposals import SqlAlchemyProposalRepository

        self._connection = self._store.engine.connect()
        self._transaction = self._connection.begin()
        self.cases = SqlAlchemyCaseRepository(self._store, self._connection)
        self.decisions = SqlAlchemyDecisionRepository(
            self._store,
            self._connection,
            before_decision_insert=self._before_decision_insert,
        )
        self.execution = SqlAlchemyExecutionRepository(
            self._store,
            self._connection,
            before_outbox_insert=self._before_outbox_insert,
        )
        self.finance_reviews = SqlAlchemyFinanceReviewRepository(
            self._store, self._connection
        )
        self.proposals = SqlAlchemyProposalRepository(self._store, self._connection)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        try:
            if self._transaction is not None and self._transaction.is_active:
                self._transaction.rollback()
        finally:
            if self._connection is not None:
                self._connection.close()

    def commit(self) -> None:
        if self._transaction is None or not self._transaction.is_active:
            raise PersistenceError("unit of work has no active transaction")
        self._transaction.commit()

    def rollback(self) -> None:
        if self._transaction is not None and self._transaction.is_active:
            self._transaction.rollback()


def build_store(settings: Settings) -> CaseStore:
    if settings.runtime_mode is RuntimeMode.LIVE:
        from services.persistence.fabric_sql import fabric_store

        return fabric_store(settings)
    from services.persistence.sqlite import sqlite_store

    if settings.database_url is None:
        raise ValueError("fallback database URL is not configured")
    return sqlite_store(
        settings.database_url,
        runtime_mode=settings.runtime_mode,
    )
