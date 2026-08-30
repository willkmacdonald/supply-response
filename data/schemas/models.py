from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class QualificationStatus(StrEnum):
    APPROVED = "approved"
    NOT_APPROVED = "not_approved"
    CONDITIONAL = "conditional"


class CaseStatus(StrEnum):
    OPEN = "open"
    ANALYZED = "analyzed"
    APPROVED = "approved"
    REJECTED = "rejected"


class Supplier(FrozenModel):
    supplier_id: str
    name: str


class Part(FrozenModel):
    part_id: str
    description: str
    unit_cost: Decimal = Field(ge=0)


class SupplierPart(FrozenModel):
    supplier_id: str
    part_id: str
    lead_time_days: int = Field(ge=0)
    is_primary: bool = False


class PurchaseOrder(FrozenModel):
    po_line_id: str
    supplier_id: str
    part_id: str
    plant_id: str
    quantity: int = Field(gt=0)
    due_date: date
    confirmed: bool = True


class InventoryPosition(FrozenModel):
    inventory_id: str
    part_id: str
    plant_id: str
    on_hand: int = Field(ge=0)
    quality_hold: int = Field(ge=0)
    protected_allocation: int = Field(ge=0)


class BomComponent(FrozenModel):
    bom_id: str
    product_id: str
    component_part_id: str
    quantity_per: int = Field(gt=0)


class ProductionOrder(FrozenModel):
    production_order_id: str
    product_id: str
    plant_id: str
    quantity: int = Field(gt=0)
    due_date: date
    status: Literal["open", "released"] = "open"


class Customer(FrozenModel):
    customer_id: str
    name: str
    priority: int = Field(ge=1, le=5)


class CustomerOrder(FrozenModel):
    customer_order_line_id: str
    customer_id: str
    product_id: str
    plant_id: str
    production_order_id: str | None = None
    quantity: int = Field(gt=0)
    due_date: date
    unit_revenue: Decimal = Field(ge=0)
    unit_margin: Decimal = Field(ge=0)


class TransportOption(FrozenModel):
    transport_option_id: str
    supplier_id: str
    plant_id: str
    mode: str
    max_quantity: int = Field(gt=0)
    incremental_cost_per_unit: Decimal = Field(ge=0)
    transit_days: int = Field(ge=0)


class QualityQualification(FrozenModel):
    qualification_id: str
    supplier_id: str
    part_id: str
    status: QualificationStatus
    effective_date: date | None = None
    evidence_ref: str


class Disruption(FrozenModel):
    disruption_id: str
    supplier_id: str
    po_line_id: str
    part_id: str
    plant_id: str
    original_quantity: int = Field(gt=0)
    original_due_date: date
    partial_quantity: int = Field(ge=0)
    partial_due_date: date | None = None
    recovery_date: date | None = None
    source_ref: str


class ResponseScenario(FrozenModel):
    scenario_id: str
    disruption_id: str
    name: str
    executable: bool
    constraint_violations: tuple[str, ...] = ()
    response_cost: Decimal = Decimal("0")
    revenue_protected: Decimal = Decimal("0")
    remaining_uncertainty: tuple[str, ...] = ()


class ActionLedgerRecord(FrozenModel):
    action_id: str
    case_id: str
    scenario_id: str
    decision: Literal["approved", "rejected"]
    decided_at: datetime
    evidence_refs: tuple[str, ...]


class OutcomeHistory(FrozenModel):
    outcome_id: str
    case_id: str
    scenario_id: str
    predicted_revenue_protected: Decimal
    actual_revenue_protected: Decimal | None = None


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
    revenue_at_risk: Decimal
    margin_at_risk: Decimal
    otif_lines_at_risk: int
    response_cost: Decimal = Decimal("0")
    revenue_protected: Decimal = Decimal("0")
    remaining_uncertainty: tuple[str, ...] = ()


class SupplyResponseCase(BaseModel):
    case_id: str
    disruption: Disruption
    status: CaseStatus = CaseStatus.OPEN
    exposure: ExposureResult | None = None
    scenarios: list[ResponseScenario] = Field(default_factory=list)
    selected_scenario_id: str | None = None
