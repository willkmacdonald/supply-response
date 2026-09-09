from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from apps.api.app._reporting_artifact import (
    REPORTING_ARTIFACT_SHA256,
    REPORTING_CONTRACT,
)

CapabilityState = Literal["configured", "unverified", "ready", "unavailable"]


@dataclass(frozen=True, slots=True)
class ReadinessSnapshot:
    capability_health: dict[str, CapabilityState]
    fabric_schema_version: int | None = None
    power_bi_verified: bool = False


class ReadinessPort(Protocol):
    def check(self) -> ReadinessSnapshot: ...


class UnverifiedLiveReadiness:
    def check(self) -> ReadinessSnapshot:
        return ReadinessSnapshot(
            capability_health={
                "operational_store": "unverified",
                "work_iq": "unverified",
                "agent_runtime": "unverified",
                "power_bi": "unverified",
            }
        )


class FallbackReadiness:
    def check(self) -> ReadinessSnapshot:
        return ReadinessSnapshot(
            capability_health={
                "operational_store": "ready",
                "work_iq": "ready",
                "agent_runtime": "ready",
                "power_bi": "unavailable",
            }
        )


class FabricBoundReadiness:
    """Bounded, user-context-free checks; configured is never reported as ready."""

    def __init__(
        self,
        *,
        engine,
        power_bi_receipt_verified: bool = False,
        work_iq_receipt_verified: bool = False,
        foundry_receipt_verified: bool = False,
    ) -> None:
        self._engine = engine
        self._power_bi_receipt_verified = power_bi_receipt_verified
        self._work_iq_receipt_verified = work_iq_receipt_verified
        self._foundry_receipt_verified = foundry_receipt_verified

    def check(self) -> ReadinessSnapshot:
        from integrations.fabric.health import check_fabric_health

        health: dict[str, CapabilityState] = {
            "operational_store": "unavailable",
            "work_iq": "ready" if self._work_iq_receipt_verified else "unverified",
            "agent_runtime": "ready"
            if self._foundry_receipt_verified
            else "unverified",
            "power_bi": "ready" if self._power_bi_receipt_verified else "unverified",
        }
        schema_version = None
        try:
            fabric = check_fabric_health(self._engine)
            schema_version = fabric.schema_version
            health["operational_store"] = "ready"
        except Exception:  # noqa: BLE001,S110 - unavailable is intentional
            pass
        return ReadinessSnapshot(
            capability_health=health,
            fabric_schema_version=schema_version,
            power_bi_verified=self._power_bi_receipt_verified,
        )


def verify_power_bi_deployment_receipt(report_url: str, receipt: str | None) -> bool:
    """A publish step records the SHA-256 binding of the exact validated report URL."""
    if receipt is None:
        return False
    expected = hashlib.sha256(report_url.encode("utf-8")).hexdigest()
    return receipt == expected


def verify_binding_receipt(parts: tuple[str, ...], receipt: str | None) -> bool:
    if receipt is None or any(not part.strip() for part in parts):
        return False
    expected = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return receipt == expected


_REPORT_UUID = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_REPORT_URL = re.compile(
    rf"https://app\.powerbi\.com/groups/{_REPORT_UUID}/reports/{_REPORT_UUID}"
)


def verify_power_bi_reporting_receipt(
    report_url: str | None,
    fabric_sql_server: str | None,
    fabric_sql_database: str | None,
    receipt: str | None,
) -> bool:
    """Match trusted release attestation; performs no availability or access check."""
    if (
        report_url is None
        or _REPORT_URL.fullmatch(report_url) is None
        or fabric_sql_server is None
        or not fabric_sql_server.strip()
        or fabric_sql_database is None
        or not fabric_sql_database.strip()
        or receipt is None
        or re.fullmatch(r"[0-9a-f]{64}", receipt) is None
    ):
        return False
    payload = [
        "supply-response-reporting-receipt-v1",
        REPORTING_CONTRACT,
        REPORTING_ARTIFACT_SHA256,
        report_url,
        fabric_sql_server,
        fabric_sql_database,
    ]
    expected = hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return hmac.compare_digest(receipt, expected)
