from datetime import datetime

from data.domain.common import RuntimeMode
from data.domain.evidence import (
    ConflictResolution,
    EvidenceBlockingCode,
    EvidenceConflict,
    EvidenceItem,
    EvidenceValidation,
)


class PolicyViolation(ValueError):
    """Raised when an actor attempts an authority-restricted policy action."""


def validate_required_evidence(
    evidence_items: tuple[EvidenceItem, ...],
    *,
    runtime_mode: RuntimeMode,
    scenario_effective_time: datetime | None = None,
    required_authority_scope: tuple[str, ...] = (),
    conflicts: tuple[EvidenceConflict, ...] = (),
    conflict_resolutions: tuple[ConflictResolution, ...] = (),
) -> EvidenceValidation:
    reference_time = scenario_effective_time
    if reference_time is None:
        retrieved_times = tuple(
            item.retrieved_at
            for item in evidence_items
            if item.retrieved_at is not None
        )
        reference_time = max(retrieved_times, default=None)

    citation_missing = any(
        runtime_mode == RuntimeMode.LIVE
        and item.source_system.lower() == "work_iq"
        and item.citation_url is None
        for item in evidence_items
    )
    timestamp_stale = any(
        item.source_timestamp is None
        or item.retrieved_at is None
        or item.source_timestamp > item.retrieved_at
        for item in evidence_items
    )
    expired = reference_time is not None and any(
        item.expires_at is not None and item.expires_at < reference_time
        for item in evidence_items
    )
    unresolved_conflict = any(
        conflict.feasibility_relevant
        and not any(
            resolution.conflict_id == conflict.conflict_id
            and resolution.governing_evidence_id in conflict.evidence_ids
            and "agent" not in resolution.actor_roles
            for resolution in conflict_resolutions
        )
        for conflict in conflicts
    )
    actual_scope = {scope for item in evidence_items for scope in item.authority_scope}
    authority_mismatch = any(
        not item.authority_scope for item in evidence_items
    ) or not set(required_authority_scope).issubset(actual_scope)
    checks = (
        (citation_missing, EvidenceBlockingCode.REQUIRED_CITATION_MISSING),
        (timestamp_stale, EvidenceBlockingCode.EVIDENCE_TIMESTAMP_STALE),
        (expired, EvidenceBlockingCode.EVIDENCE_EXPIRED),
        (unresolved_conflict, EvidenceBlockingCode.EVIDENCE_CONFLICT_UNRESOLVED),
        (authority_mismatch, EvidenceBlockingCode.AUTHORITY_SCOPE_MISMATCH),
    )
    return EvidenceValidation(
        blocking_codes=tuple(code for blocked, code in checks if blocked)
    )


def resolve_conflict(
    conflict: EvidenceConflict,
    *,
    actor_roles: tuple[str, ...],
    governing_evidence_id: str,
) -> ConflictResolution:
    authorized_human_roles = {
        "material_planner",
        "finance_approver",
        "quality_approver",
        "response_approver",
    }
    if "agent" in actor_roles or not authorized_human_roles.intersection(actor_roles):
        raise PolicyViolation("Conflict resolution requires an authorized human.")
    if governing_evidence_id not in conflict.evidence_ids:
        raise PolicyViolation("Governing evidence must belong to the conflict.")
    return ConflictResolution(
        conflict_id=conflict.conflict_id,
        governing_evidence_id=governing_evidence_id,
        actor_roles=actor_roles,
    )
