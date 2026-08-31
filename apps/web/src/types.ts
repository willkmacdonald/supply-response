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
export type ExternalSideEffect =
  | "external_sending"
  | "purchase_order_change"
  | "financial_commitment";
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
export type EvidenceKind =
  | "operational_fact"
  | "source_statement"
  | "prerequisite_approval"
  | "contextual_evidence";
export type EvidenceSourceSystem =
  | "fabric"
  | "sqlite"
  | "work_iq"
  | "server"
  | "synthetic_fixture";
export type EvidenceRequirement = "required_authoritative" | "contextual";
export type FreshnessState = "current" | "stale";
export type BusinessValidityState = "valid" | "not_yet_effective" | "expired";
export type UncertaintyState = "certain" | "uncertain" | "conflicted";
export type RetrievalHealth = "healthy" | "unhealthy";

export interface ActorProvenance {
  persona_id: string;
  roles: string[];
  identity_source: "entra";
  source_id: string;
}

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
  requested_side_effects: ExternalSideEffect[];
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
  global_blocking_codes: string[];
  item_results: EvidenceItemValidation[];
}

export interface EvidenceItemValidation {
  evidence_id: string;
  requirement: EvidenceRequirement;
  validated_authority_scope: AuthorityScope[];
  freshness: FreshnessState;
  business_validity: BusinessValidityState;
  uncertainty_state: UncertaintyState;
  retrieval_health: RetrievalHealth;
  authoritative: boolean;
  blocking_codes: string[];
}

export interface EvidenceItem {
  evidence_id: string;
  case_id: string;
  kind: EvidenceKind;
  authority_scope: AuthorityScope[];
  source_system: EvidenceSourceSystem;
  source_id: string;
  source_timestamp: string | null;
  retrieved_at: string | null;
  retrieved_for_analysis_id: string;
  retrieval_health: RetrievalHealth;
  effective_at: string | null;
  expires_at: string | null;
  claim: string;
  excerpt: string | null;
  citation_url: string | null;
  runtime_mode: RuntimeMode;
  synthetic: boolean;
  requirement: EvidenceRequirement;
  uncertainty_state: UncertaintyState;
}

export interface AuthorizationConditions {
  allowed_option_kinds: ResponseOptionKind[];
  maximum_response_cost: string;
  allowed_corpora: CorpusScope[];
  allowed_template_ids: string[];
  allowed_case_purposes: CasePurpose[];
  valid_from: string;
  valid_through: string;
  forbidden_external_side_effects: ExternalSideEffect[];
}

export interface ApprovalTarget {
  case: CaseInstance;
  corpus: CorpusScope;
  scenario_effective_time: string;
  total_response_cost: string;
  requested_side_effects: ExternalSideEffect[];
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

export interface AnalysisEvidenceMaterial {
  evidence_id: string;
  case_id: string;
  kind: EvidenceKind;
  authority_scope: AuthorityScope[];
  source_system: EvidenceSourceSystem;
  source_id: string;
  source_timestamp: string | null;
  effective_at: string | null;
  expires_at: string | null;
  claim: string;
  citation_present: boolean;
  source_metadata_complete: boolean;
  runtime_mode: RuntimeMode;
  synthetic: boolean;
  requirement: EvidenceRequirement;
  uncertainty_state: UncertaintyState;
  validation: EvidenceItemValidation;
}

export interface AnalysisConflictMaterial {
  conflict_id: string;
  case_id: string;
  evidence_ids: string[];
  authority_scope: AuthorityScope[];
  description: string;
  feasibility_relevant: boolean;
}

export interface AnalysisConflictResolutionMaterial {
  conflict_id: string;
  governing_evidence_id: string;
  actor: ActorProvenance;
  why: string;
}

export type AnalysisResponseOptionMaterial = Omit<ResponseOption, "name">;

export interface AnalysisStandingAuthorizationMaterial {
  authorization_id: string;
  persona_id: string;
  role: string;
  conditions: AuthorizationConditions;
}

export interface AnalysisApprovalTargetMaterial {
  case_id: string;
  template_id: string;
  purpose: CasePurpose;
  runtime_mode: RuntimeMode;
  scenario_effective_time: string;
  corpus: CorpusScope;
  total_response_cost: string;
  requested_side_effects: ExternalSideEffect[];
}

export interface AnalysisApprovalMaterial {
  option_id: string;
  authorization_id: string;
  persona_id: string;
  role: string;
  satisfied: boolean;
  target: AnalysisApprovalTargetMaterial;
  authorization_conditions: AuthorizationConditions;
}

export interface AnalysisMaterial {
  case_id: string;
  template_id: string;
  case_purpose: CasePurpose;
  runtime_mode: RuntimeMode;
  corpus: CorpusScope;
  scenario_effective_time: string;
  operational_snapshot_json: string;
  required_authority_scope: AuthorityScope[];
  evidence: AnalysisEvidenceMaterial[];
  conflicts: AnalysisConflictMaterial[];
  conflict_resolutions: AnalysisConflictResolutionMaterial[];
  evidence_validation: EvidenceValidation;
  response_options: AnalysisResponseOptionMaterial[];
  standing_authorizations: AnalysisStandingAuthorizationMaterial[];
  approval_satisfactions: AnalysisApprovalMaterial[];
  ranking: RankingResult;
  calculation_version: string;
  evidence_policy_version: string;
  approval_policy_version: string;
}

export interface AnalysisVersion {
  analysis_id: string;
  case_id: string;
  analysis_started_at: string;
  retrieval_window_ends_at: string;
  created_at: string;
  material_hash: string;
  material: AnalysisMaterial;
  evidence_items: EvidenceItem[];
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
