from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from .common import FrozenModel, Money


class ExternalSideEffect(StrEnum):
    EXTERNAL_SENDING = "external_sending"
    PURCHASE_ORDER_CHANGE = "purchase_order_change"
    FINANCIAL_COMMITMENT = "financial_commitment"


class StandingAuthorization(FrozenModel):
    authorization_id: str
    persona_id: str
    role: str
    allowed_option_kinds: tuple[str, ...]
    maximum_response_cost: Money = Field(ge=0)
    corpus_scope: str
    valid_from: datetime
    valid_through: datetime
    forbidden_external_side_effects: tuple[ExternalSideEffect, ...]

    @classmethod
    def taylor_rl001(cls) -> StandingAuthorization:
        scenario_day_zero = datetime.fromisoformat("2026-09-01T09:00:00-05:00")
        return cls(
            authorization_id="RL-AUTH-TAYLOR-FINANCE-1",
            persona_id="RL-PERSONA-TAYLOR",
            role="finance_approver",
            allowed_option_kinds=("expedite", "combined"),
            maximum_response_cost=Decimal("25000"),
            corpus_scope="demo_corpus",
            valid_from=scenario_day_zero,
            valid_through=scenario_day_zero + timedelta(days=14),
            forbidden_external_side_effects=tuple(ExternalSideEffect),
        )

    def permits(self, option: object, scenario_effective_time: datetime) -> bool:
        predicted = getattr(option, "predicted", None)
        option_id = getattr(option, "option_id", "")
        if predicted is None:
            return False
        option_kind = option_id.removeprefix("RL-OPTION-").lower()
        return (
            option_kind in self.allowed_option_kinds
            and predicted.response_cost <= self.maximum_response_cost
            and self.valid_from <= scenario_effective_time <= self.valid_through
            and self.corpus_scope == "demo_corpus"
            and set(self.forbidden_external_side_effects) == set(ExternalSideEffect)
        )


class ApprovalSatisfaction(FrozenModel):
    analysis_id: str
    option_id: str
    authorization_id: str
    persona_id: str
    role: str
    satisfied: bool

    @classmethod
    def from_authorization(
        cls,
        analysis_id: str,
        option: object,
        authorization: StandingAuthorization,
    ) -> ApprovalSatisfaction:
        return cls(
            analysis_id=analysis_id,
            option_id=getattr(option, "option_id"),
            authorization_id=authorization.authorization_id,
            persona_id=authorization.persona_id,
            role=authorization.role,
            satisfied=True,
        )
