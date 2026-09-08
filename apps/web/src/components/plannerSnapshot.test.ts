import {describe, expect, it} from "vitest";
import {editSnapshot, recordFixture} from "./supportingRecord.fixture";
import {customerLineBasis, readPlannerSnapshot} from "./plannerSnapshot";
import {resolveSupportingRecord} from "./supportingRecord";
import {parseSnapshotEnvelope, validDate, validInstant, validMoney} from "./snapshotValidation";

function fixture() {
  const input = recordFixture();
  editSnapshot(input, s => {
    s.disruption = {disruption_id: "d", supplier_id: "RL-SUP-ALPHA", po_line_id: "po",
      part_id: "p", plant_id: "RL-PLANT-CHI", original_quantity: 8000,
      original_due_date: "2026-09-03", partial_quantity: 0,
      partial_due_date: null, recovery_date: null, source_ref: "RL-001"};
    s.inventory_positions = [{inventory_id: "i", part_id: "p", plant_id: "RL-PLANT-CHI",
      on_hand: 4500, quality_hold: 200, protected_allocation: 300}];
    s.production_orders = [{production_order_id: "mo", product_id: "product", plant_id: "RL-PLANT-CHI",
      quantity: 2, due_date: "2026-09-05", component_demand: 4,
      customer_order_id: "co", customer_revenue: "10.00"}];
    s.customer_orders = [{customer_order_line_id: "co", production_order_id: "mo",
      customer_id: "customer", product_id: "product", plant_id: "RL-PLANT-CHI",
      quantity: 2, due_date: "2026-09-05", unit_revenue: "5.00"}];
  });
  return input;
}

describe("planner snapshot", () => {
  it("shares strict value checks and keeps caller-specific section rules separate", () => {
    expect(validDate("2026-02-30")).toBe(false);
    expect(validInstant("2026-09-01T09:00:00")).toBe(false);
    expect(validMoney("0.00")).toBe(true);
    expect(validMoney("0")).toBe(false);
    const input = fixture();
    editSnapshot(input, s => { s.customer_orders = "malformed"; });
    expect(parseSnapshotEnvelope(input)).not.toBeNull();
    expect(readPlannerSnapshot(input)?.disruption?.original_quantity).toBe(8000);
    expect(readPlannerSnapshot(input)?.customers).toBeNull();
    expect(resolveSupportingRecord(input, input.analysis.evidence_items[0].evidence_id).status).toBe("unavailable");
  });
  it("retains zero and null and accepts a historical analysis without mutation", () => {
    const input = fixture(); const before = JSON.stringify(input);
    const saved = readPlannerSnapshot(input)!;
    expect(saved.disruption?.partial_quantity).toBe(0);
    expect(saved.disruption?.recovery_date).toBeNull();
    expect(saved.inventory?.[0].on_hand).toBe(4500);
    expect(JSON.stringify(input)).toBe(before);
    expect(readPlannerSnapshot({...input, caseInstance: {...input.caseInstance,
      ...{current_analysis_id: "newer-analysis"}}})).not.toBeNull();
  });
  it.each(["case", "runtime", "scenario", "corpus", "json"])("rejects %s identity problems", kind => {
    const input = fixture();
    if (kind === "case") input.analysis.material.case_id = "other";
    if (kind === "runtime") input.caseInstance.runtime_mode = "fallback";
    if (kind === "scenario") input.analysis.material.scenario_effective_time = "2026-09-02T09:00:00-05:00";
    if (kind === "corpus") input.analysis.material.corpus = "real_business";
    if (kind === "json") input.analysis.material.operational_snapshot_json = "{";
    expect(readPlannerSnapshot(input)).toBeNull();
  });
  it("rejects malformed fields locally, including impossible calendar dates and duplicate IDs", () => {
    const input = fixture();
    editSnapshot(input, s => { s.customer_orders[0].due_date = "2026-02-30"; });
    expect(readPlannerSnapshot(input)?.customers).toBeNull();
    expect(readPlannerSnapshot(input)?.disruption).not.toBeNull();
    editSnapshot(input, s => { s.inventory_positions.push({...s.inventory_positions[0]}); });
    expect(readPlannerSnapshot(input)?.inventory).toBeNull();
    editSnapshot(input, s => { s.disruption.partial_quantity = "0"; });
    expect(readPlannerSnapshot(input)?.disruption).toBeNull();
  });
  it("distinguishes empty arrays, zero stock, and negative net availability inputs", () => {
    const input = fixture();
    editSnapshot(input, s => { s.inventory_positions[0].on_hand = 0; });
    expect(readPlannerSnapshot(input)?.inventory?.[0].on_hand).toBe(0);
    editSnapshot(input, s => { s.inventory_positions = []; });
    expect(readPlannerSnapshot(input)?.inventory).toEqual([]);
  });
  it("permits customer-line counts only for exact one-to-one metric lineage", () => {
    const input = fixture();
    expect(customerLineBasis(readPlannerSnapshot(input), [])).toEqual({total: 1, missed: 1});
    expect(customerLineBasis(readPlannerSnapshot(input), ["co"])).toEqual({total: 1, missed: 0});
    expect(customerLineBasis(readPlannerSnapshot(input), ["unknown"])).toBeNull();
    expect(customerLineBasis(readPlannerSnapshot(input), ["co", "co"])).toBeNull();
    editSnapshot(input, s => { s.production_orders[0].customer_revenue = "11.00"; });
    expect(customerLineBasis(readPlannerSnapshot(input), [])).toBeNull();
    editSnapshot(input, s => { s.production_orders[0].customer_order_id = null; });
    expect(customerLineBasis(readPlannerSnapshot(input), [])).toBeNull();
  });
});
