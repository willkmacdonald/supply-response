from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field, StrictInt, field_validator, model_validator

from .cases import WorkflowVersion
from .common import FrozenModel
from .decisions import IdentitySnapshot
from .finance import FinanceProposal, FinanceReview


class ProposalToken(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    generation: StrictInt = Field(ge=0)
    analysis_id: str | None
    analysis_material_hash: str | None
    selection_id: str | None

    @field_validator("analysis_id", "selection_id")
    @classmethod
    def validate_id(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or len(value) > 128):
            raise ValueError("identifier must be nonblank and at most 128 characters")
        return value

    @field_validator("analysis_material_hash")
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError("analysis_material_hash must be lowercase 64-hex")
        return value

    @model_validator(mode="after")
    def validate_pair(self) -> "ProposalToken":
        if (self.analysis_id is None) != (self.analysis_material_hash is None):
            raise ValueError("analysis ID and hash must be paired")
        if self.selection_id is not None and self.analysis_id is None:
            raise ValueError("selection requires analysis")
        return self


class ProposalSelection(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    selection_id: str
    proposal: FinanceProposal
    workflow_version: WorkflowVersion
    submitted_by: IdentitySnapshot
    submitted_at: datetime
    finance_review_id: str | None

    @field_validator("selection_id", "finance_review_id")
    @classmethod
    def validate_id(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or len(value) > 128):
            raise ValueError("identifier must be nonblank and at most 128 characters")
        return value

    @field_validator("submitted_at")
    @classmethod
    def require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("submitted_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_policy(self) -> "ProposalSelection":
        if self.workflow_version is not WorkflowVersion.INDEPENDENT_FINANCE:
            raise ValueError("selection requires independent Finance workflow")
        requires_review = self.proposal.response_cost > Decimal(20000)
        if requires_review != (self.finance_review_id is not None):
            raise ValueError("Finance review must be present iff cost exceeds 20000")
        return self


class SelectionReceipt(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    selection: ProposalSelection
    expected: ProposalToken
    idempotency_key: str
    request_fingerprint: str

    @field_validator("idempotency_key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not value.strip() or len(value) > 256:
            raise ValueError(
                "idempotency_key must be nonblank and at most 256 characters"
            )
        return value

    @field_validator("request_fingerprint")
    @classmethod
    def validate_fingerprint(cls, value: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("request_fingerprint must be lowercase 64-hex")
        return value


class ProposalState(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    token: ProposalToken
    selection: ProposalSelection | None
    review: FinanceReview | None
    review_revision: int | None

    @model_validator(mode="after")
    def validate_consistency(self) -> "ProposalState":
        if self.selection is None:
            if (
                self.review is not None
                or self.review_revision is not None
                or self.token.selection_id is not None
            ):
                raise ValueError("missing selection cannot have review or pointer")
            return self
        if self.token.selection_id != self.selection.selection_id:
            raise ValueError("selection pointer mismatch")
        if self.selection.finance_review_id is None:
            if self.review is not None or self.review_revision is not None:
                raise ValueError("low-cost selection cannot have review")
        elif (
            self.review is None
            or self.review.review_id != self.selection.finance_review_id
            or self.review.proposal != self.selection.proposal
            or isinstance(self.review_revision, bool)
            or not isinstance(self.review_revision, int)
            or self.review_revision <= 0
        ):
            raise ValueError("high-cost selection requires matching review")
        return self
