from datetime import datetime, timedelta
from urllib.parse import urlparse

from data.domain.common import RuntimeMode
from data.domain.evidence import (
    ActorProvenance,
    AuthorityScope,
    BusinessValidityState,
    ConflictResolution,
    EvidenceBlockingCode,
    EvidenceConflict,
    EvidenceItem,
    EvidenceItemValidation,
    EvidenceKind,
    EvidenceRequirement,
    EvidenceSourceSystem,
    EvidenceValidation,
    FreshnessState,
    IdentitySource,
    RetrievalHealth,
    UncertaintyState,
)


EVIDENCE_POLICY_VERSION = "evidence-policy-v2"
EVIDENCE_RETRIEVAL_WINDOW = timedelta(minutes=5)


class PolicyViolation(ValueError):
    """Raised when an actor attempts an authority-restricted policy action."""


_OPERATIONAL_SCOPES = {
    AuthorityScope.OPERATIONAL_QUANTITY,
    AuthorityScope.OPERATIONAL_DATE,
    AuthorityScope.QUALIFICATION_STATE,
}
_SOURCE_AUTHORITY: dict[EvidenceSourceSystem, set[AuthorityScope]] = {
    EvidenceSourceSystem.FABRIC: _OPERATIONAL_SCOPES,
    EvidenceSourceSystem.SQLITE: _OPERATIONAL_SCOPES,
    EvidenceSourceSystem.WORK_IQ: {
        AuthorityScope.SUPPLIER_STATEMENT,
        AuthorityScope.COLLABORATION_STATEMENT,
    },
    EvidenceSourceSystem.SERVER: {AuthorityScope.PREREQUISITE_APPROVAL},
    EvidenceSourceSystem.SYNTHETIC_FIXTURE: _OPERATIONAL_SCOPES
    | {
        AuthorityScope.SUPPLIER_STATEMENT,
        AuthorityScope.COLLABORATION_STATEMENT,
    },
}
_SOURCE_RUNTIME_MODES: dict[EvidenceSourceSystem, set[RuntimeMode]] = {
    EvidenceSourceSystem.FABRIC: {RuntimeMode.LIVE},
    EvidenceSourceSystem.SQLITE: {RuntimeMode.FALLBACK},
    EvidenceSourceSystem.WORK_IQ: {RuntimeMode.LIVE},
    EvidenceSourceSystem.SERVER: {RuntimeMode.LIVE, RuntimeMode.FALLBACK},
    EvidenceSourceSystem.SYNTHETIC_FIXTURE: {RuntimeMode.FALLBACK},
}
_KIND_AUTHORITY: dict[EvidenceKind, set[AuthorityScope]] = {
    EvidenceKind.OPERATIONAL_FACT: _OPERATIONAL_SCOPES,
    EvidenceKind.SOURCE_STATEMENT: {
        AuthorityScope.SUPPLIER_STATEMENT,
        AuthorityScope.COLLABORATION_STATEMENT,
    },
    EvidenceKind.PREREQUISITE_APPROVAL: {AuthorityScope.PREREQUISITE_APPROVAL},
    EvidenceKind.CONTEXTUAL_EVIDENCE: {
        AuthorityScope.SUPPLIER_STATEMENT,
        AuthorityScope.COLLABORATION_STATEMENT,
    },
}
_PERSONA_ROLES: dict[str, set[str]] = {
    "RL-PERSONA-ALEX": {"material_planner", "response_approver"},
    "RL-PERSONA-JORDAN": {"quality_approver"},
    "RL-PERSONA-TAYLOR": {"finance_approver"},
}
_PERSONA_SOURCE_IDS = {
    "RL-PERSONA-ALEX": "RL-ENTRA-ALEX",
    "RL-PERSONA-JORDAN": "RL-ENTRA-JORDAN",
    "RL-PERSONA-TAYLOR": "RL-ENTRA-TAYLOR",
}
_SCOPE_RESOLVER_ROLES: dict[AuthorityScope, set[str]] = {
    AuthorityScope.OPERATIONAL_QUANTITY: {"material_planner", "response_approver"},
    AuthorityScope.OPERATIONAL_DATE: {"material_planner", "response_approver"},
    AuthorityScope.QUALIFICATION_STATE: {"quality_approver"},
    AuthorityScope.SUPPLIER_STATEMENT: {"material_planner", "response_approver"},
    AuthorityScope.COLLABORATION_STATEMENT: {
        "material_planner",
        "quality_approver",
        "response_approver",
    },
    AuthorityScope.PREREQUISITE_APPROVAL: {
        "material_planner",
        "finance_approver",
        "quality_approver",
        "response_approver",
    },
}


def _navigable_http_url(value: str | None) -> bool:
    if value is None or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validated_scope(
    item: EvidenceItem, runtime_mode: RuntimeMode
) -> tuple[AuthorityScope, ...]:
    if (
        item.runtime_mode != runtime_mode
        or runtime_mode not in _SOURCE_RUNTIME_MODES[item.source_system]
    ):
        return ()
    permitted = _SOURCE_AUTHORITY[item.source_system] & _KIND_AUTHORITY[item.kind]
    return tuple(
        sorted(set(item.authority_scope) & permitted, key=lambda value: value.value)
    )


def _actor_is_authorized(
    authority_scope: tuple[AuthorityScope, ...], actor: ActorProvenance
) -> bool:
    recognized_roles = _PERSONA_ROLES.get(actor.persona_id)
    roles = set(actor.roles)
    if (
        actor.identity_source != IdentitySource.ENTRA
        or not actor.source_id.strip()
        or not roles
        or "agent" in roles
        or recognized_roles is None
        or actor.source_id != _PERSONA_SOURCE_IDS.get(actor.persona_id)
        or not roles.issubset(recognized_roles)
    ):
        return False
    if not authority_scope:
        return False
    permitted_role_sets = tuple(
        _SCOPE_RESOLVER_ROLES[scope] for scope in authority_scope
    )
    conflict_roles = set.intersection(*permitted_role_sets)
    return bool(roles & conflict_roles)


def _resolution_is_valid(
    conflict: EvidenceConflict,
    resolution: ConflictResolution,
    validated_scope: tuple[AuthorityScope, ...],
) -> bool:
    return (
        resolution.conflict_id == conflict.conflict_id
        and resolution.governing_evidence_id in conflict.evidence_ids
        and bool(resolution.why.strip())
        and _actor_is_authorized(validated_scope, resolution.actor)
    )


def _validated_conflict_scope(
    conflict: EvidenceConflict,
    validation_by_evidence_id: dict[str, EvidenceItemValidation],
) -> tuple[AuthorityScope, ...]:
    referenced = tuple(
        validation_by_evidence_id.get(evidence_id)
        for evidence_id in conflict.evidence_ids
    )
    declared = tuple(
        sorted(set(conflict.authority_scope), key=lambda value: value.value)
    )
    if (
        not conflict.evidence_ids
        or not declared
        or any(result is None for result in referenced)
        or any(
            tuple(result.validated_authority_scope) != declared
            for result in referenced
            if result is not None
        )
    ):
        raise PolicyViolation(
            "Conflict authority scope must match every referenced validated evidence scope."
        )
    return declared


def _item_validation(
    item: EvidenceItem,
    *,
    analysis_id: str,
    runtime_mode: RuntimeMode,
    scenario_effective_time: datetime,
    analysis_started_at: datetime,
    conflicted_evidence_ids: set[str],
) -> EvidenceItemValidation:
    codes: list[EvidenceBlockingCode] = []
    validated_scope = _validated_scope(item, runtime_mode)
    scope_valid = (
        item.kind != EvidenceKind.CONTEXTUAL_EVIDENCE
        and bool(item.authority_scope)
        and set(item.authority_scope).issubset(validated_scope)
    )
    if not scope_valid:
        codes.append(EvidenceBlockingCode.AUTHORITY_SCOPE_MISMATCH)

    required = item.requirement == EvidenceRequirement.REQUIRED_AUTHORITATIVE
    required_live_work_iq = (
        required
        and runtime_mode == RuntimeMode.LIVE
        and item.source_system == EvidenceSourceSystem.WORK_IQ
    )
    if required_live_work_iq and not _navigable_http_url(item.citation_url):
        codes.append(EvidenceBlockingCode.REQUIRED_CITATION_MISSING)
    if required_live_work_iq and (
        not item.source_id.strip() or item.excerpt is None or not item.excerpt.strip()
    ):
        codes.append(EvidenceBlockingCode.REQUIRED_SOURCE_METADATA_MISSING)

    timestamps_ordered = (
        item.source_timestamp is not None
        and item.retrieved_at is not None
        and item.source_timestamp <= item.retrieved_at
    )
    current_retrieval = (
        item.retrieved_for_analysis_id == analysis_id
        and item.retrieval_health == RetrievalHealth.HEALTHY
    )
    retrieval_in_window = (
        item.retrieved_at is not None
        and analysis_started_at
        <= item.retrieved_at
        <= analysis_started_at + EVIDENCE_RETRIEVAL_WINDOW
    )
    freshness = (
        FreshnessState.CURRENT
        if timestamps_ordered and current_retrieval and retrieval_in_window
        else FreshnessState.STALE
    )
    if required and not timestamps_ordered:
        codes.append(EvidenceBlockingCode.EVIDENCE_TIMESTAMP_STALE)
    if required and not current_retrieval:
        codes.append(EvidenceBlockingCode.RETRIEVAL_HEALTH_UNACCEPTABLE)
    if required and not retrieval_in_window:
        codes.append(EvidenceBlockingCode.EVIDENCE_RETRIEVAL_OUTSIDE_WINDOW)

    if item.effective_at is not None and scenario_effective_time < item.effective_at:
        business_validity = BusinessValidityState.NOT_YET_EFFECTIVE
        if required:
            codes.append(EvidenceBlockingCode.EVIDENCE_NOT_YET_EFFECTIVE)
    elif item.expires_at is not None and scenario_effective_time >= item.expires_at:
        business_validity = BusinessValidityState.EXPIRED
        if required:
            codes.append(EvidenceBlockingCode.EVIDENCE_EXPIRED)
    else:
        business_validity = BusinessValidityState.VALID

    uncertainty_state = item.uncertainty_state
    if item.evidence_id in conflicted_evidence_ids:
        uncertainty_state = UncertaintyState.CONFLICTED

    authoritative = (
        required
        and scope_valid
        and freshness == FreshnessState.CURRENT
        and business_validity == BusinessValidityState.VALID
        and uncertainty_state != UncertaintyState.CONFLICTED
        and not codes
    )
    return EvidenceItemValidation(
        evidence_id=item.evidence_id,
        requirement=item.requirement,
        validated_authority_scope=validated_scope,
        freshness=freshness,
        business_validity=business_validity,
        uncertainty_state=uncertainty_state,
        retrieval_health=item.retrieval_health,
        authoritative=authoritative,
        blocking_codes=tuple(dict.fromkeys(codes)),
    )


def validate_required_evidence(
    evidence_items: tuple[EvidenceItem, ...],
    *,
    analysis_id: str,
    runtime_mode: RuntimeMode,
    scenario_effective_time: datetime,
    analysis_started_at: datetime,
    required_authority_scope: tuple[AuthorityScope, ...] = (),
    conflicts: tuple[EvidenceConflict, ...] = (),
    conflict_resolutions: tuple[ConflictResolution, ...] = (),
) -> EvidenceValidation:
    base_item_results = tuple(
        _item_validation(
            item,
            analysis_id=analysis_id,
            runtime_mode=runtime_mode,
            scenario_effective_time=scenario_effective_time,
            analysis_started_at=analysis_started_at,
            conflicted_evidence_ids=set(),
        )
        for item in sorted(evidence_items, key=lambda item: item.evidence_id)
    )
    validation_by_evidence_id = {item.evidence_id: item for item in base_item_results}
    validated_conflict_scopes = {
        conflict.conflict_id: _validated_conflict_scope(
            conflict, validation_by_evidence_id
        )
        for conflict in conflicts
    }
    for resolution in conflict_resolutions:
        matching_conflict = next(
            (
                conflict
                for conflict in conflicts
                if conflict.conflict_id == resolution.conflict_id
            ),
            None,
        )
        if (
            matching_conflict is None
            or resolution.governing_evidence_id not in matching_conflict.evidence_ids
        ):
            raise PolicyViolation(
                "Conflict resolution governing evidence must belong to its conflict."
            )
        if not resolution.why.strip():
            raise PolicyViolation("Conflict resolution requires a nonblank rationale.")
        if not _actor_is_authorized(
            validated_conflict_scopes[matching_conflict.conflict_id],
            resolution.actor,
        ):
            raise PolicyViolation("Conflict resolution requires an authorized human.")
    unresolved_conflicts = tuple(
        conflict
        for conflict in conflicts
        if conflict.feasibility_relevant
        and not any(
            _resolution_is_valid(
                conflict,
                resolution,
                validated_conflict_scopes[conflict.conflict_id],
            )
            for resolution in conflict_resolutions
        )
    )
    conflicted_ids = {
        evidence_id
        for conflict in unresolved_conflicts
        for evidence_id in conflict.evidence_ids
    }
    item_results = tuple(
        _item_validation(
            item,
            analysis_id=analysis_id,
            runtime_mode=runtime_mode,
            scenario_effective_time=scenario_effective_time,
            analysis_started_at=analysis_started_at,
            conflicted_evidence_ids=conflicted_ids,
        )
        for item in sorted(evidence_items, key=lambda item: item.evidence_id)
    )
    authoritative_scope = {
        scope
        for result in item_results
        if result.authoritative
        for scope in result.validated_authority_scope
    }
    authority_mismatch = not set(required_authority_scope).issubset(authoritative_scope)

    item_codes = {
        code
        for result in item_results
        if result.requirement == EvidenceRequirement.REQUIRED_AUTHORITATIVE
        for code in result.blocking_codes
    }
    if unresolved_conflicts:
        item_codes.add(EvidenceBlockingCode.EVIDENCE_CONFLICT_UNRESOLVED)
    if authority_mismatch:
        item_codes.add(EvidenceBlockingCode.AUTHORITY_SCOPE_MISMATCH)
    blocking_codes = tuple(code for code in EvidenceBlockingCode if code in item_codes)
    return EvidenceValidation(
        policy_version=EVIDENCE_POLICY_VERSION,
        item_results=item_results,
        blocking_codes=blocking_codes,
    )


def resolve_conflict(
    conflict: EvidenceConflict,
    *,
    evidence_validation: EvidenceValidation,
    actor: ActorProvenance,
    governing_evidence_id: str,
    why: str,
) -> ConflictResolution:
    if evidence_validation.policy_version != EVIDENCE_POLICY_VERSION:
        raise PolicyViolation(
            "Evidence validation policy version does not match the evaluator."
        )
    validation_by_evidence_id = {
        item.evidence_id: item for item in evidence_validation.item_results
    }
    validated_scope = _validated_conflict_scope(conflict, validation_by_evidence_id)
    if not _actor_is_authorized(validated_scope, actor):
        raise PolicyViolation("Conflict resolution requires an authorized human.")
    if governing_evidence_id not in conflict.evidence_ids:
        raise PolicyViolation("Governing evidence must belong to the conflict.")
    return ConflictResolution(
        conflict_id=conflict.conflict_id,
        governing_evidence_id=governing_evidence_id,
        actor=actor,
        why=why,
    )
