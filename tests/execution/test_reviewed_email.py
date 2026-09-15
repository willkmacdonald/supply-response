from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import pytest
from pydantic import ValidationError
from sqlalchemy import update

from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource
from services.execution.planner import plan_actions
from services.execution.worker import ActionPlanningWorker
from services.persistence.tables import case_projection

NOW = datetime(2026, 9, 15, 16, tzinfo=UTC)


def _mail_types():
    try:
        from data.domain.outbound_mail import (
            SupplierEmailDelivery,
            SupplierEmailRevision,
        )
    except ModuleNotFoundError:
        pytest.fail("outbound supplier email domain records are not implemented")
    return SupplierEmailRevision, SupplierEmailDelivery


def _mail_service(planning_context):
    try:
        from services.execution.mail_service import ReviewedEmailService
    except ModuleNotFoundError:
        pytest.fail("reviewed supplier email service is not implemented")
    from tests.execution.conftest import alex_identity

    return ReviewedEmailService(
        planning_context.uow_factory,
        from_address="agent@willmacdonald.com",
        to_address="will@willmacdonald.com",
        configured_actor=alex_identity(),
        clock=lambda: NOW,
    )


def _plan(planning_context):
    assert ActionPlanningWorker(planning_context.uow_factory).process_next_outbox()


def test_supplier_email_domain_requires_valid_content_and_review_pair():
    SupplierEmailRevision, SupplierEmailDelivery = _mail_types()
    from tests.execution.conftest import alex_identity

    base = {
        "email_id": "RL-EMAIL-1",
        "decision_id": "RL-DECISION-1",
        "action_id": "RL-ACTION-1",
        "revision": 1,
        "subject": "Recovery plan",
        "body": "Fictional demo recovery request.",
        "from_address": "agent@willmacdonald.com",
        "to_address": "will@willmacdonald.com",
        "edited_by": alex_identity(),
        "edited_at": NOW,
    }
    assert SupplierEmailRevision(**base).revision == 1
    for changes in (
        {"revision": 0},
        {"subject": "   "},
        {"subject": "x" * 256},
        {"body": "   "},
        {"body": "x" * 10_001},
        {"reviewed_by": alex_identity(), "reviewed_at": None},
        {"reviewed_by": None, "reviewed_at": NOW},
    ):
        with pytest.raises(ValidationError):
            SupplierEmailRevision(**{**base, **changes})
    with pytest.raises(ValidationError):
        SupplierEmailDelivery(
            email_id="RL-EMAIL-1",
            decision_id="RL-DECISION-1",
            reviewed_revision=0,
            status_updated_at=NOW,
        )


def test_initial_draft_is_generated_from_approved_option(planning_context):
    _plan(planning_context)

    state = _mail_service(planning_context).get(planning_context.decision.decision_id)

    assert state.revision == 1
    assert state.subject == "RL-001 supplier recovery request"
    assert planning_context.decision.case_id in state.body
    assert planning_context.decision.selected_option.name in state.body
    assert "fictional demo" in state.body.lower()
    assert state.from_address == "agent@willmacdonald.com"
    assert state.to_address == "will@willmacdonald.com"
    assert state.reviewed_revision is None
    assert state.send_status == "draft"


@pytest.mark.parametrize(
    "option_id, expected, excluded",
    (
        (
            "RL-OPTION-EXPEDITE",
            ("3,000", "September 6, 2026", "$7.50 per unit"),
            ("Dallas",),
        ),
        (
            "RL-OPTION-TRANSFER",
            ("1,500", "Dallas", "Chicago", "September 5, 2026"),
            ("expedited units",),
        ),
        (
            "RL-OPTION-RESEQUENCE",
            ("RL-CO-DEMO-2",),
            ("expedited units", "Dallas"),
        ),
    ),
)
def test_initial_content_describes_only_the_approved_response(
    planning_context, option_id, expected, excluded
):
    try:
        from services.execution.mail_service import ReviewedEmailService
    except ModuleNotFoundError:
        pytest.fail("reviewed supplier email service is not implemented")
    option = next(
        item
        for item in planning_context.analysis.response_options
        if item.option_id == option_id
    )
    decision = planning_context.decision.model_copy(
        update={"selected_option_id": option_id, "selected_option": option}
    )
    actions = plan_actions(decision, planning_context.analysis)

    _, body = ReviewedEmailService._initial_content(decision, actions)

    assert all(value in body for value in expected)
    assert not any(value in body for value in excluded)


def test_edit_and_review_are_versioned_and_reload_safe(planning_context):
    from tests.execution.conftest import alex_identity

    _plan(planning_context)
    service = _mail_service(planning_context)
    initial = service.get(planning_context.decision.decision_id)
    reviewed_one = service.review(
        planning_context.decision.decision_id, initial.revision, alex_identity()
    )
    second = service.save(
        planning_context.decision.decision_id,
        initial.revision,
        "Updated recovery plan",
        "Updated fictional demo body.",
        alex_identity(),
    )

    assert reviewed_one.reviewed_revision == 1
    assert reviewed_one.reviewed_by == alex_identity()
    assert reviewed_one.reviewed_at == NOW
    assert second.revision == 2
    assert second.reviewed_revision is None
    assert second.reviewed_by is None
    assert second.send_status == "draft"

    reviewed_two = service.review(
        planning_context.decision.decision_id, second.revision, alex_identity()
    )
    third = service.save(
        planning_context.decision.decision_id,
        second.revision,
        "Final recovery plan",
        "Final fictional demo body.",
        alex_identity(),
    )
    restarted = _mail_service(planning_context).get(
        planning_context.decision.decision_id
    )

    assert reviewed_two.reviewed_revision == 2
    assert third.revision == 3
    assert third.reviewed_revision is None
    assert restarted == third
    with planning_context.uow_factory() as uow:
        first_revision = uow.mail.get_revision(third.email_id, 1)
        second_revision = uow.mail.get_revision(third.email_id, 2)
    assert first_revision.reviewed_by == alex_identity()
    assert second_revision.reviewed_by == alex_identity()


def test_only_configured_alex_can_edit_or_review(planning_context):
    try:
        from services.execution.mail_service import EmailAuthorizationError
    except ModuleNotFoundError:
        pytest.fail("reviewed supplier email authorization is not implemented")
    from tests.execution.conftest import alex_identity

    _plan(planning_context)
    service = _mail_service(planning_context)
    initial = service.get(planning_context.decision.decision_id)
    taylor = IdentitySnapshot(
        persona_id="RL-PERSONA-TAYLOR",
        effective_roles=("finance_approver",),
        identity_source=IdentitySource.ENTRA,
        source_id="RL-ENTRA-TAYLOR",
    )
    for operation in (
        lambda: service.save(
            planning_context.decision.decision_id,
            1,
            "Changed",
            "Changed body",
            taylor,
        ),
        lambda: service.review(planning_context.decision.decision_id, 1, taylor),
    ):
        with pytest.raises(EmailAuthorizationError):
            operation()
    assert service.get(planning_context.decision.decision_id) == initial
    assert alex_identity().persona_id == "RL-PERSONA-ALEX"


def test_every_write_rejects_stale_decision_and_revision(planning_context):
    try:
        from services.execution.currentness import ExecutionProposalStale
        from services.execution.mail_service import EmailRevisionConflict
    except ModuleNotFoundError:
        pytest.fail("reviewed supplier email currentness guards are not implemented")
    from tests.execution.conftest import alex_identity

    _plan(planning_context)
    service = _mail_service(planning_context)
    initial = service.get(planning_context.decision.decision_id)
    service.save(
        planning_context.decision.decision_id,
        initial.revision,
        "Revision two",
        "Revision two body",
        alex_identity(),
    )
    with pytest.raises(EmailRevisionConflict):
        service.save(
            planning_context.decision.decision_id,
            1,
            "Stale edit",
            "Stale body",
            alex_identity(),
        )
    with pytest.raises(EmailRevisionConflict):
        service.review(planning_context.decision.decision_id, 1, alex_identity())

    with planning_context.store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == planning_context.decision.case_id)
            .values(current_decision_id=None)
        )
    with pytest.raises(ExecutionProposalStale):
        service.save(
            planning_context.decision.decision_id,
            2,
            "Current edit",
            "Current body",
            alex_identity(),
        )
    with pytest.raises(ExecutionProposalStale):
        service.review(planning_context.decision.decision_id, 2, alex_identity())


def test_concurrent_edits_return_one_safe_revision_conflict(
    planning_context, monkeypatch
):
    from services.execution.mail_service import EmailRevisionConflict
    from services.persistence.store import SqlAlchemySupplierEmailRepository
    from tests.execution.conftest import alex_identity

    _plan(planning_context)
    service = _mail_service(planning_context)
    initial = service.get(planning_context.decision.decision_id)
    writers_ready = Barrier(2)
    original_append = SqlAlchemySupplierEmailRepository.append_revision

    def synchronized_append(repository, revision, *, expected_revision):
        writers_ready.wait(timeout=5)
        return original_append(
            repository,
            revision,
            expected_revision=expected_revision,
        )

    monkeypatch.setattr(
        SqlAlchemySupplierEmailRepository,
        "append_revision",
        synchronized_append,
    )

    def save(subject):
        try:
            service.save(
                planning_context.decision.decision_id,
                initial.revision,
                subject,
                f"{subject} fictional demo body.",
                alex_identity(),
            )
        except EmailRevisionConflict:
            return "conflict"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(
            future.result()
            for future in (
                executor.submit(save, "Concurrent edit A"),
                executor.submit(save, "Concurrent edit B"),
            )
        )

    assert sorted(outcomes) == ["conflict", "saved"]
    current = service.get(planning_context.decision.decision_id)
    assert current.revision == 2
    assert current.subject in {"Concurrent edit A", "Concurrent edit B"}


def test_concurrent_edit_and_review_never_leave_a_non_current_effective_review(
    planning_context, monkeypatch
):
    from services.execution.mail_service import EmailRevisionConflict
    from services.persistence.store import SqlAlchemySupplierEmailRepository
    from tests.execution.conftest import alex_identity

    _plan(planning_context)
    service = _mail_service(planning_context)
    initial = service.get(planning_context.decision.decision_id)
    writers_ready = Barrier(2)
    original_append = SqlAlchemySupplierEmailRepository.append_revision
    original_review = SqlAlchemySupplierEmailRepository.mark_reviewed

    def synchronized_append(repository, revision, *, expected_revision):
        writers_ready.wait(timeout=5)
        return original_append(
            repository,
            revision,
            expected_revision=expected_revision,
        )

    def synchronized_review(
        repository,
        revision,
        delivery,
        *,
        expected_revision,
    ):
        writers_ready.wait(timeout=5)
        return original_review(
            repository,
            revision,
            delivery,
            expected_revision=expected_revision,
        )

    monkeypatch.setattr(
        SqlAlchemySupplierEmailRepository,
        "append_revision",
        synchronized_append,
    )
    monkeypatch.setattr(
        SqlAlchemySupplierEmailRepository,
        "mark_reviewed",
        synchronized_review,
    )

    def save():
        try:
            service.save(
                planning_context.decision.decision_id,
                initial.revision,
                "Concurrent edit",
                "Concurrent fictional demo body.",
                alex_identity(),
            )
        except EmailRevisionConflict:
            return "conflict"
        return "saved"

    def review():
        try:
            service.review(
                planning_context.decision.decision_id,
                initial.revision,
                alex_identity(),
            )
        except EmailRevisionConflict:
            return "conflict"
        return "reviewed"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(
            future.result()
            for future in (executor.submit(save), executor.submit(review))
        )

    assert set(outcomes) <= {"saved", "reviewed", "conflict"}
    assert "saved" in outcomes
    current = service.get(planning_context.decision.decision_id)
    assert current.revision == 2
    assert current.reviewed_revision is None


def test_database_conflict_classification_is_narrow():
    import sqlite3

    from sqlalchemy.exc import IntegrityError, OperationalError

    from services.persistence.store import (
        _is_supplier_email_revision_collision,
        _is_write_contention,
    )

    busy = sqlite3.OperationalError("database is locked")
    busy.sqlite_errorcode = sqlite3.SQLITE_BUSY
    unrelated = sqlite3.OperationalError("unrelated failure")
    unrelated.sqlite_errorcode = sqlite3.SQLITE_ERROR
    duplicate = sqlite3.IntegrityError(
        "UNIQUE constraint failed: supplier_email_revisions.email_id, "
        "supplier_email_revisions.revision"
    )
    duplicate.sqlite_errorcode = sqlite3.SQLITE_CONSTRAINT_UNIQUE

    assert _is_write_contention(OperationalError("update", {}, busy))
    assert not _is_write_contention(OperationalError("update", {}, unrelated))
    assert _is_supplier_email_revision_collision(
        IntegrityError("insert", {}, duplicate)
    )
    assert not _is_supplier_email_revision_collision(
        IntegrityError("insert", {}, sqlite3.IntegrityError("foreign key failed"))
    )


def test_mismatched_action_cannot_own_supplier_email(planning_context):
    try:
        from services.execution.mail_service import EmailStateError
    except ModuleNotFoundError:
        pytest.fail("reviewed supplier email action binding is not implemented")
    from tests.execution.conftest import alex_identity

    _plan(planning_context)
    service = _mail_service(planning_context)
    initial = service.get(planning_context.decision.decision_id)
    draft_action = None
    other_action = None
    with planning_context.uow_factory() as uow:
        for action in uow.execution.list_actions(
            decision_id=planning_context.decision.decision_id
        ):
            if action.draft_artifact_id is not None:
                draft_action = action
            else:
                other_action = action
    assert draft_action is not None and other_action is not None
    with planning_context.store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == planning_context.decision.case_id)
            .values(current_decision_id=planning_context.decision.decision_id)
        )
        connection.execute(
            update(
                __import__(
                    "services.persistence.tables", fromlist=["draft_artifacts"]
                ).draft_artifacts
            )
            .where(
                __import__(
                    "services.persistence.tables", fromlist=["draft_artifacts"]
                ).draft_artifacts.c.action_id
                == draft_action.action_id
            )
            .values(action_id=other_action.action_id)
        )
    with pytest.raises(EmailStateError):
        service.review(
            planning_context.decision.decision_id,
            initial.revision,
            alex_identity(),
        )
