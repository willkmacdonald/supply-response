from __future__ import annotations

from dataclasses import dataclass

from data.domain.evidence import EvidenceItem


@dataclass(frozen=True, slots=True)
class WorkIQRetrievalLineage:
    context_id: str
    task_id: str
    artifact_ids: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkIQRetrieval:
    evidence: tuple[EvidenceItem, ...]
    lineage: WorkIQRetrievalLineage
