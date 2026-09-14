"""Additive approval upgrade proof, only on a fresh disposable localhost SQL DB."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from integrations.fabric.schema import apply_sql_script, split_go_batches


def test_approval_upgrade_preserves_legacy_data_and_enforces_new_constraints():
    raw = os.environ.get("SUPPLY_RESPONSE_LOCAL_REPORTING_SQL_URL")
    if not raw:
        pytest.skip("isolated localhost SQL execution gate not configured")
    url = make_url(raw)
    assert url.drivername == "mssql+pyodbc"
    assert url.host in {"localhost", "127.0.0.1", "::1"}
    assert (url.database or "").startswith("supply_response_projection_test_")
    assert not {key.lower() for key in url.query} & {"odbc_connect", "server"}
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM sys.tables")) == 0
        script = Path("fabric/sql/001_operational_schema.sql").read_text()
        # The additive Finance batches are omitted to recreate the deployed shape.
        additions = (
            "finance_review_revisions",
            "case_proposal_selections",
            "proposal_generation",
            "current_selection_id",
        )
        legacy = "\nGO\n".join(
            batch
            for batch in split_go_batches(script)
            if not any(name in batch for name in additions)
        )
        apply_sql_script(engine, legacy)
        with engine.begin() as connection:
            connection.exec_driver_sql("""
                UPDATE app.schema_version SET schema_version=12;
                INSERT app.case_instances
                  (case_id,template_id,purpose,runtime_mode,status,scenario_effective_time,payload_json)
                VALUES ('legacy','RL-001','showcase','live','open',SYSDATETIMEOFFSET(),'{"legacy":true}');
                INSERT app.case_projection
                  (case_id,purpose,runtime_mode,status,scenario_effective_time,payload_json)
                VALUES ('legacy','showcase','live','open',SYSDATETIMEOFFSET(),'{"legacy":true}');
                INSERT app.analysis_versions
                  (analysis_id,case_id,material_hash,runtime_mode,analysis_started_at,
                   retrieval_window_ends_at,created_at,payload_json)
                VALUES ('analysis','legacy','hash','live',SYSDATETIMEOFFSET(),
                        SYSDATETIMEOFFSET(),SYSDATETIMEOFFSET(),'{"saved":true}');
            """)
        apply_sql_script(engine, script)
        apply_sql_script(engine, script)
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT payload_json,proposal_generation,current_selection_id FROM app.case_projection"
            ).one() == ('{"legacy":true}', 0, None)
            assert (
                connection.scalar(
                    text("SELECT payload_json FROM app.analysis_versions")
                )
                == '{"saved":true}'
            )
            assert (
                connection.scalar(text("SELECT schema_version FROM app.schema_version"))
                == 12
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM sys.tables WHERE name IN ('finance_review_revisions','case_proposal_selections')"
                    )
                )
                == 2
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM sys.foreign_keys WHERE is_disabled=1 OR is_not_trusted=1"
                    )
                )
                == 0
            )

        # SQL Server must allow multiple non-Finance selections (filtered unique index).
        selection_sql = text("""
            INSERT app.case_proposal_selections
              (selection_id,case_id,analysis_id,analysis_material_hash,workflow_version,
               finance_review_id,finance_review_revision,expected_generation,
               idempotency_key,request_fingerprint,submitted_at,payload_json)
            VALUES (:id,'legacy','analysis','hash','independent-finance-v1',
                    :review,:revision,0,:id,'fingerprint',SYSDATETIMEOFFSET(),'{}')
        """)
        with engine.begin() as connection:
            for selection_id in ("low-cost-1", "low-cost-2"):
                connection.execute(
                    selection_sql,
                    {"id": selection_id, "review": None, "revision": None},
                )
            connection.exec_driver_sql("""
                INSERT app.finance_review_revisions
                  (review_id,revision,case_id,analysis_id,analysis_material_hash,option_id,
                   status,idempotency_key,request_fingerprint,recorded_at,payload_json)
                VALUES ('review',1,'legacy','analysis','hash','option','pending',
                        'review-key','fingerprint',SYSDATETIMEOFFSET(),'{}');
            """)
            connection.execute(
                selection_sql, {"id": "high-cost", "review": "review", "revision": 1}
            )
            connection.exec_driver_sql(
                "UPDATE app.case_projection SET current_selection_id='high-cost',proposal_generation=1"
            )
        for parameters in (
            {"id": "duplicate-review", "review": "review", "revision": 1},
            {"id": "missing-review", "review": "absent", "revision": 1},
            {"id": "invalid-pair", "review": "review", "revision": None},
        ):
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(selection_sql, parameters)
        apply_sql_script(engine, script)
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT current_selection_id,proposal_generation,payload_json FROM app.case_projection"
            ).one() == ("high-cost", 1, '{"legacy":true}')
            assert (
                connection.scalar(
                    text("SELECT COUNT(*) FROM app.case_proposal_selections")
                )
                == 3
            )
    finally:
        engine.dispose()
