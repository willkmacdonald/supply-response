from datetime import datetime
from uuid import UUID

from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceProposal, FinanceReview, FinanceReviewStatus
from services.policy.thresholds import requires_finance_approval


class FinanceReviewViolation(ValueError):
    pass


def _require_aware(now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise FinanceReviewViolation("Timestamp must be timezone-aware")


def _require_uuid(value: str | None, label: str) -> UUID:
    try:
        return UUID(value or "")
    except ValueError as exc:
        raise FinanceReviewViolation(f"{label} must be a valid UUID") from exc


def _require_actor(
    actor: IdentitySnapshot, *, persona: str, source: str, roles: tuple[str, ...]
) -> tuple[UUID, UUID]:
    if (
        actor.persona_id != persona
        or actor.source_id != source
        or actor.identity_source is not IdentitySource.ENTRA
        or actor.effective_roles != tuple(sorted(roles))
    ):
        raise FinanceReviewViolation(
            "Actor is not authorized for this Finance transition"
        )
    return (
        _require_uuid(actor.tenant_id, "tenant_id"),
        _require_uuid(actor.object_id, "object_id"),
    )


def require_proposal_submitter(actor: IdentitySnapshot) -> None:
    """Validate the pure identity shape allowed to submit a Finance proposal."""
    _require_actor(
        actor,
        persona="RL-PERSONA-ALEX",
        source="RL-ENTRA-ALEX",
        roles=("material_planner", "response_approver"),
    )


def submit_finance_review(
    *, review_id: str, proposal: FinanceProposal, actor: IdentitySnapshot, now: datetime
) -> FinanceReview:
    _require_aware(now)
    require_proposal_submitter(actor)
    if not review_id.strip():
        raise FinanceReviewViolation("review_id must be nonblank")
    if not requires_finance_approval(proposal.response_cost):
        raise FinanceReviewViolation("Finance review is not required for this cost")
    return FinanceReview(
        review_id=review_id,
        proposal=proposal,
        submitted_by=actor,
        submitted_at=now,
        status=FinanceReviewStatus.PENDING,
    )


def resolve_finance_review(
    *,
    review: FinanceReview,
    current_proposal: FinanceProposal,
    actor: IdentitySnapshot,
    approved: bool,
    reason: str | None,
    now: datetime,
) -> FinanceReview:
    _require_aware(now)
    reviewer_tenant, reviewer_object = _require_actor(
        actor,
        persona="RL-PERSONA-TAYLOR",
        source="RL-ENTRA-TAYLOR",
        roles=("finance_approver",),
    )
    submitter_tenant = _require_uuid(
        review.submitted_by.tenant_id, "submitter tenant_id"
    )
    submitter_object = _require_uuid(
        review.submitted_by.object_id, "submitter object_id"
    )
    if reviewer_tenant != submitter_tenant:
        raise FinanceReviewViolation("Finance reviewer must share the submitter tenant")
    if reviewer_object == submitter_object:
        raise FinanceReviewViolation("Finance reviewer must be a different person")
    if review.status is not FinanceReviewStatus.PENDING:
        raise FinanceReviewViolation("Only a pending review can be resolved")
    if review.proposal != current_proposal:
        raise FinanceReviewViolation("The proposal has changed; submit a new review")
    if now < review.submitted_at:
        raise FinanceReviewViolation("Review time cannot precede submission")
    normalized_reason = reason.strip() if reason is not None else None
    if not approved and not normalized_reason:
        raise FinanceReviewViolation("Rejected review requires a nonblank reason")
    values = review.model_dump()
    values.update(
        status=FinanceReviewStatus.APPROVED
        if approved
        else FinanceReviewStatus.REJECTED,
        reviewed_by=actor,
        reviewed_at=now,
        reason=normalized_reason,
    )
    return FinanceReview.model_validate(values)


def supersede_finance_review(*, review: FinanceReview, now: datetime) -> FinanceReview:
    _require_aware(now)
    if now < review.submitted_at or (
        review.reviewed_at is not None and now < review.reviewed_at
    ):
        raise FinanceReviewViolation(
            "Supersession cannot precede existing review history"
        )
    if review.status is FinanceReviewStatus.SUPERSEDED:
        return review
    values = review.model_dump()
    values.update(status=FinanceReviewStatus.SUPERSEDED, superseded_at=now)
    return FinanceReview.model_validate(values)
