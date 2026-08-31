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

export type RuntimeMode = "live" | "fallback";
export type CasePurpose = "automated_test" | "rehearsal" | "showcase";
export type CorpusScope = "demo_corpus" | "real_business" | "unspecified";
export type ResponseOptionKind =
  | "no_mitigation"
  | "expedite"
  | "transfer"
  | "resequence"
  | "alternate_source"
  | "combined";

export interface CaseInstance {
  case_id: string;
  template_id: string;
  purpose: CasePurpose;
  runtime_mode: RuntimeMode;
  scenario_effective_time: string;
  scenario_timezone: "America/Chicago";
  status: CaseStatus;
}

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

export type AuthorityScope =
  | "operational_quantity"
  | "operational_date"
  | "qualification_state"
  | "supplier_statement"
  | "collaboration_statement"
  | "prerequisite_approval";

export interface ResponseOptionEvidenceRequirement {
  evidence_id: string;
  authority_scope: AuthorityScope[];
}

export interface ResponseOption {
  option_id: string;
  option_kind: ResponseOptionKind;
  name: string;
  executable: boolean;
  active_mitigation: boolean;
  predicted: PredictedOutcome | null;
  assumptions: string[];
  evidence_ids: string[];
  evidence_requirements: ResponseOptionEvidenceRequirement[];
  blocking_codes: string[];
  prerequisite_roles: string[];
  source_data_lineage: string[];
  approval_burden: number;
  execution_risk: number;
  requested_side_effects: string[];
}

export interface RankingStage {
  comparator: string;
  threshold: string;
  lower_is_better: boolean;
  input_option_ids: string[];
  values: {option_id: string; value: string}[];
  retained_option_ids: string[];
  eliminated_option_ids: string[];
}

export interface RankingResult {
  policy_version: string;
  eligible_option_ids: string[];
  infeasible_option_ids: string[];
  excluded_baseline_ids: string[];
  stages: RankingStage[];
  recommended_option_id: string | null;
  no_feasible_mitigation: boolean;
}

export interface EvidenceValidation {
  policy_version: string;
  blocking_codes: string[];
  item_results: {
    evidence_id: string;
    requirement: "required_authoritative" | "contextual";
    validated_authority_scope: AuthorityScope[];
    freshness: "current" | "stale";
    business_validity: "valid" | "not_yet_effective" | "expired";
    uncertainty_state: "certain" | "uncertain" | "conflicted";
    retrieval_health: "healthy" | "unhealthy";
    authoritative: boolean;
    blocking_codes: string[];
  }[];
}

export interface AuthorizationConditions {
  allowed_option_kinds: ResponseOptionKind[];
  maximum_response_cost: string;
  allowed_corpora: CorpusScope[];
  allowed_template_ids: string[];
  allowed_case_purposes: CasePurpose[];
  valid_from: string;
  valid_through: string;
  forbidden_external_side_effects: string[];
}

export interface ApprovalTarget {
  case: CaseInstance;
  corpus: CorpusScope;
  scenario_effective_time: string;
  total_response_cost: string;
  requested_side_effects: string[];
}

export interface ApprovalSatisfaction {
  analysis_id: string;
  option_id: string;
  authorization_id: string;
  persona_id: string;
  role: string;
  satisfied: boolean;
  target: ApprovalTarget;
  authorization_conditions: AuthorizationConditions;
}

export interface AnalysisVersion {
  analysis_id: string;
  case_id: string;
  analysis_started_at: string;
  retrieval_window_ends_at: string;
  created_at: string;
  material_hash: string;
  material: {
    calculation_version: string;
    evidence_policy_version: string;
    approval_policy_version: string;
    required_authority_scope: AuthorityScope[];
  };
  evidence_items: {
    evidence_id: string;
    source_id: string;
    retrieved_at: string | null;
  }[];
  evidence_validation: EvidenceValidation;
  response_options: ResponseOption[];
  approval_satisfactions: ApprovalSatisfaction[];
  ranking: RankingResult;
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
