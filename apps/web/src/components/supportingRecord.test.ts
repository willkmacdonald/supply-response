import {describe, expect, it} from "vitest";
import {resolveSupportingRecord, type SupportingRecordInput} from "./supportingRecord";
import {editSnapshot, recordFixture, selectRecord} from "./supportingRecord.fixture";

const resolve = (input: SupportingRecordInput) =>
  resolveSupportingRecord(input, input.analysis.evidence_items[0].evidence_id);

describe("exact saved supporting records", () => {
  it("resolves a frozen receipt and exact report context without changing its input", () => {
    const input = recordFixture();
    const before = JSON.stringify(input);
    const result = resolve(input);
    expect(result.status).toBe("available");
    if (result.status !== "available") throw new Error("Expected record");
    expect(result.context).toEqual({caseId: "case-1", analysisId: "analysis-1", runtimeMode: "live",
      evidenceId: "RL-ALPHA-OPTIONAL-3000", recordKind: "shipment",
      recordId: "RL-ALPHA-OPTIONAL-3000", sourceId: "fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000"});
    expect(result.record).toMatchObject({kind: "shipment", quantity: 3000, due_date: "2026-09-06"});
    expect(Object.isFrozen(result.record)).toBe(true);
    expect(Object.isFrozen(result.context)).toBe(true);
    expect(JSON.stringify(input)).toBe(before);
  });

  it.each(["transfer", "qualification"] as const)("resolves %s using its own identity", kind => {
    const input = recordFixture();
    selectRecord(input, kind);
    const result = resolve(input);
    expect(result.status).toBe("available");
    if (result.status !== "available") throw new Error("Expected record");
    expect(result.record.kind).toBe(kind);
    expect(result.context.recordId).toBe(kind === "transfer" ? "RL-TRANSFER-DAL-CHI-1500" : "RL-QUAL-BETA");
  });

  it("preserves zero cost, false flags, and nullable dates", () => {
    const input = recordFixture();
    editSnapshot(input, s => { s.alpha_expedite.incremental_cost_per_unit = "0.00"; });
    expect(resolve(input)).toMatchObject({record: {incremental_cost_per_unit: "0.00"}});
    selectRecord(input, "qualification");
    expect(resolve(input)).toMatchObject({record: {audit_complete: false, first_article_complete: false, effective_date: null}});
  });

  it("resolves a valid transfer when the optional shipment is absent", () => {
    const input = recordFixture();
    selectRecord(input, "transfer");
    editSnapshot(input, s => { s.alpha_expedite = null; });
    expect(resolve(input)).toMatchObject({status: "available", record: {kind: "transfer", transfer_id: "RL-TRANSFER-DAL-CHI-1500"}});
  });

  it.each(["shipment", "transfer", "qualification"] as const)("resolves explicit %s fixture lineage without claiming Fabric", kind => {
    const input = recordFixture();
    if (kind !== "shipment") selectRecord(input, kind);
    input.caseInstance.runtime_mode = "fallback";
    input.analysis.runtime_mode = "fallback";
    input.analysis.material.runtime_mode = "fallback";
    editSnapshot(input, s => { s.runtime_mode = "fallback"; });
    const item = input.analysis.evidence_items[0];
    Object.assign(item, {runtime_mode: "fallback", source_system: "synthetic_fixture", synthetic: true,
      source_id: `RL-SOURCE-${item.evidence_id}`});
    input.analysis.material.evidence = [{...item}];
    expect(resolve(input)).toMatchObject({status: "available", provenance: "Demo fixture — not a live retrieval"});
  });

  const invalid: [string, (input: SupportingRecordInput) => void][] = [
    ["malformed JSON", i => { i.analysis.material.operational_snapshot_json = "{"; }],
    ["array root", i => { i.analysis.material.operational_snapshot_json = "[]"; }],
    ["case", i => { i.caseInstance.case_id = "other"; }],
    ["material case", i => { i.analysis.material.case_id = "other"; }],
    ["snapshot case", i => editSnapshot(i, s => { s.case_id = "other"; })],
    ["runtime", i => { i.caseInstance.runtime_mode = "fallback"; }],
    ["snapshot runtime", i => editSnapshot(i, s => { s.runtime_mode = "fallback"; })],
    ["retrieval analysis", i => { i.analysis.evidence_items[0].retrieved_for_analysis_id = "old"; }],
    ["missing material membership", i => { i.analysis.material.evidence = []; }],
    ["duplicate evidence", i => { i.analysis.evidence_items.push({...i.analysis.evidence_items[0]}); }],
    ["duplicate material", i => { i.analysis.material.evidence.push({...i.analysis.material.evidence[0]}); }],
    ["kind", i => { i.analysis.evidence_items[0].kind = "source_statement"; }],
    ["synthetic live Fabric evidence", i => { i.analysis.evidence_items[0].synthetic = true; i.analysis.material.evidence[0].synthetic = true; }],
    ["source mismatch", i => { i.analysis.material.evidence[0].source_id = "other"; }],
    ["unsupported family", i => { i.analysis.evidence_items[0].source_id = "fabric.inventory/other"; }],
    ["missing receipt", i => editSnapshot(i, s => { s.alpha_expedite = null; })],
    ["record identity", i => editSnapshot(i, s => { s.alpha_expedite.receipt_id = "other"; })],
    ["quantity string", i => editSnapshot(i, s => { s.alpha_expedite.quantity = "3000"; })],
    ["zero positive quantity", i => editSnapshot(i, s => { s.alpha_expedite.quantity = 0; })],
    ["fractional quantity", i => editSnapshot(i, s => { s.alpha_expedite.quantity = 1.5; })],
    ["impossible date", i => editSnapshot(i, s => { s.alpha_expedite.due_date = "2026-02-30"; })],
    ["timestamp as date", i => editSnapshot(i, s => { s.alpha_expedite.due_date = "2026-09-06T00:00:00Z"; })],
    ["numeric money", i => editSnapshot(i, s => { s.alpha_expedite.incremental_cost_per_unit = 7.5; })],
    ["negative money", i => editSnapshot(i, s => { s.alpha_expedite.incremental_cost_per_unit = "-1.00"; })],
    ["currency text", i => editSnapshot(i, s => { s.alpha_expedite.incremental_cost_per_unit = "$7.50"; })],
    ["scenario mismatch", i => editSnapshot(i, s => { s.scenario_effective_time = "2026-09-02T09:00:00-05:00"; })],
    ["invalid timestamp", i => { i.analysis.evidence_items[0].retrieved_at = "2026-02-30T09:00:00Z"; }],
    ["no timestamp offset", i => { i.analysis.evidence_items[0].retrieved_at = "2026-09-01T09:00:00"; }],
    ["non-demo corpus", i => { i.analysis.material.corpus = "real_business"; }],
    ["qualification reference", i => { selectRecord(i, "qualification"); editSnapshot(i, s => { s.beta_qualification.evidence_ref = "other"; }); }],
    ["qualification string false", i => { selectRecord(i, "qualification"); editSnapshot(i, s => { s.beta_qualification.audit_complete = "false"; }); }],
    ["qualification unknown status", i => { selectRecord(i, "qualification"); editSnapshot(i, s => { s.beta_qualification.status = "ready"; }); }],
    ["transfer arrival date", i => { selectRecord(i, "transfer"); editSnapshot(i, s => { s.transfer.arrival_date = "bad"; }); }],
  ];
  it.each(invalid)("rejects %s without another record", (_name, corrupt) => {
    const input = recordFixture(); corrupt(input);
    expect(resolve(input)).toEqual({status: "unavailable", message: "Supporting record unavailable"});
  });

  it("requires requested evidence membership and leaves nullable timestamps unavailable", () => {
    const input = recordFixture();
    expect(resolveSupportingRecord(input, "missing").status).toBe("unavailable");
    input.analysis.evidence_items[0].retrieved_at = null;
    input.analysis.evidence_items[0].source_timestamp = null;
    input.analysis.material.evidence[0].source_timestamp = null;
    expect(resolve(input)).toMatchObject({status: "available", retrievedAt: null, sourceTimestamp: null});
  });
});
