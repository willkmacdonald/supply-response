from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class RuntimeMode(StrEnum):
    LIVE = "live"
    FALLBACK = "fallback"


class CasePurpose(StrEnum):
    AUTOMATED_TEST = "automated_test"
    REHEARSAL = "rehearsal"
    SHOWCASE = "showcase"
