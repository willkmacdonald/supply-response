"""Temporary compatibility exports for the pre-canonical import path."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from data.domain import (
    BomComponent,
    CalculationMetadata,
    Customer,
    CustomerOrder,
    Disruption,
    ExposureResult,
    FrozenModel,
    InventoryPosition,
    Part,
    ProductionOrder,
    ProjectionPoint,
    PurchaseOrder,
    QualificationStatus,
    QualityQualification,
    Supplier,
    SupplierPart,
    TimedQuantity,
    TransportOption,
)

__all__ = [
    "ActionLedgerRecord",
    "BomComponent",
    "CalculationMetadata",
    "CaseStatus",
    "Customer",
    "CustomerOrder",
    "Disruption",
    "ExposureResult",
    "FrozenModel",
    "InventoryPosition",
    "OutcomeHistory",
    "Part",
    "ProductionOrder",
    "ProjectionPoint",
    "PurchaseOrder",
    "QualificationStatus",
    "QualityQualification",
    "ResponseScenario",
    "Supplier",
    "SupplierPart",
    "SupplyResponseCase",
    "TimedQuantity",
    "TransportOption",
]


# legacy: remove in Task 4
class CaseStatus(StrEnum):
    OPEN = "open"
    ANALYZED = "analyzed"
    APPROVED = "approved"
    REJECTED = "rejected"


# legacy: remove in Task 4
class ResponseScenario(FrozenModel):
    scenario_id: str
    disruption_id: str
    name: str
    executable: bool
    constraint_violations: tuple[str, ...] = ()
    constraint_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    required_approver_roles: tuple[str, ...] = ()
    response_cost: Decimal = Decimal("0")
    revenue_protected: Decimal = Decimal("0")
    remaining_uncertainty: tuple[str, ...] = ()


# legacy: remove in Task 4
class ActionLedgerRecord(FrozenModel):
    action_id: str
    case_id: str
    scenario_id: str
    decision: Literal["approved", "rejected"]
    decided_at: datetime
    scenario_evidence_refs: tuple[str, ...]
    approval_evidence_refs: tuple[str, ...]
    calculation_version: str
    source_data_lineage: tuple[str, ...]


# legacy: remove in Task 4
class OutcomeHistory(FrozenModel):
    outcome_id: str
    case_id: str
    scenario_id: str
    predicted_revenue_protected: Decimal
    actual_revenue_protected: Decimal | None = None


# legacy: remove in Task 4
class SupplyResponseCase(BaseModel):
    case_id: str
    disruption: Disruption
    status: CaseStatus = CaseStatus.OPEN
    exposure: ExposureResult | None = None
    scenarios: list[ResponseScenario] = Field(default_factory=list)
    selected_scenario_id: str | None = None
