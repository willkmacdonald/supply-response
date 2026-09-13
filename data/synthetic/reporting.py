"""Deterministic fictional context for traditional operational reporting."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from data.domain import FrozenModel, Money
from data.synthetic.rl001 import OperationalSnapshot

REPORTING_DATASET_ID = "TRADITIONAL-OPS-2026-09-V1"
RecordFamily = Literal[
    "inventory",
    "purchase",
    "shipment",
    "transfer",
    "qualification",
    "production_order",
    "customer_order",
]
DataOrigin = Literal["canonical_scenario", "fictional_reporting_context"]
RecordId = Annotated[str, Field(min_length=1, max_length=128)]
DisplayName = Annotated[str, Field(min_length=1, max_length=256)]
Status = Annotated[str, Field(min_length=1, max_length=64)]


class OperationalReportingRecord(FrozenModel):
    record_id: RecordId
    record_family: RecordFamily
    supplier_id: RecordId | None = None
    supplier_name: DisplayName | None = None
    part_id: RecordId | None = None
    part_name: DisplayName | None = None
    plant_id: RecordId | None = None
    plant_name: DisplayName | None = None
    source_plant_id: RecordId | None = None
    source_plant_name: DisplayName | None = None
    destination_plant_id: RecordId | None = None
    destination_plant_name: DisplayName | None = None
    customer_id: RecordId | None = None
    product_id: RecordId | None = None
    production_order_id: RecordId | None = None
    customer_order_id: RecordId | None = None
    quantity: int | None = Field(default=None, ge=0)
    on_hand: int | None = Field(default=None, ge=0)
    quality_hold: int | None = Field(default=None, ge=0)
    protected_allocation: int | None = Field(default=None, ge=0)
    usable_inventory: int | None = Field(default=None, ge=0)
    component_demand: int | None = Field(default=None, ge=0)
    due_date: date | None = None
    original_due_date: date | None = None
    dispatch_date: date | None = None
    arrival_date: date | None = None
    incremental_cost_per_unit: Money | None = Field(default=None, ge=0)
    line_revenue: Money | None = Field(default=None, ge=0)
    line_margin: Money | None = Field(default=None, ge=0)
    status: Status | None = None
    audit_complete: bool | None = None
    first_article_complete: bool | None = None
    expected_decision_date: date | None = None
    data_origin: DataOrigin

    @model_validator(mode="after")
    def validate_link_labels(self) -> OperationalReportingRecord:
        pairs = (
            (self.supplier_id, self.supplier_name, "supplier"),
            (self.part_id, self.part_name, "part"),
            (self.plant_id, self.plant_name, "plant"),
            (self.source_plant_id, self.source_plant_name, "source plant"),
            (
                self.destination_plant_id,
                self.destination_plant_name,
                "destination plant",
            ),
        )
        for identifier, name, label in pairs:
            if (identifier is None) != (name is None):
                raise ValueError(f"{label} ID and name must be supplied together")
        if self.record_family == "inventory" and self.usable_inventory != (
            self.on_hand or 0
        ) - (self.quality_hold or 0) - (self.protected_allocation or 0):
            raise ValueError("usable inventory must reconcile")
        return self


class OperationalReportingDataset(FrozenModel):
    dataset_id: str
    effective_at: datetime
    is_synthetic: Literal[True] = True
    records: tuple[OperationalReportingRecord, ...]
    payload_json: str
    content_sha256: str

    def calculate_content_sha256(self) -> str:
        return hashlib.sha256(self.payload_json.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def validate_envelope(self) -> OperationalReportingDataset:
        if len({record.record_id for record in self.records}) != len(self.records):
            raise ValueError("reporting record IDs must be unique")
        entity_names: dict[tuple[str, str], str] = {}
        for record in self.records:
            for kind, identifier, name in (
                ("supplier", record.supplier_id, record.supplier_name),
                ("part", record.part_id, record.part_name),
                ("plant", record.plant_id, record.plant_name),
                ("plant", record.source_plant_id, record.source_plant_name),
                (
                    "plant",
                    record.destination_plant_id,
                    record.destination_plant_name,
                ),
            ):
                if identifier is None or name is None:
                    continue
                key = (kind, identifier)
                previous = entity_names.setdefault(key, name)
                if previous != name:
                    raise ValueError(f"{kind} ID maps to multiple names")
        production = {
            record.production_order_id: record
            for record in self.records
            if record.record_family == "production_order"
        }
        for record in self.records:
            if record.record_family != "customer_order":
                continue
            linked = production.get(record.production_order_id)
            if (
                linked is None
                or linked.customer_order_id != record.customer_order_id
                or linked.quantity != record.quantity
                or linked.part_id != record.part_id
            ):
                raise ValueError("customer order has an inconsistent production link")
        expected = _canonical_json(
            _payload(self.dataset_id, self.effective_at, self.records)
        )
        if self.payload_json != expected:
            raise ValueError("payload JSON does not match the reporting records")
        if self.content_sha256 != self.calculate_content_sha256():
            raise ValueError("reporting content hash does not match payload JSON")
        return self


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _payload(
    dataset_id: str,
    effective_at: datetime,
    records: tuple[OperationalReportingRecord, ...],
) -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "effective_at": effective_at.isoformat(),
        "is_synthetic": True,
        "records": [record.model_dump(mode="json") for record in records],
    }


def _canonical_records(
    snapshot: OperationalSnapshot,
) -> list[OperationalReportingRecord]:
    plants = {"RL-PLANT-CHI": "Chicago", "RL-PLANT-DAL": "Dallas"}
    part_id = "RL-MAT-10247"
    part_name = "Component RL-MAT-10247"
    records = [
        OperationalReportingRecord(
            record_id=item.inventory_id,
            record_family="inventory",
            part_id=part_id,
            part_name=part_name,
            plant_id=item.plant_id,
            plant_name=plants[item.plant_id],
            on_hand=item.on_hand,
            quality_hold=item.quality_hold,
            protected_allocation=item.protected_allocation,
            usable_inventory=item.on_hand
            - item.quality_hold
            - item.protected_allocation,
            status="available",
            data_origin="canonical_scenario",
        )
        for item in snapshot.inventory_positions
    ]
    disruption = snapshot.disruption
    records.append(
        OperationalReportingRecord(
            record_id=disruption.po_line_id,
            record_family="purchase",
            supplier_id=disruption.supplier_id,
            supplier_name="RL-Supplier Alpha — Current supplier",
            part_id=part_id,
            part_name=part_name,
            plant_id=disruption.plant_id,
            plant_name=plants[disruption.plant_id],
            quantity=disruption.original_quantity,
            due_date=disruption.original_due_date,
            original_due_date=disruption.original_due_date,
            status="disrupted",
            data_origin="canonical_scenario",
        )
    )
    if snapshot.alpha_expedite is not None:
        receipt = snapshot.alpha_expedite
        records.append(
            OperationalReportingRecord(
                record_id=receipt.receipt_id,
                record_family="shipment",
                supplier_id=receipt.supplier_id,
                supplier_name="RL-Supplier Alpha — Current supplier",
                part_id=part_id,
                part_name=part_name,
                plant_id=receipt.plant_id,
                plant_name=plants[receipt.plant_id],
                quantity=receipt.quantity,
                arrival_date=receipt.due_date,
                incremental_cost_per_unit=receipt.incremental_cost_per_unit,
                status="proposed",
                data_origin="canonical_scenario",
            )
        )
    transfer = snapshot.transfer
    records.append(
        OperationalReportingRecord(
            record_id=transfer.transfer_id,
            record_family="transfer",
            part_id=part_id,
            part_name=part_name,
            source_plant_id=transfer.source_plant_id,
            source_plant_name=plants[transfer.source_plant_id],
            destination_plant_id=transfer.destination_plant_id,
            destination_plant_name=plants[transfer.destination_plant_id],
            quantity=transfer.quantity,
            dispatch_date=transfer.dispatch_date,
            arrival_date=transfer.arrival_date,
            incremental_cost_per_unit=transfer.incremental_cost_per_unit,
            status="proposed",
            data_origin="canonical_scenario",
        )
    )
    qualification = snapshot.beta_qualification
    records.append(
        OperationalReportingRecord(
            record_id=qualification.qualification_id,
            record_family="qualification",
            supplier_id=qualification.supplier_id,
            supplier_name="RL-Supplier Beta — Alternate supplier",
            part_id=part_id,
            part_name=part_name,
            status=qualification.status.value,
            audit_complete=qualification.audit_complete,
            first_article_complete=qualification.first_article_complete,
            expected_decision_date=qualification.expected_decision_date,
            data_origin="canonical_scenario",
        )
    )
    for order in snapshot.production_orders:
        records.append(
            OperationalReportingRecord(
                record_id=order.production_order_id,
                record_family="production_order",
                part_id=part_id,
                part_name=part_name,
                plant_id=order.plant_id,
                plant_name=plants[order.plant_id],
                product_id=order.product_id,
                production_order_id=order.production_order_id,
                customer_order_id=order.customer_order_id,
                quantity=order.quantity,
                component_demand=order.component_demand,
                due_date=order.due_date,
                line_revenue=order.customer_revenue,
                line_margin=order.customer_margin,
                status=order.status,
                data_origin="canonical_scenario",
            )
        )
    for order in snapshot.customer_orders:
        records.append(
            OperationalReportingRecord(
                record_id=order.customer_order_line_id,
                record_family="customer_order",
                part_id=part_id,
                part_name=part_name,
                plant_id=order.plant_id,
                plant_name=plants[order.plant_id],
                customer_id=order.customer_id,
                product_id=order.product_id,
                production_order_id=order.production_order_id,
                customer_order_id=order.customer_order_line_id,
                quantity=order.quantity,
                due_date=order.due_date,
                line_revenue=order.unit_revenue * order.quantity,
                line_margin=order.unit_margin * order.quantity,
                status="open",
                data_origin="canonical_scenario",
            )
        )
    return records


def _background_records(effective: datetime) -> list[OperationalReportingRecord]:
    plants = [
        ("RPT-PLANT-ATL", "Atlanta"),
        ("RPT-PLANT-DEN", "Denver"),
        ("RPT-PLANT-PHX", "Phoenix"),
        ("RPT-PLANT-SEA", "Seattle"),
        ("RL-PLANT-CHI", "Chicago"),
        ("RL-PLANT-DAL", "Dallas"),
    ]
    suppliers = [
        (f"RPT-SUP-{i:02d}", f"Fictional Supplier {i:02d}") for i in range(1, 7)
    ]
    parts = [(f"RPT-MAT-{i:05d}", f"Fictional component {i:02d}") for i in range(1, 13)]
    day = effective.date()
    records: list[OperationalReportingRecord] = []
    for pidx, (part_id, part_name) in enumerate(parts):
        for lidx, (plant_id, plant_name) in enumerate(plants):
            on_hand = 900 + pidx * 83 + lidx * 47
            hold = (pidx + lidx) % 5 * 10
            allocation = (pidx * 2 + lidx) % 7 * 15
            records.append(
                OperationalReportingRecord(
                    record_id=f"RPT-INV-{pidx + 1:02d}-{lidx + 1:02d}",
                    record_family="inventory",
                    part_id=part_id,
                    part_name=part_name,
                    plant_id=plant_id,
                    plant_name=plant_name,
                    on_hand=on_hand,
                    quality_hold=hold,
                    protected_allocation=allocation,
                    usable_inventory=on_hand - hold - allocation,
                    status="available" if hold == 0 else "hold present",
                    data_origin="fictional_reporting_context",
                )
            )
        supplier_id, supplier_name = suppliers[pidx % len(suppliers)]
        plant_id, plant_name = plants[pidx % len(plants)]
        quantity = 500 + pidx * 75
        records.extend(
            (
                OperationalReportingRecord(
                    record_id=f"RPT-PO-{pidx + 1:04d}",
                    record_family="purchase",
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    part_id=part_id,
                    part_name=part_name,
                    plant_id=plant_id,
                    plant_name=plant_name,
                    quantity=quantity,
                    due_date=day + timedelta(days=2 + pidx),
                    original_due_date=day + timedelta(days=1 + pidx),
                    status="confirmed" if pidx % 3 else "late",
                    data_origin="fictional_reporting_context",
                ),
                OperationalReportingRecord(
                    record_id=f"RPT-SHIP-{pidx + 1:04d}",
                    record_family="shipment",
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    part_id=part_id,
                    part_name=part_name,
                    plant_id=plant_id,
                    plant_name=plant_name,
                    quantity=quantity - 50,
                    dispatch_date=day - timedelta(days=pidx % 3),
                    arrival_date=day + timedelta(days=1 + pidx),
                    incremental_cost_per_unit=Decimal("0.75") + Decimal(pidx) / 10,
                    status="in_transit" if pidx % 4 else "delayed",
                    data_origin="fictional_reporting_context",
                ),
                OperationalReportingRecord(
                    record_id=f"RPT-XFER-{pidx + 1:04d}",
                    record_family="transfer",
                    part_id=part_id,
                    part_name=part_name,
                    source_plant_id=plants[pidx % 4][0],
                    source_plant_name=plants[pidx % 4][1],
                    destination_plant_id=plants[(pidx + 1) % 4][0],
                    destination_plant_name=plants[(pidx + 1) % 4][1],
                    quantity=120 + pidx * 10,
                    dispatch_date=day + timedelta(days=pidx % 4),
                    arrival_date=day + timedelta(days=pidx % 4 + 2),
                    incremental_cost_per_unit=Decimal("1.25"),
                    status="planned",
                    data_origin="fictional_reporting_context",
                ),
                OperationalReportingRecord(
                    record_id=f"RPT-QUAL-{pidx + 1:04d}",
                    record_family="qualification",
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    part_id=part_id,
                    part_name=part_name,
                    status=("approved" if pidx % 3 else "pending"),
                    audit_complete=pidx % 3 != 0,
                    first_article_complete=pidx % 2 == 0,
                    expected_decision_date=day + timedelta(days=10 + pidx),
                    data_origin="fictional_reporting_context",
                ),
                OperationalReportingRecord(
                    record_id=f"RPT-MO-{pidx + 1:04d}",
                    record_family="production_order",
                    part_id=part_id,
                    part_name=part_name,
                    plant_id=plant_id,
                    plant_name=plant_name,
                    product_id=f"RPT-PROD-{pidx % 6 + 1:03d}",
                    production_order_id=f"RPT-MO-{pidx + 1:04d}",
                    customer_order_id=f"RPT-CO-{pidx + 1:04d}",
                    quantity=200 + pidx * 20,
                    component_demand=400 + pidx * 40,
                    due_date=day + timedelta(days=4 + pidx),
                    status="released" if pidx % 2 else "open",
                    data_origin="fictional_reporting_context",
                ),
                OperationalReportingRecord(
                    record_id=f"RPT-CO-{pidx + 1:04d}",
                    record_family="customer_order",
                    part_id=part_id,
                    part_name=part_name,
                    plant_id=plant_id,
                    plant_name=plant_name,
                    customer_id=f"RPT-CUST-{pidx % 8 + 1:03d}",
                    product_id=f"RPT-PROD-{pidx % 6 + 1:03d}",
                    production_order_id=f"RPT-MO-{pidx + 1:04d}",
                    customer_order_id=f"RPT-CO-{pidx + 1:04d}",
                    quantity=200 + pidx * 20,
                    due_date=day + timedelta(days=4 + pidx),
                    line_revenue=Decimal(30000 + pidx * 3500),
                    line_margin=Decimal(9000 + pidx * 900),
                    status="open",
                    data_origin="fictional_reporting_context",
                ),
                OperationalReportingRecord(
                    record_id=f"RPT-PO-B-{pidx + 1:04d}",
                    record_family="purchase",
                    supplier_id=suppliers[(pidx + 1) % len(suppliers)][0],
                    supplier_name=suppliers[(pidx + 1) % len(suppliers)][1],
                    part_id=part_id,
                    part_name=part_name,
                    plant_id=plants[(pidx + 2) % 4][0],
                    plant_name=plants[(pidx + 2) % 4][1],
                    quantity=quantity + 125,
                    due_date=day + timedelta(days=9 + pidx),
                    original_due_date=day + timedelta(days=9 + pidx),
                    status="confirmed",
                    data_origin="fictional_reporting_context",
                ),
                OperationalReportingRecord(
                    record_id=f"RPT-SHIP-B-{pidx + 1:04d}",
                    record_family="shipment",
                    supplier_id=suppliers[(pidx + 1) % len(suppliers)][0],
                    supplier_name=suppliers[(pidx + 1) % len(suppliers)][1],
                    part_id=part_id,
                    part_name=part_name,
                    plant_id=plants[(pidx + 2) % 4][0],
                    plant_name=plants[(pidx + 2) % 4][1],
                    quantity=quantity + 75,
                    dispatch_date=day + timedelta(days=3 + pidx),
                    arrival_date=day + timedelta(days=6 + pidx),
                    incremental_cost_per_unit=Decimal("0.50"),
                    status="planned",
                    data_origin="fictional_reporting_context",
                ),
            )
        )
    return records


def build_operational_reporting_dataset() -> OperationalReportingDataset:
    snapshot = OperationalSnapshot.rl001()
    records = tuple(
        _canonical_records(snapshot)
        + _background_records(snapshot.scenario_effective_time)
    )
    payload_json = _canonical_json(
        _payload(REPORTING_DATASET_ID, snapshot.scenario_effective_time, records)
    )
    return OperationalReportingDataset(
        dataset_id=REPORTING_DATASET_ID,
        effective_at=snapshot.scenario_effective_time,
        records=records,
        payload_json=payload_json,
        content_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
    )
