# Data model

Fifteen tables, defined once in `data/schemas/models.py` (Pydantic v2) and
mirrored in `fabric/sql/schema.sql`. Every business key uses the `RL-` prefix.

| Table | Key | Notes |
|---|---|---|
| `suppliers` | `RL-SUP-0000` | Risk tier, OTD rate, quality score |
| `parts` | `RL-PART-00000` | Components and finished goods |
| `supplier_parts` | `RL-SP-000000` | Sourcing, price, lead time |
| `purchase_orders` | `RL-PO-000000` + line | `revised_date` is the supplier commitment |
| `inventory_positions` | `RL-INV-000000` | `on_hand`, `quality_hold`, `protected_allocation` |
| `bom_components` | `RL-BOM-000000` | `qty_per`, `scrap_factor` |
| `production_orders` | `RL-PRD-000000` | Demand source; `priority` 1 (highest) to 5 |
| `customers` | `RL-CUST-0000` | `priority_tier` 1 (highest) to 3 |
| `customer_orders` | `RL-CO-000000` + line | Revenue and margin exposure |
| `transport_options` | `RL-TRN-00000` | Air, ocean, road, rail, courier |
| `quality_qualifications` | `RL-QUALITY-000` | Drives executability (`RL-QUALITY-001`) |
| `disruptions` | `RL-000` | The supplier signal (`RL-001` is the demo) |
| `response_scenarios` | `RL-SCN-000` | Candidate responses |
| `action_ledger` | `RL-ACT-000000` | Approved and rejected decisions |
| `outcome_history` | `RL-OUT-000000` | Predicted versus actual |

## Derived quantities

| Field | Definition |
|---|---|
| `usable_inventory` | `on_hand - quality_hold - protected_allocation`, floored at zero |
| `open_qty` | `order_qty - received_qty`, floored at zero |
| `effective_date` | `revised_date` if present, otherwise `promised_date` |
| `revenue` | `quantity * unit_price` |
| `margin` | `quantity * (unit_price - unit_cost)` |
| `lost_output_qty` | `ceil(order_quantity * shortage_qty / required_qty)` |

## Relationships

```text
Supplier supplies Part
PurchaseOrder orders Part
Part isUsedBy Product
Plant produces Product
ProductionOrder requires Part
CustomerOrder requests Product
Disruption affects PurchaseOrder
ResponseScenario mitigates Disruption
```

These are the same relationships bound in `fabric/ontology/entities.json`.
