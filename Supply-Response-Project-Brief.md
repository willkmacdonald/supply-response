# Supply Response: Agents and Microsoft IQ for Faster Supply Chain Decisions

## Project objective

Build a working multi-agent prototype that helps manufacturing supply-chain teams respond to supplier disruptions faster.

The system combines:

- **Work IQ** for emails, Teams conversations, policies, and human context
- **Fabric** for operational data, semantic models, and dashboards
- **Fabric IQ** for governed business relationships and natural-language queries
- **Microsoft Foundry agents** for orchestration and reasoning
- **Deterministic services** for shortage, financial-impact, and scenario calculations
- **Human approval** before consequential actions

The primary outcome is reducing the time between learning that supply changed and choosing an approved response.

## Business problem

When a supplier changes a delivery commitment, the supplier generally communicates only purchasing facts:

- Affected PO lines
- Delayed quantities
- Original and revised dates
- Partial-shipment options
- Known and unknown recovery dates

The manufacturer must determine the consequences across ERP, planning, inventory, production, logistics, finance, quality, email, and Teams.

Today this frequently requires:

1. Running MRP.
2. Exporting exceptions to Excel.
3. Tracing parts through BOMs.
4. Identifying affected production orders.
5. Finding affected customers and revenue.
6. Obtaining expedite alternatives.
7. Checking supplier and material qualifications.
8. Reconciling information across several people.
9. Obtaining approval.
10. Updating execution systems manually.

The mathematics often already exists. The delay comes from assembling context and coordinating a decision.

## Demo scenario

### Supplier signal

Alex Morgan, Material Planner, receives:

**Subject:** `RL-001 Supplier Alpha delivery delay`

> Supplier Alpha cannot deliver 8,000 units of MAT-10247 on September 3. It can provide 3,000 units on September 6 by air freight. The remaining delivery date is unconfirmed.

### Internal Quality constraint

Jordan Lee, Quality Manager, sends Alex a Teams message:

**Reference:** `RL-QUALITY-001`

> Supplier Beta is not approved for MAT-10247. The supplier audit and first-article approval remain incomplete. Do not place an emergency purchase order until both are complete. Earliest expected decision: September 15.

### Key reveal

Operational data identifies Supplier Beta as an alternate source. Work IQ finds that Quality has not approved it.

Supply Response must therefore exclude Beta from immediately executable scenarios while retaining it as a conditional future option.

## Personas

| Persona | Role |
|---|---|
| Alex Morgan | Material Planner and primary application user |
| Jordan Lee | Quality Manager |
| Supplier Alpha | External supplier represented through fictional email |
| Finance approver | Initially represented through policy data rather than a separate user |
| Administrator | Infrastructure only; never appears in the demo |

All scenario data and communications must be fictional and prefixed with `RL-`.

## User experience

The user opens a Supply Response decision console showing:

1. The supplier event
2. Confirmed facts
3. Unresolved uncertainties
4. Affected parts, plants, production, and customers
5. Operational and financial exposure
6. Applicable policies and human constraints
7. Ranked response scenarios
8. Evidence and assumptions
9. Required approvals
10. Approved actions and outcome tracking

## Runtime architecture

```text
Supplier email / Teams / SharePoint
                 |
                 v
             Work IQ
                 |
                 v
        Foundry Orchestrator
          |-- Signal Agent
          |-- Context Agent
          |-- Decision Agent
          |-- Calculation Tools
          `-- Scenario Tools
                 |
                 v
      Fabric Lakehouse / Warehouse
          |-- Semantic model
          |-- Power BI dashboard
          |-- Fabric IQ ontology
          `-- Action ledger
                 |
                 v
        Supply Response web app
```

## Agent design

### Orchestrator

**Type:** Foundry hosted agent using Microsoft Agent Framework.

Responsibilities:

- Create and manage disruption cases
- Invoke specialist agents and deterministic tools
- Preserve evidence lineage
- Separate facts, assumptions, and unknowns
- Present recommendations
- Enforce approval boundaries
- Record actions and outcomes

### Signal Agent

**Type:** Foundry prompt agent.

Responsibilities:

- Retrieve supplier communications through Work IQ
- Extract parts, quantities, dates, and alternatives
- Identify missing or conflicting information
- Produce structured JSON
- Never invent missing dates, quantities, or commitments

### Context Agent

**Type:** Foundry prompt agent.

Responsibilities:

- Search Teams, email, and SharePoint through Work IQ
- Retrieve Quality constraints, ownership, and commitments
- Retrieve relevant SOPs and policies
- Return citations and source dates
- Distinguish formal policy from informal discussion

### Decision Agent

**Type:** Foundry prompt agent.

Responsibilities:

- Compare scenarios returned by deterministic services
- Explain trade-offs
- Exclude infeasible scenarios
- Recommend immediate and conditional actions
- Identify approvals and unresolved questions

### Deterministic tools-not agents

Use tested Python or SQL for:

- Time-phased supply-and-demand netting
- Inventory runout
- Shortage quantities
- Affected production and customer orders
- Revenue and margin exposure
- OTIF exposure
- Expedite and transfer costs
- Scenario scoring and constraint checks

Do not ask an LLM to perform authoritative arithmetic.

## Synthetic data model

Initial tables:

- `suppliers`
- `parts`
- `supplier_parts`
- `purchase_orders`
- `inventory_positions`
- `bom_components`
- `production_orders`
- `customers`
- `customer_orders`
- `transport_options`
- `quality_qualifications`
- `disruptions`
- `response_scenarios`
- `action_ledger`
- `outcome_history`

Target demonstration scale:

- 250 suppliers
- 10,000 parts
- 100,000 BOM relationships
- Multiple plants and inventory locations
- 50,000 open customer-order lines
- Twelve months of disruption and fulfillment history

The dataset is entirely synthetic.

## Core calculations

At minimum, calculate:

```text
usable inventory =
    on hand
  - quality hold
  - protected allocation
```

```text
projected balance by date =
    prior balance
  + confirmed receipts
  + approved transfers
  - component demand
```

Determine:

- First projected stockout date
- Maximum shortage quantity
- Affected production orders
- Affected customer-order lines
- Revenue and margin at risk
- OTIF lines at risk
- Response cost
- Revenue protected by scenario
- Remaining uncertainty

Every result should include:

- Scenario ID
- Calculation version
- Timestamp
- Assumptions
- Source-data lineage

## Initial response scenarios

1. Accept the delay and allow backlog.
2. Expedite Supplier Alpha's 3,000-unit partial shipment.
3. Transfer inventory from another plant.
4. Resequence production toward priority customers.
5. Source from Supplier Beta.
6. Combine expedite, transfer, and resequencing.

Scenario 5 must be marked **not executable** because of the Work IQ Quality constraint.

## Fabric foundation

Use Fabric as the primary operational-data layer:

- Lakehouse or Warehouse
- Managed tables
- SQL endpoint
- Semantic model
- Power BI report
- Calculation output tables
- Action and outcome history

Keep table schemas and calculation contracts portable so local development can use SQLite or equivalent fixtures.

## Dashboard

Create a Power BI report with four pages:

### Command Center

- Active disruptions
- Exceptions by severity
- Decision status
- Revenue and OTIF exposure
- Time since signal received

### Exposure

- Supplier to part to plant to product to customer
- Projected inventory
- Stockout dates
- Affected orders
- Revenue and margin at risk

### Scenario Comparison

- Cost
- Revenue protected
- OTIF impact
- Inventory impact
- Constraint violations
- Approval requirements

### Actions and Outcomes

- Approved response
- Owners and due dates
- Predicted result
- Actual result
- Variance and lessons learned

## Web application

Recommended stack:

- **Frontend:** React and TypeScript
- **Backend:** Python 3.12 with FastAPI
- **Agents:** Microsoft Agent Framework and Foundry Agent Service
- **Testing:** pytest plus frontend component tests
- **Local database:** SQLite fixtures
- **Primary data:** Fabric SQL endpoint
- **Dashboard:** Power BI embedded or linked

The browser must call the backend API. Do not expose Fabric credentials in frontend code.

Suggested endpoints:

```text
POST /api/cases
GET  /api/cases/{caseId}
POST /api/cases/{caseId}/analyze
GET  /api/cases/{caseId}/scenarios
POST /api/cases/{caseId}/approve
POST /api/cases/{caseId}/reject
GET  /api/dashboard/summary
```

## Fabric IQ stretch goal

Build toward Fabric IQ from the beginning.

Create ontology entities for:

- Supplier
- Part
- PurchaseOrder
- InventoryPosition
- Plant
- ProductionOrder
- Product
- CustomerOrder
- Disruption
- ResponseScenario

Create governed relationships such as:

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

Connect the ontology through Fabric IQ MCP.

## September 11 go/no-go

Keep live Fabric IQ in the hackathon demo only if:

1. Paid F2+ capacity is available.
2. Ontology preview is enabled.
3. Entities and relationships bind correctly.
4. MCP returns known-answer results.
5. Permissions work correctly.
6. The full demo succeeds repeatedly.

If any of these fail, remove only the live ontology/MCP dependency. Keep Fabric tables, dashboards, and the web application.

## Bounded action

After Alex approves a recommendation, the prototype should:

- Write the decision to `action_ledger`
- Record supporting evidence
- Draft a supplier recovery request
- Create Procurement and Quality follow-up tasks
- Mark Supplier Beta as conditional
- Update the disruption-case status

The prototype must not create a real PO or financial commitment.

## Acceptance criteria

1. The supplier email is extracted accurately without inference.
2. The system identifies affected operational entities.
3. Calculations are reproducible and tested.
4. Work IQ retrieves the Supplier Beta Quality constraint.
5. Supplier Beta is excluded from executable scenarios.
6. At least three feasible scenarios are compared.
7. Every recommendation shows evidence and assumptions.
8. Alex can approve or reject the response.
9. Approval writes a complete action-ledger record.
10. The dashboard reflects the disruption and selected action.
11. The demo works without personal or customer data.
12. The end-to-end scenario completes reliably within the three-minute video.

## Evaluation cases

Include tests for:

- Confirmed supplier recovery date
- Unconfirmed recovery date
- Partial shipment
- Conflicting email and ERP dates
- Alternate supplier approved
- Alternate supplier not approved
- Inventory available at another plant
- No feasible mitigation
- Premium freight above approval threshold
- Missing or stale collaboration evidence

## Delivery plan

| Date | Deliverable |
|---|---|
| Aug 25-28 | Repository, synthetic schema, fixtures, and calculation tests |
| Aug 29-Sep 3 | Fabric tables, semantic model, and first dashboard |
| Sep 4-8 | Agents, Work IQ integration, and decision API |
| Sep 9-10 | Fabric IQ ontology and MCP attempt |
| Sep 11 | Fabric IQ go/no-go |
| Sep 12-14 | Web application and approval workflow |
| Sep 15-18 | Hardening, evaluation, and three-minute video |
| Sep 20 | Final repository and submission package |

## Repository structure

```text
supply-response/
  apps/
    web/
    api/
  agents/
    orchestrator/
    signal/
    context/
    decision/
  services/
    exposure/
    scenarios/
    policy/
  data/
    schemas/
    synthetic/
    fixtures/
  fabric/
    notebooks/
    sql/
    semantic-model/
    ontology/
    power-bi/
  evaluations/
    datasets/
    expected-results/
  tests/
  docs/
    architecture/
    demo-script/
  .env.example
  README.md
```

## Security and development rules

- Use fictional data only.
- Never commit secrets or tenant credentials.
- Use environment variables and managed identity where available.
- Keep calculation logic versioned and tested.
- Require explicit approval before consequential actions.
- Preserve source citations and calculation lineage.
- Keep Fabric IQ optional until September 11.
- Install Azure Developer CLI before deploying hosted Foundry agents; it is currently missing from the local environment.
