from typing import Annotated

from pydantic import (
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from data.domain.common import FrozenModel
from data.domain.finance import FinanceReview
from data.domain.proposals import ProposalSelection, ProposalToken

Identifier = Annotated[StrictStr, Field(min_length=1, max_length=128)]
CommandKey = Annotated[StrictStr, Field(min_length=1, max_length=200)]


class SubmitProposalCommand(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: Identifier
    option_id: Identifier
    expected: ProposalToken
    idempotency_key: CommandKey

    @field_validator("case_id", "option_id", "idempotency_key")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("value must be nonblank")
        return value

    @model_validator(mode="after")
    def analyzed(self):
        if (
            self.expected.analysis_id is None
            or self.expected.analysis_material_hash is None
        ):
            raise ValueError("submission requires an analyzed case")
        return self


class ResolveFinanceCommand(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    review_id: Identifier
    expected: ProposalToken
    expected_review_revision: StrictInt = Field(gt=0)
    approved: StrictBool
    reason: Annotated[StrictStr, Field(max_length=4000)] | None = None
    idempotency_key: CommandKey

    @field_validator("review_id", "idempotency_key")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("value must be nonblank")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value):
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def request_shape(self):
        if not self.approved and self.reason is None:
            raise ValueError("rejection requires a nonblank reason")
        if self.expected.selection_id is None or self.expected.analysis_id is None:
            raise ValueError("resolution requires a current proposal selection")
        return self


class SubmissionResult(FrozenModel):
    selection: ProposalSelection
    review: FinanceReview | None
    review_revision: int | None


class ResolutionResult(FrozenModel):
    review: FinanceReview
    review_revision: int
