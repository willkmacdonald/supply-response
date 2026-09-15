from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import (
    Boolean,
    DateTime,
    Engine,
    Integer,
    event,
    func,
    insert,
    select,
    update,
)

from data.domain import CaseInstance, CasePurpose, RuntimeMode
from data.synthetic.rl001 import OperationalSnapshot, instantiate_rl001
from services.persistence import presenter_runs, tables
from services.persistence.presenter_runs import (
    PRESENTER_AGGREGATE_DELETE_ORDER,
    PresenterRetentionPlan,
    PresenterRetentionPlanChanged,
    PresenterRetentionResult,
)
from services.persistence.sqlite import sqlite_store
from services.persistence.store import SqlAlchemyStore
from tests.persistence.test_inbound_binding import source


@dataclass
class PopulatedPresenterStore:
    store: SqlAlchemyStore
    current_case: CaseInstance
    current_snapshot: OperationalSnapshot
    three_recent_presenter_cases: tuple[CaseInstance, ...]
    oldest_presenter_case: CaseInstance
    unbound_showcase_case: CaseInstance
    automated_test_case: CaseInstance


def bound_case(case_id, *, run_id=None, runtime_mode=RuntimeMode.LIVE):
    case, snapshot = instantiate_rl001(
        case_id=case_id, purpose=CasePurpose.SHOWCASE, runtime_mode=runtime_mode
    )
    return CaseInstance.model_validate(
        {**case.model_dump(), "supplier_email": source(), "presenter_run_id": run_id}
    ), snapshot


def populate_aggregate(store, case):
    """Insert FK-valid descendants, including both proposal self-reference ends."""
    now = datetime(2026, 9, 14, tzinfo=UTC)
    ids = {
        "case_id": case.case_id,
        "analysis_id": f"{case.case_id}:analysis",
        "decision_id": f"{case.case_id}:decision",
        "action_id": f"{case.case_id}:action",
        "playback_id": f"{case.case_id}:playback",
        "review_id": f"{case.case_id}:review",
        "selection_id": f"{case.case_id}:selection",
    }
    order = (
        "analysis_claims",
        "analysis_versions",
        "evidence_items",
        "finance_review_revisions",
        "case_proposal_selections",
        "decisions",
        "approval_satisfactions",
        "outbox_events",
        "execution_actions",
        "supplier_email_deliveries",
        "supplier_email_revisions",
        "action_projection",
        "draft_artifacts",
        "execution_events",
        "execution_attempts",
        "playbacks",
        "outcome_observations",
    )
    with store.engine.begin() as connection:
        for name in order:
            table = tables.metadata.tables[name]
            values = {}
            for column in table.columns:
                if (
                    column.nullable
                    or column.server_default is not None
                    or column.autoincrement is True
                ):
                    continue
                if column.name in ids:
                    value = ids[column.name]
                elif isinstance(column.type, DateTime):
                    value = now
                elif isinstance(column.type, Boolean):
                    value = True
                elif isinstance(column.type, Integer):
                    value = 1
                else:
                    value = f"{case.case_id}:{name}:{column.name}"
                values[column.name] = value
            if name == "case_proposal_selections":
                values.update(
                    workflow_version="independent-finance-v1",
                    finance_review_id=ids["review_id"],
                    finance_review_revision=1,
                )
            if name == "outcome_observations":
                values.update(
                    kind="simulated",
                    synthetic=True,
                    playback_id=ids["playback_id"],
                    action_id=ids["action_id"],
                )
            if name in ("supplier_email_deliveries", "supplier_email_revisions"):
                values["email_id"] = f"{case.case_id}:email"
            if name == "supplier_email_deliveries":
                values["send_status"] = "draft"
            if name == "approval_satisfactions":
                values.update(
                    decision_id=ids["decision_id"],
                    persona_id="RL-PERSONA-TAYLOR",
                    role="finance_approver",
                    satisfied=True,
                )
            connection.execute(insert(table).values(**values))
            if name == "case_proposal_selections":
                values.update(
                    selection_id=f"{case.case_id}:selection-2",
                    expected_selection_id=ids["selection_id"],
                    finance_review_id=None,
                    finance_review_revision=None,
                    idempotency_key=f"{case.case_id}:selection-2",
                )
                connection.execute(insert(table).values(**values))
        connection.execute(
            update(tables.case_projection)
            .where(tables.case_projection.c.case_id == case.case_id)
            .values(
                current_analysis_id=ids["analysis_id"],
                current_selection_id=ids["selection_id"],
                current_decision_id=ids["decision_id"],
            )
        )


@pytest.fixture
def populated_presenter_store(tmp_path):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'presenter.db'}", runtime_mode=RuntimeMode.LIVE
    )
    cases = []
    snapshots = []
    for index in range(5):
        case, snapshot = bound_case(
            f"presenter-{index}", run_id=None if index == 0 else f"RL-RUN-{index:032x}"
        )
        cases.append(case)
        snapshots.append(snapshot)
        if index < 4:
            store.create_case(case, snapshot)
            with store.engine.begin() as connection:
                connection.execute(
                    update(tables.case_instances)
                    .where(tables.case_instances.c.case_id == case.case_id)
                    .values(
                        recorded_at=datetime(2026, 9, 1, tzinfo=UTC)
                        + timedelta(days=index)
                    )
                )
    unbound, unbound_snapshot = instantiate_rl001(
        case_id="unbound", purpose=CasePurpose.SHOWCASE, runtime_mode=RuntimeMode.LIVE
    )
    automated, automated_snapshot = instantiate_rl001(
        case_id="automated",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.LIVE,
    )
    store.create_case(unbound, unbound_snapshot)
    store.create_case(automated, automated_snapshot)
    populate_aggregate(store, cases[0])
    populate_aggregate(store, unbound)
    populate_aggregate(store, automated)
    return PopulatedPresenterStore(
        store, cases[4], snapshots[4], tuple(cases[1:4]), cases[0], unbound, automated
    )


def aggregate_row_count(engine: Engine, name: str, case_id: str) -> int:
    table = tables.metadata.tables[name]
    key = next(
        key
        for key in ("case_id", "analysis_id", "decision_id", "action_id")
        if key in table.c
    )
    value = case_id if key == "case_id" else f"{case_id}:{key.removesuffix('_id')}"
    with engine.connect() as connection:
        return connection.execute(
            select(func.count()).select_from(table).where(table.c[key] == value)
        ).scalar_one()


def case_ids(store):
    with store.engine.connect() as connection:
        return set(connection.scalars(select(tables.case_instances.c.case_id)))


def test_create_presenter_case_keeps_current_plus_three_and_deletes_aggregate(
    populated_presenter_store,
):
    fixture = populated_presenter_store
    before = {
        name: aggregate_row_count(
            fixture.store.engine, name, fixture.oldest_presenter_case.case_id
        )
        for name in PRESENTER_AGGREGATE_DELETE_ORDER
    }
    assert all(before.values())
    excluded_before = {
        (case.case_id, name): aggregate_row_count(
            fixture.store.engine, name, case.case_id
        )
        for case in (fixture.unbound_showcase_case, fixture.automated_test_case)
        for name in PRESENTER_AGGREGATE_DELETE_ORDER
    }
    result = fixture.store.create_presenter_case(
        fixture.current_case, fixture.current_snapshot
    )
    assert result.plan.current_case_id == fixture.current_case.case_id
    assert result.plan.retained_case_ids == (
        fixture.current_case.case_id,
        "presenter-3",
        "presenter-2",
        "presenter-1",
    )
    assert result.plan.pruned_case_ids == (fixture.oldest_presenter_case.case_id,)
    assert {
        case.case_id for case in fixture.store.list_cases(purpose=CasePurpose.SHOWCASE)
    } == {
        fixture.current_case.case_id,
        *(case.case_id for case in fixture.three_recent_presenter_cases),
        fixture.unbound_showcase_case.case_id,
    }
    assert result.deleted_rows == before
    assert all(
        aggregate_row_count(fixture.store.engine, name, case_id) == count
        for (case_id, name), count in excluded_before.items()
    )
    for name in PRESENTER_AGGREGATE_DELETE_ORDER:
        assert (
            aggregate_row_count(
                fixture.store.engine, name, fixture.oldest_presenter_case.case_id
            )
            == 0
        )
    assert (
        fixture.store.get_case(fixture.automated_test_case.case_id)
        == fixture.automated_test_case
    )


def test_pruning_failure_rolls_back_new_case_and_history(
    populated_presenter_store, monkeypatch
):
    fixture = populated_presenter_store
    before = case_ids(fixture.store)
    original = presenter_runs.delete_presenter_aggregates

    def fail(connection, plan):
        original(connection, plan)
        raise RuntimeError("forced")

    monkeypatch.setattr(presenter_runs, "delete_presenter_aggregates", fail)
    with pytest.raises(RuntimeError, match="forced"):
        fixture.store.create_presenter_case(
            fixture.current_case, fixture.current_snapshot
        )
    assert case_ids(fixture.store) == before
    assert all(
        aggregate_row_count(
            fixture.store.engine, name, fixture.oldest_presenter_case.case_id
        )
        for name in PRESENTER_AGGREGATE_DELETE_ORDER
    )


def test_apply_rejects_a_changed_preview(populated_presenter_store):
    fixture = populated_presenter_store
    preview = fixture.store.preview_presenter_retention(historical_limit=3)
    fixture.store.create_presenter_case(fixture.current_case, fixture.current_snapshot)
    before = case_ids(fixture.store)
    with pytest.raises(PresenterRetentionPlanChanged):
        fixture.store.apply_presenter_retention(preview)
    assert case_ids(fixture.store) == before


def test_preview_counts_every_aggregate_table_including_zero_rows(tmp_path):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'preview-counts.db'}", runtime_mode=RuntimeMode.LIVE
    )
    expired, expired_snapshot = bound_case("expired", run_id="RL-RUN-" + "a" * 32)
    current, current_snapshot = bound_case("current", run_id="RL-RUN-" + "b" * 32)
    store.create_case(expired, expired_snapshot)
    store.create_case(current, current_snapshot)
    with store.engine.begin() as connection:
        connection.execute(
            update(tables.case_instances)
            .where(tables.case_instances.c.case_id == expired.case_id)
            .values(recorded_at=datetime(2026, 9, 13, tzinfo=UTC))
        )
        connection.execute(
            update(tables.case_instances)
            .where(tables.case_instances.c.case_id == current.case_id)
            .values(recorded_at=datetime(2026, 9, 14, tzinfo=UTC))
        )

    plan = store.preview_presenter_retention(historical_limit=0)
    expected = {
        name: aggregate_row_count(store.engine, name, expired.case_id)
        for name in PRESENTER_AGGREGATE_DELETE_ORDER
    }

    assert tuple(plan.planned_deletions) == PRESENTER_AGGREGATE_DELETE_ORDER
    assert plan.planned_deletions == expected
    assert any(count == 0 for count in expected.values())
    assert expected["case_instances"] == 1


def test_apply_rolls_back_when_actual_deletion_counts_differ_from_preview(
    populated_presenter_store, monkeypatch
):
    fixture = populated_presenter_store
    fixture.store.create_case(fixture.current_case, fixture.current_snapshot)
    preview = fixture.store.preview_presenter_retention()
    before = case_ids(fixture.store)
    original = presenter_runs.delete_presenter_aggregates

    def misreport(connection, plan):
        result = original(connection, plan)
        actual = dict(result.deleted_rows)
        actual["analysis_versions"] += 1
        return PresenterRetentionResult(result.plan, actual)

    monkeypatch.setattr(presenter_runs, "delete_presenter_aggregates", misreport)

    with pytest.raises(PresenterRetentionPlanChanged, match="preview again"):
        fixture.store.apply_presenter_retention(preview)

    assert case_ids(fixture.store) == before
    assert all(
        aggregate_row_count(
            fixture.store.engine, name, fixture.oldest_presenter_case.case_id
        )
        for name in PRESENTER_AGGREGATE_DELETE_ORDER
    )


def test_apply_recomputes_counts_under_lock_and_rejects_changed_rows(
    populated_presenter_store,
):
    fixture = populated_presenter_store
    fixture.store.create_case(fixture.current_case, fixture.current_snapshot)
    preview = fixture.store.preview_presenter_retention()
    expired_id = fixture.oldest_presenter_case.case_id
    with fixture.store.engine.begin() as connection:
        connection.execute(
            insert(tables.analysis_claims).values(
                case_id=expired_id,
                material_version="late-row",
                claim_id="late-row",
                claimed_at=datetime(2026, 9, 14, tzinfo=UTC),
                claim_expires_at=datetime(2026, 9, 15, tzinfo=UTC),
            )
        )

    with pytest.raises(PresenterRetentionPlanChanged, match="preview again"):
        fixture.store.apply_presenter_retention(preview)

    assert (
        aggregate_row_count(fixture.store.engine, "analysis_claims", expired_id)
        == preview.planned_deletions["analysis_claims"] + 1
    )


def test_preview_order_ties_and_custom_limit(populated_presenter_store):
    store = populated_presenter_store.store
    with store.engine.begin() as connection:
        connection.execute(
            update(tables.case_instances).values(
                recorded_at=datetime(2026, 9, 1, tzinfo=UTC)
            )
        )
    plan = store.preview_presenter_retention(historical_limit=1)
    assert plan.current_case_id == "presenter-3"
    assert plan.retained_case_ids == ("presenter-3", "presenter-2")
    assert plan.pruned_case_ids == ("presenter-1", "presenter-0")
    assert plan.planned_deletions == {
        name: sum(
            aggregate_row_count(store.engine, name, case_id)
            for case_id in plan.pruned_case_ids
        )
        for name in PRESENTER_AGGREGATE_DELETE_ORDER
    }
    assert store.apply_presenter_retention(plan).plan == plan


@pytest.mark.parametrize("kind", ["unbound", "automated", "fallback", "negative"])
def test_rejects_ineligible_current_and_negative_limit(tmp_path, kind):
    mode = RuntimeMode.FALLBACK if kind == "fallback" else RuntimeMode.LIVE
    store = sqlite_store(f"sqlite:///{tmp_path / 'invalid.db'}", runtime_mode=mode)
    case, snapshot = bound_case("invalid", runtime_mode=mode)
    if kind in ("unbound", "automated"):
        case = CaseInstance.model_validate(
            {
                **case.model_dump(),
                "supplier_email": None,
                "purpose": CasePurpose.AUTOMATED_TEST
                if kind == "automated"
                else CasePurpose.SHOWCASE,
            }
        )
    with pytest.raises(ValueError):
        store.create_presenter_case(
            case, snapshot, historical_limit=-1 if kind == "negative" else 3
        )
    assert case_ids(store) == set()
    with pytest.raises(ValueError):
        store.preview_presenter_retention(historical_limit=-1)


def test_empty_and_fallback_preview_are_safe_noops(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'fallback.db'}")
    empty = PresenterRetentionPlan("", (), ())
    assert store.preview_presenter_retention() == empty
    case, snapshot = instantiate_rl001(
        case_id="fallback",
        purpose=CasePurpose.SHOWCASE,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    store.create_case(case, snapshot)
    assert store.preview_presenter_retention() == empty
    result = store.apply_presenter_retention(empty)
    assert not any(result.deleted_rows.values())
    assert store.get_case(case.case_id) == case


def test_command_defaults_to_preview_and_apply_keeps_four(
    populated_presenter_store, monkeypatch, capsys
):
    from scripts import prune_presenter_runs

    fixture = populated_presenter_store
    fixture.store.create_case(fixture.current_case, fixture.current_snapshot)
    monkeypatch.setattr(prune_presenter_runs, "Settings", lambda: object())
    monkeypatch.setattr(
        prune_presenter_runs, "build_store", lambda settings: fixture.store
    )
    before = case_ids(fixture.store)
    prune_presenter_runs.main([])
    assert case_ids(fixture.store) == before
    assert "presenter-0" in capsys.readouterr().out
    prune_presenter_runs.main(["--apply"])
    assert case_ids(fixture.store) == before - {"presenter-0"}


def test_apply_recreate_interleaving_preserves_current_and_four_cases(
    populated_presenter_store, monkeypatch
):
    from services.persistence.presenter_runs import PresenterRetentionLockUnavailable

    fixture = populated_presenter_store
    store = fixture.store
    store.create_case(fixture.current_case, fixture.current_snapshot)
    preview = store.preview_presenter_retention()
    assert preview.pruned_case_ids == ("presenter-0",)
    other = sqlite_store(str(store.engine.url), runtime_mode=RuntimeMode.LIVE)

    @event.listens_for(other.engine, "checkout")
    def fail_immediately_if_locked(dbapi_connection, *_):
        dbapi_connection.execute("PRAGMA busy_timeout=0")

    extra, extra_snapshot = bound_case("presenter-5", run_id="RL-RUN-" + "5" * 32)
    recreated, recreated_snapshot = bound_case(
        "presenter-0", run_id="RL-RUN-" + "6" * 32
    )

    def create_and_recreate():  # allowed: reproduce the competing writer's API calls
        other.create_presenter_case(extra, extra_snapshot)
        other.create_presenter_case(recreated, recreated_snapshot)

    original_plan = presenter_runs.plan_presenter_retention
    interleavings = []

    def pause_after_recompute(connection, active_store, **kwargs):
        plan = original_plan(connection, active_store, **kwargs)
        if active_store is store and kwargs["current_case_id"] is None:
            # Deterministically attempt the reviewer's two writes after recomputation,
            # before apply can compare/delete. The other store has a separate pool.
            try:
                create_and_recreate()
            except PresenterRetentionLockUnavailable:
                interleavings.append("blocked")
            else:
                interleavings.append("interleaved")
        return plan

    monkeypatch.setattr(
        presenter_runs, "plan_presenter_retention", pause_after_recompute
    )
    store.apply_presenter_retention(preview)
    if interleavings == ["blocked"]:
        # The competing writer can safely retry after apply commits/releases its lock.
        create_and_recreate()
    assert store.get_case(recreated.case_id) == recreated
    assert len(other.preview_presenter_retention().retained_case_ids) == 4
    assert interleavings == ["blocked"]


@pytest.mark.parametrize("operation", ["create", "apply"])
def test_sqlite_retention_lock_failure_is_closed(populated_presenter_store, operation):
    from services.persistence.presenter_runs import PresenterRetentionLockUnavailable

    fixture = populated_presenter_store
    store = fixture.store
    before = case_ids(store)
    preview = store.preview_presenter_retention()
    locker = sqlite_store(str(store.engine.url), runtime_mode=RuntimeMode.LIVE)

    @event.listens_for(store.engine, "checkout")
    def fail_immediately_if_locked(dbapi_connection, *_):
        dbapi_connection.execute("PRAGMA busy_timeout=0")

    with locker.engine.begin() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        with pytest.raises(PresenterRetentionLockUnavailable):
            if operation == "create":
                store.create_presenter_case(
                    fixture.current_case, fixture.current_snapshot
                )
            else:
                store.apply_presenter_retention(preview)
        assert case_ids(store) == before
    if operation == "create":
        store.create_presenter_case(fixture.current_case, fixture.current_snapshot)
    else:
        store.apply_presenter_retention(preview)


@pytest.mark.parametrize("operation", ["create", "apply"])
def test_sqlite_retention_holds_lock_until_commit(populated_presenter_store, operation):
    from services.persistence.presenter_runs import PresenterRetentionLockUnavailable

    fixture = populated_presenter_store
    store = fixture.store
    preview = store.preview_presenter_retention()
    other = sqlite_store(str(store.engine.url), runtime_mode=RuntimeMode.LIVE)

    @event.listens_for(other.engine, "checkout")
    def fail_immediately_if_locked(dbapi_connection, *_):
        dbapi_connection.execute("PRAGMA busy_timeout=0")

    attempted = []

    @event.listens_for(store.engine, "commit")
    def assert_still_locked(_connection):
        with (
            other.engine.begin() as connection,
            pytest.raises(PresenterRetentionLockUnavailable),
        ):
            other._acquire_presenter_retention_lock(connection)
        attempted.append(True)

    if operation == "create":
        store.create_presenter_case(fixture.current_case, fixture.current_snapshot)
    else:
        store.apply_presenter_retention(preview)
    assert attempted == [True]
    with other.engine.begin() as connection:
        other._acquire_presenter_retention_lock(connection)
