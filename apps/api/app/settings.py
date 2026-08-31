from datetime import datetime
from typing import Literal

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
    database_url: str | None = None
    scenario_effective_time: datetime = SCENARIO_EFFECTIVE_TIME
    allowed_tenant_id: str | None = None
    fabric_sql_server: str | None = None
    fabric_sql_database: str | None = None
    credential_mode: Literal["azure_cli", "managed_identity"] | None = None
    tenant_domain: str = "willmacdonald.com"
    frontend_origin: str = "http://localhost:5173"
    automated_test_faults_enabled: bool = False
    api_client_id: str | None = None
    entra_client_secret: str | None = None
    alex_object_id: str | None = None
    workiq_supplier_source_id: str | None = None
    workiq_quality_source_id: str | None = None
    tenant_sharepoint_host: str | None = None
    foundry_project_endpoint: str | None = None
    foundry_signal_agent_name: str | None = None
    foundry_signal_agent_version: str | None = None
    foundry_context_agent_name: str | None = None
    foundry_context_agent_version: str | None = None
    foundry_decision_agent_name: str | None = None
    foundry_decision_agent_version: str | None = None
    power_bi_report_url: str | None = None
    fabric_citation_base_url: str | None = None

    @model_validator(mode="after")
    def validate_mode_specific_settings(self) -> "Settings":
        if self.runtime_mode is RuntimeMode.FALLBACK:
            if not self.database_url:
                raise ValueError("fallback mode requires SUPPLY_RESPONSE_DATABASE_URL")
            return self

        missing: list[str] = []
        if self.credential_mode in (None, "azure_cli") and not self.allowed_tenant_id:
            missing.append("SUPPLY_RESPONSE_ALLOWED_TENANT_ID")
        if not self.fabric_sql_server:
            missing.append("SUPPLY_RESPONSE_FABRIC_SQL_SERVER")
        if not self.fabric_sql_database:
            missing.append("SUPPLY_RESPONSE_FABRIC_SQL_DATABASE")
        if self.credential_mode is None:
            missing.append("SUPPLY_RESPONSE_CREDENTIAL_MODE")
        if missing:
            raise ValueError(f"live mode requires {', '.join(missing)}")
        return self
