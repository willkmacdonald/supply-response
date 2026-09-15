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
export type WorkflowVersion = "standing-authorization-v1" | "independent-finance-v1";
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
  current_analysis_id: string | null;
  current_decision_id: string | null;
  display_status: string | null;
  recorded_at: string;
  projection_updated_at: string;
  controls: CaseControls;
  workflow_version?: WorkflowVersion;
  supplier_email?: {sender: string; subject: string; received_at: string} | null;
  presenter_run_id?: string | null;
}

export interface CaseControls {
  new_analysis: boolean;
  decide: boolean;
  retry_action_planning: boolean;
  start_playback: boolean;
}

export interface RuntimeStatus {
  runtime_mode: RuntimeMode;
  work_iq: "synthetic" | "work_iq";
  operational_store: "sqlite" | "fabric_sql";
  agent_runtime: "local" | "foundry";
  power_bi_available: boolean;
  power_bi_url?: string | null;
  capability_health?: Record<string, "configured" | "unverified" | "ready" | "unavailable">;
  deployment_contract?: Record<string, string> | null;
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

export interface IdentitySnapshot {
  persona_id: string;
  effective_roles: string[];
  identity_source: "entra";
  source_id: string;
  tenant_id: string | null;
  object_id: string | null;
  display_name: string | null;
  user_principal_name: string | null;
}

export interface SessionInfo {
  mode: "entra" | "fallback";
  persona_id: string | null;
  display_name: string | null;
  independent_finance_enabled: boolean;
}

export interface ProposalToken { generation: number; analysis_id: string | null; analysis_material_hash: string | null; selection_id: string | null }
export interface FinanceProposal { case_id: string; analysis_id: string; analysis_material_hash: string; option_id: string; response_cost: string }
export interface ProposalSelection { selection_id: string; proposal: FinanceProposal; workflow_version: WorkflowVersion; submitted_by: IdentitySnapshot; submitted_at: string; finance_review_id: string | null }
export interface FinanceReview { review_id: string; proposal: FinanceProposal; submitted_by: IdentitySnapshot; submitted_at: string; status: "pending" | "approved" | "rejected" | "superseded"; reviewed_by: IdentitySnapshot | null; reviewed_at: string | null; reason: string | null; superseded_at: string | null }
export interface ProposalState { token: ProposalToken; selection: ProposalSelection | null; review: FinanceReview | null; review_revision: number | null }
export interface SubmissionResult { selection: ProposalSelection; review: FinanceReview | null; review_revision: number | null }
export interface ResolutionResult { review: FinanceReview; review_revision: number }
export interface FinanceReviewDetail { selection: ProposalSelection; review: FinanceReview; review_revision: number; analysis: AnalysisVersion; option: ResponseOption; is_current: boolean; current_token: ProposalToken }
export interface SubmitProposalInput { option_id: string; expected: ProposalToken }
export interface ResolveFinanceInput { expected: ProposalToken; expected_review_revision: number; approved: boolean; reason?: string }
export interface FinalizeProposalInput { expected: ProposalToken; kind: "approved" | "rejected"; rejection_reason?: string }

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
  citation_classification?: "fabric" | "work_iq" | "untrusted" | null;
  navigable_citation_url?: string | null;
  citation_trusted_host?: string | null;
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

export type CaseMaterial = Pick<
  CaseInstance,
  | "case_id"
  | "template_id"
  | "purpose"
  | "runtime_mode"
  | "scenario_effective_time"
  | "scenario_timezone"
  | "status"
>;

export interface ApprovalTarget {
  case: CaseMaterial;
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
  runtime_mode: RuntimeMode;
  scenario_effective_time: string;
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
  recommendation: ResponseOption | null;
}

export type DecisionInput =
  | {
      analysis_id: string;
      kind: "approved";
      selected_option_id: string;
    }
  | {
      analysis_id: string;
      kind: "rejected";
      rejection_reason: string;
    };

export interface Decision {
  decision_id: string;
  case_id: string;
  analysis_id: string;
  analysis_material_hash: string;
  kind: "approved" | "rejected";
  selected_option_id: string | null;
  rejection_reason: string | null;
  evidence_ids: string[];
  assumptions: string[];
  constraints: string[];
  prerequisite_roles: string[];
  approval_satisfactions: ApprovalSatisfaction[];
  calculation_version: string;
  evidence_policy_version: string;
  approval_policy_version: string;
  ranking_policy_version: string;
  runtime_mode: RuntimeMode;
  scenario_effective_time: string;
  decided_at: string;
  projection_updated_at: string;
  action_planning_status: "not_applicable" | "pending" | "failed" | "complete";
  new_analysis_available: boolean;
  proposal_approval_evidence?: {selection: ProposalSelection; review: FinanceReview | null; review_revision: number | null} | null;
}

export interface ExecutionAction {
  action_id: string;
  case_id: string;
  decision_id: string;
  kind: string;
  owner_kind: string;
  owner_persona_id: string | null;
  status: string;
  created_at: string;
  draft_artifact_id: string | null;
  purpose: string | null;
  expected_result: string | null;
  execution_mode: "simulation" | "communication_preparation" | null;
  runtime_mode: RuntimeMode;
  scenario_effective_time: string;
  projection_updated_at: string;
}

export interface DraftArtifact {
  artifact_id: string;
  action_id: string;
  decision_id: string;
  artifact_kind: string;
  created_at: string;
  subject: string | null;
  body: string | null;
  sent: false;
  runtime_mode: RuntimeMode;
  scenario_effective_time: string;
}

export interface Playback {
  playback_id: string;
  case_id: string;
  decision_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  failed_at?: string | null;
  error_code?: "PLAYBACK_EXECUTION_FAILED" | null;
  runtime_mode: RuntimeMode;
  scenario_effective_time: string;
}

export interface OutcomeObservation {
  observation_id: string;
  case_id: string;
  decision_id: string;
  playback_id: string | null;
  action_id: string | null;
  metric: string;
  observed_value: string;
  unit: string;
  predicted_value: string;
  scenario_effective_time: string;
  scenario_timezone: "America/Chicago";
  recorded_at: string;
  source_reference: string;
  kind: string;
  synthetic: boolean;
  display_label: string;
  runtime_mode: RuntimeMode;
}
export interface SupplierDisruptionFacts {
  original_quantity: number;
  part_id: string;
  plant_name: string;
  original_due_date: string;
  partial_quantity: number;
  partial_due_date: string;
  additional_cost_per_unit: string;
  remaining_quantity: number;
  recovery_date: string | null;
}

export interface InboxMessage {
  message_id: string;
  subject: string;
  sender: string;
  received_at: string;
  excerpt: string;
  citation_url: string;
  internet_message_id?: string | null;
  review_fingerprint?: string | null;
  facts?: SupplierDisruptionFacts | null;
  creation_blocker?: string | null;
}

export interface InboxCheckResult {
  presenter_run_id: string;
  checked_at: string;
  incomplete: boolean;
  messages: InboxMessage[];
}
