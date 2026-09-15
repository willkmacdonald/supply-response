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
    taylor_object_id: str | None = None
    independent_finance_enabled: bool = False
    mail_from_address: str | None = None
    mail_to_address: str | None = None
    mail_send_enabled: bool = False
    workiq_supplier_source_id: str | None = None
    workiq_quality_source_id: str | None = None
    workiq_supplier_sender: str | None = None
    workiq_quality_author_object_id: str | None = None
    workiq_team_id: str | None = None
    workiq_channel_id: str | None = None
    workiq_corpus_version: str | None = None
    workiq_deployment_receipt: str | None = None
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
    power_bi_deployment_receipt: str | None = None
    power_bi_reporting_receipt: str | None = None
    foundry_deployment_receipt: str | None = None

    @model_validator(mode="after")
    def validate_mode_specific_settings(self) -> "Settings":
        if self.runtime_mode is RuntimeMode.FALLBACK:
            if self.independent_finance_enabled:
                raise ValueError("independent Finance requires live mode")
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
        if self.independent_finance_enabled:
            identity_values = (
                self.allowed_tenant_id,
                self.alex_object_id,
                self.taylor_object_id,
            )
            if not all(identity_values):
                raise ValueError(
                    "independent Finance requires tenant, Alex, and Taylor IDs"
                )
            if self.alex_object_id == self.taylor_object_id:
                raise ValueError("Alex and Taylor must be different people")
        if (
            self.mail_from_address
            and not self.mail_send_enabled
            and self.mail_from_address != "agent@willmacdonald.com"
        ):
            raise ValueError("mail capability requires the fixed sender address")
        if self.mail_send_enabled:
            if not self.mail_from_address or not self.mail_to_address:
                raise ValueError(
                    "mail sending requires configured sender and recipient addresses"
                )
            if (
                self.mail_from_address.lower() != self.mail_from_address
                or self.mail_to_address.lower() != self.mail_to_address
                or self.mail_from_address == self.mail_to_address
                or self.mail_from_address != "agent@willmacdonald.com"
                or self.mail_to_address != "will@willmacdonald.com"
            ):
                raise ValueError("mail sending requires the fixed demo addresses")
        return self
