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


def test_sql_readiness_and_explicit_report_inventory(engine):
    from integrations.fabric.health import check_fabric_health

    assert check_fabric_health(engine).schema_version == 12
    assert (
        rows(
            engine,
            "SELECT OBJECT_ID(N'analytics.report_scalar',N'FN') AS object_id",
        )[0]["object_id"]
        is not None
    )
    expected = {
        "saved_analyses",
        "saved_options",
        "saved_records",
        "saved_record_evidence",
        "case_reporting",
    }
    actual = rows(
        engine,
        "SELECT v.name FROM sys.views v JOIN sys.schemas s ON s.schema_id=v.schema_id "
        "WHERE s.name='analytics'",
    )
    assert expected <= {row["name"] for row in actual}
    for view in sorted(expected):
        # Names come from a constant allowlist, never user input.
        columns = rows(engine, f"SELECT TOP (0) * FROM analytics.{view}")
        assert columns == []


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


def test_new_analysis_does_not_replace_governing_approved_prediction(engine):
    c, old, payload = seed(
        engine,
        options=[
            option("baseline", "no_mitigation", "100"),
            option("response", value="20"),
            option("chosen", value="30"),
        ],
    )
    new, decision = str(uuid4()), str(uuid4())
    new_payload = dict(
        payload,
        analysis_id=new,
        response_options=[
            option("baseline", "no_mitigation", "200"),
            option("response", value="5"),
        ],
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                """
            INSERT app.analysis_versions
            (analysis_id,case_id,material_hash,runtime_mode,analysis_started_at,
             retrieval_window_ends_at,created_at,payload_json)
            SELECT :n,case_id,'new','live',analysis_started_at,retrieval_window_ends_at,
                   DATEADD(second,1,created_at),:p FROM app.analysis_versions WHERE analysis_id=:a
        """
            ),
            {"n": new, "p": json.dumps(new_payload), "a": old},
        )
        connection.execute(
            text(
                """
            INSERT app.decisions
            (decision_id,case_id,analysis_id,idempotency_key,kind,runtime_mode,decided_at,payload_json)
            VALUES (:d,:c,:a,:d,'approved','live',SYSDATETIMEOFFSET(),:p)
        """
            ),
            {
                "d": decision,
                "c": c,
                "a": old,
                "p": json.dumps({"selected_option_id": "chosen"}),
            },
        )
        connection.execute(
            text(
                """
            INSERT app.case_projection
            (case_id,purpose,status,runtime_mode,scenario_effective_time,
             current_analysis_id,current_decision_id,payload_json)
            VALUES (:c,'automated_test','open','live',SYSDATETIMEOFFSET(),:n,:d,'{}')
        """
            ),
            {"c": c, "n": new, "d": decision},
        )
    result = rows(
        engine, "SELECT * FROM analytics.case_reporting WHERE case_id=:c", c=c
    )[0]
    assert result["current_analysis_id"] == new
    assert result["decision_analysis_id"] == old
    assert result["baseline_revenue_at_risk"] == 200
    assert result["recommended_revenue_at_risk"] == 5
    assert result["approved_revenue_at_risk"] == 30
    assert (
        rows(
            engine,
            "SELECT revenue_at_risk FROM analytics.saved_options WHERE case_id=:c AND analysis_id=:a AND option_id='response'",
            c=c,
            a=old,
        )[0]["revenue_at_risk"]
        == 20
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.decisions SET kind='rejected',payload_json='{}' WHERE decision_id=:d"
            ),
            {"d": decision},
        )
    assert (
        rows(
            engine,
            "SELECT approved_revenue_at_risk FROM analytics.case_reporting WHERE case_id=:c",
            c=c,
        )[0]["approved_revenue_at_risk"]
        is None
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.case_projection SET current_analysis_id=NULL,current_decision_id=NULL WHERE case_id=:c"
            ),
            {"c": c},
        )
    result = rows(
        engine, "SELECT * FROM analytics.case_reporting WHERE case_id=:c", c=c
    )[0]
    assert result["recommended_revenue_at_risk"] is None
    assert result["baseline_revenue_at_risk"] is None
    assert result["approved_revenue_at_risk"] is None


def test_absent_recommendation_and_ambiguous_baselines_do_not_pick_an_option(engine):
    c, a, _ = seed(
        engine,
        recommendation=None,
        options=[
            option("baseline-1", "no_mitigation", "10"),
            option("baseline-2", "no_mitigation", "20"),
        ],
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                """
            INSERT app.case_projection
            (case_id,purpose,status,runtime_mode,scenario_effective_time,
             current_analysis_id,payload_json)
            VALUES (:c,'automated_test','open','live',SYSDATETIMEOFFSET(),:a,'{}')
        """
            ),
            {"c": c, "a": a},
        )
    result = rows(
        engine, "SELECT * FROM analytics.case_reporting WHERE case_id=:c", c=c
    )[0]
    assert result["recommended_option_id"] is None
    assert result["recommended_revenue_at_risk"] is None
    assert result["baseline_option_id"] is None
    assert result["baseline_revenue_at_risk"] is None


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


def test_stock_order_and_historical_record_grains(engine):
    stock = {
        "inventory_id": "shared",
        "part_id": "P",
        "plant_id": "CHI",
        "on_hand": 10,
        "quality_hold": 2,
        "protected_allocation": 8,
    }
    customer = {
        "customer_order_line_id": "line",
        "customer_id": "C",
        "product_id": "FG",
        "plant_id": "CHI",
        "quantity": 2,
        "unit_revenue": "12.50",
        "unit_margin": "0.00",
        "due_date": "2026-09-06",
        "production_order_id": "production",
    }
    c, a, payload = seed(
        engine,
        snapshot={"inventory_positions": [stock], "customer_orders": [customer]},
    )
    c2, a2, payload2 = seed(
        engine, snapshot={"inventory_positions": [dict(stock, on_hand=99)]}
    )
    result = rows(
        engine,
        "SELECT * FROM analytics.saved_records WHERE case_id=:c AND analysis_id=:a",
        c=c,
        a=a,
    )
    by_family = {row["record_family"]: row for row in result}
    assert by_family["inventory"]["usable_inventory"] == 0
    assert by_family["customer_order_line"]["line_revenue"] == 25
    assert str(by_family["customer_order_line"]["due_date"]) == "2026-09-06"
    assert (
        rows(
            engine,
            "SELECT * FROM analytics.saved_records WHERE case_id=:c AND analysis_id=:a",
            c=c2,
            a=a,
        )
        == []
    )
    payload2["case_id"] = c
    payload2["material"]["case_id"] = c
    snapshot2 = json.loads(payload2["material"]["operational_snapshot_json"])
    snapshot2["case_id"] = c
    payload2["material"]["operational_snapshot_json"] = json.dumps(snapshot2)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT app.case_projection "
                "(case_id,purpose,runtime_mode,status,scenario_effective_time,"
                "current_analysis_id,current_analysis_hash,current_decision_id,payload_json) "
                "VALUES (:c,'automated_test','live','open',:at,:old,'hash',NULL,'{}')"
            ),
            {"c": c, "at": "2026-09-01T09:00:00-05:00", "old": a},
        )
        connection.execute(
            text(
                "UPDATE app.analysis_versions SET case_id=:c,payload_json=:p "
                "WHERE analysis_id=:a"
            ),
            {"c": c, "a": a2, "p": json.dumps(payload2)},
        )
        connection.execute(
            text(
                "UPDATE app.case_projection SET current_analysis_id=:a WHERE case_id=:c"
            ),
            {"c": c, "a": a2},
        )
    newer = rows(
        engine,
        "SELECT on_hand FROM analytics.saved_records "
        "WHERE case_id=:c AND analysis_id=:a AND record_family='inventory'",
        c=c,
        a=a2,
    )
    assert newer[0]["on_hand"] == 99
    historical = rows(
        engine,
        "SELECT on_hand FROM analytics.saved_records "
        "WHERE case_id=:c AND analysis_id=:a AND record_family='inventory'",
        c=c,
        a=a,
    )
    assert historical[0]["on_hand"] == 10
    snapshot = json.loads(payload["material"]["operational_snapshot_json"])
    snapshot["inventory_positions"].append(stock)
    payload["material"]["operational_snapshot_json"] = json.dumps(snapshot)
    rewrite_fixture_payload(engine, a, payload)
    assert (
        rows(
            engine,
            "SELECT * FROM analytics.saved_records WHERE analysis_id=:a AND record_family='inventory'",
            a=a,
        )
        == []
    )


@pytest.mark.parametrize(
    "field,value,column",
    [
        ("quantity", "", "quantity"),
        ("quantity", 1.5, "quantity"),
        ("due_date", "", "due_date"),
        ("due_date", "09/06/2026", "due_date"),
        ("incremental_cost_per_unit", "0.001", "incremental_cost_per_unit"),
    ],
)
def test_malformed_required_record_fact_never_becomes_available_zero(
    engine, field, value, column
):
    receipt = {
        "receipt_id": "receipt",
        "supplier_id": "supplier",
        "part_id": "part",
        "plant_id": "CHI",
        "quantity": 1,
        "due_date": "2026-09-06",
        "incremental_cost_per_unit": "0.00",
        field: value,
    }
    _c, a, _ = seed(
        engine,
        snapshot={
            "alpha_expedite": receipt,
            "inventory_positions": [
                {
                    "inventory_id": "stock",
                    "part_id": "part",
                    "plant_id": "CHI",
                    "on_hand": 0,
                    "quality_hold": 0,
                    "protected_allocation": 0,
                }
            ],
        },
    )
    result = rows(
        engine,
        "SELECT * FROM analytics.saved_records WHERE analysis_id=:a AND record_family='shipment'",
        a=a,
    )[0]
    assert result["record_state"] == "unavailable"
    assert result[column] is None
    inventory = rows(
        engine,
        "SELECT * FROM analytics.saved_records WHERE analysis_id=:a AND record_family='inventory'",
        a=a,
    )[0]
    assert inventory["record_state"] == "available"
    assert inventory["usable_inventory"] == 0
    assert inventory["due_date"] is None


@pytest.mark.parametrize(
    "status,expected",
    [
        ("approved", "available"),
        ("pending", "available"),
        ("APPROVED", "unavailable"),
        ("Pending", "unavailable"),
    ],
)
def test_qualification_status_uses_exact_enum(engine, status, expected):
    _c, a, _ = seed(
        engine,
        snapshot={
            "beta_qualification": {
                "qualification_id": "qualification",
                "supplier_id": "supplier",
                "part_id": "part",
                "evidence_ref": "proof",
                "status": status,
                "audit_complete": False,
                "first_article_complete": None,
                "effective_date": None,
                "expected_decision_date": None,
            }
        },
    )
    result = rows(
        engine,
        "SELECT record_state FROM analytics.saved_records WHERE analysis_id=:a AND record_family='qualification'",
        a=a,
    )[0]
    assert result["record_state"] == expected


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


@pytest.mark.parametrize(
    "family,member,key,prefix",
    [
        ("shipment", "alpha_expedite", "receipt_id", "fabric.supply_receipt/"),
        ("transfer", "transfer", "transfer_id", "fabric.inventory_transfer/"),
        (
            "qualification",
            "beta_qualification",
            "qualification_id",
            "fabric.qualification/",
        ),
    ],
)
def test_exact_evidence_and_duplicate_or_missing_provenance(
    engine, family, member, key, prefix
):
    expected_id = "proof" if family == "qualification" else "record"
    record = {
        key: "record",
        "evidence_ref": "proof",
        "audit_complete": False,
        "first_article_complete": None,
        "effective_date": None,
        "expected_decision_date": None,
        "supplier_id": "supplier",
        "part_id": "part",
        "plant_id": "CHI",
        "source_plant_id": "DAL",
        "destination_plant_id": "CHI",
        "quantity": 1,
        "due_date": "2026-09-06",
        "dispatch_date": "2026-09-05",
        "arrival_date": "2026-09-06",
        "incremental_cost_per_unit": "0.00",
        "status": "pending",
    }
    c, a, payload = seed(engine, snapshot={member: record})
    times = rows(
        engine,
        "SELECT analysis_started_at FROM app.analysis_versions WHERE analysis_id=:a",
        a=a,
    )[0]
    evidence = {
        "evidence_id": expected_id,
        "case_id": c,
        "source_id": prefix + "record",
        "kind": "operational_fact",
        "source_system": "fabric",
        "retrieved_for_analysis_id": a,
        "runtime_mode": "live",
        "synthetic": False,
        "retrieved_at": times["analysis_started_at"].isoformat(),
        "source_timestamp": None,
    }
    query = "SELECT * FROM analytics.saved_record_evidence WHERE case_id=:c AND analysis_id=:a AND record_family=:f"
    for items, material, expected in [
        ([evidence], [evidence], "available"),
        ([evidence, evidence], [evidence], "unavailable"),
        ([evidence, dict(evidence, source_id="different")], [evidence], "unavailable"),
        (
            [evidence, dict(evidence, evidence_id="different")],
            [evidence],
            "unavailable",
        ),
        ([evidence], [evidence, evidence], "unavailable"),
        ([evidence], [], "unavailable"),
        (
            [dict(evidence, evidence_id="wrong")],
            [dict(evidence, evidence_id="wrong")],
            "unavailable",
        ),
        (
            [dict(evidence, kind="source_statement")],
            [dict(evidence, kind="source_statement")],
            "unavailable",
        ),
        (
            [dict(evidence, synthetic=True)],
            [dict(evidence, synthetic=True)],
            "unavailable",
        ),
        (
            [dict(evidence, synthetic="false")],
            [dict(evidence, synthetic="false")],
            "unavailable",
        ),
        ([evidence], [dict(evidence, synthetic=True)], "unavailable"),
        ([evidence], [dict(evidence, source_id="other")], "unavailable"),
        (
            [evidence],
            [dict(evidence, source_timestamp="2026-09-01T00:00:00Z")],
            "unavailable",
        ),
        (
            [dict(evidence, retrieved_for_analysis_id="other")],
            [evidence],
            "unavailable",
        ),
        ([dict(evidence, retrieved_at=None)], [evidence], "available"),
        ([dict(evidence, retrieved_at="")], [evidence], "unavailable"),
        (
            [dict(evidence, source_timestamp="")],
            [dict(evidence, source_timestamp="")],
            "unavailable",
        ),
        (
            [{k: v for k, v in evidence.items() if k != "source_timestamp"}],
            [evidence],
            "unavailable",
        ),
        ([dict(evidence, source_id=prefix + "RECORD")], [evidence], "unavailable"),
        ([], [], "unavailable"),
    ]:
        payload["evidence_items"] = items
        payload["material"]["evidence"] = material
        rewrite_fixture_payload(engine, a, payload)
        result = rows(engine, query, c=c, a=a, f=family)[0]
        assert result["evidence_state"] == expected
        assert result["source_timestamp"] is None
        assert result["provenance"] == (
            "saved_fabric" if expected == "available" else None
        )
        if items and items[0].get("retrieved_at") is None:
            assert result["retrieved_at"] is None

        if family == "qualification":
            audit_rows = rows(
                engine,
                "SELECT audit_complete FROM analytics.saved_records "
                "WHERE case_id=:c AND analysis_id=:a AND record_family=:f "
                "AND source_record_id=:r",
                c=c,
                a=a,
                f=family,
                r=record[key],
            )
            assert len(audit_rows) == 1
            assert audit_rows[0]["audit_complete"] is False

    fixture = dict(
        evidence,
        runtime_mode="fallback",
        source_system="synthetic_fixture",
        synthetic=True,
        source_id="RL-SOURCE-" + expected_id,
        retrieved_at=None,
    )
    snapshot = json.loads(payload["material"]["operational_snapshot_json"])
    snapshot["runtime_mode"] = "fallback"
    payload["material"].update(
        runtime_mode="fallback",
        evidence=[fixture],
        operational_snapshot_json=json.dumps(snapshot),
    )
    payload["evidence_items"] = [fixture]
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.case_instances SET runtime_mode='fallback' WHERE case_id=:c"
            ),
            {"c": c},
        )
        connection.execute(
            text(
                "UPDATE app.analysis_versions SET runtime_mode='fallback' WHERE analysis_id=:a"
            ),
            {"a": a},
        )
    rewrite_fixture_payload(engine, a, payload)
    result = rows(engine, query, c=c, a=a, f=family)[0]
    assert result["evidence_state"] == "available"
    assert result["provenance"] == "demo_fixture"
    assert result["synthetic"] is True
    assert result["retrieved_at"] is None


def partition_rows(engine, table_name, case_id):
    from pathlib import Path

    assert table_name in {
        "CaseCommandCenter",
        "SavedAnalyses",
        "SavedRecords",
        "SavedOptions",
        "ActionOutcomes",
    }
    query = (
        Path(__file__).resolve().parents[2]
        / "fabric"
        / "reporting"
        / "queries"
        / f"{table_name}.sql"
    ).read_text()
    return rows(
        engine, f"SELECT * FROM ({query}) AS partition_data WHERE case_id=:c", c=case_id
    )


def test_partition_queries_preserve_identity_and_utc_without_exposing_payload(engine):
    from datetime import datetime

    c, a, _ = seed(engine, options=[option("A'😀"), option("a'😀")])
    analysis = partition_rows(engine, "SavedAnalyses", c)
    assert len(analysis) == 1
    assert analysis[0]["case_key"] == c.encode("utf-16le").hex().upper()
    assert analysis[0]["analysis_key"] == a.encode("utf-16le").hex().upper()
    assert analysis[0]["scenario_effective_time"] == datetime(2026, 9, 1, 14)  # noqa: DTZ001
    assert not any(key.endswith("_json") for key in analysis[0])
    options = partition_rows(engine, "SavedOptions", c)
    assert {r["option_key"] for r in options} == {
        identity.encode("utf-16le").hex().upper() for identity in ("A'😀", "a'😀")
    }
    assert all(r["response_cost"] == Decimal(0) for r in options)
    assert all(r["executable"] is False for r in options)
    for table in ("CaseCommandCenter", "SavedRecords", "ActionOutcomes"):
        result = partition_rows(engine, table, c)
        assert all(r["case_id"] == c for r in result)
        assert all(not any(key.endswith("_json") for key in r) for r in result)


def test_partition_stock_and_customer_membership_follow_saved_planning_scope(engine):
    from datetime import date

    disruption = {
        "disruption_id": "signal",
        "supplier_id": "supplier",
        "part_id": "Part",
        "plant_id": "Plant",
        "po_line_id": "po",
        "source_ref": "source",
        "original_quantity": 100,
        "partial_quantity": 0,
        "original_due_date": "2026-09-02",
        "partial_due_date": None,
        "recovery_date": None,
    }

    def inventory(identity, part):
        return {
            "inventory_id": identity,
            "part_id": part,
            "plant_id": "Plant",
            "on_hand": 10,
            "quality_hold": 2,
            "protected_allocation": 3,
        }

    production = {
        "production_order_id": "production",
        "product_id": "product",
        "plant_id": "OtherPlant",
        "quantity": 10,
        "due_date": "2026-09-03",
        "component_demand": 10,
        "customer_priority": 1,
        "customer_revenue": "200.00",
        "customer_margin": "20.00",
    }

    def customer(identity, production_id):
        return {
            "customer_order_line_id": identity,
            "customer_order_id": identity,
            "production_order_id": production_id,
            "customer_id": "customer",
            "product_id": "product",
            "plant_id": "OtherPlant",
            "quantity": 10,
            "due_date": "2026-09-03",
            "unit_revenue": "5.00",
            "unit_margin": "1.00",
        }

    c, a, _ = seed(
        engine,
        snapshot={
            "disruption": disruption,
            "inventory_positions": [
                inventory("stock", "Part"),
                inventory("wrong-case", "part"),
            ],
            "production_orders": [production],
            "customer_orders": [
                customer("linked", "production"),
                customer("unlinked", "Production"),
            ],
        },
    )
    records = partition_rows(engine, "SavedRecords", c)
    by_id = {r["source_record_id"]: r for r in records}
    assert by_id["stock"]["in_disruption_scope"] is True
    assert by_id["stock"]["usable_inventory"] == 5
    assert by_id["wrong-case"]["in_disruption_scope"] is False
    assert by_id["production"]["in_disruption_scope"] is True
    assert by_id["linked"]["in_disruption_scope"] is True
    assert by_id["unlinked"]["in_disruption_scope"] is False
    assert by_id["linked"]["due_date"] == date(2026, 9, 3)
    assert by_id["linked"]["line_revenue"] == Decimal(50)
    assert len(records) == len(
        {
            (r["case_key"], r["analysis_key"], r["record_family"], r["record_key"])
            for r in records
        }
    )
    assert all(r["analysis_key"] == a.encode("utf-16le").hex().upper() for r in records)


def test_partition_reused_source_ids_do_not_cross_case_or_analysis(engine):
    one, a, _ = seed(engine, options=[option("same", value="1")])
    two, b, _ = seed(engine, options=[option("same", value="2")])
    first = partition_rows(engine, "SavedOptions", one)
    second = partition_rows(engine, "SavedOptions", two)
    assert first[0]["option_key"] == second[0]["option_key"]
    assert first[0]["analysis_key"] != second[0]["analysis_key"]
    assert first[0]["analysis_id"] == a and second[0]["analysis_id"] == b
    assert first[0]["response_cost"] == Decimal(1)
    assert second[0]["response_cost"] == Decimal(2)


@pytest.mark.parametrize(
    "field,value,output,expected",
    [
        (
            "blocking_codes",
            ["QUALITY_QUALIFICATION_PENDING"],
            "blockers_text",
            "Cannot use Supplier Beta yet: supplier qualification is incomplete",
        ),
        ("blocking_codes", [], "blockers_text", "No planning blockers recorded"),
        ("blocking_codes", None, "blockers_text", None),
        ("blocking_codes", {"code": "x"}, "blockers_text", None),
        ("blocking_codes", ["x", 1], "blockers_text", None),
        ("blocking_codes", [" "], "blockers_text", None),
        (
            "prerequisite_roles",
            ["finance_approver", "quality_approver"],
            "required_roles_text",
            "Finance approver\nQuality approver",
        ),
        (
            "assumptions",
            ["Saved assumption", "<literal text>"],
            "assumptions_text",
            "Saved assumption\n<literal text>",
        ),
        ("protected_customer_order_ids", [], "protected_customer_order_count", 0),
        (
            "protected_customer_order_ids",
            ["A", "a"],
            "protected_customer_order_count",
            2,
        ),
        (
            "protected_customer_order_ids",
            ["A", "A"],
            "protected_customer_order_count",
            None,
        ),
        (
            "protected_customer_order_ids",
            ["A", None],
            "protected_customer_order_count",
            None,
        ),
    ],
)
def test_partition_lists_are_ordered_validated_and_do_not_multiply_options(
    engine, field, value, output, expected
):
    item = option("one")
    target = item["predicted"] if field == "protected_customer_order_ids" else item
    target[field] = value
    c, _, _ = seed(engine, options=[item])
    result = partition_rows(engine, "SavedOptions", c)
    assert len(result) == 1
    assert result[0][output] == expected
    assert result[0]["response_cost"] == Decimal(0)
