# Three-minute demo script

Persona: **Alex Morgan**, Material Planner. All data is fictional (`RL-` prefix).

## 0:00 - 0:20 · The signal

> "Alex receives email `RL-001`. Supplier Alpha cannot deliver 8,000 units of
> MAT-10247 on September 3. It can provide 3,000 units on September 6 by air
> freight. The remaining delivery date is unconfirmed."

Open the decision console. The case header shows the supplier event, the
confirmed facts, and the unresolved uncertainty: the recovery date is unknown.
Nothing has been inferred.

## 0:20 - 0:50 · The consequences

Point at the exposure panel:

- Usable inventory at RL-PLANT-01: **4,000** (5,200 on hand − 400 quality hold −
  800 protected allocation)
- First projected stockout: **2025-09-05**
- Maximum shortage: **6,800 units**
- Affected production orders: **RL-PRD-000102 … RL-PRD-000105**
- Revenue at risk: **$1,071,000** · Margin at risk: **$408,000** · OTIF lines at
  risk: **4**

> "This normally takes an MRP run, an Excel export, and four people."

## 0:50 - 1:20 · The human context

Scroll to evidence. Work IQ surfaced a Teams message from Jordan Lee,
Quality Manager, reference `RL-QUALITY-001`:

> "Supplier Beta is not approved for MAT-10247. The supplier audit and
> first-article approval remain incomplete. Do not place an emergency purchase
> order until both are complete. Earliest expected decision: September 15."

> "Operational data says Beta can supply this part. The organisation's own
> knowledge says it must not be used yet."

## 1:20 - 2:20 · Ranked scenarios

| Rank | Scenario | Cost | Revenue protected | OTIF lines at risk |
|---|---|---|---|---|
| 1 | `RL-SCN-006` Combine expedite, transfer, resequence | $35,800 | $777,000 | 2 |
| 2 | `RL-SCN-004` Resequence production | $3,000 | $357,000 | 4 |
| 3 | `RL-SCN-002` Expedite 3,000-unit partial | $28,000 | $273,000 | 4 |
| 4 | `RL-SCN-003` Transfer from RL-PLANT-02 | $4,800 | $168,000 | 4 |
| 5 | `RL-SCN-001` Accept the delay | $17,000 | $0 | 4 |
| — | `RL-SCN-005` Source from Supplier Beta | — | — | **Not executable** |

> "Scenario 5 is excluded, not hidden. It stays a conditional option once
> Quality decides on September 15."

Note the approval routing: the recommended scenario includes $28,000 of premium
freight, above the $25,000 threshold, so a finance approver is required.

## 2:20 - 2:50 · The decision

Alex selects `RL-SCN-006`, enters a rationale, and approves. The system:

1. Writes the action-ledger record with evidence and calculation version.
2. Drafts a supplier recovery request for the outstanding 5,000 units.
3. Creates Procurement and Quality follow-up tasks.
4. Marks Supplier Beta as a conditional future option.
5. Updates the disruption-case status.

> "No purchase order is created. No financial commitment is made."

## 2:50 - 3:00 · The outcome

Show the dashboard summary: the case moves to approved, exposure is attributed
to the selected action, and the time from signal to decision is recorded.

> "Every number came from tested, versioned code. The agents assembled the
> context; the human made the decision."
