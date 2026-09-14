from decimal import Decimal
from uuid import UUID

from pydantic import Field, StrictInt, model_validator

from data.domain.common import FrozenModel
from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceReview, FinanceReviewStatus
from data.domain.proposals import ProposalSelection


def _require_identity(
    actor: IdentitySnapshot,
    *,
    persona_id: str,
    source_id: str,
    roles: tuple[str, ...],
) -> tuple[UUID, UUID]:
    if (
        actor.persona_id != persona_id
        or actor.source_id != source_id
        or actor.identity_source is not IdentitySource.ENTRA
        or actor.effective_roles != roles
    ):
        raise ValueError("Proposal evidence contains an invalid identity shape")
    try:
        return UUID(actor.tenant_id or ""), UUID(actor.object_id or "")
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError(
            "Proposal evidence identity requires tenant/object UUIDs"
        ) from error


class ProposalApprovalEvidence(FrozenModel):
    selection: ProposalSelection
    review: FinanceReview | None = None
    review_revision: StrictInt | None = Field(default=None, gt=1)

    @model_validator(mode="after")
    def validate_evidence(self) -> "ProposalApprovalEvidence":
        submitter_tenant, submitter_object = _require_identity(
            self.selection.submitted_by,
            persona_id="RL-PERSONA-ALEX",
            source_id="RL-ENTRA-ALEX",
            roles=("material_planner", "response_approver"),
        )
        needs_finance = self.selection.proposal.response_cost > Decimal("20000.00")
        if needs_finance != (self.review is not None):
            raise ValueError("Finance review presence conflicts with proposal cost")
        if self.review is None:
            if (
                self.review_revision is not None
                or self.selection.finance_review_id is not None
            ):
                raise ValueError(
                    "Low-cost proposal cannot contain Finance review evidence"
                )
            return self
        review = self.review
        if (
            self.review_revision is None
            or review.status is not FinanceReviewStatus.APPROVED
            or self.selection.finance_review_id != review.review_id
            or review.proposal != self.selection.proposal
            or review.submitted_by != self.selection.submitted_by
            or review.submitted_at != self.selection.submitted_at
            or review.reviewed_by is None
            or review.reviewed_at is None
        ):
            raise ValueError("Proposal requires an exact approved Finance revision")
        reviewer_tenant, reviewer_object = _require_identity(
            review.reviewed_by,
            persona_id="RL-PERSONA-TAYLOR",
            source_id="RL-ENTRA-TAYLOR",
            roles=("finance_approver",),
        )
        if reviewer_tenant != submitter_tenant:
            raise ValueError("Finance reviewer must share the submitter tenant")
        if reviewer_object == submitter_object:
            raise ValueError("Submitter and reviewer must differ")
        return self
