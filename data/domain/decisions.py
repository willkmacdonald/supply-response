from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import Field

from .cases import CaseInstance
from .common import CasePurpose, FrozenModel, Money, ResponseOptionKind

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
