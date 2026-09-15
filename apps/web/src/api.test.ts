import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError, api, safeErrorMessage, setAccessTokenProvider } from "./api";
import type { AnalysisVersion, ResponseOption } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessTokenProvider(async () => null);
});

describe("API client", () => {
  it("creates from the server-issued presenter run and reviewed email identity without copied facts or message text", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok:true,json:async()=>({case_id:"email-case"})});
    vi.stubGlobal("fetch", fetchMock);
    await api.createCaseFromEmail("RL-RUN-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "<email@example.com>", "a".repeat(64));
    expect(fetchMock).toHaveBeenCalledWith("/api/inbox/cases", expect.objectContaining({
      method:"POST",body:JSON.stringify({presenter_run_id:"RL-RUN-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",internet_message_id:"<email@example.com>",review_fingerprint:"a".repeat(64)}),
    }));
  });
  it("maps live source failures to safe display copy without leaking diagnostics", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: "LIVE_SOURCE_UNAVAILABLE",
        message: "Internal exception: tenant secret failed",
        traceback: "SensitiveTraceback",
      },
    }), {status: 503, headers: {"Content-Type": "application/json"}})));

    await expect(api.runtime()).rejects.toThrow(
      "The information needed for this analysis could not be retrieved.",
    );

    await api.runtime().catch((error: unknown) => {
      expect(String(error)).not.toContain("tenant secret");
      expect(String(error)).not.toContain("SensitiveTraceback");
      expect(String(error)).not.toContain("LIVE_SOURCE_UNAVAILABLE");
    });
  });

  it("uses a generic safe message for unknown JSON and HTML failures", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        detail: {code: "UNKNOWN_FAILURE", exception: "DatabaseError: password=secret"},
      }), {status: 500, headers: {"Content-Type": "application/json"}}))
      .mockResolvedValueOnce(new Response("<html><body>proxy secret traceback</body></html>", {
        status: 502,
        headers: {"Content-Type": "text/html"},
      }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.runtime()).rejects.toThrow("The request could not be completed.");
    await expect(api.runtime()).rejects.toThrow("The request could not be completed.");

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each(["constructor", "toString"])("does not treat inherited key %s as a safe error code", async (code) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: {code}}), {
      status: 500,
      headers: {"Content-Type": "application/json"},
    })));

    await expect(api.runtime()).rejects.toThrow("The request could not be completed.");
  });

  it("derives display copy from the allowlisted code rather than a mutable error message", () => {
    const error = new ApiRequestError("untrusted mutable message", 503, "LIVE_SOURCE_UNAVAILABLE");
    expect(safeErrorMessage(error)).toBe("The information needed for this analysis could not be retrieved.");
  });

  it("attaches fresh bearer tokens dynamically without persistence", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ok: true, json: async () => ({runtime_mode: "fallback"})})
      .mockResolvedValueOnce({ok: true, json: async () => ({runtime_mode: "fallback"})});
    vi.stubGlobal("fetch", fetchMock);
    const tokens = ["first-token", "second-token"];
    setAccessTokenProvider(async () => tokens.shift() ?? null);

    await api.runtime();
    await api.runtime();

    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      headers: {Authorization: "Bearer first-token"},
    });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      headers: {Authorization: "Bearer second-token"},
    });
  });

  it.each([
    ["GET", () => api.runtime()],
    ["POST", () => api.createCase("showcase")],
  ])("does not send a %s request when token acquisition fails", async (_method, request) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    setAccessTokenProvider(async () => { throw new Error("authentication recovery required"); });

    await expect(request()).rejects.toThrow("authentication recovery required");

    expect(fetchMock).not.toHaveBeenCalled();
  });

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
      runtime_mode: "fallback",
      scenario_effective_time: "2026-09-01T09:00:00-05:00",
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
      recommendation: null,
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

  it("uses typed Task 9 routes and sends the decision idempotency header", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok: true, json: async () => ({})});
    vi.stubGlobal("fetch", fetchMock);

    await api.runtime();
    await api.createCase("showcase");
    await api.analyze("RL-CASE-1");
    await api.decide(
      "RL-CASE-1",
      {analysis_id: "RL-ANALYSIS-1", kind: "approved", selected_option_id: "RL-OPTION-COMBINED"},
      "RL-WEB-DECISION-1",
    );
    await api.decision("RL-DECISION-1");
    await api.actions("RL-DECISION-1");
    await api.retryAction("RL-DECISION-1", "RL-ACTION-1");
    await api.startPlayback("RL-DECISION-1");
    await api.playback("RL-DECISION-1");
    await api.observations("RL-DECISION-1");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/runtime", undefined);
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/cases", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({template_id: "RL-001", purpose: "showcase"}),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/cases/RL-CASE-1/decisions", {
      method: "POST",
      headers: {"Content-Type": "application/json", "Idempotency-Key": "RL-WEB-DECISION-1"},
      body: JSON.stringify({
        analysis_id: "RL-ANALYSIS-1",
        kind: "approved",
        selected_option_id: "RL-OPTION-COMBINED",
      }),
    });
  });

  it("never sends a caller-owned runtime mode override", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok: true, json: async () => ({})});
    vi.stubGlobal("fetch", fetchMock);

    await api.createCase("rehearsal");

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(request.body).toBe(JSON.stringify({template_id: "RL-001", purpose: "rehearsal"}));
    expect(request.body).not.toContain("runtime_mode");
  });

  it("uses the authenticated Finance journey contracts without changing command intent", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok: true, json: async () => ({})});
    vi.stubGlobal("fetch", fetchMock);
    const expected = {generation: 3, analysis_id: "analysis-1", analysis_material_hash: "a".repeat(64), selection_id: "selection-1"};

    await api.me();
    await api.proposal("case/1");
    await api.submitProposal("case/1", {option_id: "option-1", expected}, "submit-key");
    await api.financeReviews();
    await api.financeReview("review/1");
    await api.resolveFinanceReview("review/1", {expected, expected_review_revision: 2, approved: false, reason: "Revise cost"}, "resolve-key");
    await api.finalizeProposal("case/1", {expected, kind: "approved"}, "final-key");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/me", undefined);
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/cases/case%2F1/proposal", undefined);
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/cases/case%2F1/proposals", expect.objectContaining({
      method: "POST", headers: {"Content-Type": "application/json", "Idempotency-Key": "submit-key"},
      body: JSON.stringify({option_id: "option-1", expected}),
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(6, "/api/finance/reviews/review%2F1/resolutions", expect.objectContaining({
      method: "POST", headers: {"Content-Type": "application/json", "Idempotency-Key": "resolve-key"},
      body: JSON.stringify({expected, expected_review_revision: 2, approved: false, reason: "Revise cost"}),
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(7, "/api/cases/case%2F1/proposal-decisions", expect.objectContaining({
      method: "POST", headers: {"Content-Type": "application/json", "Idempotency-Key": "final-key"},
      body: JSON.stringify({expected, kind: "approved"}),
    }));
  });
});
