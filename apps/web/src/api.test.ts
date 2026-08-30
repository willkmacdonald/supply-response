import { afterEach, describe, expect, it, vi } from "vitest";
import { getCase } from "./api";
import type { ResponseScenario } from "./types";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("represents the complete backend scenario metadata contract", () => {
    const scenario: ResponseScenario = {
      scenario_id: "RL-SCENARIO-5",
      disruption_id: "RL-DISRUPTION-001",
      name: "Source from Supplier Beta",
      executable: false,
      constraint_violations: ["RL-QUALITY-001: alternate supplier is not approved"],
      constraint_codes: ["QUALITY_NOT_APPROVED"],
      evidence_refs: ["RL-QUALITY-001"],
      required_approver_roles: ["material_planner"],
      response_cost: "0",
      revenue_protected: "0",
      remaining_uncertainty: ["Supplier Beta approval date remains conditional"],
    };

    expect(scenario.constraint_codes).toEqual(["QUALITY_NOT_APPROVED"]);
    expect(scenario.evidence_refs).toEqual(["RL-QUALITY-001"]);
    expect(scenario.required_approver_roles).toEqual(["material_planner"]);
  });

  it("uses the backend case contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok: true, json: async () => ({case_id: "RL-CASE-1", disruption: {}, status: "open", scenarios: [], selected_scenario_id: null})});
    vi.stubGlobal("fetch", fetchMock);
    const result = await getCase("RL-CASE-1");
    expect(result.case_id).toBe("RL-CASE-1");
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
