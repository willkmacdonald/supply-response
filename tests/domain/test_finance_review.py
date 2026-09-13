from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceProposal, FinanceReview, FinanceReviewStatus
from services.policy.finance_review import (
    FinanceReviewViolation,
    resolve_finance_review,
    submit_finance_review,
    supersede_finance_review,
)

NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)
TENANT = "11111111-1111-4111-8111-111111111111"


def actor(persona: str, **changes: object) -> IdentitySnapshot:
    values = {
        "persona_id": f"RL-PERSONA-{persona}",
        "source_id": f"RL-ENTRA-{persona}",
        "identity_source": IdentitySource.ENTRA,
        "tenant_id": TENANT,
        "object_id": (
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            if persona == "ALEX"
            else "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        ),
        "effective_roles": (
            ("material_planner", "response_approver")
            if persona == "ALEX"
            else ("finance_approver",)
        ),
    }
    values.update(changes)
    return IdentitySnapshot(**values)


def proposal(**changes: object) -> FinanceProposal:
    values = {
        "case_id": "case-1",
        "analysis_id": "analysis-1",
        "analysis_material_hash": "a" * 64,
        "option_id": "combined",
        "response_cost": Decimal("24750.00"),
    }
    values.update(changes)
    return FinanceProposal(**values)


def pending_review() -> FinanceReview:
    return submit_finance_review(
        review_id="review-1", proposal=proposal(), actor=actor("ALEX"), now=NOW
    )


def test_rejection_preserves_original_request():
    pending = pending_review()
    rejected = resolve_finance_review(
        review=pending,
        current_proposal=proposal(),
        actor=actor("TAYLOR"),
        approved=False,
        reason="Use a lower-cost response",
        now=NOW + timedelta(seconds=1),
    )
    assert pending.status == FinanceReviewStatus.PENDING
    assert rejected.status == FinanceReviewStatus.REJECTED
    assert rejected.reason == "Use a lower-cost response"
    assert rejected.reviewed_by == actor("TAYLOR")


@pytest.mark.parametrize(
    ("cost", "required"),
    [("20000", False), ("20000.01", True), ("22500", True), ("24750", True)],
)
def test_submission_obeys_finance_threshold(cost: str, required: bool):
    if required:
        assert (
            submit_finance_review(
                review_id="review-1",
                proposal=proposal(response_cost=Decimal(cost)),
                actor=actor("ALEX"),
                now=NOW,
            ).status
            is FinanceReviewStatus.PENDING
        )
    else:
        with pytest.raises(FinanceReviewViolation, match="not required"):
            submit_finance_review(
                review_id="review-1",
                proposal=proposal(response_cost=Decimal(cost)),
                actor=actor("ALEX"),
                now=NOW,
            )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_id", "case-2"),
        ("analysis_id", "analysis-2"),
        ("analysis_material_hash", "b" * 64),
        ("option_id", "expedite"),
        ("response_cost", Decimal("24750.01")),
    ],
)
def test_every_proposal_field_affects_fingerprint(field: str, value: object):
    assert proposal().fingerprint != proposal(**{field: value}).fingerprint


def test_equivalent_decimal_scales_share_a_fingerprint():
    assert (
        proposal(response_cost=Decimal("24750.000")).fingerprint
        == proposal(response_cost=Decimal("24750.00")).fingerprint
    )


@pytest.mark.parametrize(
    "cost", [Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity"), Decimal("1.001")]
)
def test_invalid_cost_is_rejected(cost: Decimal):
    with pytest.raises(ValidationError):
        proposal(response_cost=cost)


@pytest.mark.parametrize("value", ["", " "])
@pytest.mark.parametrize("field", ["case_id", "analysis_id", "option_id"])
def test_blank_proposal_identifiers_are_rejected(field: str, value: str):
    with pytest.raises(ValidationError):
        proposal(**{field: value})


@pytest.mark.parametrize("value", ["A" * 64, "a" * 63, "g" * 64])
def test_malformed_analysis_hash_is_rejected(value: str):
    with pytest.raises(ValidationError):
        proposal(analysis_material_hash=value)


def test_approval_records_taylor_and_optional_note_and_preserves_pending_object():
    pending = pending_review()
    approved = resolve_finance_review(
        review=pending,
        current_proposal=proposal(),
        actor=actor("TAYLOR"),
        approved=True,
        reason="  Approved within budget  ",
        now=NOW + timedelta(seconds=1),
    )
    assert pending.status is FinanceReviewStatus.PENDING
    assert approved.status is FinanceReviewStatus.APPROVED
    assert approved.reviewed_by == actor("TAYLOR")
    assert approved.reason == "Approved within budget"
    superseded = supersede_finance_review(
        review=approved, now=NOW + timedelta(seconds=2)
    )
    assert superseded.reason == "Approved within budget"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_rejection_requires_nonblank_reason(reason: str | None):
    with pytest.raises(FinanceReviewViolation, match="nonblank reason"):
        resolve_finance_review(
            review=pending_review(),
            current_proposal=proposal(),
            actor=actor("TAYLOR"),
            approved=False,
            reason=reason,
            now=NOW + timedelta(seconds=1),
        )


def test_reason_is_trimmed_and_limited():
    rejected = resolve_finance_review(
        review=pending_review(),
        current_proposal=proposal(),
        actor=actor("TAYLOR"),
        approved=False,
        reason="  reduce cost  ",
        now=NOW + timedelta(seconds=1),
    )
    assert rejected.reason == "reduce cost"
    with pytest.raises(ValidationError):
        rejected.model_validate({**rejected.model_dump(), "reason": "x" * 4001})


@pytest.mark.parametrize(
    "bad_actor",
    [
        actor("TAYLOR"),
        actor("ALEX", persona_id="RL-PERSONA-OTHER"),
        actor("ALEX", source_id="RL-ENTRA-OTHER"),
        actor("ALEX", effective_roles=("response_approver",)),
        actor("ALEX", tenant_id="bad"),
        actor("ALEX", object_id="bad"),
    ],
)
def test_only_exact_alex_entra_identity_can_submit(bad_actor: IdentitySnapshot):
    with pytest.raises(FinanceReviewViolation):
        submit_finance_review(
            review_id="review-1", proposal=proposal(), actor=bad_actor, now=NOW
        )


@pytest.mark.parametrize(
    "bad_actor",
    [
        actor("ALEX"),
        actor("TAYLOR", persona_id="RL-PERSONA-OTHER"),
        actor("TAYLOR", source_id="RL-ENTRA-OTHER"),
        actor("TAYLOR", effective_roles=("finance_approver", "response_approver")),
        actor("TAYLOR", tenant_id="22222222-2222-4222-8222-222222222222"),
        actor("TAYLOR", object_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    ],
)
def test_only_exact_independent_taylor_identity_can_resolve(
    bad_actor: IdentitySnapshot,
):
    with pytest.raises(FinanceReviewViolation):
        resolve_finance_review(
            review=pending_review(),
            current_proposal=proposal(),
            actor=bad_actor,
            approved=True,
            reason=None,
            now=NOW + timedelta(seconds=1),
        )


def test_naive_and_backwards_transition_times_are_rejected():
    with pytest.raises(FinanceReviewViolation):
        submit_finance_review(
            review_id="review-1",
            proposal=proposal(),
            actor=actor("ALEX"),
            now=datetime(2026, 9, 13, 12),  # noqa: DTZ001 - intentionally naive
        )
    with pytest.raises(FinanceReviewViolation):
        resolve_finance_review(
            review=pending_review(),
            current_proposal=proposal(),
            actor=actor("TAYLOR"),
            approved=True,
            reason=None,
            now=NOW - timedelta(seconds=1),
        )


def test_blank_review_identifier_is_rejected():
    with pytest.raises(FinanceReviewViolation, match="nonblank"):
        submit_finance_review(
            review_id=" ", proposal=proposal(), actor=actor("ALEX"), now=NOW
        )


def test_terminal_review_cannot_be_resolved_again_or_for_another_proposal():
    approved = resolve_finance_review(
        review=pending_review(),
        current_proposal=proposal(),
        actor=actor("TAYLOR"),
        approved=True,
        reason=None,
        now=NOW + timedelta(seconds=1),
    )
    with pytest.raises(FinanceReviewViolation, match="pending"):
        resolve_finance_review(
            review=approved,
            current_proposal=proposal(),
            actor=actor("TAYLOR"),
            approved=False,
            reason="changed",
            now=NOW + timedelta(seconds=2),
        )
    with pytest.raises(FinanceReviewViolation, match="proposal has changed"):
        resolve_finance_review(
            review=pending_review(),
            current_proposal=proposal(option_id="expedite"),
            actor=actor("TAYLOR"),
            approved=True,
            reason=None,
            now=NOW + timedelta(seconds=1),
        )


def test_supersession_is_immutable_idempotent_and_preserves_review_metadata():
    rejected = resolve_finance_review(
        review=pending_review(),
        current_proposal=proposal(),
        actor=actor("TAYLOR"),
        approved=False,
        reason="reduce cost",
        now=NOW + timedelta(seconds=1),
    )
    superseded = supersede_finance_review(
        review=rejected, now=NOW + timedelta(seconds=2)
    )
    assert rejected.status is FinanceReviewStatus.REJECTED
    assert superseded.status is FinanceReviewStatus.SUPERSEDED
    assert superseded.reviewed_by == rejected.reviewed_by
    assert superseded.reviewed_at == rejected.reviewed_at
    assert superseded.reason == rejected.reason
    assert (
        supersede_finance_review(review=superseded, now=NOW + timedelta(seconds=3))
        is superseded
    )
    with pytest.raises(FinanceReviewViolation):
        supersede_finance_review(review=rejected, now=NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"submitted_at": datetime(2026, 9, 13, 12)},  # noqa: DTZ001
        {"reviewed_by": actor("TAYLOR")},
        {
            "status": FinanceReviewStatus.REJECTED,
            "reviewed_by": actor("TAYLOR"),
            "reviewed_at": NOW,
        },
        {"status": FinanceReviewStatus.SUPERSEDED},
        {
            "status": FinanceReviewStatus.SUPERSEDED,
            "superseded_at": NOW,
            "reason": "orphan",
        },
        {
            "status": FinanceReviewStatus.APPROVED,
            "reviewed_by": actor("TAYLOR"),
            "reviewed_at": datetime(2026, 9, 13, 12),  # noqa: DTZ001
        },
        {
            "status": FinanceReviewStatus.APPROVED,
            "reviewed_by": actor("TAYLOR"),
            "reviewed_at": NOW - timedelta(seconds=1),
        },
        {
            "status": FinanceReviewStatus.SUPERSEDED,
            "superseded_at": NOW - timedelta(seconds=1),
        },
    ],
)
def test_invalid_review_metadata_is_rejected_on_construction(
    changes: dict[str, object],
):
    values = pending_review().model_dump()
    values.update(changes)
    with pytest.raises(ValidationError):
        FinanceReview.model_validate(values)


def test_json_serialization_round_trip_revalidates():
    review = pending_review()
    assert FinanceReview.model_validate_json(review.model_dump_json()) == review
    payload = review.model_dump(mode="json")
    payload["submitted_at"] = "2026-09-13T12:00:00"
    with pytest.raises(ValidationError):
        FinanceReview.model_validate(payload)
