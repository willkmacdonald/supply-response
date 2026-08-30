export type CaseStatus = "open" | "analyzed" | "approved" | "rejected";

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

export interface ResponseScenario {
  scenario_id: string;
  disruption_id: string;
  name: string;
  executable: boolean;
  constraint_violations: string[];
  response_cost: string;
  revenue_protected: string;
  remaining_uncertainty: string[];
}

export interface SupplyResponseCase {
  case_id: string;
  disruption: Disruption;
  status: CaseStatus;
  scenarios: ResponseScenario[];
  selected_scenario_id: string | null;
}
