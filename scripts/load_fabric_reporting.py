"""Guarded loader for the immutable traditional reporting dataset."""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal

from azure.core.exceptions import AzureError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from data.synthetic.reporting import (
    OperationalReportingDataset,
    build_operational_reporting_dataset,
)
from integrations.fabric.reporting_source import ensure_reporting_dataset
from services.persistence.fabric_sql import build_credential, build_fabric_engine


class LoaderVerificationError(RuntimeError):
    """The transaction committed, but independent readback did not verify."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="insert the immutable reporting dataset when it is absent",
    )
    return parser.parse_args(argv)


def _validate_target(settings: Settings) -> None:
    if settings.runtime_mode is not RuntimeMode.LIVE:
        raise SystemExit("loader requires live runtime")
    if settings.credential_mode != "azure_cli":
        raise SystemExit("loader requires an Azure CLI credential")
    if not settings.fabric_sql_server or not settings.fabric_sql_database:
        raise SystemExit("loader requires an explicit Fabric SQL target")


def verify_readback(engine: Engine, dataset: OperationalReportingDataset) -> None:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT d.dataset_id, d.effective_at, d.content_sha256, "
                    "d.is_synthetic, d.payload_json, "
                    "(SELECT COUNT(*) FROM reporting.operational_records r "
                    " WHERE r.dataset_id = d.dataset_id) AS row_count "
                    "FROM reporting.datasets d WHERE d.dataset_id = :dataset_id"
                ),
                {"dataset_id": dataset.dataset_id},
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise RuntimeError("committed reporting dataset was not found")
    effective_at = row["effective_at"]
    if (
        row["dataset_id"] != dataset.dataset_id
        or not isinstance(effective_at, datetime)
        or effective_at.tzinfo is None
        or effective_at.astimezone(UTC) != dataset.effective_at.astimezone(UTC)
        or not bool(row["is_synthetic"])
    ):
        raise RuntimeError("committed reporting dataset identity differs")
    payload_json = row["payload_json"]
    if (
        not isinstance(payload_json, str)
        or hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        != dataset.content_sha256
    ):
        raise RuntimeError("committed reporting dataset payload hash differs")
    if row["content_sha256"] != dataset.content_sha256:
        raise RuntimeError("committed reporting dataset hash differs")
    if payload_json != dataset.payload_json:
        raise RuntimeError("committed reporting dataset payload differs")
    if row["row_count"] != len(dataset.records):
        raise RuntimeError("committed reporting dataset row count differs")


def run(
    *,
    apply: bool,
    settings: Settings,
    engine: Engine | None = None,
) -> Literal["planned", "inserted", "unchanged"]:
    _validate_target(settings)
    dataset = build_operational_reporting_dataset()
    active_engine = engine
    credential = None
    owns_resources = active_engine is None
    try:
        if active_engine is None:
            credential = build_credential(settings)
            active_engine = build_fabric_engine(settings, credential)
        context = active_engine.begin() if apply else active_engine.connect()
        with context as connection:
            outcome = ensure_reporting_dataset(connection, dataset, apply=apply)
        if apply:
            try:
                verify_readback(active_engine, dataset)
            except Exception as error:
                raise LoaderVerificationError(
                    "reporting dataset transaction committed, but immutable readback failed"
                ) from error
        return outcome
    finally:
        if owns_resources:
            try:
                if active_engine is not None:
                    active_engine.dispose()
            finally:
                if credential is not None:
                    close = getattr(credential, "close", None)
                    if callable(close):
                        close()


def main() -> int:
    args = parse_args()
    try:
        outcome = run(
            apply=args.apply,
            settings=Settings(),  # pyright: ignore[reportCallIssue]
        )
    except SystemExit as error:
        print(f"Reporting dataset failed: {error}", file=sys.stderr)
        return 2
    except (
        AzureError,
        LoaderVerificationError,
        OSError,
        RuntimeError,
        SQLAlchemyError,
    ):
        print(
            "Reporting dataset failed: configuration, identity, or SQL operation failed",
            file=sys.stderr,
        )
        return 1
    print(f"Reporting dataset: {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
