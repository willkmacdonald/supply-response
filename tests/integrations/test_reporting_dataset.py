from __future__ import annotations

import hashlib
import json
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy import Connection, Engine

from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from data.synthetic.reporting import (
    REPORTING_DATASET_ID,
    OperationalReportingDataset,
    build_operational_reporting_dataset,
)
from data.synthetic.rl001 import OperationalSnapshot
from integrations.fabric.reporting_source import ensure_reporting_dataset
from scripts import load_fabric_reporting

ROOT = Path(__file__).resolve().parents[2]
FIELDS = {
    "record_id",
    "record_family",
    "supplier_id",
    "supplier_name",
    "part_id",
    "part_name",
    "plant_id",
    "plant_name",
    "source_plant_id",
    "source_plant_name",
    "destination_plant_id",
    "destination_plant_name",
    "customer_id",
    "product_id",
    "production_order_id",
    "customer_order_id",
    "quantity",
    "on_hand",
    "quality_hold",
    "protected_allocation",
    "usable_inventory",
    "component_demand",
    "due_date",
    "original_due_date",
    "dispatch_date",
    "arrival_date",
    "incremental_cost_per_unit",
    "line_revenue",
    "line_margin",
    "status",
    "audit_complete",
    "first_article_complete",
    "expected_decision_date",
    "data_origin",
}


def _dataset() -> OperationalReportingDataset:
    return build_operational_reporting_dataset()


def test_dataset_is_deterministic_frozen_and_canonically_hashed() -> None:
    first = _dataset()
    second = _dataset()

    assert first == second
    assert first.dataset_id == REPORTING_DATASET_ID
    assert first.content_sha256 == second.content_sha256
    assert json.loads(first.payload_json)["dataset_id"] == first.dataset_id
    assert first.content_sha256 == first.calculate_content_sha256()
    with pytest.raises(ValidationError):
        first.dataset_id = "changed"  # type: ignore[misc]


def test_dataset_has_one_flat_varied_operational_contract() -> None:
    dataset = _dataset()
    families = Counter(record.record_family for record in dataset.records)

    assert len(dataset.records) >= 150
    assert len({record.record_id for record in dataset.records}) == len(dataset.records)
    assert set(families) == {
        "inventory",
        "purchase",
        "shipment",
        "transfer",
        "qualification",
        "production_order",
        "customer_order",
    }
    assert all(count >= 12 for count in families.values())
    assert set(type(dataset.records[0]).model_fields) == FIELDS
    assert len({record.part_id for record in dataset.records if record.part_id}) >= 12
    plants = {record.plant_id for record in dataset.records if record.plant_id}
    plants |= {
        record.source_plant_id for record in dataset.records if record.source_plant_id
    }
    plants |= {
        record.destination_plant_id
        for record in dataset.records
        if record.destination_plant_id
    }
    assert len(plants) >= 4
    suppliers = {
        (record.supplier_id, record.supplier_name)
        for record in dataset.records
        if record.supplier_id and record.data_origin == "fictional_reporting_context"
    }
    assert len(suppliers) >= 6
    assert all(name and "Fictional" in name for _, name in suppliers)
    assert {record.data_origin for record in dataset.records} == {
        "canonical_scenario",
        "fictional_reporting_context",
    }


def test_canonical_rows_derive_exact_rl001_values_without_competing_context() -> None:
    dataset = _dataset()
    snapshot = OperationalSnapshot.rl001()
    canonical = {
        record.record_id: record
        for record in dataset.records
        if record.data_origin == "canonical_scenario"
    }

    chicago = canonical["RL-INV-DEMO-CHI"]
    assert (chicago.on_hand, chicago.quality_hold, chicago.protected_allocation) == (
        4500,
        200,
        300,
    )
    assert chicago.usable_inventory == snapshot.usable_inventory(
        "RL-MAT-10247", "RL-PLANT-CHI"
    )
    assert canonical[snapshot.disruption.po_line_id].quantity == 8000
    assert canonical[snapshot.disruption.po_line_id].status == "disrupted"
    assert canonical[snapshot.alpha_expedite.receipt_id].status == "proposed"
    assert canonical[snapshot.transfer.transfer_id].status == "proposed"
    assert canonical[snapshot.beta_qualification.qualification_id].status == "pending"
    assert canonical[snapshot.disruption.po_line_id].supplier_name == (
        "RL-Supplier Alpha — Current supplier"
    )
    assert canonical[snapshot.beta_qualification.qualification_id].supplier_name == (
        "RL-Supplier Beta — Alternate supplier"
    )
    assert chicago.part_name == "Component RL-MAT-10247"
    assert not [
        record
        for record in dataset.records
        if record.data_origin == "fictional_reporting_context"
        and record.part_id == "RL-MAT-10247"
        and (
            record.component_demand is not None
            or record.plant_id in {"RL-PLANT-CHI", "RL-PLANT-DAL"}
        )
    ]
    assert {
        record.plant_id
        for record in dataset.records
        if record.data_origin == "fictional_reporting_context"
        and record.record_family == "inventory"
        and record.plant_id in {"RL-PLANT-CHI", "RL-PLANT-DAL"}
        and record.part_id != "RL-MAT-10247"
    } == {"RL-PLANT-CHI", "RL-PLANT-DAL"}


def test_dataset_validator_rejects_inconsistent_entity_links() -> None:
    dataset = _dataset()
    records = list(dataset.records)
    records[11] = records[11].model_copy(update={"plant_name": "Wrong plant"})
    payload = json.loads(dataset.payload_json)
    payload["records"] = [record.model_dump(mode="json") for record in records]
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    with pytest.raises(ValidationError, match="plant ID maps to multiple names"):
        OperationalReportingDataset(
            dataset_id=dataset.dataset_id,
            effective_at=dataset.effective_at,
            records=tuple(records),
            payload_json=payload_json,
            content_sha256=hashlib.sha256(payload_json.encode()).hexdigest(),
        )


def test_flat_record_rejects_oversized_ids() -> None:
    record = _dataset().records[0]
    with pytest.raises(ValidationError):
        type(record).model_validate({**record.model_dump(), "record_id": "x" * 129})


def test_qualification_cannot_be_approved_before_required_checks() -> None:
    qualification = next(
        record
        for record in _dataset().records
        if record.record_family == "qualification"
    )
    with pytest.raises(ValidationError, match="approved qualification"):
        type(qualification).model_validate(
            {
                **qualification.model_dump(),
                "status": "approved",
                "audit_complete": True,
                "first_article_complete": False,
            }
        )

    approved = [
        record
        for record in _dataset().records
        if record.record_family == "qualification" and record.status == "approved"
    ]
    assert approved
    assert all(
        record.audit_complete is True and record.first_article_complete is True
        for record in approved
    )


def test_production_and_customer_order_links_reconcile() -> None:
    records = _dataset().records
    production = {
        record.production_order_id: record
        for record in records
        if record.record_family == "production_order"
    }
    customers = [
        record for record in records if record.record_family == "customer_order"
    ]
    assert all(record.production_order_id in production for record in customers)
    assert all(
        production[record.production_order_id].customer_order_id
        == record.customer_order_id
        and production[record.production_order_id].quantity == record.quantity
        and production[record.production_order_id].part_id == record.part_id
        for record in customers
    )


class _Mappings:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row

    def mappings(self) -> _Mappings:
        return self

    def one_or_none(self) -> dict[str, object] | None:
        return self.row


class _Connection:
    def __init__(self, row: dict[str, object] | None = None) -> None:
        self.row = row
        self.statements: list[str] = []

    def execute(self, statement: Any, parameters: dict[str, object]) -> _Mappings:
        self.statements.append(str(statement))
        return _Mappings(self.row)


def test_reporting_insert_is_planned_dry_run_and_rejects_content_conflict() -> None:
    dataset = _dataset()
    absent = _Connection()
    assert (
        ensure_reporting_dataset(cast(Connection, absent), dataset, apply=False)
        == "planned"
    )
    assert not any("INSERT" in statement for statement in absent.statements)

    conflict = _Connection(
        {
            "dataset_id": dataset.dataset_id,
            "effective_at": dataset.effective_at,
            "content_sha256": "0" * 64,
            "is_synthetic": True,
            "payload_json": dataset.payload_json,
        }
    )
    with pytest.raises(RuntimeError, match="different content"):
        ensure_reporting_dataset(cast(Connection, conflict), dataset, apply=True)


class _Engine:
    def __init__(self) -> None:
        self.connection = object()
        self.begin_calls = 0
        self.connect_calls = 0

    def begin(self):
        self.begin_calls += 1
        return nullcontext(self.connection)

    def connect(self):
        self.connect_calls += 1
        return nullcontext(self.connection)


class _ReadbackEngine:
    def __init__(self, row: dict[str, object]) -> None:
        self.connection = _Connection(row)

    def connect(self):
        return nullcontext(self.connection)


def test_readback_recomputes_payload_hash_and_counts_typed_view_rows() -> None:
    dataset = _dataset()
    changed = dataset.payload_json.replace("Atlanta", "Atlantx", 1)
    engine = _ReadbackEngine(
        {
            "dataset_id": dataset.dataset_id,
            "effective_at": dataset.effective_at,
            "content_sha256": dataset.content_sha256,
            "is_synthetic": True,
            "payload_json": changed,
            "row_count": len(dataset.records),
        }
    )
    with pytest.raises(RuntimeError, match="payload hash differs"):
        load_fabric_reporting.verify_readback(cast(Engine, engine), dataset)
    statement = engine.connection.statements[0]
    assert "reporting.operational_records" in statement


def _settings() -> Settings:
    return Settings(
        runtime_mode=RuntimeMode.LIVE,
        allowed_tenant_id="11111111-1111-4111-8111-111111111111",
        fabric_sql_server="demo.database.fabric.microsoft.com,1433",
        fabric_sql_database="SupplyResponseDemo-id",
        credential_mode="azure_cli",
    )


def test_loader_defaults_to_read_only_and_apply_verifies_after_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert load_fabric_reporting.parse_args([]).apply is False
    engine = _Engine()
    events: list[str] = []
    monkeypatch.setattr(
        load_fabric_reporting,
        "ensure_reporting_dataset",
        lambda connection, dataset, *, apply: (
            events.append(f"ensure:{apply}") or ("inserted" if apply else "planned")
        ),
    )
    monkeypatch.setattr(
        load_fabric_reporting,
        "verify_readback",
        lambda active_engine, dataset: events.append("verify"),
    )

    assert (
        load_fabric_reporting.run(
            apply=False, settings=_settings(), engine=cast(Engine, engine)
        )
        == "planned"
    )
    assert engine.connect_calls == 1 and engine.begin_calls == 0
    assert (
        load_fabric_reporting.run(
            apply=True, settings=_settings(), engine=cast(Engine, engine)
        )
        == "inserted"
    )
    assert events == ["ensure:False", "ensure:True", "verify"]
    assert engine.begin_calls == 1


def test_loader_main_redacts_validation_error_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "dummy-secret-that-must-never-appear"

    def invalid_settings() -> Settings:
        raise ValueError(f"invalid settings input_value={secret}")

    monkeypatch.setattr(load_fabric_reporting, "Settings", invalid_settings)
    monkeypatch.setattr("sys.argv", ["load_fabric_reporting.py"])

    assert load_fabric_reporting.main() == 1
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
    assert len(captured.err) < 200


def test_reporting_sql_is_isolated_typed_explicit_and_version_scoped() -> None:
    schema = (ROOT / "fabric/sql/003_reporting_dataset.sql").read_text()
    query = (ROOT / "fabric/reporting/queries/OperationalRecords.sql").read_text()
    normalized = " ".join(schema.lower().split())

    assert "create table reporting.datasets" in normalized
    assert "primary key" in normalized
    assert "check (is_synthetic = 1)" in normalized
    assert "isjson(payload_json)" in normalized
    assert "create or alter view reporting.operational_records" in normalized
    assert "cross apply openjson" in normalized
    assert "j.[type] = 5" in normalized
    assert "len(json_value(j.[value], '$.record_id')) between 1 and 128" in normalized
    assert "r.quantity is null or r.quantity >= 0" in normalized
    assert "app.live_operational_sources" not in normalized
    assert "app.schema_version" not in normalized
    assert "latest" not in query.lower()
    assert "select *" not in query.lower()
    for field in ("dataset_id", "effective_at", *sorted(FIELDS)):
        assert field in query
