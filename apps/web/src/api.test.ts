import { afterEach, describe, expect, it, vi } from "vitest";
import { getCase } from "./api";
import type { AnalysisVersion, ResponseOption } from "./types";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("represents the canonical backend response-option contract", () => {
    const option: ResponseOption = {
      option_id: "RL-OPTION-BETA",
      option_kind: "alternate_source",
      name: "Source from Supplier Beta",
      executable: false,
      active_mitigation: true,
      predicted: null,
      assumptions: [],
      evidence_ids: ["RL-QUALITY-001"],
      evidence_requirements: [{evidence_id: "RL-QUALITY-001", authority_scope: ["qualification_state"]}],
      blocking_codes: ["QUALITY_QUALIFICATION_PENDING"],
      prerequisite_roles: ["material_planner", "quality_approver"],
      source_data_lineage: ["RL-QUALITY-001"],
      approval_burden: 2,
      execution_risk: 2,
      requested_side_effects: [],
    };

    expect(option.blocking_codes).toEqual(["QUALITY_QUALIFICATION_PENDING"]);
    expect(option.evidence_ids).toEqual(["RL-QUALITY-001"]);
    expect(option.prerequisite_roles).toContain("quality_approver");
  });

  it("types the analysis audit and elimination-trace contract", () => {
    const analysis: AnalysisVersion = {
      analysis_id: "RL-ANALYSIS-1",
      case_id: "RL-CASE-1",
      analysis_started_at: "2026-08-31T12:00:00Z",
      retrieval_window_ends_at: "2026-08-31T12:00:01Z",
      created_at: "2026-08-31T12:00:01Z",
      material_hash: "a".repeat(64),
      material: {
        case_id: "RL-CASE-1",
        template_id: "RL-001",
        case_purpose: "showcase",
        runtime_mode: "fallback",
        corpus: "demo_corpus",
        scenario_effective_time: "2026-09-01T09:00:00-05:00",
        operational_snapshot_json: '{"case_id":"RL-CASE-1"}',
        calculation_version: "rl001-options-v1",
        evidence_policy_version: "evidence-policy-v3",
        approval_policy_version: "standing-authorization-v1",
        required_authority_scope: ["operational_date"],
        evidence: [{
          evidence_id: "RL-E-1",
          case_id: "RL-CASE-1",
          kind: "operational_fact",
          authority_scope: ["operational_date"],
          source_system: "synthetic_fixture",
          source_id: "RL-SOURCE-1",
          source_timestamp: "2026-08-31T11:59:00Z",
          effective_at: "2026-09-01T09:00:00-05:00",
          expires_at: "2026-09-02T09:00:00-05:00",
          claim: "Transfer date is confirmed.",
          citation_present: true,
          source_metadata_complete: true,
          runtime_mode: "fallback",
          synthetic: true,
          requirement: "required_authoritative",
          uncertainty_state: "certain",
          validation: {
            evidence_id: "RL-E-1",
            requirement: "required_authoritative",
            validated_authority_scope: ["operational_date"],
            freshness: "current",
            business_validity: "valid",
            uncertainty_state: "certain",
            retrieval_health: "healthy",
            authoritative: true,
            blocking_codes: [],
          },
        }],
        conflicts: [{
          conflict_id: "RL-CONFLICT-1",
          case_id: "RL-CASE-1",
          evidence_ids: ["RL-E-1", "RL-E-2"],
          authority_scope: ["operational_date"],
          description: "Dates initially differed.",
          feasibility_relevant: true,
        }],
        conflict_resolutions: [{
          conflict_id: "RL-CONFLICT-1",
          governing_evidence_id: "RL-E-1",
          actor: {
            persona_id: "RL-PERSONA-ALEX",
            roles: ["material_planner"],
            identity_source: "entra",
            source_id: "RL-ENTRA-ALEX",
          },
          why: "The operational record governs.",
        }],
        evidence_validation: {
          policy_version: "evidence-policy-v3",
          blocking_codes: [],
          global_blocking_codes: [],
          item_results: [{
            evidence_id: "RL-E-1",
            requirement: "required_authoritative",
            validated_authority_scope: ["operational_date"],
            freshness: "current",
            business_validity: "valid",
            uncertainty_state: "certain",
            retrieval_health: "healthy",
            authoritative: true,
            blocking_codes: [],
          }],
        },
        response_options: [{
          option_id: "RL-OPTION-COMBINED",
          option_kind: "combined",
          executable: true,
          active_mitigation: true,
          predicted: {
            uncovered_part_demand: 2300,
            otif_loss_percentage: 50,
            revenue_at_risk: "375000.00",
            margin_at_risk: "125000.00",
            response_cost: "24750.00",
            protected_customer_order_ids: ["RL-CO-DEMO-2"],
          },
          assumptions: ["Remaining supplier recovery date is unconfirmed."],
          evidence_ids: ["RL-E-1"],
          evidence_requirements: [{evidence_id: "RL-E-1", authority_scope: ["operational_date"]}],
          blocking_codes: [],
          prerequisite_roles: ["material_planner", "finance_approver"],
          source_data_lineage: ["RL-E-1"],
          approval_burden: 2,
          execution_risk: 6,
          requested_side_effects: [],
        }],
        standing_authorizations: [{
          authorization_id: "RL-AUTH-TAYLOR-FINANCE-1",
          persona_id: "RL-PERSONA-TAYLOR",
          role: "finance_approver",
          conditions: {
            allowed_option_kinds: ["combined"],
            maximum_response_cost: "25000.00",
            allowed_corpora: ["demo_corpus"],
            allowed_template_ids: ["RL-001"],
            allowed_case_purposes: ["showcase"],
            valid_from: "2026-09-01T09:00:00-05:00",
            valid_through: "2026-09-15T09:00:00-05:00",
            forbidden_external_side_effects: [],
          },
        }],
        approval_satisfactions: [{
          option_id: "RL-OPTION-COMBINED",
          authorization_id: "RL-AUTH-TAYLOR-FINANCE-1",
          persona_id: "RL-PERSONA-TAYLOR",
          role: "finance_approver",
          satisfied: true,
          target: {
            case_id: "RL-CASE-1",
            template_id: "RL-001",
            purpose: "showcase",
            runtime_mode: "fallback",
            scenario_effective_time: "2026-09-01T09:00:00-05:00",
            corpus: "demo_corpus",
            total_response_cost: "24750.00",
            requested_side_effects: [],
          },
          authorization_conditions: {
            allowed_option_kinds: ["combined"],
            maximum_response_cost: "25000.00",
            allowed_corpora: ["demo_corpus"],
            allowed_template_ids: ["RL-001"],
            allowed_case_purposes: ["showcase"],
            valid_from: "2026-09-01T09:00:00-05:00",
            valid_through: "2026-09-15T09:00:00-05:00",
            forbidden_external_side_effects: [],
          },
        }],
        ranking: {
          policy_version: "thresholded-lexicographic-v1",
          eligible_option_ids: ["RL-OPTION-COMBINED"],
          infeasible_option_ids: ["RL-OPTION-BETA"],
          excluded_baseline_ids: ["RL-OPTION-NO-MITIGATION"],
          stages: [],
          recommended_option_id: "RL-OPTION-COMBINED",
          no_feasible_mitigation: false,
        },
      },
      evidence_items: [{
        evidence_id: "RL-E-1",
        case_id: "RL-CASE-1",
        kind: "operational_fact",
        authority_scope: ["operational_date"],
        source_system: "synthetic_fixture",
        source_id: "RL-SOURCE-1",
        source_timestamp: "2026-08-31T11:59:00Z",
        retrieved_at: "2026-08-31T12:00:00Z",
        retrieved_for_analysis_id: "RL-ANALYSIS-1",
        retrieval_health: "healthy",
        effective_at: "2026-09-01T09:00:00-05:00",
        expires_at: "2026-09-02T09:00:00-05:00",
        claim: "Transfer date is confirmed.",
        excerpt: "Transfer date is confirmed.",
        citation_url: "https://rl.example/evidence/RL-E-1",
        runtime_mode: "fallback",
        synthetic: true,
        requirement: "required_authoritative",
        uncertainty_state: "certain",
      }],
      evidence_validation: {
        policy_version: "evidence-policy-v3",
        blocking_codes: [],
        global_blocking_codes: [],
        item_results: [{
          evidence_id: "RL-E-1",
          requirement: "required_authoritative",
          validated_authority_scope: ["operational_date"],
          freshness: "current",
          business_validity: "valid",
          uncertainty_state: "certain",
          retrieval_health: "healthy",
          authoritative: true,
          blocking_codes: [],
        }],
      },
      response_options: [],
      approval_satisfactions: [{
        analysis_id: "RL-ANALYSIS-1",
        option_id: "RL-OPTION-COMBINED",
        authorization_id: "RL-AUTH-TAYLOR-FINANCE-1",
        persona_id: "RL-PERSONA-TAYLOR",
        role: "finance_approver",
        satisfied: true,
        target: {
          case: {
            case_id: "RL-CASE-1",
            template_id: "RL-001",
            purpose: "showcase",
            runtime_mode: "fallback",
            scenario_effective_time: "2026-09-01T09:00:00-05:00",
            scenario_timezone: "America/Chicago",
            status: "awaiting_decision",
          },
          corpus: "demo_corpus",
          scenario_effective_time: "2026-09-01T09:00:00-05:00",
          total_response_cost: "24750.00",
          requested_side_effects: [],
        },
        authorization_conditions: {
          allowed_option_kinds: ["combined"],
          maximum_response_cost: "25000.00",
          allowed_corpora: ["demo_corpus"],
          allowed_template_ids: ["RL-001"],
          allowed_case_purposes: ["showcase"],
          valid_from: "2026-09-01T09:00:00-05:00",
          valid_through: "2026-09-15T09:00:00-05:00",
          forbidden_external_side_effects: [],
        },
      }],
      ranking: {
        policy_version: "thresholded-lexicographic-v1",
        eligible_option_ids: ["RL-OPTION-COMBINED"],
        infeasible_option_ids: ["RL-OPTION-BETA"],
        excluded_baseline_ids: ["RL-OPTION-NO-MITIGATION"],
        stages: [{
          comparator: "uncovered_part_demand",
          threshold: "500",
          lower_is_better: true,
          input_option_ids: ["RL-OPTION-COMBINED", "RL-OPTION-EXPEDITE"],
          values: [
            {option_id: "RL-OPTION-COMBINED", value: "2300"},
            {option_id: "RL-OPTION-EXPEDITE", value: "3800"},
          ],
          retained_option_ids: ["RL-OPTION-COMBINED"],
          eliminated_option_ids: ["RL-OPTION-EXPEDITE"],
        }],
        recommended_option_id: "RL-OPTION-COMBINED",
        no_feasible_mitigation: false,
      },
    };

    expect(analysis.ranking.stages[0].threshold).toBe("500");
    expect(analysis.evidence_validation.item_results[0].authoritative).toBe(true);
    expect(analysis.approval_satisfactions[0].role).toBe("finance_approver");
    expect(analysis.material.scenario_effective_time).toContain("2026-09-01");
    expect(analysis.material.operational_snapshot_json).toContain("RL-CASE-1");
    expect(analysis.material.evidence[0].claim).toBe("Transfer date is confirmed.");
    expect(analysis.material.conflict_resolutions[0].actor.persona_id).toBe("RL-PERSONA-ALEX");
    expect(analysis.material.response_options[0].source_data_lineage).toEqual(["RL-E-1"]);
    expect(analysis.material.standing_authorizations[0].conditions.maximum_response_cost).toBe("25000.00");
    expect(analysis.material.approval_satisfactions[0].target.corpus).toBe("demo_corpus");
    expect(analysis.evidence_items[0].citation_url).toContain("RL-E-1");
    expect(analysis.evidence_items[0].excerpt).toBe("Transfer date is confirmed.");
    expect(analysis.material_hash).toHaveLength(64);
  });

  it("uses the backend case contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok: true, json: async () => ({case: {case_id: "RL-CASE-1", status: "open"}, disruption: {}, analysis: null, selected_option_id: null})});
    vi.stubGlobal("fetch", fetchMock);
    const result = await getCase("RL-CASE-1");
    expect(result.case.case_id).toBe("RL-CASE-1");
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
