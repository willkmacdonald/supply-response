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
        calculation_version: "rl001-options-v1",
        evidence_policy_version: "evidence-policy-v3",
        approval_policy_version: "standing-authorization-v1",
        required_authority_scope: ["operational_date"],
      },
      evidence_items: [{evidence_id: "RL-E-1", source_id: "RL-SOURCE-1", retrieved_at: "2026-08-31T12:00:00Z"}],
      evidence_validation: {
        policy_version: "evidence-policy-v3",
        blocking_codes: [],
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
