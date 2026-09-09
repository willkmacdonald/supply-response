import json
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from integrations.fabric.schema import apply_fabric_schema


@pytest.fixture(scope="module")
def engine():
    raw = os.environ.get("SUPPLY_RESPONSE_LOCAL_REPORTING_SQL_URL")
    if not raw:
        pytest.skip("local SQL execution gate not configured")
    url = make_url(raw)
    assert url.drivername == "mssql+pyodbc"
    assert url.host in {"localhost", "127.0.0.1", "::1"}
    assert (url.database or "").startswith("supply_response_projection_test_")
    assert "odbc_connect" not in url.query
    assert "server" not in {key.lower() for key in url.query}
    value = create_engine(url)
    with value.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT compatibility_level FROM sys.databases WHERE name = DB_NAME()"
                )
            )
            >= 130
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s "
                    "ON s.schema_id=t.schema_id WHERE s.name IN ('app','analytics')"
                )
            )
            == 0
        ), "Use a fresh dedicated test database"
    apply_fabric_schema(value)
    apply_fabric_schema(value)
    yield value
    value.dispose()


def rows(engine, query, **parameters):
    with engine.connect() as connection:
        return list(connection.execute(text(query), parameters).mappings())


def seed(engine, *, snapshot=None, options=None, recommendation="response"):
    case_id, analysis_id = str(uuid4()), str(uuid4())
    snapshot = dict(snapshot or {})
    at = "2026-09-01T09:00:00-05:00"
    snapshot = {
        "scenario_effective_time": at,
        "scenario_timezone": "America/Chicago",
        "analysis_horizon_start": at,
        "analysis_horizon_end": "2026-09-10",
        "inventory_positions": [],
        "production_orders": [],
        "customer_orders": [],
        "disruption": {},
        **snapshot,
        "case_id": case_id,
        "runtime_mode": "live",
    }
    payload = {
        "case_id": case_id,
        "analysis_id": analysis_id,
        "material": {
            "case_id": case_id,
            "runtime_mode": "live",
            "template_id": "RL-001",
            "corpus": "demo_corpus",
            "evidence": [],
            "scenario_effective_time": "2026-09-01T09:00:00-05:00",
            "calculation_version": "test-v1",
            "operational_snapshot_json": json.dumps(snapshot),
        },
        "response_options": options or [],
        "ranking": {"recommended_option_id": recommendation},
        "evidence_items": [],
    }
    with engine.begin() as connection:
        connection.execute(
            text("""
            INSERT app.case_instances
            (case_id,template_id,purpose,runtime_mode,status,scenario_effective_time,payload_json)
            VALUES (:c,'RL-001','automated_test','live','open',:at,'{}')
        """),
            {"c": case_id, "at": at},
        )
        connection.execute(
            text("""
            INSERT app.analysis_versions
            (analysis_id,case_id,material_hash,runtime_mode,analysis_started_at,
             retrieval_window_ends_at,created_at,payload_json)
            VALUES (:a,:c,'test','live',SYSDATETIMEOFFSET(),SYSDATETIMEOFFSET(),
                    SYSDATETIMEOFFSET(),:p)
        """),
            {"a": analysis_id, "c": case_id, "p": json.dumps(payload)},
        )
    return case_id, analysis_id, payload


# Test-only malformed/history fixture.
def rewrite_fixture_payload(
    engine, analysis_id, payload
):  # allowed: test-only malformed/history fixture
    # Test-only malformed/history fixtures; production never updates saved analysis.
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.analysis_versions SET payload_json=:p WHERE analysis_id=:a"
            ),
            {"a": analysis_id, "p": json.dumps(payload)},
        )


def option(identity, kind="expedite", value="0.00"):
    value = f"{Decimal(value):.2f}"
    return {
        "option_id": identity,
        "option_kind": kind,
        "name": identity,
        "executable": False,
        "active_mitigation": kind != "no_mitigation",
        "predicted": {
            "revenue_at_risk": value,
            "margin_at_risk": value,
            "response_cost": value,
            "uncovered_part_demand": 0,
            "otif_loss_percentage": 0,
            "protected_customer_order_ids": [],
        },
        "blocking_codes": ["QUALIFICATION_PENDING"],
        "assumptions": [],
        "prerequisite_roles": [],
        "evidence_ids": [],
    }


def test_options_preserve_zero_null_false_and_reject_duplicate_identity(engine):
    missing = option("missing")
    missing["predicted"] = None
    c, a, _ = seed(
        engine,
        options=[
            option("baseline", "no_mitigation"),
            option("response"),
            missing,
            option("duplicate"),
            option("duplicate"),
        ],
    )
    result = rows(
        engine,
        "SELECT * FROM analytics.saved_options WHERE case_id=:c AND analysis_id=:a",
        c=c,
        a=a,
    )
    by_id = {row["option_id"]: row for row in result}
    assert set(by_id) == {"baseline", "response", "missing"}
    assert by_id["baseline"]["is_baseline"]
    assert by_id["response"]["is_recommended"]
    assert by_id["response"]["revenue_at_risk"] == 0
    assert by_id["response"]["executable"] is False
    assert by_id["missing"]["revenue_at_risk"] is None


def test_snapshot_is_full_length_and_identity_checked(engine):
    c, a, payload = seed(engine, snapshot={"padding": "x" * 5000})
    result = rows(
        engine, "SELECT * FROM analytics.saved_analyses WHERE analysis_id=:a", a=a
    )[0]
    assert result["case_id"] == c
    assert result["snapshot_state"] == "available"
    assert len(result["snapshot_json"]) > 5000
    for invalid in (
        "{",
        "null",
        "[]",
        json.dumps({"case_id": "wrong", "runtime_mode": "live"}),
    ):
        payload["material"]["operational_snapshot_json"] = invalid
        rewrite_fixture_payload(engine, a, payload)
        result = rows(
            engine, "SELECT * FROM analytics.saved_analyses WHERE analysis_id=:a", a=a
        )[0]
        assert result["snapshot_state"] == "unavailable"
        assert result["snapshot_json"] is None


@pytest.mark.parametrize(
    "kind,value,expected",
    [
        ("integer", 0, "0"),
        ("integer", "0", None),
        ("integer", "", None),
        ("integer", 0.5, None),
        ("integer", True, None),
        ("integer", 2147483648, None),
        ("money", "0.00", "0.00"),
        ("money", "", None),
        ("money", "1.239", None),
        ("money", 0, None),
        ("money", "1e2", None),
        ("money", " 0.00", None),
        ("date", "2026-09-06", "2026-09-06"),
        ("date", "", None),
        ("date", "2026-9-6", None),
        ("date", "09/06/2026", None),
        ("date", "2026-02-30", None),
        ("date", "2026-09-06 ", None),
        ("nullable_date", None, "#null"),
        ("nullable_flag", False, "false"),
        ("flag", "false", None),
        ("nullable_instant", None, "#null"),
        ("instant", "2026-09-01T09:00:00-05:00", "2026-09-01T09:00:00-05:00"),
        ("instant", "2026-09-01", None),
        ("instant", "2026-09-01T09:00:00", None),
        ("instant", "2026-09-01T09:00:00.1234567Z", None),
    ],
)
def test_strict_scalar_semantics(engine, kind, value, expected):
    result = rows(
        engine,
        "SELECT analytics.report_scalar(:p,N'value',:kind) AS value",
        p=json.dumps({"value": value}),
        kind=kind,
    )[0]
    assert result["value"] == expected


@pytest.mark.parametrize("payload", ["{}", '{"value":0,"value":0}', "{"])
def test_missing_duplicate_or_malformed_scalar_is_unavailable(engine, payload):
    assert (
        rows(
            engine,
            "SELECT analytics.report_scalar(:p,N'value',N'integer') AS value",
            p=payload,
        )[0]["value"]
        is None
    )


def test_snapshot_absence_is_separate_from_payload_identity(engine):
    _c, a, payload = seed(engine, options=[option("response")])
    payload["material"]["operational_snapshot_json"] = "{"
    rewrite_fixture_payload(engine, a, payload)
    result = rows(
        engine,
        "SELECT payload_state,snapshot_state FROM analytics.saved_analyses WHERE analysis_id=:a",
        a=a,
    )[0]
    assert result == {"payload_state": "available", "snapshot_state": "unavailable"}
    assert (
        len(
            rows(
                engine,
                "SELECT * FROM analytics.saved_options WHERE analysis_id=:a",
                a=a,
            )
        )
        == 1
    )
    payload["case_id"] = "wrong"
    rewrite_fixture_payload(engine, a, payload)
    assert (
        rows(engine, "SELECT * FROM analytics.saved_options WHERE analysis_id=:a", a=a)
        == []
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("template_id", "other"),
        ("corpus", "real_business"),
        ("scenario_effective_time", "2026-09-02T09:00:00-05:00"),
        ("runtime_mode", "fallback"),
        ("case_id", "wrong"),
    ],
)
def test_material_envelope_mismatch_suppresses_all_facts(engine, field, value):
    _c, a, payload = seed(engine, options=[option("response")])
    payload["material"][field] = value
    rewrite_fixture_payload(engine, a, payload)
    result = rows(
        engine,
        "SELECT payload_state,snapshot_state FROM analytics.saved_analyses WHERE analysis_id=:a",
        a=a,
    )[0]
    assert result == {"payload_state": "unavailable", "snapshot_state": "unavailable"}
    assert (
        rows(engine, "SELECT * FROM analytics.saved_options WHERE analysis_id=:a", a=a)
        == []
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario_timezone", "UTC"),
        ("analysis_horizon_end", "2026-9-10"),
        ("analysis_horizon_start", ""),
        ("inventory_positions", {}),
        ("scenario_effective_time", "2026-09-02T09:00:00-05:00"),
    ],
)
def test_snapshot_envelope_mismatch_preserves_only_valid_options(engine, field, value):
    _c, a, payload = seed(engine, options=[option("response")])
    snapshot = json.loads(payload["material"]["operational_snapshot_json"])
    snapshot[field] = value
    payload["material"]["operational_snapshot_json"] = json.dumps(snapshot)
    rewrite_fixture_payload(engine, a, payload)
    result = rows(
        engine,
        "SELECT payload_state,snapshot_state FROM analytics.saved_analyses WHERE analysis_id=:a",
        a=a,
    )[0]
    assert result == {"payload_state": "available", "snapshot_state": "unavailable"}
    assert (
        len(
            rows(
                engine,
                "SELECT * FROM analytics.saved_options WHERE analysis_id=:a",
                a=a,
            )
        )
        == 1
    )
