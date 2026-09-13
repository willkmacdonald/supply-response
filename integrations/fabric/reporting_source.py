"""Insert-only persistence for the isolated reporting dataset."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import Connection, DateTime, bindparam, text

from data.synthetic.reporting import OperationalReportingDataset


def _same_instant(actual: object, expected: datetime) -> bool:
    if not isinstance(actual, datetime) or actual.tzinfo is None:
        return False
    return actual.astimezone(UTC) == expected.astimezone(UTC)


def _matches(row: Mapping[Any, object], dataset: OperationalReportingDataset) -> bool:
    return (
        row["dataset_id"] == dataset.dataset_id
        and _same_instant(row["effective_at"], dataset.effective_at)
        and row["content_sha256"] == dataset.content_sha256
        and bool(row["is_synthetic"]) is True
        and row["payload_json"] == dataset.payload_json
    )


def ensure_reporting_dataset(
    connection: Connection,
    dataset: OperationalReportingDataset,
    *,
    apply: bool,
) -> Literal["planned", "inserted", "unchanged"]:
    lock_hint = " WITH (UPDLOCK, HOLDLOCK)" if apply else ""
    existing = (
        connection.execute(
            text(
                "SELECT dataset_id, effective_at, content_sha256, is_synthetic, payload_json "
                f"FROM reporting.datasets{lock_hint} WHERE dataset_id = :dataset_id"
            ),
            {"dataset_id": dataset.dataset_id},
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if not _matches(existing, dataset):
            raise RuntimeError("existing reporting dataset ID has different content")
        return "unchanged"
    if not apply:
        return "planned"
    statement = text(
        "INSERT INTO reporting.datasets "
        "(dataset_id, effective_at, content_sha256, is_synthetic, payload_json) VALUES "
        "(:dataset_id, :effective_at, :content_sha256, :is_synthetic, :payload_json)"
    ).bindparams(bindparam("effective_at", type_=DateTime(timezone=True)))
    connection.execute(
        statement,
        {
            "dataset_id": dataset.dataset_id,
            "effective_at": dataset.effective_at,
            "content_sha256": dataset.content_sha256,
            "is_synthetic": True,
            "payload_json": dataset.payload_json,
        },
    )
    return "inserted"
