import {describe, expect, it} from "vitest";
import type {EvidenceItemValidation} from "../types";
import {evidenceStatus, type StatusItem, type StatusContext} from "./evidenceStatus";

const item: StatusItem = {
  evidence_id: "e1", case_id: "c1", source_system: "work_iq",
  runtime_mode: "live", synthetic: false, retrieval_health: "healthy",
  retrieved_for_analysis_id: "a1", retrieved_at: "2026-09-08T15:00:00Z",
};
const validation: EvidenceItemValidation = {
  evidence_id: "e1", requirement: "required_authoritative",
  validated_authority_scope: ["supplier_statement"], freshness: "current",
  business_validity: "valid", uncertainty_state: "certain",
  retrieval_health: "healthy", authoritative: true, blocking_codes: [],
};
const context: StatusContext = {
  case_id: "c1", analysis_id: "a1", runtime_mode: "live",
  analysis_started_at: "2026-09-08T14:59:00Z",
  retrieval_window_ends_at: "2026-09-08T15:01:00Z",
  created_at: "2026-09-08T15:00:01Z", results: [validation],
};

describe("evidence status", () => {
  it("uses recorded retrieval and policy results, not a confidence promise", () => {
    expect(evidenceStatus(item, context)).toMatchObject({
      platform: "Work IQ", retrieval: "Retrieved for this analysis",
      recordedAt: item.retrieved_at, validation: "Required checks passed",
      warning: null,
    });
  });
  it("does not infer validation from successful retrieval", () => {
    const result = evidenceStatus(item, {...context, results: []});
    expect(result.validation).toBe("Check result unavailable");
    expect(result.warning).toBe("Check result unavailable for this source");
  });
  it("uses plain consequences for identity and retrieval failures", () => {
    expect(evidenceStatus({...item, case_id: "other"}, context).warning)
      .toBe("Source does not belong to this analysis");
    expect(evidenceStatus({...item, retrieval_health: "unhealthy"}, context).warning)
      .toBe("Source could not be retrieved for this analysis");
  });
  it("does not treat fixture provenance as a live retrieval", () => {
    expect(evidenceStatus({...item, synthetic: true}, context)).toMatchObject({
      platform: "Demo data", retrieval: "Sample data — not a live retrieval",
      recordedAt: null,
    });
  });
  it.each([
    {...item, case_id: "other"}, {...item, retrieved_for_analysis_id: "old"},
    {...item, runtime_mode: "fallback" as const},
    {...item, retrieval_health: "unhealthy" as const},
    {...item, retrieved_at: null}, {...item, retrieved_at: "bad"},
    {...item, retrieved_at: "2026-09-08T16:00:00Z"},
  ])("does not claim a valid current retrieval for %j", (changed) => {
    const result = evidenceStatus(changed, context);
    expect(result.retrieval).not.toBe("Retrieved for this analysis");
    expect(result.warning).not.toBeNull();
  });
  it.each([
    {...validation, freshness: "stale" as const},
    {...validation, business_validity: "expired" as const},
    {...validation, uncertainty_state: "conflicted" as const},
    {...validation, retrieval_health: "unhealthy" as const},
    {...validation, blocking_codes: ["EVIDENCE_TIMESTAMP_STALE"]},
  ])("exposes failed checks independently from retrieval", (changed) => {
    const result = evidenceStatus(item, {...context, results: [changed]});
    expect(result.validation).not.toBe("Required checks passed");
    expect(result.warning).not.toBeNull();
  });
  it("does not select arbitrarily between duplicate validation results", () => {
    expect(evidenceStatus(item, {...context, results: [validation, validation]}).validation)
      .toBe("Check result unavailable");
  });
  it("warns when a synthetic fixture has invalid policy evidence", () => {
    const result = evidenceStatus({...item, synthetic: true}, {
      ...context,
      results: [{...validation, freshness: "stale"}],
    });
    expect(result.retrieval).toBe("Sample data — not a live retrieval");
    expect(result.warning).not.toBeNull();
    expect(result.validation).not.toBe("Required checks passed");
  });
  it("warns for synthetic evidence with the wrong analysis binding", () => {
    const result = evidenceStatus({...item, synthetic: true, case_id: "other"}, context);
    expect(result.warning).toBe("Source does not belong to this analysis");
    expect(result.retrieval).toBe("Sample data — not a live retrieval");
  });
  it("warns when synthetic retrieval health is unhealthy", () => {
    const result = evidenceStatus({...item, synthetic: true, retrieval_health: "unhealthy"}, context);
    expect(result.warning).toBe("Source could not be retrieved for this analysis");
  });
  it("warns for missing or duplicate validation results", () => {
    expect(evidenceStatus({...item, synthetic: true}, {...context, results: []}).warning)
      .toBe("Check result unavailable for this source");
    expect(evidenceStatus({...item, synthetic: true}, {...context, results: [validation, validation]}).warning)
      .toBe("Check result unavailable for this source");
  });
  it("keeps valid fallback server evidence distinct from fixtures", () => {
    const result = evidenceStatus({...item, source_system: "server", runtime_mode: "fallback"}, {
      ...context, runtime_mode: "fallback",
    });
    expect(result.platform).toBe("Other source");
    expect(result.retrieval).toBe("Recorded for this analysis (fallback)");
    expect(result.warning).toBeNull();
  });
  it("labels valid contextual evidence as supporting context", () => {
    const result = evidenceStatus(item, {
      ...context,
      results: [{...validation, requirement: "contextual", authoritative: false}],
    });
    expect(result.validation).toBe("Context only — not authoritative evidence");
    expect(result.warning).toBeNull();
  });
  it("does not accept non-authoritative required evidence", () => {
    const result = evidenceStatus(item, {
      ...context,
      results: [{...validation, authoritative: false}],
    });
    expect(result.validation).toBe("Required checks did not pass");
    expect(result.warning).not.toBeNull();
  });
  it.each([
    "retrieved_at",
    "analysis_started_at",
    "retrieval_window_ends_at",
    "created_at",
  ] as const)("rejects impossible calendar dates in %s", (field) => {
    const impossibleTimestamp = "2026-02-30T15:00:00Z";
    const marchSecondContext: StatusContext = {
      ...context,
      analysis_started_at: "2026-03-02T14:59:00Z",
      retrieval_window_ends_at: "2026-03-02T15:01:00Z",
      created_at: "2026-03-02T15:00:01Z",
    };
    const changedItem = {...item, retrieved_at: "2026-03-02T15:00:00Z"};
    const changedContext = field === "retrieved_at"
      ? marchSecondContext
      : {...marchSecondContext, [field]: impossibleTimestamp};
    const result = evidenceStatus(
      field === "retrieved_at" ? {...changedItem, retrieved_at: impossibleTimestamp} : changedItem,
      changedContext,
    );
    expect(result.retrieval).not.toBe("Retrieved for this analysis");
    expect(result.validation).not.toBe("Required checks passed");
    expect(result.warning).not.toBeNull();
  });
});
