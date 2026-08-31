from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import Field

from .common import (
    CasePurpose,
    FrozenModel,
    Money,
    ResponseOptionKind,
    RuntimeMode,
)
from .decisions import (
    ApprovalSatisfaction,
    AuthorizationConditions,
    CorpusScope,
    ExternalSideEffect,
    StandingAuthorization,
)
from .evidence import (
    ActorProvenance,
    AuthorityScope,
    ConflictResolution,
    EvidenceConflict,
    EvidenceItem,
    EvidenceItemValidation,
    EvidenceKind,
    EvidenceRequirement,
    EvidenceSourceSystem,
    EvidenceValidation,
    UncertaintyState,
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
    option_kind: ResponseOptionKind
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
    requested_side_effects: tuple[ExternalSideEffect, ...] = ()


class AnalysisEvidenceMaterial(FrozenModel):
    evidence_id: str
    case_id: str
    kind: EvidenceKind
    authority_scope: tuple[AuthorityScope, ...]
    source_system: EvidenceSourceSystem
    source_id: str
    source_timestamp: datetime | None
    effective_at: datetime | None
    expires_at: datetime | None
    claim: str
    citation_present: bool
    source_metadata_complete: bool
    runtime_mode: RuntimeMode
    synthetic: bool
    requirement: EvidenceRequirement
    uncertainty_state: UncertaintyState
    validation: EvidenceItemValidation

    @classmethod
    def from_evidence(
        cls, item: EvidenceItem, validation: EvidenceItemValidation
    ) -> "AnalysisEvidenceMaterial":
        return cls(
            evidence_id=item.evidence_id,
            case_id=item.case_id,
            kind=item.kind,
            authority_scope=tuple(
                sorted(set(item.authority_scope), key=lambda value: value.value)
            ),
            source_system=item.source_system,
            source_id=item.source_id,
            source_timestamp=item.source_timestamp,
            effective_at=item.effective_at,
            expires_at=item.expires_at,
            claim=item.claim,
            citation_present=item.citation_url is not None,
            source_metadata_complete=bool(
                item.source_id.strip()
                and item.excerpt is not None
                and item.excerpt.strip()
            ),
            runtime_mode=item.runtime_mode,
            synthetic=item.synthetic,
            requirement=item.requirement,
            uncertainty_state=item.uncertainty_state,
            validation=validation,
        )


class AnalysisConflictMaterial(FrozenModel):
    conflict_id: str
    case_id: str
    evidence_ids: tuple[str, ...]
    authority_scope: tuple[AuthorityScope, ...]
    description: str
    feasibility_relevant: bool

    @classmethod
    def from_conflict(cls, item: EvidenceConflict) -> "AnalysisConflictMaterial":
        return cls(
            conflict_id=item.conflict_id,
            case_id=item.case_id,
            evidence_ids=tuple(sorted(set(item.evidence_ids))),
            authority_scope=tuple(
                sorted(set(item.authority_scope), key=lambda value: value.value)
            ),
            description=item.description,
            feasibility_relevant=item.feasibility_relevant,
        )


class AnalysisConflictResolutionMaterial(FrozenModel):
    conflict_id: str
    governing_evidence_id: str
    actor: ActorProvenance
    why: str

    @classmethod
    def from_resolution(
        cls, item: ConflictResolution
    ) -> "AnalysisConflictResolutionMaterial":
        actor = item.actor.model_copy(
            update={"roles": tuple(sorted(set(item.actor.roles)))}
        )
        return cls(
            conflict_id=item.conflict_id,
            governing_evidence_id=item.governing_evidence_id,
            actor=actor,
            why=item.why,
        )


class AnalysisAuthorizationConditionsMaterial(FrozenModel):
    allowed_option_kinds: tuple[ResponseOptionKind, ...]
    maximum_response_cost: Money
    allowed_corpora: tuple[CorpusScope, ...]
    allowed_template_ids: tuple[str, ...]
    allowed_case_purposes: tuple[CasePurpose, ...]
    valid_from: datetime
    valid_through: datetime
    forbidden_external_side_effects: tuple[ExternalSideEffect, ...]

    @classmethod
    def from_conditions(
        cls, item: AuthorizationConditions
    ) -> "AnalysisAuthorizationConditionsMaterial":
        return cls(
            allowed_option_kinds=tuple(
                sorted(set(item.allowed_option_kinds), key=lambda value: value.value)
            ),
            maximum_response_cost=item.maximum_response_cost,
            allowed_corpora=tuple(
                sorted(set(item.allowed_corpora), key=lambda value: value.value)
            ),
            allowed_template_ids=tuple(sorted(set(item.allowed_template_ids))),
            allowed_case_purposes=tuple(
                sorted(set(item.allowed_case_purposes), key=lambda value: value.value)
            ),
            valid_from=item.valid_from,
            valid_through=item.valid_through,
            forbidden_external_side_effects=tuple(
                sorted(
                    set(item.forbidden_external_side_effects),
                    key=lambda value: value.value,
                )
            ),
        )


class AnalysisStandingAuthorizationMaterial(FrozenModel):
    authorization_id: str
    persona_id: str
    role: str
    conditions: AnalysisAuthorizationConditionsMaterial

    @classmethod
    def from_authorization(
        cls, item: StandingAuthorization
    ) -> "AnalysisStandingAuthorizationMaterial":
        return cls(
            authorization_id=item.authorization_id,
            persona_id=item.persona_id,
            role=item.role,
            conditions=AnalysisAuthorizationConditionsMaterial.from_conditions(
                item.conditions
            ),
        )


class AnalysisApprovalTargetMaterial(FrozenModel):
    case_id: str
    template_id: str
    purpose: CasePurpose
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime
    corpus: CorpusScope
    total_response_cost: Money
    requested_side_effects: tuple[ExternalSideEffect, ...]


class AnalysisApprovalMaterial(FrozenModel):
    option_id: str
    authorization_id: str
    persona_id: str
    role: str
    satisfied: bool
    target: AnalysisApprovalTargetMaterial
    authorization_conditions: AnalysisAuthorizationConditionsMaterial

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
            target=AnalysisApprovalTargetMaterial(
                case_id=item.target.case.case_id,
                template_id=item.target.case.template_id,
                purpose=item.target.case.purpose,
                runtime_mode=item.target.case.runtime_mode,
                scenario_effective_time=item.target.scenario_effective_time,
                corpus=item.target.corpus,
                total_response_cost=item.target.total_response_cost,
                requested_side_effects=tuple(
                    sorted(
                        set(item.target.requested_side_effects),
                        key=lambda value: value.value,
                    )
                ),
            ),
            authorization_conditions=(
                AnalysisAuthorizationConditionsMaterial.from_conditions(
                    item.authorization_conditions
                )
            ),
        )


class AnalysisResponseOptionMaterial(FrozenModel):
    option_id: str
    option_kind: ResponseOptionKind
    executable: bool
    active_mitigation: bool
    predicted: PredictedOutcome | None
    assumptions: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    blocking_codes: tuple[str, ...]
    prerequisite_roles: tuple[str, ...]
    source_data_lineage: tuple[str, ...]
    approval_burden: int
    execution_risk: int
    requested_side_effects: tuple[ExternalSideEffect, ...]

    @classmethod
    def from_option(cls, item: ResponseOption) -> "AnalysisResponseOptionMaterial":
        predicted = item.predicted
        if predicted is not None:
            predicted = predicted.model_copy(
                update={
                    "protected_customer_order_ids": tuple(
                        sorted(set(predicted.protected_customer_order_ids))
                    )
                }
            )
        return cls(
            option_id=item.option_id,
            option_kind=item.option_kind,
            executable=item.executable,
            active_mitigation=item.active_mitigation,
            predicted=predicted,
            assumptions=tuple(sorted(set(item.assumptions))),
            evidence_ids=tuple(sorted(set(item.evidence_ids))),
            blocking_codes=tuple(sorted(set(item.blocking_codes))),
            prerequisite_roles=tuple(sorted(set(item.prerequisite_roles))),
            source_data_lineage=tuple(sorted(set(item.source_data_lineage))),
            approval_burden=item.approval_burden,
            execution_risk=item.execution_risk,
            requested_side_effects=tuple(
                sorted(set(item.requested_side_effects), key=lambda value: value.value)
            ),
        )


class AnalysisMaterial(FrozenModel):
    case_id: str
    template_id: str
    case_purpose: CasePurpose
    runtime_mode: RuntimeMode
    corpus: CorpusScope
    scenario_effective_time: datetime
    operational_snapshot_json: str
    required_authority_scope: tuple[AuthorityScope, ...]
    evidence: tuple[AnalysisEvidenceMaterial, ...]
    conflicts: tuple[AnalysisConflictMaterial, ...]
    conflict_resolutions: tuple[AnalysisConflictResolutionMaterial, ...]
    evidence_validation: EvidenceValidation
    response_options: tuple[AnalysisResponseOptionMaterial, ...]
    standing_authorizations: tuple[AnalysisStandingAuthorizationMaterial, ...]
    approval_satisfactions: tuple[AnalysisApprovalMaterial, ...]
    calculation_version: str
    evidence_policy_version: str
    approval_policy_version: str


class AnalysisVersion(FrozenModel):
    analysis_id: str
    case_id: str
    analysis_started_at: datetime
    retrieval_window_ends_at: datetime
    created_at: datetime
    material_hash: str
    material: AnalysisMaterial
    evidence_items: tuple[EvidenceItem, ...]
    evidence_validation: EvidenceValidation
    response_options: tuple[ResponseOption, ...]
    approval_satisfactions: tuple[ApprovalSatisfaction, ...]
