import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Callable, TypeVar

from data.domain.analysis import (
    AnalysisApprovalMaterial,
    AnalysisConflictMaterial,
    AnalysisConflictResolutionMaterial,
    AnalysisEvidenceMaterial,
    AnalysisMaterial,
    AnalysisResponseOptionMaterial,
    AnalysisStandingAuthorizationMaterial,
    AnalysisVersion,
    ResponseOption,
)
from data.domain.cases import CaseInstance
from data.domain.decisions import (
    ApprovalSatisfaction,
    ApprovalTarget,
    CorpusScope,
    StandingAuthorization,
)
from data.domain.evidence import (
    AuthorityScope,
    ConflictResolution,
    EvidenceConflict,
    EvidenceItem,
)
from data.synthetic.rl001 import OperationalSnapshot
from services.policy.approvals import evaluate_approval_satisfaction
from services.policy.evidence import (
    EVIDENCE_RETRIEVAL_WINDOW,
    EVIDENCE_POLICY_VERSION,
    PolicyViolation,
    validate_required_evidence,
)


APPROVAL_POLICY_VERSION = "standing-authorization-v1"

_OPERATIONAL_COLLECTION_KEYS = {
    "inventory_positions": "inventory_id",
    "production_orders": "production_order_id",
    "customer_orders": "customer_order_line_id",
}

_T = TypeVar("_T")


def _reject_duplicate_ids(
    items: tuple[_T, ...],
    *,
    key: Callable[[_T], str],
    label: str,
) -> None:
    values = tuple(key(item) for item in items)
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label} stable ID")


def _validate_provenance(
    *,
    case: CaseInstance,
    operational_snapshot: OperationalSnapshot,
    evidence_items: tuple[EvidenceItem, ...],
    conflicts: tuple[EvidenceConflict, ...],
) -> None:
    if (
        operational_snapshot.case_id != case.case_id
        or operational_snapshot.runtime_mode != case.runtime_mode
        or operational_snapshot.scenario_effective_time != case.scenario_effective_time
    ):
        raise PolicyViolation(
            "Operational snapshot provenance does not match the case."
        )
    if any(
        item.case_id != case.case_id or item.runtime_mode != case.runtime_mode
        for item in evidence_items
    ):
        raise PolicyViolation("Evidence provenance does not match the case.")
    if any(conflict.case_id != case.case_id for conflict in conflicts):
        raise PolicyViolation("Conflict provenance does not match the case.")
    evidence_ids = {item.evidence_id for item in evidence_items}
    if any(
        not set(conflict.evidence_ids).issubset(evidence_ids) for conflict in conflicts
    ):
        raise PolicyViolation(
            "Conflict evidence provenance is outside the case bundle."
        )


def _canonical_snapshot(snapshot: OperationalSnapshot) -> str:
    payload = snapshot.model_dump(mode="json")
    for field_name, id_field in _OPERATIONAL_COLLECTION_KEYS.items():
        items = payload[field_name]
        stable_ids = tuple(item[id_field] for item in items)
        if len(stable_ids) != len(set(stable_ids)):
            raise ValueError(f"duplicate operational {field_name} stable ID")
        payload[field_name] = sorted(items, key=lambda item: item[id_field])
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def analysis_material_hash(payload: AnalysisMaterial) -> str:
    canonical = payload.model_dump_json(
        exclude_none=False,
        by_alias=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_analysis_version(
    *,
    analysis_id: str,
    case: CaseInstance,
    corpus: CorpusScope,
    operational_snapshot: OperationalSnapshot,
    evidence_items: tuple[EvidenceItem, ...],
    response_options: tuple[ResponseOption, ...],
    standing_authorizations: tuple[StandingAuthorization, ...],
    analysis_started_at: datetime,
    created_at: datetime,
    calculation_version: str,
    conflicts: tuple[EvidenceConflict, ...] = (),
    conflict_resolutions: tuple[ConflictResolution, ...] = (),
    required_authority_scope: tuple[AuthorityScope, ...] = (),
    evidence_policy_version: str = EVIDENCE_POLICY_VERSION,
    approval_policy_version: str = APPROVAL_POLICY_VERSION,
) -> AnalysisVersion:
    if evidence_policy_version != EVIDENCE_POLICY_VERSION:
        raise PolicyViolation("Evidence policy version does not match the evaluator.")
    if approval_policy_version != APPROVAL_POLICY_VERSION:
        raise PolicyViolation("Approval policy version does not match the evaluator.")
    if created_at < analysis_started_at:
        raise PolicyViolation("Analysis creation cannot precede analysis start.")
    _reject_duplicate_ids(
        evidence_items, key=lambda item: item.evidence_id, label="evidence"
    )
    _reject_duplicate_ids(
        response_options, key=lambda item: item.option_id, label="response option"
    )
    _reject_duplicate_ids(
        conflicts, key=lambda item: item.conflict_id, label="conflict"
    )
    _reject_duplicate_ids(
        conflict_resolutions,
        key=lambda item: item.conflict_id,
        label="conflict resolution",
    )
    _reject_duplicate_ids(
        standing_authorizations,
        key=lambda item: item.authorization_id,
        label="standing authorization",
    )
    _validate_provenance(
        case=case,
        operational_snapshot=operational_snapshot,
        evidence_items=evidence_items,
        conflicts=conflicts,
    )

    canonical_evidence = tuple(
        sorted(evidence_items, key=lambda item: item.evidence_id)
    )
    canonical_options = tuple(sorted(response_options, key=lambda item: item.option_id))
    canonical_conflicts = tuple(sorted(conflicts, key=lambda item: item.conflict_id))
    canonical_resolutions = tuple(
        sorted(conflict_resolutions, key=lambda item: item.conflict_id)
    )
    canonical_authorizations = tuple(
        sorted(standing_authorizations, key=lambda item: item.authorization_id)
    )

    evidence_validation = validate_required_evidence(
        canonical_evidence,
        analysis_id=analysis_id,
        runtime_mode=case.runtime_mode,
        scenario_effective_time=case.scenario_effective_time,
        analysis_started_at=analysis_started_at,
        analysis_recorded_at=created_at,
        required_authority_scope=tuple(
            sorted(set(required_authority_scope), key=lambda value: value.value)
        ),
        conflicts=canonical_conflicts,
        conflict_resolutions=canonical_resolutions,
    )
    approval_satisfactions: tuple[ApprovalSatisfaction, ...] = tuple(
        satisfaction
        for option in canonical_options
        for satisfaction in evaluate_approval_satisfaction(
            option=option,
            analysis_id=analysis_id,
            standing_authorizations=canonical_authorizations,
            target=ApprovalTarget(
                case=case,
                corpus=corpus,
                scenario_effective_time=case.scenario_effective_time,
                total_response_cost=(
                    option.predicted.response_cost
                    if option.predicted is not None
                    else Decimal("0")
                ),
                requested_side_effects=option.requested_side_effects,
            ),
        )
    )
    validation_by_evidence_id = {
        item.evidence_id: item for item in evidence_validation.item_results
    }
    canonical_required_scope = tuple(
        sorted(set(required_authority_scope), key=lambda value: value.value)
    )
    material = AnalysisMaterial(
        case_id=case.case_id,
        template_id=case.template_id,
        case_purpose=case.purpose,
        runtime_mode=case.runtime_mode,
        corpus=corpus,
        scenario_effective_time=case.scenario_effective_time,
        operational_snapshot_json=_canonical_snapshot(operational_snapshot),
        required_authority_scope=canonical_required_scope,
        evidence=tuple(
            AnalysisEvidenceMaterial.from_evidence(
                item, validation_by_evidence_id[item.evidence_id]
            )
            for item in canonical_evidence
        ),
        conflicts=tuple(
            AnalysisConflictMaterial.from_conflict(item) for item in canonical_conflicts
        ),
        conflict_resolutions=tuple(
            AnalysisConflictResolutionMaterial.from_resolution(item)
            for item in canonical_resolutions
        ),
        evidence_validation=evidence_validation,
        response_options=tuple(
            AnalysisResponseOptionMaterial.from_option(item)
            for item in canonical_options
        ),
        standing_authorizations=tuple(
            AnalysisStandingAuthorizationMaterial.from_authorization(item)
            for item in canonical_authorizations
        ),
        approval_satisfactions=tuple(
            AnalysisApprovalMaterial.from_satisfaction(item)
            for item in sorted(
                approval_satisfactions,
                key=lambda item: (
                    item.option_id,
                    item.role,
                    item.persona_id,
                    item.authorization_id,
                ),
            )
        ),
        calculation_version=calculation_version,
        evidence_policy_version=EVIDENCE_POLICY_VERSION,
        approval_policy_version=APPROVAL_POLICY_VERSION,
    )
    return AnalysisVersion(
        analysis_id=analysis_id,
        case_id=case.case_id,
        analysis_started_at=analysis_started_at,
        retrieval_window_ends_at=min(
            analysis_started_at + EVIDENCE_RETRIEVAL_WINDOW, created_at
        ),
        created_at=created_at,
        material_hash=analysis_material_hash(material),
        material=material,
        evidence_items=canonical_evidence,
        evidence_validation=evidence_validation,
        response_options=canonical_options,
        approval_satisfactions=approval_satisfactions,
    )
