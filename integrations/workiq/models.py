from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from data.domain.evidence import EvidenceItem

SourceKind = Literal["supplier", "quality"]


@dataclass(frozen=True, slots=True)
class DiscoveryTopic:
    source_kind: SourceKind
    case_reference: str = "RL-001"


@dataclass(frozen=True, slots=True)
class SourceBinding:
    tenant_id: str
    alex_object_id: str
    supplier_sender: str
    quality_author_object_id: str
    team_id: str
    channel_id: str
    supplier_source_id: str
    quality_source_id: str


@dataclass(frozen=True, slots=True)
class WorkIQRetrievalLineage:
    context_id: str
    task_id: str
    artifact_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    protocol: Literal["a2a", "mcp"] = "a2a"
    request_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkIQRetrieval:
    evidence: tuple[EvidenceItem, ...]
    lineage: WorkIQRetrievalLineage
