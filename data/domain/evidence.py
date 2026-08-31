from datetime import datetime
from enum import StrEnum

from .common import FrozenModel, RuntimeMode


class EvidenceKind(StrEnum):
    OPERATIONAL_FACT = "operational_fact"
    SOURCE_STATEMENT = "source_statement"
    PREREQUISITE_APPROVAL = "prerequisite_approval"
    CONTEXTUAL_EVIDENCE = "contextual_evidence"


class ObservationKind(StrEnum):
    ACTUAL = "actual"
    SIMULATED = "simulated"


class EvidenceBlockingCode(StrEnum):
    REQUIRED_CITATION_MISSING = "REQUIRED_CITATION_MISSING"
    EVIDENCE_TIMESTAMP_STALE = "EVIDENCE_TIMESTAMP_STALE"
    EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
    EVIDENCE_CONFLICT_UNRESOLVED = "EVIDENCE_CONFLICT_UNRESOLVED"
    AUTHORITY_SCOPE_MISMATCH = "AUTHORITY_SCOPE_MISMATCH"


class EvidenceItem(FrozenModel):
    evidence_id: str
    case_id: str
    kind: EvidenceKind
    authority_scope: tuple[str, ...]
    source_system: str
    source_id: str
    source_timestamp: datetime | None
    retrieved_at: datetime | None
    effective_at: datetime | None
    expires_at: datetime | None
    claim: str
    excerpt: str | None
    citation_url: str | None
    runtime_mode: RuntimeMode
    synthetic: bool


class EvidenceConflict(FrozenModel):
    conflict_id: str
    case_id: str
    evidence_ids: tuple[str, ...]
    authority_scope: tuple[str, ...]
    description: str
    feasibility_relevant: bool


class ConflictResolution(FrozenModel):
    conflict_id: str
    governing_evidence_id: str
    actor_roles: tuple[str, ...]


class EvidenceValidation(FrozenModel):
    blocking_codes: tuple[EvidenceBlockingCode, ...] = ()
