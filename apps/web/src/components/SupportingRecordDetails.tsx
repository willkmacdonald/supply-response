import type {ReactNode} from "react";
import type {RuntimeStatus} from "../types";
import {buildReportUrl} from "../reporting/reportNavigation";
import type {SupportingRecordResult} from "./supportingRecord";

const calendar = (value: string | null) => value === null ? "Unavailable" : new Intl.DateTimeFormat("en-US", {
  year: "numeric", month: "long", day: "numeric", timeZone: "UTC",
}).format(new Date(`${value}T00:00:00Z`));
const instantFormat = new Intl.DateTimeFormat("en-US", {
  year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  second: "2-digit", timeZone: "UTC", timeZoneName: "short",
});
const instant = (value: string | null): ReactNode => value === null ? "Unavailable"
  : <time dateTime={value}>{instantFormat.format(new Date(value))}</time>;
const flag = (value: boolean | null) => value === null ? "Unavailable" : value ? "Complete" : "Incomplete";
const supplier = (id: string) => id === "RL-SUP-ALPHA" ? "RL-Supplier Alpha — Current supplier"
  : id === "RL-SUP-BETA" ? "RL-Supplier Beta — Alternate supplier" : `Supplier ${id}`;
const plant = (id: string) => id === "RL-PLANT-DAL" ? "Dallas plant" : id === "RL-PLANT-CHI" ? "Chicago plant" : `Plant ${id}`;
const qualification = {approved: "Supplier qualification approved", pending: "Supplier qualification pending",
  not_approved: "Supplier qualification not approved", conditional: "Supplier qualification conditional"};

export function SupportingRecordDetails({result, runtime = null}: {result: SupportingRecordResult; runtime?: RuntimeStatus | null}) {
  if (result.status === "unavailable") return <p>{result.message}</p>;
  const r = result.record;
  const page = r.kind === "shipment" ? "supplier-shipment"
    : r.kind === "transfer" ? "plant-transfer" : "supplier-qualification";
  const reportUrl = runtime && result.context.runtimeMode === "live"
    && result.provenance === "Saved Microsoft Fabric record"
    ? buildReportUrl(runtime, {
        page,
        caseId: result.context.caseId,
        analysisId: result.context.analysisId,
        recordId: result.context.recordId,
        runtimeMode: result.context.runtimeMode,
      })
    : null;
  const rows: [string, string][] = [["Component part", r.part_id]];
  if (r.kind === "shipment") rows.push(
    ["Supplier", supplier(r.supplier_id)], ["Receiving plant", plant(r.plant_id)],
    ["Scheduled receipt quantity", `${r.quantity.toLocaleString("en-US")} units`],
    ["Scheduled receipt date", calendar(r.due_date)],
    ["Incremental cost", `${r.incremental_cost_per_unit} per unit (currency not specified)`],
  );
  if (r.kind === "transfer") rows.push(
    ["From", plant(r.source_plant_id)], ["To", plant(r.destination_plant_id)],
    ["Transfer quantity", `${r.quantity.toLocaleString("en-US")} units`],
    ["Dispatch date", calendar(r.dispatch_date)], ["Arrival date", calendar(r.arrival_date)],
    ["Incremental cost", `${r.incremental_cost_per_unit} per unit (currency not specified)`],
  );
  if (r.kind === "qualification") rows.push(
    ["Supplier", supplier(r.supplier_id)], ["Qualification status", qualification[r.status]],
    ["Audit", flag(r.audit_complete)], ["First article", flag(r.first_article_complete)],
    ["Qualification effective date", calendar(r.effective_date)],
    ["Expected qualification decision date", calendar(r.expected_decision_date)],
  );
  const sourceRows: [string, ReactNode][] = [
    ["Case ID", result.context.caseId], ["Analysis ID", result.context.analysisId],
    ["Source record ID", result.context.recordId], ["Evidence reference", result.context.evidenceId],
    ["Source identifier", result.context.sourceId], ["Runtime mode", result.context.runtimeMode],
    ["Analysis saved at", instant(result.analysisCreatedAt)], ["Source time", instant(result.sourceTimestamp)],
    [result.context.runtimeMode === "fallback" ? "Fixture recorded for analysis at" : "Retrieved for this analysis at", instant(result.retrievedAt)],
  ];
  const list = (values: [string, ReactNode][]) => <dl>{values.map(([label, value]) =>
    <div key={label}><dt>{label}</dt><dd style={{overflowWrap: "anywhere"}}>{value}</dd></div>)}</dl>;
  return <>
    <details>
      <summary>View {r.kind} record</summary>
      <p>Snapshot used for this analysis</p>
      <p>Demo corpus — fictional</p>
      <p>{result.provenance}</p>
      <p>In this scenario, as of {instant(result.scenarioEffectiveTime)}</p>
      {list(rows)}
      {r.kind === "qualification" && <p>A review date is not an approval or delivery date.</p>}
      <details><summary>Source details</summary>{list(sourceRows)}</details>
    </details>
    {reportUrl && <a href={reportUrl} target="_blank" rel="noopener noreferrer">
      Explore {r.kind} in Power BI
    </a>}
  </>;
}
