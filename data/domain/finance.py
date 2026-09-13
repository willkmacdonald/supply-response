import hashlib
import json
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from .common import FrozenModel, Money
from .decisions import IdentitySnapshot


class FinanceReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class FinanceProposal(FrozenModel):
    case_id: str
    analysis_id: str
    analysis_material_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    option_id: str
    response_cost: Money = Field(ge=0)

    @field_validator("case_id", "analysis_id", "option_id")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be nonblank")
        return value

    @field_validator("response_cost")
    @classmethod
    def require_exact_cents(cls, value: Money) -> Money:
        if not value.is_finite() or value != value.quantize(Decimal("0.01")):
            raise ValueError(
                "response_cost must be finite and exactly representable to cents"
            )
        return value

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


class FinanceReview(FrozenModel):
    review_id: str
    proposal: FinanceProposal
    submitted_by: IdentitySnapshot
    submitted_at: datetime
    status: FinanceReviewStatus
    reviewed_by: IdentitySnapshot | None = None
    reviewed_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=4000)
    superseded_at: datetime | None = None

    @field_validator("review_id")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be nonblank")
        return value

    @field_validator("submitted_at", "reviewed_at", "superseded_at")
    @classmethod
    def require_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamps must be timezone-aware")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_state(self) -> "FinanceReview":
        paired = (self.reviewed_by is None) == (self.reviewed_at is None)
        if not paired:
            raise ValueError("reviewer and review time must be paired")
        if self.reviewed_at is not None and self.reviewed_at < self.submitted_at:
            raise ValueError("review time cannot precede submission")
        if self.superseded_at is not None:
            if self.superseded_at < self.submitted_at:
                raise ValueError("supersession cannot precede submission")
            if self.reviewed_at is not None and self.superseded_at < self.reviewed_at:
                raise ValueError("supersession cannot precede review")
        if self.reason is not None and self.reviewed_by is None:
            raise ValueError("reason requires completed review metadata")
        if self.status is FinanceReviewStatus.PENDING:
            if any(
                (self.reviewed_by, self.reviewed_at, self.reason, self.superseded_at)
            ):
                raise ValueError("pending review cannot contain review metadata")
        elif self.status in (
            FinanceReviewStatus.APPROVED,
            FinanceReviewStatus.REJECTED,
        ):
            if (
                self.reviewed_by is None
                or self.reviewed_at is None
                or self.superseded_at is not None
            ):
                raise ValueError("resolved review requires reviewer and review time")
            if self.status is FinanceReviewStatus.APPROVED and self.reason is not None:
                raise ValueError("approved review cannot contain a reason")
            if self.status is FinanceReviewStatus.REJECTED and self.reason is None:
                raise ValueError("rejected review requires a nonblank reason")
        elif self.superseded_at is None:
            raise ValueError("superseded review requires superseded time")
        return self
