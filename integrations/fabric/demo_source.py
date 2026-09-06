"""Canonical, insert-only RL-001 source bundle for Fabric SQL."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import Connection, DateTime, bindparam, text

from apps.api.app.live import validate_live_https_url
from data.domain import RuntimeMode
from data.domain.evidence import (
    AuthorityScope,
    EvidenceItem,
    EvidenceKind,
    EvidenceRequirement,
    EvidenceSourceSystem,
    RetrievalHealth,
    UncertaintyState,
)
from data.synthetic.rl001 import SCENARIO_EFFECTIVE_TIME, OperationalSnapshot

SOURCE_SNAPSHOT_ID = "RL-001-OPERATIONAL-V1"
TEMPLATE_CASE_ID = "RL-CASE-TEMPLATE"
TEMPLATE_ANALYSIS_ID = "RL-ANALYSIS-TEMPLATE"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class LiveOperationalSourceBundle:
    source_snapshot_id: str
    template_id: str
    effective_at: datetime
    is_verified: bool
    snapshot_payload_json: str
    evidence_payload_json: str

    def snapshot(self) -> OperationalSnapshot:
        return OperationalSnapshot.model_validate_json(self.snapshot_payload_json)

    def evidence(self) -> tuple[EvidenceItem, ...]:
        values = json.loads(self.evidence_payload_json)
        if not isinstance(values, list):
            raise TypeError("evidence payload must be a JSON array")
        return tuple(EvidenceItem.model_validate(value) for value in values)

    def parameters(self) -> dict[str, object]:
        return {
            "source_snapshot_id": self.source_snapshot_id,
            "template_id": self.template_id,
            "effective_at": self.effective_at,
            "is_verified": self.is_verified,
            "snapshot_payload_json": self.snapshot_payload_json,
            "evidence_payload_json": self.evidence_payload_json,
        }


def _fabric_evidence(
    *,
    evidence_id: str,
    source_id: str,
    authority_scope: tuple[AuthorityScope, ...],
    claim: str,
    citation_url: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        case_id=TEMPLATE_CASE_ID,
        kind=EvidenceKind.OPERATIONAL_FACT,
        authority_scope=authority_scope,
        source_system=EvidenceSourceSystem.FABRIC,
        source_id=source_id,
        source_timestamp=SCENARIO_EFFECTIVE_TIME,
        retrieved_at=SCENARIO_EFFECTIVE_TIME,
        retrieved_for_analysis_id=TEMPLATE_ANALYSIS_ID,
        retrieval_health=RetrievalHealth.HEALTHY,
        effective_at=SCENARIO_EFFECTIVE_TIME,
        expires_at=SCENARIO_EFFECTIVE_TIME + timedelta(days=1),
        claim=claim,
        excerpt=claim,
        citation_url=citation_url,
        runtime_mode=RuntimeMode.LIVE,
        synthetic=False,
        requirement=EvidenceRequirement.REQUIRED_AUTHORITATIVE,
        uncertainty_state=UncertaintyState.CERTAIN,
    )


def build_rl001_live_source(citation_url: str) -> LiveOperationalSourceBundle:
    trusted_citation = validate_live_https_url(
        citation_url, allowed_hosts={"app.powerbi.com"}
    )
    snapshot = OperationalSnapshot.rl001(
        case_id=TEMPLATE_CASE_ID,
        runtime_mode=RuntimeMode.LIVE,
    )
    evidence = (
        _fabric_evidence(
            evidence_id="RL-ALPHA-OPTIONAL-3000",
            source_id="fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000",
            authority_scope=(
                AuthorityScope.OPERATIONAL_QUANTITY,
                AuthorityScope.OPERATIONAL_DATE,
            ),
            claim="Alpha partial shipment quantity and date are confirmed.",
            citation_url=trusted_citation,
        ),
        _fabric_evidence(
            evidence_id="RL-TRANSFER-DAL-CHI-1500",
            source_id="fabric.inventory_transfer/RL-TRANSFER-DAL-CHI-1500",
            authority_scope=(
                AuthorityScope.OPERATIONAL_QUANTITY,
                AuthorityScope.OPERATIONAL_DATE,
            ),
            claim="Dallas transfer quantity and date are confirmed.",
            citation_url=trusted_citation,
        ),
        _fabric_evidence(
            evidence_id="RL-QUALITY-001",
            source_id="fabric.qualification/RL-QUAL-BETA",
            authority_scope=(AuthorityScope.QUALIFICATION_STATE,),
            claim="Beta qualification state is pending.",
            citation_url=trusted_citation,
        ),
    )
    return LiveOperationalSourceBundle(
        source_snapshot_id=SOURCE_SNAPSHOT_ID,
        template_id="RL-001",
        effective_at=SCENARIO_EFFECTIVE_TIME,
        is_verified=True,
        snapshot_payload_json=_canonical_json(snapshot.model_dump(mode="json")),
        evidence_payload_json=_canonical_json(
            [item.model_dump(mode="json") for item in evidence]
        ),
    )


def _validate_canonical_bundle(bundle: LiveOperationalSourceBundle) -> None:
    try:
        evidence = bundle.evidence()
        citations = {item.citation_url for item in evidence}
        if len(citations) != 1 or None in citations:
            raise ValueError("canonical evidence must share one citation URL")
        citation = next(iter(citations))
        assert citation is not None
        canonical = build_rl001_live_source(citation)
    except (AssertionError, TypeError, ValueError) as error:
        raise ValueError("invalid canonical RL-001 source bundle") from error
    if bundle != canonical:
        raise ValueError("invalid canonical RL-001 source bundle")


def _same_effective_at(actual: object, expected: datetime) -> bool:
    if not isinstance(actual, datetime):
        return False
    if actual.tzinfo is None or actual.utcoffset() is None:
        raise RuntimeError("Fabric effective_at must be timezone-aware")
    return actual.astimezone(UTC) == expected.astimezone(UTC)


def _matches(row: Mapping[Any, object], bundle: LiveOperationalSourceBundle) -> bool:
    expected = bundle.parameters()
    return all(
        (
            _same_effective_at(row[key], bundle.effective_at)
            if key == "effective_at"
            else bool(row[key]) == value
            if key == "is_verified"
            else row[key] == value
        )
        for key, value in expected.items()
    )


def ensure_rl001_live_source(
    connection: Connection,
    bundle: LiveOperationalSourceBundle,
    *,
    apply: bool,
) -> Literal["planned", "inserted", "unchanged"]:
    _validate_canonical_bundle(bundle)
    lock_hint = " WITH (UPDLOCK, HOLDLOCK)" if apply else ""
    existing = (
        connection.execute(
            text(
                "SELECT source_snapshot_id, template_id, effective_at, is_verified, "
                "snapshot_payload_json, evidence_payload_json "
                f"FROM app.live_operational_sources{lock_hint} "
                "WHERE source_snapshot_id = :source_snapshot_id"
            ),
            {"source_snapshot_id": bundle.source_snapshot_id},
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if not _matches(existing, bundle):
            raise RuntimeError(
                "existing RL-001 source differs from the canonical bundle"
            )
        return "unchanged"
    if not apply:
        return "planned"
    insert = text(
        "INSERT INTO app.live_operational_sources "
        "(source_snapshot_id, template_id, effective_at, is_verified, "
        "snapshot_payload_json, evidence_payload_json) VALUES "
        "(:source_snapshot_id, :template_id, :effective_at, :is_verified, "
        ":snapshot_payload_json, :evidence_payload_json)"
    ).bindparams(bindparam("effective_at", type_=DateTime(timezone=True)))
    connection.execute(insert, bundle.parameters())
    return "inserted"
