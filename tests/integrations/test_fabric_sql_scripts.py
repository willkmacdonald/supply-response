from pathlib import Path
import re

from integrations.fabric.schema import split_go_batches


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

    assert "select n'operational' as component, 11 as schema_version" in operational
    assert "set schema_version = 12" in analytics
    assert analytics.index("create or alter view analytics.action_outcomes") < (
        analytics.index("set schema_version = 12")
    )


def test_every_operational_table_and_inline_constraint_is_retry_guarded():
    batches = split_go_batches(OPERATIONAL.read_text(encoding="utf-8"))
    table_count = 0
    constraint_count = 0

    for batch in batches:
        match = re.search(r"CREATE TABLE app\.(\w+)", batch, re.IGNORECASE)
        if match is None:
            continue
        table_count += 1
        table_name = match.group(1)
        assert re.search(
            rf"IF\s+OBJECT_ID\(N'app\.{table_name}',\s*N'U'\)\s+IS\s+NULL",
            batch,
            re.IGNORECASE,
        ), table_name
        constraints = re.findall(r"CONSTRAINT\s+(\w+)", batch, re.IGNORECASE)
        assert constraints
        constraint_count += len(constraints)

    assert table_count == 16
    assert constraint_count >= 50


def test_every_operational_index_has_its_own_retry_guard():
    batches = split_go_batches(OPERATIONAL.read_text(encoding="utf-8"))
    indexes: list[str] = []

    for batch in batches:
        for index_name in re.findall(r"CREATE INDEX\s+(\w+)", batch, re.IGNORECASE):
            indexes.append(index_name)
            assert re.search(
                rf"IF\s+NOT\s+EXISTS\s*\([^;]*sys\.indexes[^;]*"
                rf"N'{index_name}'[^;]*\)",
                batch,
                re.IGNORECASE | re.DOTALL,
            ), index_name

    assert len(indexes) == 24


def test_schemas_views_and_version_publication_are_idempotent():
    operational = OPERATIONAL.read_text(encoding="utf-8")
    analytics = ANALYTICS.read_text(encoding="utf-8")

    assert re.search(
        r"IF\s+NOT\s+EXISTS\s*\([^)]*sys\.schemas[^)]*N'app'",
        operational,
        re.IGNORECASE,
    )
    assert re.search(
        r"IF\s+NOT\s+EXISTS\s*\([^)]*sys\.schemas[^)]*N'analytics'",
        analytics,
        re.IGNORECASE,
    )
    assert len(re.findall(r"CREATE OR ALTER VIEW", analytics, re.IGNORECASE)) == 4
    assert "MERGE app.schema_version WITH (HOLDLOCK)" in operational
    assert "schema_version < 12" in analytics
    assert "@@ROWCOUNT" not in analytics


def test_operational_version_publication_advances_to_11_without_downgrade():
    version_batch = " ".join(
        split_go_batches(OPERATIONAL.read_text(encoding="utf-8"))[-1].lower().split()
    )

    assert "merge app.schema_version with (holdlock)" in version_batch
    assert "when matched and target.schema_version < source.schema_version" in (
        version_batch
    )
    assert "when not matched then insert" in version_batch
    assert "values (source.component, source.schema_version)" in version_batch


def test_partial_operational_application_and_double_retry_do_not_collide():
    operational = split_go_batches(OPERATIONAL.read_text(encoding="utf-8"))
    analytics = split_go_batches(ANALYTICS.read_text(encoding="utf-8"))
    existing: set[tuple[str, str]] = set()
    schema_version: int | None = None

    def execute(batch: str) -> None:
        nonlocal schema_version
        creations = [
            *(
                ("table", name)
                for name in re.findall(r"CREATE TABLE app\.(\w+)", batch, re.IGNORECASE)
            ),
            *(
                ("index", name)
                for name in re.findall(r"CREATE INDEX\s+(\w+)", batch, re.IGNORECASE)
            ),
        ]
        guarded = "IF " in batch.upper()
        for creation in creations:
            if creation in existing and not guarded:
                raise AssertionError(f"object collision: {creation}")
            existing.add(creation)
        if "MERGE app.schema_version WITH (HOLDLOCK)" in batch:
            schema_version = max(schema_version or 0, 11)
        if "SET schema_version = 12" in batch and schema_version is not None:
            schema_version = 12

    prefix = len(operational) // 2
    for batch in operational[:prefix]:
        execute(batch)
    for script in (operational, analytics, operational, analytics):
        for batch in script:
            execute(batch)

    assert len({name for kind, name in existing if kind == "table"}) == 16
    assert len({name for kind, name in existing if kind == "index"}) == 24
    assert schema_version == 12
