"""Bounded retention of supplier-bound live presenter Case aggregates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from sqlalchemy import Connection, Table, delete, func, or_, select, update

from data.domain import CasePurpose, RuntimeMode
from services.persistence import tables
from services.persistence.store import PersistenceError

PRESENTER_AGGREGATE_DELETE_ORDER = (
    "case_projection",
    "outcome_observations",
    "supplier_email_revisions",
    "supplier_email_deliveries",
    "draft_artifacts",
    "execution_attempts",
    "execution_events",
    "action_projection",
    "playbacks",
    "outbox_events",
    "approval_satisfactions",
    "execution_actions",
    "case_proposal_selections",
    "finance_review_revisions",
    "decisions",
    "evidence_items",
    "analysis_versions",
    "analysis_claims",
    "operational_snapshots",
    "case_instances",
)


if TYPE_CHECKING:
    from services.persistence.store import SqlAlchemyStore


def _empty_planned_deletions() -> dict[str, int]:
    return dict.fromkeys(PRESENTER_AGGREGATE_DELETE_ORDER, 0)


@dataclass(frozen=True)
class PresenterRetentionPlan:
    current_case_id: str
    retained_case_ids: tuple[str, ...]
    pruned_case_ids: tuple[str, ...]
    planned_deletions: dict[str, int] = field(default_factory=_empty_planned_deletions)


@dataclass(frozen=True)
class PresenterRetentionResult:
    plan: PresenterRetentionPlan
    deleted_rows: dict[str, int]


class PresenterRetentionPlanChanged(PersistenceError):
    """The eligible history changed after retention was previewed."""


class PresenterRetentionLockUnavailable(PersistenceError):
    """The database could not grant the transaction's exclusive retention lock."""


def plan_presenter_retention(
    connection: Connection,
    store: SqlAlchemyStore,
    *,
    current_case_id: str | None,
    historical_limit: int,
) -> PresenterRetentionPlan:
    if historical_limit < 0:
        raise ValueError("historical_limit must be nonnegative")
    rows = connection.execute(
        select(tables.case_instances)
        .where(
            tables.case_instances.c.runtime_mode == RuntimeMode.LIVE.value,
            tables.case_instances.c.purpose == CasePurpose.SHOWCASE.value,
        )
        .order_by(
            tables.case_instances.c.recorded_at.desc(),
            tables.case_instances.c.case_id.desc(),
        )
    ).mappings()
    eligible: list[str] = []
    for row in rows:
        case = store._decode_case(
            row["payload_json"], record_name="immutable case record"
        )
        if (
            case.runtime_mode is RuntimeMode.LIVE
            and case.purpose is CasePurpose.SHOWCASE
            and case.supplier_email is not None
            and case.case_id == row["case_id"]
        ):
            eligible.append(case.case_id)
    if current_case_id is None:
        if not eligible:
            return PresenterRetentionPlan("", (), ())
        current_case_id = eligible[0]
    if current_case_id not in eligible:
        raise ValueError("current Case must be live, showcase, and supplier-bound")
    history = tuple(case_id for case_id in eligible if case_id != current_case_id)
    partial_plan = PresenterRetentionPlan(
        current_case_id,
        (current_case_id, *history[:historical_limit]),
        history[historical_limit:],
    )
    return PresenterRetentionPlan(
        partial_plan.current_case_id,
        partial_plan.retained_case_ids,
        partial_plan.pruned_case_ids,
        count_presenter_aggregate_deletions(connection, partial_plan),
    )


def presenter_aggregate_targets(plan: PresenterRetentionPlan):
    """Yield each aggregate table with the predicate used to delete its rows."""
    case_ids = plan.pruned_case_ids
    analysis_ids = select(tables.analysis_versions.c.analysis_id).where(
        tables.analysis_versions.c.case_id.in_(case_ids)
    )
    decision_ids = select(tables.decisions.c.decision_id).where(
        tables.decisions.c.case_id.in_(case_ids)
    )
    action_ids = select(tables.execution_actions.c.action_id).where(
        tables.execution_actions.c.case_id.in_(case_ids)
    )
    playback_ids = select(tables.playbacks.c.playback_id).where(
        tables.playbacks.c.case_id.in_(case_ids)
    )
    predicates = {
        "case_id": case_ids,
        "analysis_id": analysis_ids,
        "decision_id": decision_ids,
        "action_id": action_ids,
        "playback_id": playback_ids,
    }
    for name in PRESENTER_AGGREGATE_DELETE_ORDER:
        table = tables.metadata.tables[name]
        # Parent primary keys must not match another aggregate's subquery.
        keys = {
            "case_instances": ("case_id",),
            "analysis_versions": ("case_id",),
            "decisions": ("case_id",),
            "execution_actions": ("case_id",),
            "playbacks": ("case_id",),
        }.get(name, tuple(predicates))
        predicate = or_(
            *(table.c[key].in_(predicates[key]) for key in keys if key in table.c)
        )
        yield name, table, predicate


def count_presenter_aggregate_deletions(
    connection: Connection, plan: PresenterRetentionPlan
) -> dict[str, int]:
    if not plan.pruned_case_ids:
        return _empty_planned_deletions()
    return {
        name: connection.execute(
            select(func.count()).select_from(table).where(predicate)
        ).scalar_one()
        for name, table, predicate in presenter_aggregate_targets(plan)
    }


def presenter_aggregate_delete_statements(plan: PresenterRetentionPlan):
    """Build portable statements while parents still exist for child subqueries."""
    for name, table, predicate in presenter_aggregate_targets(plan):
        if name == "case_proposal_selections":
            yield update(table).where(predicate).values(expected_selection_id=None)
        yield delete(table).where(predicate)


def delete_presenter_aggregates(
    connection: Connection, plan: PresenterRetentionPlan
) -> PresenterRetentionResult:
    deleted_rows: dict[str, int] = dict.fromkeys(PRESENTER_AGGREGATE_DELETE_ORDER, 0)
    if plan.pruned_case_ids:
        for statement in presenter_aggregate_delete_statements(plan):
            result = connection.execute(statement)
            if statement.is_delete:
                deleted_rows[cast(Table, statement.table).name] = result.rowcount
    return PresenterRetentionResult(plan, deleted_rows)
