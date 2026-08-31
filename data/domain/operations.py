from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field

from .common import FrozenModel


class QualificationStatus(StrEnum):
    APPROVED = "approved"
    PENDING = "pending"
    NOT_APPROVED = "not_approved"
    CONDITIONAL = "conditional"


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
    component_demand: int | None = Field(default=None, gt=0)
    customer_order_id: str | None = None
    customer_priority: int | None = Field(default=None, ge=1, le=5)
    customer_revenue: Decimal | None = Field(default=None, ge=0)
    customer_margin: Decimal | None = Field(default=None, ge=0)


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


class SupplyReceiptOption(FrozenModel):
    receipt_id: str
    supplier_id: str
    part_id: str
    plant_id: str
    quantity: int = Field(gt=0)
    due_date: date
    incremental_cost_per_unit: Decimal = Field(ge=0)


class InventoryTransfer(FrozenModel):
    transfer_id: str
    part_id: str
    source_plant_id: str
    destination_plant_id: str
    quantity: int = Field(gt=0)
    dispatch_date: date
    arrival_date: date
    incremental_cost_per_unit: Decimal = Field(ge=0)


class QualityQualification(FrozenModel):
    qualification_id: str
    supplier_id: str
    part_id: str
    status: QualificationStatus
    effective_date: date | None = None
    evidence_ref: str
    audit_complete: bool | None = None
    first_article_complete: bool | None = None
    expected_decision_date: date | None = None


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
