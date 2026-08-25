# Power BI report pages

Four pages backed by the semantic model in `../semantic-model/model.json`.

## 1. Command Center

- Active disruptions (card)
- Exceptions by severity (stacked column: `disruptions[severity]`)
- Decision status (donut: `disruptions[status]`)
- Revenue and OTIF exposure (cards: `Revenue at Risk`, `OTIF Lines at Risk`)
- Time since signal received (card: `Minutes Since Signal`)

## 2. Exposure

- Supplier → part → plant → product → customer (decomposition tree)
- Projected inventory by date (line: `Projected Balance`)
- Stockout dates (table: `First Stockout Date`)
- Affected orders (table: production and customer orders)
- Revenue and margin at risk (cards)

## 3. Scenario Comparison

- Cost vs revenue protected (scatter: `Response Cost`, `Revenue Protected`)
- OTIF impact (column: `OTIF Lines At Risk` by `scenario_id`)
- Inventory impact (column)
- Constraint violations (table: `blocking_constraint`)
- Approval requirements (table: `approver_roles`)

## 4. Actions and Outcomes

- Approved response (table: `action_ledger`)
- Owners and due dates (table: `follow_up_tasks`)
- Predicted vs actual result (clustered column from `outcome_history`)
- Variance and lessons learned (table: `Revenue Variance`, `Cost Variance`)
