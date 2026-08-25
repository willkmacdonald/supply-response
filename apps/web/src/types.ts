export interface EvidenceItem {
  evidence_id: string;
  source: string;
  reference: string;
  title: string;
  content: string;
  captured_at: string;
}

export interface BalanceRow {
  date: string;
  opening_balance: number;
  confirmed_receipts: number;
  approved_transfers: number;
  component_demand: number;
  projected_balance: number;
  shortage: number;
}

export interface AffectedProductionOrder {
  production_order_id: string;
  plant_id: string;
  due_date: string;
  required_qty: number;
  shortage_qty: number;
  lost_output_qty: number;
  priority: number;
}

export interface AffectedCustomerOrder {
  customer_order_id: string;
  customer_id: string;
  promised_date: string;
  at_risk_qty: number;
  revenue_at_risk: number;
  margin_at_risk: number;
  priority_tier: number;
}

export interface ExposureResult {
  scenario_id: string;
  calculation_version: string;
  calculated_at: string;
  part_id: string;
  plant_id: string;
  horizon_start: string;
  horizon_end: string;
  usable_inventory: number;
  balances: BalanceRow[];
  first_stockout_date: string | null;
  max_shortage_qty: number;
  total_shortage_qty: number;
  affected_production_orders: AffectedProductionOrder[];
  affected_customer_orders: AffectedCustomerOrder[];
  revenue_at_risk: number;
  margin_at_risk: number;
  otif_lines_at_risk: number;
  assumptions: string[];
  lineage: Record<string, string[]>;
  open_questions: string[];
}

export interface ScenarioEvaluation {
  scenario_id: string;
  disruption_id: string;
  scenario_type: string;
  title: string;
  description: string;
  calculation_version: string;
  evaluated_at: string;
  executable: boolean;
  conditional: boolean;
  blocking_constraint: string | null;
  requires_approval: boolean;
  approver_roles: string[];
  response_cost: number;
  revenue_protected: number;
  net_benefit: number;
  revenue_at_risk: number;
  margin_at_risk: number;
  otif_lines_at_risk: number;
  first_stockout_date: string | null;
  max_shortage_qty: number;
  score: number;
  rank: number;
  recommended: boolean;
  assumptions: string[];
  evidence: string[];
  open_questions: string[];
}

export interface ActionResponse {
  action_id: string;
  case_id: string;
  scenario_id: string | null;
  action_type: string;
  status: string;
  decided_by: string;
  decided_at: string;
  rationale: string;
  evidence: string[];
  follow_up_tasks: string[];
  predicted_cost: number;
  predicted_revenue_protected: number;
}

export interface CaseDetail {
  case_id: string;
  disruption_id: string;
  supplier_id: string;
  part_id: string;
  plant_id: string;
  title: string;
  status: string;
  severity: string;
  signal_reference: string;
  signal_received_at: string;
  summary: string;
  horizon_start: string;
  horizon_end: string;
  facts: string[];
  uncertainties: string[];
  evidence: EvidenceItem[];
  exposure: ExposureResult | null;
  scenarios: ScenarioEvaluation[];
  actions: ActionResponse[];
  revenue_at_risk: number;
  margin_at_risk: number;
  otif_lines_at_risk: number;
}

export interface DecisionResponse {
  case_id: string;
  status: string;
  action: ActionResponse;
  scenario: ScenarioEvaluation;
  bounded_actions: string[];
}

export interface DashboardSummary {
  generated_at: string;
  active_cases: number;
  cases_by_status: Record<string, number>;
  cases_by_severity: Record<string, number>;
  total_revenue_at_risk: number;
  total_margin_at_risk: number;
  total_otif_lines_at_risk: number;
  approved_actions: number;
  rejected_actions: number;
  average_minutes_to_decision: number | null;
}

export interface AnalyzeResponse {
  case_id: string;
  status: string;
  analyzed_at: string;
  calculation_version: string;
  exposure: ExposureResult;
  scenarios: ScenarioEvaluation[];
  recommended_scenario_id: string | null;
  facts: string[];
  uncertainties: string[];
  evidence: EvidenceItem[];
}
