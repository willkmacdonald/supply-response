import re
from contextlib import nullcontext
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Engine

from integrations.fabric.health import (
    FABRIC_SCHEMA_VERSION,
    FabricSchemaError,
    check_fabric_health,
)
from integrations.fabric.schema import apply_sql_script, split_go_batches

OPERATIONAL = Path("fabric/sql/001_operational_schema.sql")
ANALYTICS = Path("fabric/sql/002_analytics_views.sql")


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_operational_schema_contains_the_complete_canonical_store_contract():
    sql = _normalized(OPERATIONAL)
    required_tables = {
        "action_projection",
        "analysis_versions",
        "analysis_claims",
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
        "live_operational_sources",
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
    assert "create or alter view analytics.saved_analyses" in sql
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
    assert "12 as schema_version" not in operational
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

    assert table_count == 18
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

    assert len(indexes) == 26


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
    assert len(re.findall(r"CREATE OR ALTER VIEW", analytics, re.IGNORECASE)) == 8
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
    assert "select n'operational' as component, 11 as schema_version" in version_batch
    assert f"{FABRIC_SCHEMA_VERSION} as schema_version" not in version_batch


class _SequencedResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _SequencedFabricEngine:
    """Exercise the production script runner while tracking publication state."""

    def __init__(self) -> None:
        self.schema_version: int | None = None
        self.views: set[str] = set()

    def begin(self):
        return nullcontext(self)

    def connect(self):
        return nullcontext(self)

    def exec_driver_sql(self, batch: str) -> None:
        for schema_name, view_name in re.findall(
            r"CREATE OR ALTER VIEW\s+(\w+)\.(\w+)", batch, re.IGNORECASE
        ):
            self.views.add(f"{schema_name.lower()}.{view_name.lower()}")
        version_match = re.search(
            r"SELECT\s+N'operational'\s+AS\s+component,\s+(\d+)\s+AS\s+schema_version",
            batch,
            re.IGNORECASE,
        )
        if version_match:
            self.schema_version = max(
                self.schema_version or 0, int(version_match.group(1))
            )
        if re.search(r"SET\s+schema_version\s*=\s*12", batch, re.IGNORECASE):
            self.schema_version = 12

    def execute(self, statement):
        query = str(statement)
        if query == "SELECT 1":
            return _SequencedResult(1)
        if "FROM app.schema_version" in query:
            assert self.schema_version is not None
            return _SequencedResult(self.schema_version)
        if "FROM sys.views" in query:
            required = {
                "app.analysis_projection",
                "app.decision_projection",
                "analytics.case_command_center",
                "analytics.action_outcomes",
            }
            return _SequencedResult(len(required & self.views))
        raise AssertionError(f"unexpected health query: {query}")


def test_real_script_sequence_promotes_readiness_only_after_analytics():
    engine = _SequencedFabricEngine()
    typed_engine = cast(Engine, engine)

    apply_sql_script(typed_engine, OPERATIONAL.read_text(encoding="utf-8"))

    assert engine.schema_version == 11
    assert engine.views == set()
    with pytest.raises(FabricSchemaError, match="expected 12, found 11"):
        check_fabric_health(typed_engine)

    apply_sql_script(typed_engine, ANALYTICS.read_text(encoding="utf-8"))

    assert engine.schema_version == FABRIC_SCHEMA_VERSION
    assert engine.views == {
        "app.analysis_projection",
        "app.decision_projection",
        "analytics.case_command_center",
        "analytics.action_outcomes",
        "analytics.saved_analyses",
        "analytics.saved_options",
        "analytics.saved_records",
        "analytics.saved_record_evidence",
    }
    health = check_fabric_health(typed_engine)
    assert health.schema_version == FABRIC_SCHEMA_VERSION
    assert health.power_bi_available is True


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

    assert len({name for kind, name in existing if kind == "table"}) == 18
    assert len({name for kind, name in existing if kind == "index"}) == 26
    assert schema_version == 12
