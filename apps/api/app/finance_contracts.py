from typing import Literal

from pydantic import ConfigDict, Field, StrictBool, StrictInt, StrictStr

from apps.api.app.contracts import StrictRequest
from data.domain.proposals import ProposalToken


class SubmitProposalRequest(StrictRequest):
    option_id: StrictStr = Field(min_length=1, max_length=128)
    expected: ProposalToken


class ResolveFinanceRequest(StrictRequest):
    expected: ProposalToken
    expected_review_revision: StrictInt = Field(gt=0)
    approved: StrictBool
    reason: StrictStr | None = Field(default=None, max_length=4000)


class FinalizeProposalRequest(StrictRequest):
    model_config = ConfigDict(extra="forbid")
    expected: ProposalToken
    kind: Literal["approved", "rejected"]
    rejection_reason: StrictStr | None = Field(default=None, max_length=4000)
