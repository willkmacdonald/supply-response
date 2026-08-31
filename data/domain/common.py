from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


MONEY_QUANTUM = Decimal("0.01")


def serialize_money(value: Decimal | int) -> str:
    """Serialize monetary values as fixed-scale decimal strings for every API boundary."""
    return format(Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP), ".2f")


Money = Annotated[
    Decimal,
    PlainSerializer(serialize_money, return_type=str, when_used="json"),
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class RuntimeMode(StrEnum):
    LIVE = "live"
    FALLBACK = "fallback"


class CasePurpose(StrEnum):
    AUTOMATED_TEST = "automated_test"
    REHEARSAL = "rehearsal"
    SHOWCASE = "showcase"
