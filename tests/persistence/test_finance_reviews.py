from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select, update
from sqlalchemy.exc import IntegrityError

from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceProposal, FinanceReviewStatus
from services.persistence.finance_reviews import (
    FinanceReviewIdempotencyConflict,
    FinanceReviewRevisionConflict,
    SqlAlchemyFinanceReviewRepository,
    append_finance_review,
)
from services.persistence.sqlite import sqlite_store
from services.persistence.store import PersistenceIntegrityError, RecordNotFound
from services.persistence.tables import finance_review_revisions
from services.policy.finance_review import (
    resolve_finance_review,
    submit_finance_review,
    supersede_finance_review,
)
from tests.persistence.test_sqlite_store import (
    fallback_rl001_analysis,
    fallback_rl001_case,
)

NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)
TENANT = "11111111-1111-4111-8111-111111111111"


def actor(persona: str) -> IdentitySnapshot:
    return IdentitySnapshot(
        persona_id=f"RL-PERSONA-{persona}",
        source_id=f"RL-ENTRA-{persona}",
        identity_source=IdentitySource.ENTRA,
        tenant_id=TENANT,
        object_id=(
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            if persona == "ALEX"
            else "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        ),
        effective_roles=(
            ("material_planner", "response_approver")
            if persona == "ALEX"
            else ("finance_approver",)
        ),
    )


@pytest.fixture
def finance_context(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'finance.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-FINANCE")
    analysis = fallback_rl001_analysis(case, snapshot, "RL-ANALYSIS-FINANCE")
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    option = next(
        item
        for item in analysis.response_options
        if item.option_id == "RL-OPTION-COMBINED"
    )
    proposal = FinanceProposal(
        case_id=case.case_id,
        analysis_id=analysis.analysis_id,
        analysis_material_hash=analysis.material_hash,
        option_id=option.option_id,
        response_cost=option.predicted.response_cost,
    )
    pending = submit_finance_review(
        review_id="review-1", proposal=proposal, actor=actor("ALEX"), now=NOW
    )
    return store, pending


def approved(review):
    return resolve_finance_review(
        review=review,
        current_proposal=review.proposal,
        actor=actor("TAYLOR"),
        approved=True,
        reason="Within budget",
        now=NOW + timedelta(seconds=1),
    )


def rejected(review):
    return resolve_finance_review(
        review=review,
        current_proposal=review.proposal,
        actor=actor("TAYLOR"),
        approved=False,
        reason="Too costly",
        now=NOW + timedelta(seconds=1),
    )


def test_finance_review_revision_schema_is_append_only_and_bound():
    table = finance_review_revisions
    assert [c.name for c in table.primary_key.columns] == ["review_id", "revision"]
    assert {fk.target_fullname for fk in table.c.case_id.foreign_keys} == {
        "case_instances.case_id"
    }
    assert {fk.target_fullname for fk in table.c.analysis_id.foreign_keys} == {
        "analysis_versions.analysis_id"
    }
    assert {c.name for c in table.constraints} >= {
        "uq_finance_review_revisions_idempotency_key",
        "ck_finance_review_revisions_revision_positive",
    }


def test_finance_review_migration_is_frozen_and_downgrades_only_its_table(tmp_path):
    migration = Path("migrations/versions/0007_finance_review_revisions.py")
    source = migration.read_text()
    assert "services.persistence" not in source
    config = Config("migrations/alembic.ini")
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    assert "finance_review_revisions" in inspect(engine).get_table_names()
    command.downgrade(config, "0006_playback_terminal_failure")
    tables = set(inspect(engine).get_table_names())
    assert "finance_review_revisions" not in tables
    assert "analysis_versions" in tables


def test_uncommitted_first_append_rolls_back(finance_context):
    store, pending = finance_context
    with store.uow_factory() as uow:
        assert uow.finance_reviews.append(
            pending,
            expected_revision=None,
            idempotency_key="submit-rollback",
            request_fingerprint="a" * 64,
        ) == (pending, 1)
        uow.rollback()
    with store.uow_factory() as uow, pytest.raises(RecordNotFound):
        uow.finance_reviews.get_latest(pending.review_id)


def test_uncommitted_resolved_append_rolls_back(finance_context):
    store, pending = finance_context
    accepted = approved(pending)
    append_finance_review(
        store.uow_factory,
        pending,
        expected_revision=None,
        idempotency_key="submit-kept",
        request_fingerprint="b" * 64,
    )
    with store.uow_factory() as uow:
        assert uow.finance_reviews.append(
            accepted,
            expected_revision=1,
            idempotency_key="approve-rollback",
            request_fingerprint="c" * 64,
        ) == (accepted, 2)
        uow.rollback()
    with store.uow_factory() as uow:
        assert uow.finance_reviews.get_latest(pending.review_id) == (pending, 1)


def test_append_preserves_three_complete_snapshots_and_replays(finance_context):
    store, pending = finance_context
    accepted = approved(pending)
    superseded = supersede_finance_review(
        review=accepted, now=NOW + timedelta(seconds=2)
    )
    assert append_finance_review(
        store.uow_factory,
        pending,
        expected_revision=None,
        idempotency_key="submit",
        request_fingerprint="a" * 64,
    ) == (pending, 1)
    assert append_finance_review(
        store.uow_factory,
        accepted,
        expected_revision=1,
        idempotency_key="approve",
        request_fingerprint="b" * 64,
    ) == (accepted, 2)
    assert append_finance_review(
        store.uow_factory,
        superseded,
        expected_revision=2,
        idempotency_key="supersede",
        request_fingerprint="c" * 64,
    ) == (superseded, 3)
    assert (superseded.reviewed_by, superseded.reviewed_at, superseded.reason) == (
        accepted.reviewed_by,
        accepted.reviewed_at,
        accepted.reason,
    )
    assert append_finance_review(
        store.uow_factory,
        superseded,
        expected_revision=2,
        idempotency_key="supersede",
        request_fingerprint="c" * 64,
    ) == (superseded, 3)


def test_failed_append_has_no_partial_persistence(finance_context):
    store, pending = finance_context
    append_finance_review(
        store.uow_factory,
        pending,
        expected_revision=None,
        idempotency_key="submit-stale",
        request_fingerprint="d" * 64,
    )
    append_finance_review(
        store.uow_factory,
        approved(pending),
        expected_revision=1,
        idempotency_key="approve-kept",
        request_fingerprint="e" * 64,
    )
    with pytest.raises(FinanceReviewRevisionConflict):
        append_finance_review(
            store.uow_factory,
            rejected(pending),
            expected_revision=1,
            idempotency_key="reject-stale",
            request_fingerprint="f" * 64,
        )
    with store.engine.connect() as connection:
        rows = (
            connection.execute(
                select(finance_review_revisions)
                .where(finance_review_revisions.c.review_id == pending.review_id)
                .order_by(finance_review_revisions.c.revision)
            )
            .mappings()
            .all()
        )
    assert [row["revision"] for row in rows] == [1, 2]
    assert [row["status"] for row in rows] == ["pending", "approved"]


@pytest.mark.parametrize("expected_revision", [True, False, 0, -1])
def test_expected_revision_must_be_positive_integer(finance_context, expected_revision):
    store, pending = finance_context
    with (
        store.uow_factory() as uow,
        pytest.raises(ValueError, match="positive integer"),
    ):
        uow.finance_reviews.append(
            pending,
            expected_revision=expected_revision,
            idempotency_key="invalid",
            request_fingerprint="a" * 64,
        )


def test_idempotency_requires_same_fingerprint_and_full_snapshot(finance_context):
    store, pending = finance_context
    append_finance_review(
        store.uow_factory,
        pending,
        expected_revision=None,
        idempotency_key="submit",
        request_fingerprint="a" * 64,
    )
    with pytest.raises(FinanceReviewIdempotencyConflict):
        append_finance_review(
            store.uow_factory,
            pending,
            expected_revision=None,
            idempotency_key="submit",
            request_fingerprint="b" * 64,
        )
    changed = pending.model_copy(update={"review_id": "another-review"})
    with pytest.raises(FinanceReviewIdempotencyConflict):
        append_finance_review(
            store.uow_factory,
            changed,
            expected_revision=None,
            idempotency_key="submit",
            request_fingerprint="a" * 64,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"status": FinanceReviewStatus.APPROVED},
        {"proposal": None},
        {"submitted_by": None},
        {"submitted_at": NOW + timedelta(minutes=1)},
    ],
)
def test_first_or_transition_state_must_preserve_lifecycle(finance_context, mutation):
    store, pending = finance_context
    if mutation.get("status", False):
        candidate = approved(pending)
        with pytest.raises(PersistenceIntegrityError):
            append_finance_review(
                store.uow_factory,
                candidate,
                expected_revision=None,
                idempotency_key="bad-first",
                request_fingerprint="a" * 64,
            )
        return
    append_finance_review(
        store.uow_factory,
        pending,
        expected_revision=None,
        idempotency_key="submit",
        request_fingerprint="a" * 64,
    )
    if "proposal" in mutation:
        candidate = approved(pending).model_copy(
            update={
                "proposal": pending.proposal.model_copy(
                    update={"response_cost": Decimal("22500.00")}
                )
            }
        )
    elif "submitted_by" in mutation:
        candidate = approved(pending).model_copy(
            update={"submitted_by": actor("TAYLOR")}
        )
    else:
        candidate = approved(pending).model_copy(update=mutation)
    with pytest.raises(PersistenceIntegrityError):
        append_finance_review(
            store.uow_factory,
            candidate,
            expected_revision=1,
            idempotency_key="bad-transition",
            request_fingerprint="b" * 64,
        )


def test_terminal_transition_rules(finance_context):
    store, pending = finance_context
    accepted = approved(pending)
    terminal = supersede_finance_review(review=accepted, now=NOW + timedelta(seconds=2))
    for review, revision, key, fingerprint in [
        (pending, None, "one", "1" * 64),
        (accepted, 1, "two", "2" * 64),
        (terminal, 2, "three", "3" * 64),
    ]:
        append_finance_review(
            store.uow_factory,
            review,
            expected_revision=revision,
            idempotency_key=key,
            request_fingerprint=fingerprint,
        )
    with pytest.raises(PersistenceIntegrityError):
        append_finance_review(
            store.uow_factory,
            terminal,
            expected_revision=3,
            idempotency_key="four",
            request_fingerprint="f" * 64,
        )


def test_tampered_duplicated_column_is_detected(finance_context):
    store, pending = finance_context
    append_finance_review(
        store.uow_factory,
        pending,
        expected_revision=None,
        idempotency_key="submit",
        request_fingerprint="a" * 64,
    )
    with store.engine.begin() as connection:
        connection.execute(update(finance_review_revisions).values(status="approved"))
    with store.uow_factory() as uow, pytest.raises(PersistenceIntegrityError):
        uow.finance_reviews.get_latest(pending.review_id)


def test_facade_preserves_unclassified_integrity_error(finance_context, monkeypatch):
    store, pending = finance_context
    original = IntegrityError("insert", {}, RuntimeError("foreign key failure"))

    def fail_append(self, review, **kwargs):
        del self, review, kwargs
        raise original

    monkeypatch.setattr(SqlAlchemyFinanceReviewRepository, "append", fail_append)
    with pytest.raises(IntegrityError) as caught:
        append_finance_review(
            store.uow_factory,
            pending,
            expected_revision=None,
            idempotency_key="non-unique-error",
            request_fingerprint="9" * 64,
        )
    assert caught.value is original
    with store.engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count()).select_from(finance_review_revisions)
            )
            == 0
        )
