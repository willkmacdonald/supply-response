from pathlib import Path


OPERATIONAL = Path("fabric/sql/001_operational_schema.sql")
ANALYTICS = Path("fabric/sql/002_analytics_views.sql")


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_operational_schema_contains_the_complete_canonical_store_contract():
    sql = _normalized(OPERATIONAL)
    required_tables = {
        "action_projection",
        "analysis_versions",
        "approval_satisfactions",
        "case_instances",
        "case_projection",
        "decisions",
        "draft_artifacts",
        "evidence_items",
        "execution_actions",
        "execution_attempts",
        "execution_events",
        "operational_snapshots",
        "outbox_events",
        "outcome_observations",
        "playbacks",
        "schema_version",
    }

    for table in required_tables:
        assert f"create table app.{table}" in sql
    assert "unique (decision_id, event_type)" in sql
    assert "unique (action_id, attempt_number)" in sql
    assert "unique (decision_id)" in sql
    assert "foreign key (current_analysis_id)" in sql
    assert "foreign key (current_decision_id)" in sql
    assert "nvarchar(max)" in sql
    assert "datetimeoffset" in sql
    assert "isjson" in sql


def test_operational_schema_avoids_sqlite_only_ddl_and_commands():
    sql = _normalized(OPERATIONAL)

    for forbidden in ("pragma", "autoincrement", "insert or", "sqlite"):
        assert forbidden not in sql


def test_analytics_views_preserve_decision_lineage_and_provenance():
    sql = _normalized(ANALYTICS)

    assert "create or alter view analytics.case_command_center" in sql
    assert "create or alter view analytics.action_outcomes" in sql
    assert "d.decision_id = c.current_decision_id" in sql
    assert "x.decision_id = d.decision_id" in sql
    assert "o.decision_id = d.decision_id" in sql
    assert "cast('action' as nvarchar(16)) as record_type" in sql
    assert "cast('observation' as nvarchar(16)) as record_type" in sql
    assert "selected_option_id" in sql
    assert "scenario_effective_time" in sql
    assert "observation_kind" in sql


def test_analytics_views_never_infer_decision_truth_from_action_state():
    sql = _normalized(ANALYTICS)

    decision_projection_start = sql.index(
        "create or alter view app.decision_projection"
    )
    command_center_start = sql.index(
        "create or alter view analytics.case_command_center"
    )
    decision_projection = sql[decision_projection_start:command_center_start]
    assert "from app.decisions" in decision_projection
    assert "execution_actions" not in decision_projection
    assert "action_projection" not in decision_projection


def test_live_schema_version_is_published_only_after_analytics_views_exist():
    operational = _normalized(OPERATIONAL)
    analytics = _normalized(ANALYTICS)

    assert "values (n'operational', 11)" in operational
    assert "set schema_version = 12" in analytics
    assert analytics.index("create or alter view analytics.action_outcomes") < (
        analytics.index("set schema_version = 12")
    )
