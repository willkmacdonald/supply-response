from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Connection, insert, select
from sqlalchemy.exc import IntegrityError

from data.domain.analysis import AnalysisResponseOptionMaterial, AnalysisVersion
from data.domain.finance import FinanceReview, FinanceReviewStatus
from services.persistence.ports import UnitOfWork
from services.persistence.store import (
    PersistenceIntegrityError,
    RecordNotFound,
    SqlAlchemyCaseRepository,
    serialize_model,
)
from services.persistence.tables import finance_review_revisions
from services.policy.finance_review import (
    FinanceReviewViolation,
    resolve_finance_review,
    submit_finance_review,
    supersede_finance_review,
)

UnitOfWorkFactory = Callable[[], UnitOfWork]
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class FinanceReviewIdempotencyConflict(RuntimeError):
    pass


class FinanceReviewRevisionConflict(RuntimeError):
    pass


class SqlAlchemyFinanceReviewRepository:
    def __init__(self, store: Any, connection: Connection) -> None:
        self._store = store
        self._connection = connection

    @staticmethod
    def _normalize(value: datetime) -> datetime:
        return value.astimezone(UTC).replace(tzinfo=None)

    @classmethod
    def _time_matches(cls, stored: datetime, expected: datetime) -> bool:
        normalized = cls._normalize(expected)
        return (
            stored.replace(tzinfo=None)
            if stored.tzinfo is None
            else stored.astimezone(UTC).replace(tzinfo=None)
        ) == normalized

    @staticmethod
    def _recorded_at(review: FinanceReview) -> datetime:
        return review.superseded_at or review.reviewed_at or review.submitted_at

    def _analysis(self, review: FinanceReview) -> AnalysisVersion:
        try:
            return SqlAlchemyCaseRepository(self._store, self._connection).get_analysis(
                review.proposal.analysis_id
            )
        except RecordNotFound as error:
            raise PersistenceIntegrityError(
                "Finance review Analysis Version does not exist"
            ) from error

    def _require_bound_analysis(self, review: FinanceReview) -> None:
        analysis = self._analysis(review)
        proposal = review.proposal
        if (
            proposal.case_id != analysis.case_id
            or proposal.analysis_material_hash != analysis.material_hash
        ):
            raise PersistenceIntegrityError(
                "Finance proposal conflicts with immutable Analysis Version"
            )
        material_option = next(
            (
                item
                for item in analysis.material.response_options
                if item.option_id == proposal.option_id
            ),
            None,
        )
        outer_option = next(
            (
                item
                for item in analysis.response_options
                if item.option_id == proposal.option_id
            ),
            None,
        )
        if (
            material_option is None
            or material_option.predicted is None
            or material_option.predicted.response_cost != proposal.response_cost
            or outer_option is None
            or AnalysisResponseOptionMaterial.from_option(outer_option)
            != material_option
        ):
            raise PersistenceIntegrityError(
                "Finance proposal option or evaluated cost conflicts with Analysis Version"
            )

    def _from_row(self, row: Mapping[Any, Any]) -> tuple[FinanceReview, int]:
        try:
            review = FinanceReview.model_validate_json(row["payload_json"])
        except (ValidationError, ValueError) as error:
            raise PersistenceIntegrityError(
                "persisted Finance Review contains invalid JSON"
            ) from error
        revision = row["revision"]
        recorded = self._recorded_at(review)
        if (
            isinstance(revision, bool)
            or not isinstance(revision, int)
            or revision <= 0
            or review.review_id != row["review_id"]
            or review.proposal.case_id != row["case_id"]
            or review.proposal.analysis_id != row["analysis_id"]
            or review.proposal.analysis_material_hash != row["analysis_material_hash"]
            or review.proposal.option_id != row["option_id"]
            or review.status.value != row["status"]
            or not _FINGERPRINT.fullmatch(row["request_fingerprint"])
            or not self._time_matches(row["recorded_at"], recorded)
        ):
            raise PersistenceIntegrityError(
                "Finance Review duplicated columns conflict with canonical JSON"
            )
        self._require_bound_analysis(review)
        return review, revision

    def get_latest(self, review_id: str) -> tuple[FinanceReview, int]:
        row = (
            self._connection.execute(
                select(finance_review_revisions)
                .where(finance_review_revisions.c.review_id == review_id)
                .order_by(finance_review_revisions.c.revision.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(f"finance review does not exist: {review_id}")
        return self._from_row(row)

    def get_revision(self, review_id: str, revision: int) -> FinanceReview:
        if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 0:
            raise ValueError("revision must be a positive integer")
        row = (
            self._connection.execute(
                select(finance_review_revisions).where(
                    finance_review_revisions.c.review_id == review_id,
                    finance_review_revisions.c.revision == revision,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound(
                f"finance review revision does not exist: {review_id}/{revision}"
            )
        return self._from_row(row)[0]

    def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> tuple[FinanceReview, int, str] | None:
        row = (
            self._connection.execute(
                select(finance_review_revisions).where(
                    finance_review_revisions.c.idempotency_key == idempotency_key
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        review, revision = self._from_row(row)
        return review, revision, row["request_fingerprint"]

    def append(
        self,
        review: FinanceReview,
        *,
        expected_revision: int | None,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[FinanceReview, int]:
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision <= 0
        ):
            raise ValueError("expected_revision must be a positive integer or None")
        if not idempotency_key or not idempotency_key.strip():
            raise ValueError("idempotency_key must be nonblank")
        if not _FINGERPRINT.fullmatch(request_fingerprint):
            raise ValueError("request_fingerprint must be lowercase 64-hex")
        replay = self.get_by_idempotency_key(idempotency_key)
        if replay is not None:
            stored, revision, fingerprint = replay
            if stored == review and fingerprint == request_fingerprint:
                return stored, revision
            raise FinanceReviewIdempotencyConflict(
                "Finance idempotency key was used for another request"
            )
        try:
            previous, current_revision = self.get_latest(review.review_id)
        except RecordNotFound:
            previous, current_revision = None, None
        if current_revision != expected_revision:
            raise FinanceReviewRevisionConflict(
                f"expected revision {expected_revision}; current revision is {current_revision}"
            )
        if previous is None:
            if review.status is not FinanceReviewStatus.PENDING:
                raise PersistenceIntegrityError(
                    "first Finance review revision must be pending"
                )
            try:
                canonical = submit_finance_review(
                    review_id=review.review_id,
                    proposal=review.proposal,
                    actor=review.submitted_by,
                    now=review.submitted_at,
                )
            except FinanceReviewViolation as error:
                raise PersistenceIntegrityError(
                    "first Finance review revision violates submission policy"
                ) from error
            if canonical != review:
                raise PersistenceIntegrityError(
                    "first Finance review revision is not canonical"
                )
            revision = 1
        else:
            allowed = {
                FinanceReviewStatus.PENDING: {
                    FinanceReviewStatus.APPROVED,
                    FinanceReviewStatus.REJECTED,
                    FinanceReviewStatus.SUPERSEDED,
                },
                FinanceReviewStatus.APPROVED: {FinanceReviewStatus.SUPERSEDED},
                FinanceReviewStatus.REJECTED: {FinanceReviewStatus.SUPERSEDED},
                FinanceReviewStatus.SUPERSEDED: set(),
            }
            if (
                review.status not in allowed[previous.status]
                or review.review_id != previous.review_id
                or review.proposal != previous.proposal
                or review.submitted_by != previous.submitted_by
                or review.submitted_at != previous.submitted_at
            ):
                raise PersistenceIntegrityError(
                    "invalid Finance review lifecycle transition"
                )
            if review.status is FinanceReviewStatus.SUPERSEDED and (
                review.reviewed_by,
                review.reviewed_at,
                review.reason,
            ) != (previous.reviewed_by, previous.reviewed_at, previous.reason):
                raise PersistenceIntegrityError(
                    "Finance supersession must preserve review metadata"
                )
            try:
                if review.status is FinanceReviewStatus.SUPERSEDED:
                    assert review.superseded_at is not None
                    canonical = supersede_finance_review(
                        review=previous, now=review.superseded_at
                    )
                else:
                    assert review.reviewed_by is not None
                    assert review.reviewed_at is not None
                    canonical = resolve_finance_review(
                        review=previous,
                        current_proposal=previous.proposal,
                        actor=review.reviewed_by,
                        approved=review.status is FinanceReviewStatus.APPROVED,
                        reason=review.reason,
                        now=review.reviewed_at,
                    )
            except FinanceReviewViolation as error:
                raise PersistenceIntegrityError(
                    "Finance review revision violates lifecycle policy"
                ) from error
            if canonical != review:
                raise PersistenceIntegrityError(
                    "Finance review revision is not a canonical transition"
                )
            assert current_revision is not None
            revision = current_revision + 1
        self._require_bound_analysis(review)
        proposal = review.proposal
        self._connection.execute(
            insert(finance_review_revisions).values(
                review_id=review.review_id,
                revision=revision,
                case_id=proposal.case_id,
                analysis_id=proposal.analysis_id,
                analysis_material_hash=proposal.analysis_material_hash,
                option_id=proposal.option_id,
                status=review.status.value,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                recorded_at=self._normalize(self._recorded_at(review)),
                payload_json=serialize_model(review),
            )
        )
        return review, revision


def append_finance_review(
    uow_factory: UnitOfWorkFactory,
    review: FinanceReview,
    *,
    expected_revision: int | None,
    idempotency_key: str,
    request_fingerprint: str,
) -> tuple[FinanceReview, int]:
    try:
        with uow_factory() as uow:
            result = uow.finance_reviews.append(
                review,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            uow.commit()
            return result
    except IntegrityError as error:
        with uow_factory() as recovery:
            replay = recovery.finance_reviews.get_by_idempotency_key(idempotency_key)
            if replay is not None:
                stored, revision, fingerprint = replay
                if fingerprint == request_fingerprint and stored == review:
                    return stored, revision
                raise FinanceReviewIdempotencyConflict(
                    "Finance idempotency key was used for another request"
                ) from error
            try:
                _, actual_revision = recovery.finance_reviews.get_latest(
                    review.review_id
                )
            except RecordNotFound:
                actual_revision = None
            if actual_revision != expected_revision:
                raise FinanceReviewRevisionConflict(
                    f"expected revision {expected_revision}; current revision is {actual_revision}"
                ) from error
        raise
