import { afterEach, describe, expect, it, vi } from "vitest";
import { getCase } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("uses the backend case contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok: true, json: async () => ({case_id: "RL-CASE-1", disruption: {}, status: "open", scenarios: [], selected_scenario_id: null})});
    vi.stubGlobal("fetch", fetchMock);
    const result = await getCase("RL-CASE-1");
    expect(result.case_id).toBe("RL-CASE-1");
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
