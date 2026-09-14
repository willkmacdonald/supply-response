from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Connection, and_, func, insert, select, update

from data.domain.analysis import AnalysisResponseOptionMaterial
from data.domain.cases import WorkflowVersion
from data.domain.finance import FinanceReviewStatus
from data.domain.proposals import (
    ProposalSelection,
    ProposalState,
    ProposalToken,
    SelectionReceipt,
)
from services.persistence.finance_reviews import SqlAlchemyFinanceReviewRepository
from services.persistence.store import (
    PersistenceIntegrityError,
    RecordNotFound,
    SqlAlchemyCaseRepository,
    serialize_model,
)
from services.persistence.tables import (
    case_projection,
    case_proposal_selections,
    finance_review_revisions,
)
from services.policy.finance_review import (
    FinanceReviewViolation,
    require_proposal_submitter,
    supersede_finance_review,
)

_HEX = re.compile(r"^[0-9a-f]{64}$")
_CAS_KEYS = {
    "current_analysis_id",
    "current_analysis_hash",
    "current_selection_id",
    "status",
    "payload_json",
    "updated_at",
}


class StaleProposal(RuntimeError):
    pass


class SelectionIdempotencyConflict(RuntimeError):
    pass


def _null_safe(column, value):
    return column.is_(None) if value is None else column == value


def _cas_projection(
    connection: Connection,
    *,
    case_id: str,
    expected: ProposalToken,
    values: Mapping[str, Any],
) -> None:
    unexpected = set(values) - _CAS_KEYS
    if unexpected:
        raise ValueError(
            f"unsupported proposal projection values: {sorted(unexpected)}"
        )
    result = connection.execute(
        update(case_projection)
        .where(
            case_projection.c.case_id == case_id,
            case_projection.c.proposal_generation == expected.generation,
            _null_safe(case_projection.c.current_analysis_id, expected.analysis_id),
            _null_safe(
                case_projection.c.current_analysis_hash, expected.analysis_material_hash
            ),
            _null_safe(case_projection.c.current_selection_id, expected.selection_id),
        )
        .values(**values, proposal_generation=expected.generation + 1)
    )
    if result.rowcount != 1:
        raise StaleProposal("Case analysis or proposal changed")


class SqlAlchemyProposalRepository:
    def __init__(self, store: Any, connection: Connection) -> None:
        self._store = store
        self._connection = connection
        self._finance = SqlAlchemyFinanceReviewRepository(store, connection)

    @staticmethod
    def _normalize(value: datetime) -> datetime:
        return value.astimezone(UTC).replace(tzinfo=None)

    @classmethod
    def _time_matches(cls, stored: datetime, expected: datetime) -> bool:
        actual = (
            stored.replace(tzinfo=None)
            if stored.tzinfo is None
            else stored.astimezone(UTC).replace(tzinfo=None)
        )
        return actual == cls._normalize(expected)

    def _token(self, case_id: str) -> ProposalToken:
        row = (
            self._connection.execute(
                select(case_projection).where(case_projection.c.case_id == case_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"case does not exist: {case_id}")
        return ProposalToken(
            generation=row["proposal_generation"],
            analysis_id=row["current_analysis_id"],
            analysis_material_hash=row["current_analysis_hash"],
            selection_id=row["current_selection_id"],
        )

    def _decode(self, row: Mapping[Any, Any]) -> SelectionReceipt:
        try:
            receipt = SelectionReceipt.model_validate_json(row["payload_json"])
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted proposal selection contains invalid JSON"
            ) from error
        selection, expected = receipt.selection, receipt.expected
        if (
            selection.selection_id != row["selection_id"]
            or selection.proposal.case_id != row["case_id"]
            or selection.proposal.analysis_id != row["analysis_id"]
            or selection.proposal.analysis_material_hash
            != row["analysis_material_hash"]
            or selection.workflow_version.value != row["workflow_version"]
            or selection.finance_review_id != row["finance_review_id"]
            or row["finance_review_revision"]
            != (1 if selection.finance_review_id else None)
            or expected.generation != row["expected_generation"]
            or expected.selection_id != row["expected_selection_id"]
            or expected.analysis_id != selection.proposal.analysis_id
            or expected.analysis_material_hash
            != selection.proposal.analysis_material_hash
            or receipt.idempotency_key != row["idempotency_key"]
            or receipt.request_fingerprint != row["request_fingerprint"]
            or not _HEX.fullmatch(row["request_fingerprint"])
            or not self._time_matches(row["submitted_at"], selection.submitted_at)
        ):
            raise PersistenceIntegrityError(
                "proposal selection duplicated columns conflict with canonical JSON"
            )
        self._validate_binding(receipt)
        return receipt

    def _validate_binding(self, receipt: SelectionReceipt) -> None:
        selection = receipt.selection
        case = self._store._stored_case(self._connection, selection.proposal.case_id)
        if case.effective_workflow_version is not WorkflowVersion.INDEPENDENT_FINANCE:
            raise PersistenceIntegrityError(
                "Case does not use independent Finance workflow"
            )
        try:
            require_proposal_submitter(selection.submitted_by)
        except FinanceReviewViolation as error:
            raise PersistenceIntegrityError(
                "proposal submitter violates Finance policy"
            ) from error
        analysis = SqlAlchemyCaseRepository(self._store, self._connection).get_analysis(
            selection.proposal.analysis_id
        )
        proposal = selection.proposal
        if (
            analysis.case_id != proposal.case_id
            or analysis.material_hash != proposal.analysis_material_hash
        ):
            raise PersistenceIntegrityError(
                "proposal conflicts with immutable Analysis Version"
            )
        material = next(
            (
                o
                for o in analysis.material.response_options
                if o.option_id == proposal.option_id
            ),
            None,
        )
        outer = next(
            (o for o in analysis.response_options if o.option_id == proposal.option_id),
            None,
        )
        if (
            material is None
            or outer is None
            or material.predicted is None
            or material.predicted.response_cost != proposal.response_cost
            or AnalysisResponseOptionMaterial.from_option(outer) != material
            or not outer.executable
            or not outer.active_mitigation
            or outer.predicted is None
            or outer.blocking_codes
        ):
            raise PersistenceIntegrityError(
                "proposal option is not an executable active mitigation"
            )
        if selection.finance_review_id is not None:
            review = self._finance.get_revision(selection.finance_review_id, 1)
            if (
                review.status is not FinanceReviewStatus.PENDING
                or review.proposal != proposal
                or review.submitted_by != selection.submitted_by
                or review.submitted_at != selection.submitted_at
            ):
                raise PersistenceIntegrityError(
                    "proposal selection conflicts with pending Finance review"
                )

    def get_selection(self, selection_id: str) -> ProposalSelection:
        row = (
            self._connection.execute(
                select(case_proposal_selections).where(
                    case_proposal_selections.c.selection_id == selection_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"proposal selection does not exist: {selection_id}")
        return self._decode(row).selection

    def get_selection_for_review(self, review_id: str) -> ProposalSelection:
        row = (
            self._connection.execute(
                select(case_proposal_selections.c.selection_id).where(
                    case_proposal_selections.c.finance_review_id == review_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"Finance review does not exist: {review_id}")
        return self.get_selection(row["selection_id"])

    def list_pending_case_ids(self) -> tuple[str, ...]:
        latest = (
            select(
                finance_review_revisions.c.review_id.label("review_id"),
                func.max(finance_review_revisions.c.revision).label("revision"),
            )
            .group_by(finance_review_revisions.c.review_id)
            .subquery()
        )
        query = (
            select(case_projection.c.case_id)
            .select_from(
                case_projection.join(
                    case_proposal_selections,
                    case_projection.c.current_selection_id
                    == case_proposal_selections.c.selection_id,
                )
                .join(
                    latest,
                    latest.c.review_id == case_proposal_selections.c.finance_review_id,
                )
                .join(
                    finance_review_revisions,
                    and_(
                        finance_review_revisions.c.review_id == latest.c.review_id,
                        finance_review_revisions.c.revision == latest.c.revision,
                    ),
                )
            )
            .where(finance_review_revisions.c.status == "pending")
            .order_by(
                case_proposal_selections.c.submitted_at, case_projection.c.case_id
            )
        )
        return tuple(self._connection.scalars(query))

    def get_by_idempotency_key(self, key: str) -> SelectionReceipt | None:
        row = (
            self._connection.execute(
                select(case_proposal_selections).where(
                    case_proposal_selections.c.idempotency_key == key
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else self._decode(row)

    def get_state(self, case_id: str) -> ProposalState:
        projection = SqlAlchemyCaseRepository(
            self._store, self._connection
        ).get_projection(case_id)
        del projection
        before = self._token(case_id)
        selection = (
            self.get_selection(before.selection_id) if before.selection_id else None
        )
        if selection is not None and (
            selection.proposal.case_id != case_id
            or selection.proposal.analysis_id != before.analysis_id
            or selection.proposal.analysis_material_hash
            != before.analysis_material_hash
        ):
            raise PersistenceIntegrityError(
                "current selection pointer conflicts with Case proposal token"
            )
        review = None
        revision = None
        if selection is not None and selection.finance_review_id is not None:
            review, revision = self._finance.get_latest(selection.finance_review_id)
        if self._token(case_id) != before:
            raise StaleProposal("Case analysis or proposal changed")
        return ProposalState(
            token=before, selection=selection, review=review, review_revision=revision
        )

    def _supersede(
        self, state: ProposalState, *, now: datetime, key: str, operation: str
    ) -> None:
        if state.review is None:
            return
        if state.review.status is FinanceReviewStatus.SUPERSEDED:
            raise PersistenceIntegrityError(
                "current proposal points to a superseded review"
            )
        superseded = supersede_finance_review(review=state.review, now=now)
        material = {
            "operation": operation,
            "selection_id": key.split(":", 1)[1],
            "prior_review_id": state.review.review_id,
            "prior_revision": state.review_revision,
            "superseded_at": now.isoformat(),
        }
        fingerprint = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self._finance.append(
            superseded,
            expected_revision=state.review_revision,
            idempotency_key=key,
            request_fingerprint=fingerprint,
        )

    def publish(self, receipt: SelectionReceipt) -> ProposalSelection:
        replay = self.get_by_idempotency_key(receipt.idempotency_key)
        if replay is not None:
            if replay == receipt:
                return replay.selection
            raise SelectionIdempotencyConflict(
                "Selection idempotency key was used for another request"
            )
        state = self.get_state(receipt.selection.proposal.case_id)
        if state.token != receipt.expected:
            raise StaleProposal("Case analysis or proposal changed")
        if (
            receipt.expected.analysis_id is None
            or receipt.selection.proposal.analysis_id != receipt.expected.analysis_id
            or receipt.selection.proposal.analysis_material_hash
            != receipt.expected.analysis_material_hash
        ):
            raise PersistenceIntegrityError(
                "selected proposal must bind the current Analysis Version"
            )
        self._validate_binding(receipt)
        selection = receipt.selection
        if selection.finance_review_id is not None:
            latest, latest_revision = self._finance.get_latest(
                selection.finance_review_id
            )
            if latest.status is not FinanceReviewStatus.PENDING or latest_revision != 1:
                raise PersistenceIntegrityError(
                    "new proposal requires a current revision-1 pending Finance review"
                )
        self._connection.execute(
            insert(case_proposal_selections).values(
                selection_id=selection.selection_id,
                case_id=selection.proposal.case_id,
                analysis_id=selection.proposal.analysis_id,
                analysis_material_hash=selection.proposal.analysis_material_hash,
                workflow_version=selection.workflow_version.value,
                finance_review_id=selection.finance_review_id,
                finance_review_revision=1 if selection.finance_review_id else None,
                expected_generation=receipt.expected.generation,
                expected_selection_id=receipt.expected.selection_id,
                idempotency_key=receipt.idempotency_key,
                request_fingerprint=receipt.request_fingerprint,
                submitted_at=self._normalize(selection.submitted_at),
                payload_json=serialize_model(receipt),
            )
        )
        _cas_projection(
            self._connection,
            case_id=selection.proposal.case_id,
            expected=receipt.expected,
            values={
                "current_selection_id": selection.selection_id,
                "updated_at": selection.submitted_at,
            },
        )
        self._supersede(
            state,
            now=selection.submitted_at,
            key=f"selection-supersede:{selection.selection_id}",
            operation="selection-supersede",
        )
        return selection

    def guard_current(self, case_id: str, *, expected: ProposalToken) -> ProposalToken:
        case = self._store._stored_case(self._connection, case_id)
        if case.effective_workflow_version is not WorkflowVersion.INDEPENDENT_FINANCE:
            raise PersistenceIntegrityError(
                "Case does not use independent Finance workflow"
            )
        state = self.get_state(case_id)
        if state.token != expected:
            raise StaleProposal("Case analysis or proposal changed")
        _cas_projection(
            self._connection,
            case_id=case_id,
            expected=expected,
            values={
                "current_selection_id": expected.selection_id,
                "updated_at": datetime.now(UTC),
            },
        )
        return expected.model_copy(update={"generation": expected.generation + 1})

    def withdraw_current(
        self,
        case_id: str,
        *,
        expected: ProposalToken,
        now: datetime,
        operation_id: str,
    ) -> ProposalToken:
        case = self._store._stored_case(self._connection, case_id)
        if case.effective_workflow_version is not WorkflowVersion.INDEPENDENT_FINANCE:
            raise PersistenceIntegrityError(
                "Case does not use independent Finance workflow"
            )
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Withdrawal time must be timezone-aware")
        if not operation_id.strip():
            raise ValueError("Withdrawal operation_id must be nonblank")
        state = self.get_state(case_id)
        if state.token != expected:
            raise StaleProposal("Case analysis or proposal changed")
        if state.selection is not None and now < state.selection.submitted_at:
            raise ValueError("Withdrawal cannot precede proposal submission")
        _cas_projection(
            self._connection,
            case_id=case_id,
            expected=expected,
            values={"current_selection_id": None, "updated_at": now},
        )
        if state.review is not None:
            superseded = supersede_finance_review(review=state.review, now=now)
            material = {
                "operation": "decision-withdraw",
                "decision_id": operation_id,
                "prior_review_id": state.review.review_id,
                "prior_revision": state.review_revision,
                "superseded_at": now.isoformat(),
            }
            fingerprint = hashlib.sha256(
                json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            self._finance.append(
                superseded,
                expected_revision=state.review_revision,
                idempotency_key=f"decision-withdraw:{operation_id}",
                request_fingerprint=fingerprint,
            )
        return expected.model_copy(
            update={"generation": expected.generation + 1, "selection_id": None}
        )
