from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import Field, TypeAdapter, field_validator, model_validator

from .cases import CaseInstance
from .common import (
    CasePurpose,
    FrozenModel,
    Money,
    ResponseOptionKind,
    RuntimeMode,
)
from .evidence import IdentitySource

if TYPE_CHECKING:
    from .analysis import ResponseOption


class ExternalSideEffect(StrEnum):
    EXTERNAL_SENDING = "external_sending"
    PURCHASE_ORDER_CHANGE = "purchase_order_change"
    FINANCIAL_COMMITMENT = "financial_commitment"


class CorpusScope(StrEnum):
    DEMO_CORPUS = "demo_corpus"
    REAL_BUSINESS = "real_business"
    UNSPECIFIED = "unspecified"


class AuthorizationConditions(FrozenModel):
    allowed_option_kinds: tuple[ResponseOptionKind, ...]
    maximum_response_cost: Money = Field(ge=0)
    allowed_corpora: tuple[CorpusScope, ...]
    allowed_template_ids: tuple[str, ...]
    allowed_case_purposes: tuple[CasePurpose, ...]
    valid_from: datetime
    valid_through: datetime
    forbidden_external_side_effects: tuple[ExternalSideEffect, ...]


class ApprovalTarget(FrozenModel):
    case: CaseInstance
    corpus: CorpusScope
    scenario_effective_time: datetime
    total_response_cost: Money = Field(ge=0)
    requested_side_effects: tuple[ExternalSideEffect, ...] = ()


class StandingAuthorization(FrozenModel):
    authorization_id: str
    persona_id: str
    role: str
    conditions: AuthorizationConditions

    @classmethod
    def taylor_rl001(cls) -> StandingAuthorization:
        scenario_day_zero = datetime.fromisoformat("2026-09-01T09:00:00-05:00")
        return cls(
            authorization_id="RL-AUTH-TAYLOR-FINANCE-1",
            persona_id="RL-PERSONA-TAYLOR",
            role="finance_approver",
            conditions=AuthorizationConditions(
                allowed_option_kinds=(
                    ResponseOptionKind.EXPEDITE,
                    ResponseOptionKind.COMBINED,
                ),
                maximum_response_cost=Decimal("25000"),
                allowed_corpora=(CorpusScope.DEMO_CORPUS,),
                allowed_template_ids=("RL-001",),
                allowed_case_purposes=tuple(CasePurpose),
                valid_from=scenario_day_zero,
                valid_through=scenario_day_zero + timedelta(days=14),
                forbidden_external_side_effects=tuple(ExternalSideEffect),
            ),
        )

    def permits(self, option: ResponseOption, target: ApprovalTarget) -> bool:
        predicted = option.predicted
        conditions = self.conditions
        if predicted is None:
            return False
        return (
            option.option_kind in conditions.allowed_option_kinds
            and target.corpus in conditions.allowed_corpora
            and target.case.template_id in conditions.allowed_template_ids
            and target.case.purpose in conditions.allowed_case_purposes
            and target.case.scenario_effective_time == target.scenario_effective_time
            and target.total_response_cost == predicted.response_cost
            and target.requested_side_effects == option.requested_side_effects
            and target.total_response_cost <= conditions.maximum_response_cost
            and conditions.valid_from
            <= target.scenario_effective_time
            <= conditions.valid_through
            and not set(target.requested_side_effects).intersection(
                conditions.forbidden_external_side_effects
            )
        )


class ApprovalSatisfaction(FrozenModel):
    analysis_id: str
    option_id: str
    authorization_id: str
    persona_id: str
    role: str
    satisfied: bool
    target: ApprovalTarget
    authorization_conditions: AuthorizationConditions

    @classmethod
    def from_authorization(
        cls,
        analysis_id: str,
        option: ResponseOption,
        authorization: StandingAuthorization,
        target: ApprovalTarget,
    ) -> ApprovalSatisfaction:
        if not authorization.permits(option, target):
            raise ValueError("Standing Authorization does not permit this target.")
        return cls(
            analysis_id=analysis_id,
            option_id=option.option_id,
            authorization_id=authorization.authorization_id,
            persona_id=authorization.persona_id,
            role=authorization.role,
            satisfied=True,
            target=target,
            authorization_conditions=authorization.conditions,
        )


class DecisionKind(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class IdentitySnapshot(FrozenModel):
    persona_id: str
    effective_roles: tuple[str, ...]
    identity_source: IdentitySource
    source_id: str
    display_name: str | None = None
    user_principal_name: str | None = None

    @field_validator("effective_roles")
    @classmethod
    def canonicalize_roles(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class RecordDecisionCommand(FrozenModel):
    case_id: str
    analysis_id: str
    selected_option_id: str | None
    kind: DecisionKind
    idempotency_key: str
    rejection_reason: str | None = None

    @field_validator("case_id", "analysis_id", "idempotency_key")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be nonblank")
        return value

    @model_validator(mode="after")
    def validate_decision_shape(self) -> RecordDecisionCommand:
        if self.kind is DecisionKind.APPROVED:
            if self.selected_option_id is None:
                raise ValueError("approval requires selected_option_id")
            if self.rejection_reason is not None:
                raise ValueError("approval cannot include rejection_reason")
        else:
            if self.selected_option_id is not None:
                raise ValueError("rejection cannot include selected_option_id")
            if self.rejection_reason is None or not self.rejection_reason.strip():
                raise ValueError("rejection requires a nonblank rejection_reason")
        return self


class CaseProjection(FrozenModel):
    case: CaseInstance
    current_analysis_id: str | None = None
    current_analysis_hash: str | None = None
    current_decision_id: str | None = None


class Decision(FrozenModel):
    decision_id: str
    case_id: str
    analysis_id: str
    analysis_material_hash: str
    idempotency_key: str
    request_fingerprint: str
    kind: DecisionKind
    selected_option_id: str | None
    selected_option: Any | None
    evidence_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]
    prerequisite_roles: tuple[str, ...]
    comparator_trace: Any | None
    calculation_version: str
    evidence_policy_version: str
    approval_policy_version: str
    ranking_policy_version: str
    runtime_mode: RuntimeMode
    scenario_effective_time: datetime
    approval_satisfactions: tuple[ApprovalSatisfaction, ...]
    actor: IdentitySnapshot
    rejection_reason: str | None
    decided_at: datetime

    @field_validator("decided_at", mode="after")
    @classmethod
    def canonicalize_decided_at(cls, value: datetime) -> datetime:
        """Match the canonical JSON representation returned by persistence."""
        return TypeAdapter(datetime).validate_json(json.dumps(value.isoformat()))

    @field_validator("selected_option", mode="before")
    @classmethod
    def decode_selected_option(cls, value: Any) -> Any:
        if value is None:
            return None
        from .analysis import ResponseOption

        return ResponseOption.model_validate(value)

    @field_validator("comparator_trace", mode="before")
    @classmethod
    def decode_comparator_trace(cls, value: Any) -> Any:
        from .analysis import RankingResult

        if value is None:
            return None
        if isinstance(value, RankingResult):
            return value
        # Preserve numeric comparator values across JSON persistence.  The
        # ``Decimal | str`` trace value needs JSON-mode validation to distinguish
        # numeric strings from option identifiers.
        return RankingResult.model_validate_json(json.dumps(value, default=str))

    @model_validator(mode="after")
    def validate_immutable_shape(self) -> Decision:
        if self.kind is DecisionKind.REJECTED:
            if (
                self.selected_option_id is not None
                or self.selected_option is not None
                or self.evidence_ids
                or self.assumptions
                or self.constraints
                or self.prerequisite_roles
                or self.comparator_trace is not None
                or self.approval_satisfactions
                or self.rejection_reason is None
                or not self.rejection_reason.strip()
            ):
                raise ValueError("rejection Decision cannot contain approval material")
            return self

        option = self.selected_option
        if (
            self.selected_option_id is None
            or option is None
            or option.option_id != self.selected_option_id
            or self.comparator_trace is None
            or self.rejection_reason is not None
            or not self.approval_satisfactions
        ):
            raise ValueError(
                "approved Decision requires a selected option and approvals"
            )
        if (
            self.evidence_ids != option.evidence_ids
            or self.assumptions != option.assumptions
            or self.constraints != option.blocking_codes
            or self.prerequisite_roles != option.prerequisite_roles
        ):
            raise ValueError("Decision option snapshot fields are inconsistent")
        seen_roles: set[str] = set()
        for satisfaction in self.approval_satisfactions:
            if (
                not satisfaction.satisfied
                or satisfaction.analysis_id != self.analysis_id
                or satisfaction.option_id != self.selected_option_id
                or satisfaction.role in seen_roles
                or satisfaction.target.case.case_id != self.case_id
                or satisfaction.target.case.runtime_mode is not self.runtime_mode
                or satisfaction.target.scenario_effective_time
                != self.scenario_effective_time
                or satisfaction.target.requested_side_effects
                != option.requested_side_effects
                or option.predicted is None
                or satisfaction.target.total_response_cost
                != option.predicted.response_cost
            ):
                raise ValueError("Decision Approval Satisfaction is inconsistent")
            seen_roles.add(satisfaction.role)
        return self

    @classmethod
    def from_command(
        cls,
        command: RecordDecisionCommand,
        actor: IdentitySnapshot,
        analysis: Any,
        satisfactions: tuple[ApprovalSatisfaction, ...],
        *,
        request_fingerprint: str,
        decided_at: datetime | None = None,
    ) -> Decision:
        option = next(
            (
                item
                for item in analysis.response_options
                if item.option_id == command.selected_option_id
            ),
            None,
        )
        return cls(
            decision_id=f"RL-DECISION-{uuid4()}",
            case_id=command.case_id,
            analysis_id=command.analysis_id,
            analysis_material_hash=analysis.material_hash,
            idempotency_key=command.idempotency_key,
            request_fingerprint=request_fingerprint,
            kind=command.kind,
            selected_option_id=command.selected_option_id,
            selected_option=option,
            evidence_ids=option.evidence_ids if option is not None else (),
            assumptions=option.assumptions if option is not None else (),
            constraints=option.blocking_codes if option is not None else (),
            prerequisite_roles=(
                option.prerequisite_roles if option is not None else ()
            ),
            comparator_trace=(
                analysis.ranking if command.kind is DecisionKind.APPROVED else None
            ),
            calculation_version=analysis.material.calculation_version,
            evidence_policy_version=analysis.material.evidence_policy_version,
            approval_policy_version=analysis.material.approval_policy_version,
            ranking_policy_version=analysis.ranking.policy_version,
            runtime_mode=analysis.material.runtime_mode,
            scenario_effective_time=analysis.material.scenario_effective_time,
            approval_satisfactions=satisfactions,
            actor=actor,
            rejection_reason=command.rejection_reason,
            decided_at=decided_at or datetime.now(UTC),
        )
