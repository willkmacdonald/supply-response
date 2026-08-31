import { afterEach, describe, expect, it, vi } from "vitest";
import { getCase } from "./api";
import type { ResponseOption } from "./types";

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

  it("uses the backend case contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok: true, json: async () => ({case: {case_id: "RL-CASE-1", status: "open"}, disruption: {}, analysis: null, selected_option_id: null})});
    vi.stubGlobal("fetch", fetchMock);
    const result = await getCase("RL-CASE-1");
    expect(result.case.case_id).toBe("RL-CASE-1");
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
