import hashlib
from datetime import datetime

from data.domain.analysis import AnalysisMaterial, AnalysisVersion, ResponseOption
from data.domain.common import RuntimeMode
from data.domain.decisions import ApprovalSatisfaction, StandingAuthorization
from data.domain.evidence import ConflictResolution, EvidenceConflict, EvidenceItem
from services.policy.approvals import evaluate_approval_satisfaction
from services.policy.evidence import validate_required_evidence


EVIDENCE_POLICY_VERSION = "evidence-policy-v1"
APPROVAL_POLICY_VERSION = "standing-authorization-v1"


def analysis_material_hash(payload: AnalysisMaterial) -> str:
    canonical = payload.model_dump_json(
        exclude_none=False,
        by_alias=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_analysis_version(
    *,
    analysis_id: str,
    case_id: str,
    operational_snapshot: object,
    evidence_items: tuple[EvidenceItem, ...],
    response_options: tuple[ResponseOption, ...],
    standing_authorizations: tuple[StandingAuthorization, ...],
    runtime_mode: RuntimeMode,
    scenario_effective_time: datetime,
    created_at: datetime,
    calculation_version: str,
    conflicts: tuple[EvidenceConflict, ...] = (),
    conflict_resolutions: tuple[ConflictResolution, ...] = (),
    required_authority_scope: tuple[str, ...] = (),
    evidence_policy_version: str = EVIDENCE_POLICY_VERSION,
    approval_policy_version: str = APPROVAL_POLICY_VERSION,
) -> AnalysisVersion:
    evidence_validation = validate_required_evidence(
        evidence_items,
        runtime_mode=runtime_mode,
        scenario_effective_time=scenario_effective_time,
        required_authority_scope=required_authority_scope,
        conflicts=conflicts,
        conflict_resolutions=conflict_resolutions,
    )
    approval_satisfactions: tuple[ApprovalSatisfaction, ...] = tuple(
        satisfaction
        for option in sorted(response_options, key=lambda item: item.option_id)
        for satisfaction in evaluate_approval_satisfaction(
            option=option,
            analysis_id=analysis_id,
            standing_authorizations=standing_authorizations,
            scenario_effective_time=scenario_effective_time,
        )
    )
    material = AnalysisMaterial.from_inputs(
        case_id=case_id,
        runtime_mode=runtime_mode,
        scenario_effective_time=scenario_effective_time,
        operational_snapshot=operational_snapshot,
        evidence_items=evidence_items,
        response_options=response_options,
        approval_satisfactions=approval_satisfactions,
        conflict_resolutions=conflict_resolutions,
        calculation_version=calculation_version,
        evidence_policy_version=evidence_policy_version,
        approval_policy_version=approval_policy_version,
    )
    return AnalysisVersion(
        analysis_id=analysis_id,
        case_id=case_id,
        created_at=created_at,
        material_hash=analysis_material_hash(material),
        material=material,
        evidence_items=evidence_items,
        evidence_validation=evidence_validation,
        response_options=response_options,
        approval_satisfactions=approval_satisfactions,
    )
