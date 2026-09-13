"""Real SQL validation in the dedicated disposable reporting-test database.

The fixture is generated locally by the validated fictional dataset builder.
This module deliberately needs only SQLAlchemy/pytest on the isolated SQL host.
"""

import hashlib
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


def test_typed_reporting_rows_round_trip_on_actual_sql():
    url = os.environ.get("SUPPLY_RESPONSE_LOCAL_REPORTING_SQL_URL")
    fixture_path = os.environ.get("SUPPLY_RESPONSE_REPORTING_DATASET_FIXTURE")
    if not url or not fixture_path:
        pytest.skip(
            "dedicated disposable SQL URL and generated fictional fixture required"
        )
    engine = create_engine(url, hide_parameters=True)
    assert engine.url.host in {"127.0.0.1", "localhost"}
    assert re.fullmatch(
        r"supply_response_projection_test_run_[0-9a-f]{32}", engine.url.database or ""
    )
    payload = Path(fixture_path).read_text(encoding="utf-8")
    expected = json.loads(payload)
    assert expected["is_synthetic"] is True
    assert len(expected["records"]) >= 150
    source = (
        Path(__file__).resolve().parents[2] / "fabric/sql/003_reporting_dataset.sql"
    )
    batches = [
        b.strip() for b in re.split(r"(?im)^\s*GO\s*$", source.read_text()) if b.strip()
    ]
    try:
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM sys.tables WHERE is_ms_shipped=0")
                ).scalar_one()
                == 0
            )
        for _ in range(2):
            with engine.begin() as connection:
                for batch in batches:
                    connection.exec_driver_sql(batch)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO reporting.datasets(dataset_id,effective_at,content_sha256,is_synthetic,payload_json) VALUES (:id,CAST(:at AS datetimeoffset(6)),:hash,1,:payload)"
                ),
                {
                    "id": expected["dataset_id"],
                    "at": expected["effective_at"],
                    "hash": hashlib.sha256(payload.encode()).hexdigest(),
                    "payload": payload,
                },
            )
        with engine.connect() as connection:
            query = (
                source.parents[1] / "reporting/queries/OperationalRecords.sql"
            ).read_text()
            actual = connection.execute(text(query)).mappings().all()
            assert len(actual) == len(expected["records"])
            by_id = {r["record_id"]: r for r in actual}
            assert len(by_id) == len(actual)
            for record in expected["records"]:
                row = by_id[record["record_id"]]
                assert row["dataset_id"] == expected["dataset_id"]
                for key, value in record.items():
                    stored = row[key]
                    if isinstance(stored, Decimal):
                        assert stored == Decimal(value), (record["record_id"], key)
                    elif isinstance(stored, (datetime, date)):
                        assert stored.isoformat() == value, (record["record_id"], key)
                    else:
                        assert stored == value, (record["record_id"], key)
            stock = by_id["RL-INV-DEMO-CHI"]
            assert [
                stock[k]
                for k in (
                    "on_hand",
                    "quality_hold",
                    "protected_allocation",
                    "usable_inventory",
                )
            ] == [4500, 200, 300, 4000]
            assert by_id["RL-ALPHA-OPTIONAL-3000"][
                "incremental_cost_per_unit"
            ] == Decimal("7.50")
            assert by_id["RL-QUAL-BETA"]["audit_complete"] is False
    finally:
        engine.dispose()
