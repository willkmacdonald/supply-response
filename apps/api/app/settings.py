from datetime import datetime

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from data.domain import RuntimeMode
from data.synthetic.rl001 import SCENARIO_EFFECTIVE_TIME


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUPPLY_RESPONSE_",
        extra="ignore",
    )

    runtime_mode: RuntimeMode
    database_url: str
    scenario_effective_time: datetime = SCENARIO_EFFECTIVE_TIME
    allowed_tenant_id: str | None = None
    tenant_domain: str = "willmacdonald.com"
    frontend_origin: str = "http://localhost:5173"

    @model_validator(mode="after")
    def validate_mode_specific_settings(self) -> "Settings":
        if self.runtime_mode is RuntimeMode.LIVE and not self.allowed_tenant_id:
            raise ValueError("live mode requires SUPPLY_RESPONSE_ALLOWED_TENANT_ID")
        return self
