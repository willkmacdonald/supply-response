from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import Field

from .common import FrozenModel


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
