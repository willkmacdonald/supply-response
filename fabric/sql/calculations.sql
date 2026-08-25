-- Portable exposure calculation.
-- Mirrors services/exposure/calculator.py. The Python implementation is
-- authoritative; this query exists so Fabric can materialise the same numbers.

-- usable inventory = on hand - quality hold - protected allocation
CREATE VIEW vw_usable_inventory AS
SELECT
    part_id,
    plant_id,
    SUM(CASE WHEN on_hand - quality_hold - protected_allocation > 0
             THEN on_hand - quality_hold - protected_allocation ELSE 0 END) AS usable_inventory
FROM inventory_positions
GROUP BY part_id, plant_id;

-- Confirmed receipts. A delayed purchase order with no revised date contributes
-- nothing: never invent a supplier commitment.
CREATE VIEW vw_confirmed_receipts AS
SELECT
    part_id,
    plant_id,
    COALESCE(revised_date, promised_date) AS receipt_date,
    SUM(order_qty - received_qty) AS confirmed_receipts
FROM purchase_orders
WHERE status IN ('open', 'confirmed', 'partial', 'delayed')
  AND order_qty > received_qty
  AND NOT (status = 'delayed' AND revised_date IS NULL)
GROUP BY part_id, plant_id, COALESCE(revised_date, promised_date);

-- Component demand exploded from open production orders.
CREATE VIEW vw_component_demand AS
SELECT
    b.component_part_id AS part_id,
    p.plant_id,
    p.start_date AS demand_date,
    SUM(CEILING(p.quantity * b.qty_per / (1.0 - b.scrap_factor))) AS component_demand
FROM production_orders p
JOIN bom_components b ON b.parent_part_id = p.part_id
WHERE p.status IN ('planned', 'released', 'in_progress')
GROUP BY b.component_part_id, p.plant_id, p.start_date;

-- projected balance by date =
--     prior balance + confirmed receipts + approved transfers - component demand
CREATE VIEW vw_projected_balance AS
WITH movements AS (
    SELECT part_id, plant_id, receipt_date AS movement_date, confirmed_receipts AS delta
    FROM vw_confirmed_receipts
    UNION ALL
    SELECT part_id, plant_id, demand_date AS movement_date, -component_demand AS delta
    FROM vw_component_demand
)
SELECT
    m.part_id,
    m.plant_id,
    m.movement_date,
    i.usable_inventory
        + SUM(m.delta) OVER (
            PARTITION BY m.part_id, m.plant_id
            ORDER BY m.movement_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS projected_balance
FROM movements m
JOIN vw_usable_inventory i
  ON i.part_id = m.part_id AND i.plant_id = m.plant_id;

-- First projected stockout date and maximum shortage quantity.
CREATE VIEW vw_stockout AS
SELECT
    part_id,
    plant_id,
    MIN(CASE WHEN projected_balance < 0 THEN movement_date END) AS first_stockout_date,
    MAX(CASE WHEN projected_balance < 0 THEN -projected_balance ELSE 0 END) AS max_shortage_qty
FROM vw_projected_balance
GROUP BY part_id, plant_id;
