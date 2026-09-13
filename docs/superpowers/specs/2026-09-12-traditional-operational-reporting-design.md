# Traditional operational reporting — approved correction

Approved by the user's September 12 direction: “REMEMBER THAT. NOW MAKE IT HAPPEN.”
This is an implementation correction, not a request for another design-approval
round. Codex reviews delegated tasks between stages.

## Purpose

Demonstrate the difference between a planner manually investigating operational
data in Power BI and the AI-assisted website bringing evidence, impacts and
response choices together. The traditional side must be credible and useful in
its own right—not intentionally bad software and not an AI answer page in Power BI.

## Non-negotiable presentation

- Lead with dense, readable operational tables, useful charts and visible filters.
- Provide a coherent fictional business context: multiple components, suppliers,
  plants and customer/production orders, with enough distinct records to filter,
  sort, compare and investigate. Do not multiply one case or repeat rows for volume.
- Use ordinary report names: Supply overview, Inventory, Supplier deliveries,
  Plant transfers, Supplier qualification, Customer orders and Production demand.
- Show operational quantities, dates, holds, allocations, open order lines,
  statuses and costs—not the website's nine questions or recommendation narrative.
- Keep USD totals at whole dollars and per-component prices at two decimals.
- Retain explicit fictional-data and snapshot context. Broad operational context
  is not evidence of a fresh retrieval, historical trend or actual execution.

## Two entry points, one honest comparison

1. **Traditional walkthrough:** start with the wider operational picture. The
   presenter filters to the Chicago plant and RL-MAT-10247, checks supplier
   delivery exceptions, stock/holds/allocations, demand and customer exposure,
   then transfers and supplier qualification. Open the original email and Teams
   source for communication context. The presenter draws the conclusion before
   returning to AI assistance. Do not present AI-produced option rankings as the
   traditional investigation's starting point.
2. **Supporting-data link from a web card:** open the appropriate operational
   report/table, scoped to the exact case and analysis used by that card. Show
   the contributing rows and relevant chart, not nine unrelated cases or a
   repeated prose answer. Make the selected snapshot and record scope visible.
   Broader context must be explicitly distinguished from those contributing rows.

## Data integrity

The canonical example must reconcile: Chicago RL-MAT-10247 has 4,500 on hand,
200 on quality hold and 300 protected allocation, leaving 4,000 usable components.
Those numbers must come from the selected analysis when reached from its card.
The proposed supplier partial shipment is not an approved, dispatched or received
shipment. Qualification review dates are not approval or delivery promises.

Additional synthetic operational context must not change existing RL-001
calculations, overwrite saved analyses, manufacture evidence, create decisions,
or silently substitute current data for missing historical data. Keep its source
and scope explicit. Reuse the existing Fabric database; no new database or cloud
resource is required merely to make the reports more useful.

## Acceptance: prove the product, not just the build

- A traditional landing renders real tables and charts with meaningful multi-row
  context, and filters visibly change both. It is not a prose/card dashboard.
- Inventory, deliveries, transfers, qualification and demand/order drill-throughs
  work without requiring an AI-generated recommendation.
- The inventory link from the actual saved case displays the contributing row(s)
  and reconciles all four quantities above; customer-order and shipment links
  similarly match their originating card and selected analysis.
- Unknown, mismatched or missing historical identities do not show another case's
  values. Do not manufacture a reporting activation receipt to enable links.
- Review native Power BI screenshots as the demo account, not only generated JSON,
  accessibility text, mocked previews or unit-test counts.
- Capture a presenter walkthrough comparing manual investigation with the same
  case in the AI website. Do not claim measured productivity gains without data.

## Scope exclusions

No case deletion, new paid capacity, permission expansion, operational purchasing,
supplier communication or execution approval. Preserve the existing website's
approved tabbed flow, header, source icons, recommendation sheet and safeguards.
