from datetime import datetime
from enum import StrEnum

from pydantic import field_validator

from .common import FrozenModel, RuntimeMode


class EvidenceKind(StrEnum):
    OPERATIONAL_FACT = "operational_fact"
    SOURCE_STATEMENT = "source_statement"
    PREREQUISITE_APPROVAL = "prerequisite_approval"
    CONTEXTUAL_EVIDENCE = "contextual_evidence"


class ObservationKind(StrEnum):
    ACTUAL = "actual"
    SIMULATED = "simulated"


class EvidenceSourceSystem(StrEnum):
    FABRIC = "fabric"
    SQLITE = "sqlite"
    WORK_IQ = "work_iq"
    SERVER = "server"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class AuthorityScope(StrEnum):
    OPERATIONAL_QUANTITY = "operational_quantity"
    OPERATIONAL_DATE = "operational_date"
    QUALIFICATION_STATE = "qualification_state"
    SUPPLIER_STATEMENT = "supplier_statement"
    COLLABORATION_STATEMENT = "collaboration_statement"
    PREREQUISITE_APPROVAL = "prerequisite_approval"


class EvidenceRequirement(StrEnum):
    REQUIRED_AUTHORITATIVE = "required_authoritative"
    CONTEXTUAL = "contextual"


class FreshnessState(StrEnum):
    CURRENT = "current"
    STALE = "stale"


class BusinessValidityState(StrEnum):
    VALID = "valid"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"


class UncertaintyState(StrEnum):
    CERTAIN = "certain"
    UNCERTAIN = "uncertain"
    CONFLICTED = "conflicted"


class RetrievalHealth(StrEnum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class IdentitySource(StrEnum):
    ENTRA = "entra"


class EvidenceBlockingCode(StrEnum):
    REQUIRED_EVIDENCE_MISSING = "REQUIRED_EVIDENCE_MISSING"
    REQUIRED_EVIDENCE_NOT_AUTHORITATIVE = "REQUIRED_EVIDENCE_NOT_AUTHORITATIVE"
    REQUIRED_CITATION_MISSING = "REQUIRED_CITATION_MISSING"
    REQUIRED_SOURCE_METADATA_MISSING = "REQUIRED_SOURCE_METADATA_MISSING"
    EVIDENCE_TIMESTAMP_STALE = "EVIDENCE_TIMESTAMP_STALE"
    EVIDENCE_RETRIEVAL_OUTSIDE_WINDOW = "EVIDENCE_RETRIEVAL_OUTSIDE_WINDOW"
    RETRIEVAL_HEALTH_UNACCEPTABLE = "RETRIEVAL_HEALTH_UNACCEPTABLE"
    EVIDENCE_NOT_YET_EFFECTIVE = "EVIDENCE_NOT_YET_EFFECTIVE"
    EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
    EVIDENCE_CONFLICT_UNRESOLVED = "EVIDENCE_CONFLICT_UNRESOLVED"
    CONFLICT_RESOLUTION_INVALID = "CONFLICT_RESOLUTION_INVALID"
    AUTHORITY_SCOPE_MISMATCH = "AUTHORITY_SCOPE_MISMATCH"
    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"


class EvidenceItem(FrozenModel):
    evidence_id: str
    case_id: str
    kind: EvidenceKind
    authority_scope: tuple[AuthorityScope, ...]
    source_system: EvidenceSourceSystem
    source_id: str
    source_timestamp: datetime | None
    retrieved_at: datetime | None
    retrieved_for_analysis_id: str
    retrieval_health: RetrievalHealth
    effective_at: datetime | None
    expires_at: datetime | None
    claim: str
    excerpt: str | None
    citation_url: str | None
    runtime_mode: RuntimeMode
    synthetic: bool
    requirement: EvidenceRequirement
    uncertainty_state: UncertaintyState


class EvidenceConflict(FrozenModel):
    conflict_id: str
    case_id: str
    evidence_ids: tuple[str, ...]
    authority_scope: tuple[AuthorityScope, ...]
    description: str
    feasibility_relevant: bool


class ActorProvenance(FrozenModel):
    persona_id: str
    roles: tuple[str, ...]
    identity_source: IdentitySource
    source_id: str


class ConflictResolution(FrozenModel):
    conflict_id: str
    governing_evidence_id: str
    actor: ActorProvenance
    why: str

    @field_validator("why")
    @classmethod
    def why_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("why must be nonblank")
        return value


class EvidenceItemValidation(FrozenModel):
    evidence_id: str
    requirement: EvidenceRequirement
    validated_authority_scope: tuple[AuthorityScope, ...]
    freshness: FreshnessState
    business_validity: BusinessValidityState
    uncertainty_state: UncertaintyState
    retrieval_health: RetrievalHealth
    authoritative: bool
    blocking_codes: tuple[EvidenceBlockingCode, ...]


class EvidenceValidation(FrozenModel):
    policy_version: str
    item_results: tuple[EvidenceItemValidation, ...]
    blocking_codes: tuple[EvidenceBlockingCode, ...] = ()

    @property
    def authoritative(self) -> bool:
        return not self.blocking_codes
