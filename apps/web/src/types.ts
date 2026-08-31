export type CaseStatus =
  | "open"
  | "analyzing"
  | "awaiting_decision"
  | "decision_rejected"
  | "action_planning"
  | "executing"
  | "monitoring"
  | "reanalysis_required"
  | "closed";

export interface Disruption {
  disruption_id: string;
  supplier_id: string;
  po_line_id: string;
  part_id: string;
  plant_id: string;
  original_quantity: number;
  original_due_date: string;
  partial_quantity: number;
  partial_due_date: string | null;
  recovery_date: string | null;
  source_ref: string;
}

export interface PredictedOutcome {
  uncovered_part_demand: number;
  otif_loss_percentage: number;
  revenue_at_risk: string;
  margin_at_risk: string;
  response_cost: string;
  protected_customer_order_ids: string[];
}

export interface ResponseOption {
  option_id: string;
  option_kind: "no_mitigation" | "expedite" | "transfer" | "resequence" | "alternate_source" | "combined";
  name: string;
  executable: boolean;
  active_mitigation: boolean;
  predicted: PredictedOutcome | null;
  assumptions: string[];
  evidence_ids: string[];
  blocking_codes: string[];
  prerequisite_roles: string[];
  source_data_lineage: string[];
  approval_burden: number;
  execution_risk: number;
  requested_side_effects: string[];
}

export interface AnalysisVersion {
  analysis_id: string;
  response_options: ResponseOption[];
  ranking: {
    policy_version: string;
    recommended_option_id: string | null;
    no_feasible_mitigation: boolean;
  };
}

export interface CaseResponse {
  case: {
    case_id: string;
    status: CaseStatus;
  };
  disruption: Disruption;
  analysis: AnalysisVersion | null;
  selected_option_id: string | null;
}
