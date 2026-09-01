from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal, Protocol

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
