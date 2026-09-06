"""Guarded local loader for the canonical Fabric RL-001 source."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from typing import Literal

from azure.core.exceptions import AzureError
from pydantic import ValidationError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from apps.api.app.settings import Settings
from data.domain import CasePurpose, RuntimeMode
from integrations.fabric.demo_source import (
    LiveOperationalSourceBundle,
    build_rl001_live_source,
    ensure_rl001_live_source,
)
from integrations.fabric.operational import FabricLiveOperationalDataPort
from services.persistence.fabric_sql import build_credential, build_fabric_engine


class LoaderVerificationError(RuntimeError):
    """The write committed, but its independent readback did not verify."""


def _retrieve(engine: Engine):
    return asyncio.run(
        FabricLiveOperationalDataPort(engine).retrieve(
            case_id="RL-CASE-LOADER-VERIFY",
            purpose=CasePurpose.SHOWCASE,
            analysis_id="RL-ANALYSIS-LOADER-VERIFY",
            retrieved_at=datetime.now(UTC),
        )
    )


def verify_readback(engine: Engine, bundle: LiveOperationalSourceBundle) -> None:
    retrieved = _retrieve(engine)
    if retrieved.source_snapshot_id != bundle.source_snapshot_id:
        raise RuntimeError("Fabric readback returned the wrong source snapshot")

    expected_snapshot = bundle.snapshot().model_copy(
        update={"case_id": retrieved.case.case_id, "runtime_mode": RuntimeMode.LIVE}
    )
    if retrieved.snapshot != expected_snapshot:
        raise RuntimeError("Fabric readback returned a different operational snapshot")

    expected_evidence = tuple(
        item.model_copy(
            update={
                "case_id": retrieved.case.case_id,
                "retrieved_for_analysis_id": "RL-ANALYSIS-LOADER-VERIFY",
                "retrieved_at": retrieved.retrieved_at,
                "runtime_mode": RuntimeMode.LIVE,
            }
        )
        for item in bundle.evidence()
    )
    if retrieved.evidence != expected_evidence:
        raise RuntimeError("Fabric readback evidence does not match RL-001")

    with engine.connect() as connection:
        count = connection.execute(
            text(
                "SELECT COUNT(*) FROM app.live_operational_sources "
                "WHERE source_snapshot_id = :source_snapshot_id AND is_verified = 1"
            ),
            {"source_snapshot_id": bundle.source_snapshot_id},
        ).scalar_one()
    if count != 1:
        raise RuntimeError("Fabric does not contain exactly one verified RL-001 source")


def _validate_local_target(settings: Settings) -> str:
    if settings.runtime_mode is not RuntimeMode.LIVE:
        raise SystemExit("loader requires live runtime")
    if settings.credential_mode != "azure_cli":
        raise SystemExit("loader requires an Azure CLI credential")
    if not settings.fabric_sql_server or not settings.fabric_sql_database:
        raise SystemExit("loader requires an explicit Fabric SQL target")
    if not settings.fabric_citation_base_url:
        raise SystemExit("loader requires the configured Fabric citation base")
    return settings.fabric_citation_base_url


def run(
    *,
    apply: bool,
    settings: Settings,
    engine: Engine | None = None,
) -> Literal["planned", "inserted", "unchanged"]:
    citation_url = _validate_local_target(settings)
    bundle = build_rl001_live_source(citation_url)

    active_engine = engine
    credential = None
    owns_resources = active_engine is None
    try:
        if active_engine is None:
            credential = build_credential(settings)
            active_engine = build_fabric_engine(settings, credential)

        context = active_engine.begin() if apply else active_engine.connect()
        with context as connection:
            outcome = ensure_rl001_live_source(connection, bundle, apply=apply)

        if apply:
            try:
                verify_readback(active_engine, bundle)
            except Exception as error:
                if outcome == "inserted":
                    message = (
                        "Fabric insert committed, but post-commit verification failed; "
                        "the inserted source was not rolled back or deleted"
                    )
                else:
                    message = (
                        "Fabric source was unchanged, but post-check verification failed; "
                        "the existing source was not updated or deleted"
                    )
                raise LoaderVerificationError(message) from error
        return outcome
    finally:
        if owns_resources:
            try:
                if active_engine is not None:
                    active_engine.dispose()
            finally:
                if credential is not None:
                    close_credential = getattr(credential, "close", None)
                    if callable(close_credential):
                        close_credential()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="insert the verified canonical RL-001 bundle when it is absent",
    )
    args = parser.parse_args()
    try:
        outcome = run(apply=args.apply, settings=Settings())  # pyright: ignore[reportCallIssue]
    except LoaderVerificationError as error:
        print(f"RL-001 Fabric source failed: {error}", file=sys.stderr)
        return 1
    except SystemExit as error:
        print(f"RL-001 Fabric source failed: {error}", file=sys.stderr)
        return 2
    except (
        AzureError,
        OSError,
        RuntimeError,
        SQLAlchemyError,
        ValidationError,
        ValueError,
    ):
        print(
            "RL-001 Fabric source failed: configuration, identity, or SQL operation failed",
            file=sys.stderr,
        )
        return 1
    print(f"RL-001 Fabric source RL-001-OPERATIONAL-V1: {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
