import type {SupportingRecordInput} from "./supportingRecord";

export function recordFixture(): SupportingRecordInput {
  const at = "2026-09-01T09:00:00-05:00";
  const evidence = {
    evidence_id: "RL-ALPHA-OPTIONAL-3000", case_id: "case-1",
    kind: "operational_fact" as const, source_system: "fabric" as const,
    source_id: "fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000",
    runtime_mode: "live" as const, synthetic: false,
    source_timestamp: at, retrieved_at: at, retrieved_for_analysis_id: "analysis-1",
  };
  return {
    caseInstance: {case_id: "case-1", runtime_mode: "live", template_id: "RL-001", scenario_effective_time: at},
    analysis: {
      analysis_id: "analysis-1", case_id: "case-1", runtime_mode: "live",
      scenario_effective_time: at, created_at: at,
      evidence_items: [evidence],
      material: {
        case_id: "case-1", runtime_mode: "live", template_id: "RL-001",
        corpus: "demo_corpus", scenario_effective_time: at, evidence: [{...evidence}],
        operational_snapshot_json: JSON.stringify({
          case_id: "case-1", runtime_mode: "live", scenario_effective_time: at,
          scenario_timezone: "America/Chicago", analysis_horizon_start: at,
          analysis_horizon_end: "2026-09-08", inventory_positions: [],
          production_orders: [], customer_orders: [], disruption: {},
          alpha_expedite: {
            receipt_id: "RL-ALPHA-OPTIONAL-3000", supplier_id: "RL-SUP-ALPHA",
            part_id: "RL-MAT-10247", plant_id: "RL-PLANT-CHI", quantity: 3000,
            due_date: "2026-09-06", incremental_cost_per_unit: "7.50",
          },
          transfer: {
            transfer_id: "RL-TRANSFER-DAL-CHI-1500", part_id: "RL-MAT-10247",
            source_plant_id: "RL-PLANT-DAL", destination_plant_id: "RL-PLANT-CHI",
            quantity: 1500, dispatch_date: "2026-09-04", arrival_date: "2026-09-05",
            incremental_cost_per_unit: "1.50",
          },
          beta_qualification: {
            qualification_id: "RL-QUAL-BETA", supplier_id: "RL-SUP-BETA",
            part_id: "RL-MAT-10247", evidence_ref: "RL-QUALITY-001", status: "pending",
            effective_date: null, audit_complete: false, first_article_complete: false,
            expected_decision_date: "2026-09-15",
          },
        }),
      },
    },
  };
}

export function editSnapshot(input: SupportingRecordInput, edit: (snapshot: Record<string, any>) => void) {
  const snapshot = JSON.parse(input.analysis.material.operational_snapshot_json);
  edit(snapshot);
  input.analysis.material.operational_snapshot_json = JSON.stringify(snapshot);
}

export function selectRecord(input: SupportingRecordInput, kind: "transfer" | "qualification") {
  const item = input.analysis.evidence_items[0];
  item.evidence_id = kind === "transfer" ? "RL-TRANSFER-DAL-CHI-1500" : "RL-QUALITY-001";
  item.source_id = kind === "transfer"
    ? "fabric.inventory_transfer/RL-TRANSFER-DAL-CHI-1500"
    : "fabric.qualification/RL-QUAL-BETA";
  input.analysis.material.evidence = [{...item}];
  return item.evidence_id;
}
