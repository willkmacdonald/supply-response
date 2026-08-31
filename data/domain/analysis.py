from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from pydantic import Field

from .common import FrozenModel, Money
from .decisions import ApprovalSatisfaction
from .evidence import (
    ConflictResolution,
    EvidenceItem,
    EvidenceKind,
    EvidenceValidation,
)


class TimedQuantity(FrozenModel):
    date: date
    quantity: int
    source_id: str


class ProjectionPoint(FrozenModel):
    date: date
    receipts: int
    transfers: int
    demand: int
    projected_balance: int


class CalculationMetadata(FrozenModel):
    scenario_id: str
    calculation_version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assumptions: tuple[str, ...] = ()
    source_data_lineage: tuple[str, ...] = ()


class ExposureResult(FrozenModel):
    metadata: CalculationMetadata
    usable_inventory: int
    projected_inventory: tuple[ProjectionPoint, ...]
    first_stockout_date: date | None
    maximum_shortage_quantity: int
    affected_production_order_ids: tuple[str, ...]
    affected_customer_order_line_ids: tuple[str, ...]
    revenue_at_risk: Money
    margin_at_risk: Money
    otif_lines_at_risk: int
    response_cost: Money = Decimal("0")
    revenue_protected: Money = Decimal("0")
    remaining_uncertainty: tuple[str, ...] = ()


class PredictedOutcome(FrozenModel):
    uncovered_part_demand: int
    otif_loss_percentage: int
    revenue_at_risk: Money
    margin_at_risk: Money
    response_cost: Money
    protected_customer_order_ids: tuple[str, ...] = ()


class ResponseOption(FrozenModel):
    option_id: str
    name: str
    executable: bool
    active_mitigation: bool
    predicted: PredictedOutcome | None
    assumptions: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    blocking_codes: tuple[str, ...] = ()
    prerequisite_roles: tuple[str, ...] = ()
    source_data_lineage: tuple[str, ...] = ()
    approval_burden: int = 0
    execution_risk: int = 0


class AnalysisEvidenceMaterial(FrozenModel):
    evidence_id: str
    case_id: str
    kind: EvidenceKind
    authority_scope: tuple[str, ...]
    source_system: str
    source_id: str
    source_timestamp: datetime | None
    effective_at: datetime | None
    expires_at: datetime | None
    claim: str
    citation_present: bool
    runtime_mode: str
    synthetic: bool

    @classmethod
    def from_evidence(cls, item: EvidenceItem) -> "AnalysisEvidenceMaterial":
        return cls(
            evidence_id=item.evidence_id,
            case_id=item.case_id,
            kind=item.kind,
            authority_scope=tuple(sorted(item.authority_scope)),
            source_system=item.source_system,
            source_id=item.source_id,
            source_timestamp=item.source_timestamp,
            effective_at=item.effective_at,
            expires_at=item.expires_at,
            claim=item.claim,
            citation_present=item.citation_url is not None,
            runtime_mode=item.runtime_mode.value,
            synthetic=item.synthetic,
        )


class AnalysisApprovalMaterial(FrozenModel):
    option_id: str
    authorization_id: str
    persona_id: str
    role: str
    satisfied: bool

    @classmethod
    def from_satisfaction(
        cls, item: ApprovalSatisfaction
    ) -> "AnalysisApprovalMaterial":
        return cls(
            option_id=item.option_id,
            authorization_id=item.authorization_id,
            persona_id=item.persona_id,
            role=item.role,
            satisfied=item.satisfied,
        )


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    return value


class AnalysisMaterial(FrozenModel):
    case_id: str
    runtime_mode: str
    scenario_effective_time: datetime
    operational_snapshot: dict[str, Any]
    evidence: tuple[AnalysisEvidenceMaterial, ...]
    response_options: tuple[ResponseOption, ...]
    approval_satisfactions: tuple[AnalysisApprovalMaterial, ...]
    conflict_resolutions: tuple[ConflictResolution, ...]
    calculation_version: str
    evidence_policy_version: str
    approval_policy_version: str

    @classmethod
    def from_inputs(
        cls,
        *,
        case_id: str,
        runtime_mode: object,
        scenario_effective_time: datetime,
        operational_snapshot: object,
        evidence_items: tuple[EvidenceItem, ...],
        response_options: tuple[ResponseOption, ...],
        approval_satisfactions: tuple[ApprovalSatisfaction, ...],
        conflict_resolutions: tuple[ConflictResolution, ...],
        calculation_version: str,
        evidence_policy_version: str,
        approval_policy_version: str,
    ) -> "AnalysisMaterial":
        snapshot = getattr(operational_snapshot, "model_dump")(mode="python")
        return cls(
            case_id=case_id,
            runtime_mode=getattr(runtime_mode, "value", str(runtime_mode)),
            scenario_effective_time=scenario_effective_time,
            operational_snapshot=_canonical_value(snapshot),
            evidence=tuple(
                AnalysisEvidenceMaterial.from_evidence(item)
                for item in sorted(evidence_items, key=lambda item: item.evidence_id)
            ),
            response_options=tuple(
                sorted(response_options, key=lambda item: item.option_id)
            ),
            approval_satisfactions=tuple(
                AnalysisApprovalMaterial.from_satisfaction(item)
                for item in sorted(
                    approval_satisfactions,
                    key=lambda item: (
                        item.role,
                        item.persona_id,
                        item.authorization_id,
                    ),
                )
            ),
            conflict_resolutions=tuple(
                sorted(conflict_resolutions, key=lambda item: item.conflict_id)
            ),
            calculation_version=calculation_version,
            evidence_policy_version=evidence_policy_version,
            approval_policy_version=approval_policy_version,
        )


class AnalysisVersion(FrozenModel):
    analysis_id: str
    case_id: str
    created_at: datetime
    material_hash: str
    material: AnalysisMaterial
    evidence_items: tuple[EvidenceItem, ...]
    evidence_validation: EvidenceValidation
    response_options: tuple[ResponseOption, ...]
    approval_satisfactions: tuple[ApprovalSatisfaction, ...]
