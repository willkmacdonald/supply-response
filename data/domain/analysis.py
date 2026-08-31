from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import Field

from .common import FrozenModel, Money


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
    revenue_at_risk: Money
    margin_at_risk: Money
    otif_lines_at_risk: int
    response_cost: Money = Decimal("0")
    revenue_protected: Money = Decimal("0")
    remaining_uncertainty: tuple[str, ...] = ()


class PredictedOutcome(FrozenModel):
    uncovered_part_demand: int
    otif_loss_percentage: int
    revenue_at_risk: Decimal
    margin_at_risk: Decimal
    response_cost: Decimal
    protected_customer_order_ids: tuple[str, ...] = ()


class ResponseOption(FrozenModel):
    option_id: str
    name: str
    executable: bool
    active_mitigation: bool
    predicted: PredictedOutcome | None
    assumptions: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    blocking_codes: tuple[str, ...] = ()
    prerequisite_roles: tuple[str, ...] = ()
    source_data_lineage: tuple[str, ...] = ()
    approval_burden: int = 0
    execution_risk: int = 0
