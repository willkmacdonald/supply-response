// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it} from "vitest";
import {PredictionSummary} from "./PredictionSummary";
import {calendar, money, blocker, rankingReason, decisionContext} from "./plannerFormatting";
afterEach(cleanup);
const predicted = {uncovered_part_demand: 0, otif_loss_percentage: 0,
  revenue_at_risk: "0.00", margin_at_risk: "0.00", response_cost: "24750.00",
  protected_customer_order_ids: []};
it("shows persisted zero, absent currency, and the baseline label without inventing line counts", () => {
  render(<PredictionSummary predicted={predicted} snapshot={null} basis="baseline" />);
  expect(screen.getByText("Expected if we do nothing — baseline")).toBeVisible();
  expect(screen.getByText("0 component units (part unavailable)")).toBeVisible();
  expect(screen.getByText("24,750.00 (currency not specified)")).toBeVisible();
  expect(screen.getByText("Production orders expected to miss the on-time, in-full target")).toBeVisible();
  expect(screen.getByText(/Customer-order-line interpretation unavailable/)).toBeInTheDocument();
});
it("labels response predictions and does not invent missing outcomes", () => {
  render(<PredictionSummary predicted={null} snapshot={null} basis="response" />);
  expect(screen.getByText("Expected if we take this option")).toBeVisible();
  expect(screen.getByText("Saved prediction unavailable")).toBeVisible();
  expect(screen.queryByText(/0 component/)).not.toBeInTheDocument();
});
it("formats calendar dates without day shifts and keeps unsafe values unavailable", () => {
  expect(calendar("2026-09-06")).toBe("September 6, 2026");
  expect(calendar("2026-02-30")).toBe("Unavailable");
  expect(money("0.00")).toBe("0.00 (currency not specified)");
  expect(money("NaN")).toBe("Unavailable");
  expect(blocker("QUALITY_QUALIFICATION_PENDING")).toBe("Cannot use Supplier Beta yet: supplier qualification is incomplete");
  expect(blocker("NEW_POLICY_CODE")).toBe("Planning requirement unresolved (NEW_POLICY_CODE)");
});
it("describes recorded ranking with business meaning and units without asserting a new ranking", () => {
  const stage = {comparator: "uncovered_part_demand", threshold: "500", lower_is_better: true,
    input_option_ids: ["a", "b"], values: [], retained_option_ids: ["a"], eliminated_option_ids: ["b"]};
  expect(rankingReason(stage, "a")).toBe("This option stayed in consideration after comparing parts still needed, allowing a difference of 500 component units under the saved planning policy. 1 other option was ruled out in this comparison.");
  expect(rankingReason({...stage, comparator: "otif_loss_percentage", threshold: "10"}, "a")).toContain("10 percentage points");
  expect(rankingReason({...stage, comparator: "response_cost", threshold: "10000"}, "a")).toContain("currency not specified");
  expect(rankingReason({...stage, comparator: "unknown"}, "a")).toContain("additional saved comparison rule");
  expect(decisionContext(null, "a", false)).toBe("Case context unavailable; no decision is shown");
});
it("keeps the comparison summary compact with parts, service and response cost", () => {
  render(<PredictionSummary predicted={predicted} snapshot={null} basis="response" compact />);
  expect(screen.getByText("Parts still needed")).toBeVisible();
  expect(screen.getByText("Response cost")).toBeVisible();
  expect(screen.queryByText("Revenue at risk")).not.toBeInTheDocument();
});
it("renders customer-line semantics only when the exact saved one-to-one lineage and percentage agree", () => {
  const snapshot = {disruption: null, inventory: [],
    production: [{production_order_id: "mo", product_id: "p", plant_id: "plant", quantity: 2,
      due_date: "2026-09-06", component_demand: 4, customer_order_id: "co", customer_revenue: "10.00"}],
    customers: [{customer_order_line_id: "co", production_order_id: "mo", customer_id: "customer", product_id: "p",
      plant_id: "plant", quantity: 2, due_date: "2026-09-06", unit_revenue: "5.00"}]};
  const {rerender} = render(<PredictionSummary predicted={{...predicted, otif_loss_percentage: 100}} snapshot={snapshot} basis="response" />);
  expect(screen.getByText("100% (1 of 1 lines)")).toBeVisible();
  expect(screen.getByText("Customer order lines expected to miss the on-time, in-full target")).toBeVisible();
  rerender(<PredictionSummary predicted={{...predicted, otif_loss_percentage: 50}} snapshot={snapshot} basis="response" />);
  expect(screen.getByText("Production orders expected to miss the on-time, in-full target")).toBeVisible();
  expect(screen.queryByText(/of 1 lines/)).not.toBeInTheDocument();
});
