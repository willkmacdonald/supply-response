import tomllib
from contextlib import nullcontext
from importlib.util import find_spec
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Engine

from integrations.fabric import schema

ROOT = Path(__file__).resolve().parents[2]


def test_fabric_schema_application_module_exists():
    assert find_spec("integrations.fabric.schema") is not None


def test_fabric_schema_application_exposes_required_contract():
    assert hasattr(schema, "split_go_batches")
    assert hasattr(schema, "apply_sql_script")
    assert hasattr(schema, "apply_fabric_schema")


def test_go_splitter_accepts_line_only_case_insensitive_delimiters():
    sql = "SELECT 'go is data';\n  go  \nSELECT 2;\nGO\n\nSELECT 3;\n"

    assert schema.split_go_batches(sql) == (
        "SELECT 'go is data';",
        "SELECT 2;",
        "SELECT 3;",
    )


class RecordingConnection:
    def __init__(self, statements: list[str], failure: str | None = None) -> None:
        self._statements = statements
        self._failure = failure

    def exec_driver_sql(self, statement: str) -> None:
        self._statements.append(statement)
        if self._failure == statement:
            raise RuntimeError("batch failed")


class RecordingEngine:
    def __init__(self, failure: str | None = None) -> None:
        self.statements: list[str] = []
        self.begin_count = 0
        self._failure = failure

    def begin(self):
        self.begin_count += 1
        return nullcontext(RecordingConnection(self.statements, self._failure))


def test_script_application_uses_one_transaction_per_nonempty_batch():
    engine = RecordingEngine()

    schema.apply_sql_script(cast(Engine, engine), "SELECT 1;\nGO\n\nGO\nSELECT 2;")

    assert engine.statements == ["SELECT 1;", "SELECT 2;"]
    assert engine.begin_count == 2


def test_script_application_stops_after_a_failed_batch():
    engine = RecordingEngine(failure="SELECT 2;")

    with pytest.raises(RuntimeError, match="batch failed"):
        schema.apply_sql_script(
            cast(Engine, engine),
            "SELECT 1;\nGO\nSELECT 2;\nGO\nSELECT 3;",
        )

    assert engine.statements == ["SELECT 1;", "SELECT 2;"]


def test_fabric_schema_application_executes_all_checked_in_scripts(monkeypatch):
    scripts: list[str] = []
    monkeypatch.setattr(
        schema,
        "apply_sql_script",
        lambda engine, sql: scripts.append(sql),
    )

    schema.apply_fabric_schema(cast(Engine, object()))

    assert len(scripts) == 3
    assert "CREATE TABLE app.case_instances" in scripts[0]
    assert "CREATE OR ALTER VIEW analytics.action_outcomes" in scripts[1]
    assert "CREATE TABLE reporting.datasets" in scripts[2]


def test_fabric_schema_scripts_are_included_in_the_production_wheel():
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    force_include = configuration["tool"]["hatch"]["build"]["targets"]["wheel"][
        "force-include"
    ]

    assert force_include == {
        "fabric/sql/001_operational_schema.sql": (
            "fabric/sql/001_operational_schema.sql"
        ),
        "fabric/sql/002_analytics_views.sql": ("fabric/sql/002_analytics_views.sql"),
        "fabric/sql/003_reporting_dataset.sql": (
            "fabric/sql/003_reporting_dataset.sql"
        ),
    }
