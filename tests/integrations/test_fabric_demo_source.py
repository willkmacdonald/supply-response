from dataclasses import replace
from datetime import UTC, timedelta

import pytest
from sqlalchemy import DateTime
from sqlalchemy.dialects.mssql.pyodbc import MSDialect_pyodbc

from data.domain import RuntimeMode
from data.domain.evidence import AuthorityScope, EvidenceSourceSystem
from data.synthetic.rl001 import SCENARIO_EFFECTIVE_TIME
from integrations.fabric.demo_source import (
    LiveOperationalSourceBundle,
    build_rl001_live_source,
    ensure_rl001_live_source,
)


class _MappingsResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def one_or_none(self):
        return self._row


class FakeConnection:
    def __init__(self, row=None):
        self.row = row
        self.inserts = []
        self.statements = []
        self.statement_objects = []

    def execute(self, statement, parameters=None):
        sql = str(statement).strip().upper()
        self.statements.append(sql)
        self.statement_objects.append(statement)
        if sql.startswith("SELECT"):
            return _MappingsResult(self.row)
        if sql.startswith("INSERT"):
            self.inserts.append(dict(parameters or {}))
            return _MappingsResult(None)
        raise AssertionError(f"Unexpected SQL: {sql}")


def _row(bundle):
    return {
        "source_snapshot_id": bundle.source_snapshot_id,
        "template_id": bundle.template_id,
        "effective_at": bundle.effective_at,
        "is_verified": bundle.is_verified,
        "snapshot_payload_json": bundle.snapshot_payload_json,
        "evidence_payload_json": bundle.evidence_payload_json,
    }


def test_builds_the_exact_live_fabric_rl001_bundle():
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )

    assert bundle.source_snapshot_id == "RL-001-OPERATIONAL-V1"
    assert bundle.template_id == "RL-001"
    assert bundle.effective_at == SCENARIO_EFFECTIVE_TIME
    assert bundle.is_verified is True
    snapshot = bundle.snapshot()
    assert snapshot.runtime_mode is RuntimeMode.LIVE
    assert snapshot.scenario_effective_time == SCENARIO_EFFECTIVE_TIME
    assert snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-CHI") == 4000
    assert snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-DAL") == 1500
    evidence = bundle.evidence()
    assert {item.evidence_id for item in evidence} == {
        "RL-ALPHA-OPTIONAL-3000",
        "RL-TRANSFER-DAL-CHI-1500",
        "RL-QUALITY-001",
    }
    assert all(item.source_system is EvidenceSourceSystem.FABRIC for item in evidence)
    assert all(item.runtime_mode is RuntimeMode.LIVE for item in evidence)
    assert all(item.synthetic is False for item in evidence)
    assert all(item.source_timestamp == SCENARIO_EFFECTIVE_TIME for item in evidence)
    assert all(item.effective_at == SCENARIO_EFFECTIVE_TIME for item in evidence)
    assert all(
        item.expires_at == SCENARIO_EFFECTIVE_TIME + timedelta(days=1)
        for item in evidence
    )
    scopes = {scope for item in evidence for scope in item.authority_scope}
    assert scopes == {
        AuthorityScope.OPERATIONAL_QUANTITY,
        AuthorityScope.OPERATIONAL_DATE,
        AuthorityScope.QUALIFICATION_STATE,
    }


def test_dry_run_plans_without_inserting():
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    connection = FakeConnection()

    assert ensure_rl001_live_source(connection, bundle, apply=False) == "planned"
    assert connection.inserts == []


def test_apply_inserts_once_and_exact_repeat_is_unchanged():
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    connection = FakeConnection()

    assert ensure_rl001_live_source(connection, bundle, apply=True) == "inserted"
    assert connection.inserts == [_row(bundle)]
    connection.row = _row(bundle)
    assert ensure_rl001_live_source(connection, bundle, apply=True) == "unchanged"
    assert connection.inserts == [_row(bundle)]


def test_insert_datetimeoffset_bind_preserves_the_source_offset():
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    connection = FakeConnection()

    ensure_rl001_live_source(connection, bundle, apply=True)

    effective_at_bind = connection.statement_objects[1]._bindparams["effective_at"]
    assert isinstance(effective_at_bind.type, DateTime)
    assert effective_at_bind.type.timezone is True
    processor = effective_at_bind.type._cached_bind_processor(MSDialect_pyodbc())
    processed = processor(bundle.effective_at) if processor else bundle.effective_at
    assert isinstance(processed, str)
    assert processed.endswith("-05:00")


def test_apply_locks_the_source_key_before_checking_for_an_existing_row():
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    connection = FakeConnection()

    ensure_rl001_live_source(connection, bundle, apply=True)

    assert "WITH (UPDLOCK, HOLDLOCK)" in connection.statements[0]


def test_datetimeoffset_returned_in_utc_matches_the_same_instant():
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    existing = _row(bundle)
    existing["effective_at"] = bundle.effective_at.astimezone(UTC)
    connection = FakeConnection(existing)

    assert ensure_rl001_live_source(connection, bundle, apply=True) == "unchanged"
    assert connection.inserts == []


def test_mismatched_existing_source_fails_without_mutation():
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    existing = _row(bundle)
    existing["snapshot_payload_json"] = "{}"
    connection = FakeConnection(existing)

    with pytest.raises(RuntimeError, match="differs from the canonical bundle"):
        ensure_rl001_live_source(connection, bundle, apply=True)

    assert connection.inserts == []


@pytest.mark.parametrize(
    "bundle",
    [
        LiveOperationalSourceBundle(
            source_snapshot_id="RL-001-OPERATIONAL-V1",
            template_id="RL-001",
            effective_at=SCENARIO_EFFECTIVE_TIME,
            is_verified=True,
            snapshot_payload_json="{}",
            evidence_payload_json="[]",
        ),
        replace(
            build_rl001_live_source(
                "https://app.powerbi.com/groups/demo/reports/report"
            ),
            source_snapshot_id="RL-001-OPERATIONAL-V2",
        ),
    ],
)
def test_manually_constructed_or_modified_bundle_is_rejected_before_sql(bundle):
    connection = FakeConnection()

    with pytest.raises(ValueError, match="canonical RL-001"):
        ensure_rl001_live_source(connection, bundle, apply=True)

    assert connection.statements == []


def test_naive_datetimeoffset_from_driver_is_rejected_as_ambiguous():
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    existing = _row(bundle)
    existing["effective_at"] = bundle.effective_at.replace(tzinfo=None)
    connection = FakeConnection(existing)

    with pytest.raises(RuntimeError, match="timezone-aware"):
        ensure_rl001_live_source(connection, bundle, apply=True)

    assert connection.inserts == []
