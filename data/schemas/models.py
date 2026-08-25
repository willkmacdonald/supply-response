"""Pydantic v2 models for the Supply Response synthetic data model.

Every table described in the project brief is represented here. The schemas are
intentionally portable: the same field names are used by the SQLite fixtures,
the deterministic calculation services and (later) the Fabric tables.

All data is fictional. Business keys use the ``RL-`` prefix.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import ClassVar, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"
ID_PREFIX = "RL-"


class SupplyResponseModel(BaseModel):
    """Base model with shared configuration."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #
class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PartType(str, Enum):
    RAW = "raw"
    COMPONENT = "component"
    SUB_ASSEMBLY = "sub_assembly"
    FINISHED_GOOD = "finished_good"


class POStatus(str, Enum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    DELAYED = "delayed"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class ProductionOrderStatus(str, Enum):
    PLANNED = "planned"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class CustomerOrderStatus(str, Enum):
    OPEN = "open"
    ALLOCATED = "allocated"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


class TransportMode(str, Enum):
    AIR = "air"
    OCEAN = "ocean"
    ROAD = "road"
    RAIL = "rail"
    COURIER = "courier"


class QualificationStatus(str, Enum):
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    NOT_APPROVED = "not_approved"
    EXPIRED = "expired"


class DisruptionStatus(str, Enum):
    NEW = "new"
    ANALYZING = "analyzing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class DisruptionSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScenarioType(str, Enum):
    ACCEPT_DELAY = "accept_delay"
    EXPEDITE_PARTIAL = "expedite_partial"
    TRANSFER_INVENTORY = "transfer_inventory"
    RESEQUENCE_PRODUCTION = "resequence_production"
    ALTERNATE_SOURCE = "alternate_source"
    COMBINED = "combined"


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


# --------------------------------------------------------------------------- #
# Core master data
# --------------------------------------------------------------------------- #
class Supplier(SupplyResponseModel):
    supplier_id: str = Field(pattern=r"^RL-SUP-\d{4}$")
    supplier_name: str
    country: str
    region: str
    risk_tier: RiskTier = RiskTier.LOW
    on_time_delivery_rate: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    preferred: bool = False


class Part(SupplyResponseModel):
    part_id: str = Field(pattern=r"^RL-PART-\d{5}$")
    part_number: str
    description: str
    part_type: PartType
    unit_of_measure: str = "EA"
    standard_cost: float = Field(ge=0.0)
    lead_time_days: int = Field(ge=0)
    safety_stock: int = Field(ge=0)
    critical: bool = False


class SupplierPart(SupplyResponseModel):
    supplier_part_id: str = Field(pattern=r"^RL-SP-\d{6}$")
    supplier_id: str
    part_id: str
    unit_price: float = Field(ge=0.0)
    lead_time_days: int = Field(ge=0)
    min_order_qty: int = Field(ge=0)
    is_primary_source: bool = False


class PurchaseOrder(SupplyResponseModel):
    po_id: str = Field(pattern=r"^RL-PO-\d{6}$")
    po_line: int = Field(ge=1)
    supplier_id: str
    part_id: str
    plant_id: str
    order_qty: int = Field(ge=0)
    received_qty: int = Field(ge=0, default=0)
    promised_date: date
    revised_date: Optional[date] = None
    status: POStatus = POStatus.OPEN
    unit_price: float = Field(ge=0.0)

    @property
    def open_qty(self) -> int:
        return max(self.order_qty - self.received_qty, 0)

    @property
    def effective_date(self) -> date:
        return self.revised_date or self.promised_date


class InventoryPosition(SupplyResponseModel):
    inventory_id: str = Field(pattern=r"^RL-INV-\d{6}$")
    part_id: str
    plant_id: str
    location_id: str
    on_hand: int = Field(ge=0)
    quality_hold: int = Field(ge=0, default=0)
    protected_allocation: int = Field(ge=0, default=0)
    in_transit: int = Field(ge=0, default=0)
    as_of_date: date


class BomComponent(SupplyResponseModel):
    bom_id: str = Field(pattern=r"^RL-BOM-\d{6}$")
    parent_part_id: str
    component_part_id: str
    qty_per: float = Field(gt=0.0)
    scrap_factor: float = Field(ge=0.0, lt=1.0, default=0.0)
    level: int = Field(ge=1, default=1)


class ProductionOrder(SupplyResponseModel):
    production_order_id: str = Field(pattern=r"^RL-PRD-\d{6}$")
    plant_id: str
    part_id: str
    quantity: int = Field(ge=0)
    start_date: date
    due_date: date
    status: ProductionOrderStatus = ProductionOrderStatus.PLANNED
    priority: int = Field(ge=1, le=5, default=3)


class Customer(SupplyResponseModel):
    customer_id: str = Field(pattern=r"^RL-CUST-\d{4}$")
    customer_name: str
    segment: str
    region: str
    priority_tier: int = Field(ge=1, le=3, default=2)
    otif_target: float = Field(ge=0.0, le=1.0, default=0.95)


class CustomerOrder(SupplyResponseModel):
    customer_order_id: str = Field(pattern=r"^RL-CO-\d{6}$")
    order_line: int = Field(ge=1)
    customer_id: str
    part_id: str
    plant_id: str
    quantity: int = Field(ge=0)
    requested_date: date
    promised_date: date
    unit_price: float = Field(ge=0.0)
    unit_cost: float = Field(ge=0.0)
    status: CustomerOrderStatus = CustomerOrderStatus.OPEN

    @property
    def revenue(self) -> float:
        return round(self.quantity * self.unit_price, 2)

    @property
    def margin(self) -> float:
        return round(self.quantity * (self.unit_price - self.unit_cost), 2)


class TransportOption(SupplyResponseModel):
    transport_option_id: str = Field(pattern=r"^RL-TRN-\d{5}$")
    origin: str
    destination: str
    mode: TransportMode
    transit_days: int = Field(ge=0)
    cost_per_unit: float = Field(ge=0.0)
    fixed_cost: float = Field(ge=0.0, default=0.0)
    max_qty: int = Field(ge=0, default=0)


class QualityQualification(SupplyResponseModel):
    qualification_id: str = Field(pattern=r"^RL-QUALITY-\d{3}$")
    supplier_id: str
    part_id: str
    status: QualificationStatus
    audit_complete: bool = False
    first_article_complete: bool = False
    expected_decision_date: Optional[date] = None
    note: str = ""
    source_reference: str = ""

    @property
    def executable(self) -> bool:
        return self.status == QualificationStatus.APPROVED


class Disruption(SupplyResponseModel):
    disruption_id: str = Field(pattern=r"^RL-\d{3}$")
    supplier_id: str
    part_id: str
    plant_id: str
    po_id: Optional[str] = None
    po_line: Optional[int] = None
    delayed_qty: int = Field(ge=0)
    original_date: date
    revised_date: Optional[date] = None
    partial_qty: int = Field(ge=0, default=0)
    partial_date: Optional[date] = None
    recovery_date_confirmed: bool = False
    severity: DisruptionSeverity = DisruptionSeverity.HIGH
    status: DisruptionStatus = DisruptionStatus.NEW
    signal_received_at: datetime
    signal_source: str = "email"
    signal_reference: str = ""
    summary: str = ""


class ResponseScenario(SupplyResponseModel):
    scenario_id: str = Field(pattern=r"^RL-SCN-\d{3}$")
    disruption_id: str
    scenario_type: ScenarioType
    title: str
    description: str
    expedite_qty: int = Field(ge=0, default=0)
    transfer_qty: int = Field(ge=0, default=0)
    resequenced_qty: int = Field(ge=0, default=0)
    alternate_supplier_id: Optional[str] = None
    transport_option_id: Optional[str] = None
    available_date: Optional[date] = None
    executable: bool = True
    blocking_constraint: Optional[str] = None
    requires_approval: bool = True
    assumptions: list[str] = Field(default_factory=list)


class ActionLedgerEntry(SupplyResponseModel):
    action_id: str = Field(pattern=r"^RL-ACT-\d{6}$")
    disruption_id: str
    scenario_id: Optional[str] = None
    action_type: str
    status: ActionStatus = ActionStatus.PROPOSED
    decided_by: str
    decided_at: datetime
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    calculation_version: str = ""
    follow_up_tasks: list[str] = Field(default_factory=list)


class OutcomeHistory(SupplyResponseModel):
    outcome_id: str = Field(pattern=r"^RL-OUT-\d{6}$")
    disruption_id: str
    scenario_id: Optional[str] = None
    action_id: Optional[str] = None
    predicted_revenue_protected: float = 0.0
    actual_revenue_protected: float = 0.0
    predicted_cost: float = 0.0
    actual_cost: float = 0.0
    predicted_otif_impact: float = 0.0
    actual_otif_impact: float = 0.0
    recorded_at: datetime
    lessons_learned: str = ""

    @property
    def revenue_variance(self) -> float:
        return round(self.actual_revenue_protected - self.predicted_revenue_protected, 2)

    @property
    def cost_variance(self) -> float:
        return round(self.actual_cost - self.predicted_cost, 2)


class Dataset(SupplyResponseModel):
    """A complete, in-memory synthetic dataset."""

    schema_version: str = SCHEMA_VERSION
    seed: int = 0
    suppliers: list[Supplier] = Field(default_factory=list)
    parts: list[Part] = Field(default_factory=list)
    supplier_parts: list[SupplierPart] = Field(default_factory=list)
    purchase_orders: list[PurchaseOrder] = Field(default_factory=list)
    inventory_positions: list[InventoryPosition] = Field(default_factory=list)
    bom_components: list[BomComponent] = Field(default_factory=list)
    production_orders: list[ProductionOrder] = Field(default_factory=list)
    customers: list[Customer] = Field(default_factory=list)
    customer_orders: list[CustomerOrder] = Field(default_factory=list)
    transport_options: list[TransportOption] = Field(default_factory=list)
    quality_qualifications: list[QualityQualification] = Field(default_factory=list)
    disruptions: list[Disruption] = Field(default_factory=list)
    response_scenarios: list[ResponseScenario] = Field(default_factory=list)
    action_ledger: list[ActionLedgerEntry] = Field(default_factory=list)
    outcome_history: list[OutcomeHistory] = Field(default_factory=list)

    TABLE_NAMES: ClassVar[tuple[str, ...]] = (
        "suppliers",
        "parts",
        "supplier_parts",
        "purchase_orders",
        "inventory_positions",
        "bom_components",
        "production_orders",
        "customers",
        "customer_orders",
        "transport_options",
        "quality_qualifications",
        "disruptions",
        "response_scenarios",
        "action_ledger",
        "outcome_history",
    )

    def table(self, name: str) -> list[SupplyResponseModel]:
        if name not in self.TABLE_NAMES:
            raise KeyError(f"unknown table: {name}")
        return getattr(self, name)

    def row_counts(self) -> dict[str, int]:
        return {name: len(self.table(name)) for name in self.TABLE_NAMES}


TABLE_NAMES = Dataset.TABLE_NAMES

__all__ = [
    "SCHEMA_VERSION",
    "ID_PREFIX",
    "TABLE_NAMES",
    "RiskTier",
    "PartType",
    "POStatus",
    "ProductionOrderStatus",
    "CustomerOrderStatus",
    "TransportMode",
    "QualificationStatus",
    "DisruptionStatus",
    "DisruptionSeverity",
    "ScenarioType",
    "ActionStatus",
    "Supplier",
    "Part",
    "SupplierPart",
    "PurchaseOrder",
    "InventoryPosition",
    "BomComponent",
    "ProductionOrder",
    "Customer",
    "CustomerOrder",
    "TransportOption",
    "QualityQualification",
    "Disruption",
    "ResponseScenario",
    "ActionLedgerEntry",
    "OutcomeHistory",
    "Dataset",
]
