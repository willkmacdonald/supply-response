import type { ReactNode } from "react";
import type { AnalysisVersion, CaseInstance, EvidenceItem, RuntimeStatus } from "../types";
import { buildReportUrl } from "../reporting/reportNavigation";
import { EvidenceSource, EvidenceFooters } from "./EvidenceSource";
import { evidenceStatus } from "./evidenceStatus";
import {
  resolveSupportingRecord,
  type SupportingRecordResult,
} from "./supportingRecord";
import { SupportingRecordDetails } from "./SupportingRecordDetails";
import { readPlannerSnapshot } from "./plannerSnapshot";
import { calendar, money, number, plant, supplier } from "./plannerFormatting";
import { PredictionSummary } from "./PredictionSummary";

type Props = {
  caseInstance: CaseInstance;
  analysis: AnalysisVersion;
  tenantSharePointHost?: string | null;
  runtime?: RuntimeStatus | null;
  row: "disruption" | "responses";
};
const unavailable: SupportingRecordResult = {
  status: "unavailable",
  message: "Supporting record unavailable",
};

export function InvestigationEvidence({
  caseInstance,
  analysis,
  tenantSharePointHost,
  runtime = null,
  row,
}: Props) {
  const input = { caseInstance, analysis };
  const snapshot = readPlannerSnapshot(input);
  const d = snapshot?.disruption;
  const all = analysis.evidence_items;
  const supportedScenario = snapshot !== null;
  const currentSupplierMapped =
    supportedScenario &&
    d?.supplier_id === "RL-SUP-ALPHA" &&
    d.part_id === "RL-MAT-10247" &&
    d.plant_id === "RL-PLANT-CHI";
  const belongs = (item: EvidenceItem) =>
    item.case_id === analysis.case_id &&
    item.runtime_mode === analysis.runtime_mode &&
    item.retrieved_for_analysis_id === analysis.analysis_id;
  const supplierItems = supportedScenario
    ? all.filter(
        (item) =>
          belongs(item) &&
          item.kind === "source_statement" &&
          item.authority_scope.includes("supplier_statement"),
      )
    : [];
  const qualityItems = supportedScenario
    ? all.filter(
        (item) =>
          belongs(item) &&
          item.kind === "source_statement" &&
          item.authority_scope.includes("collaboration_statement"),
      )
    : [];
  const resolved = all.map((item) => ({
    item,
    result: resolveSupportingRecord(input, item.evidence_id),
  }));
  const select = (kind: "shipment" | "transfer" | "qualification") => {
    const matches = resolved.filter(
      (entry) =>
        entry.result.status === "available" &&
        entry.result.record.kind === kind,
    );
    if (matches.length !== 1) return null;
    const match = matches[0];
    if (match.result.status !== "available") return null;
    const r = match.result.record;
    const mapped =
      r.part_id === "RL-MAT-10247" &&
      (r.kind === "shipment"
        ? r.supplier_id === "RL-SUP-ALPHA" && r.plant_id === "RL-PLANT-CHI"
        : r.kind === "transfer"
          ? r.source_plant_id === "RL-PLANT-DAL" &&
            r.destination_plant_id === "RL-PLANT-CHI"
          : r.supplier_id === "RL-SUP-BETA");
    return mapped ? match : null;
  };
  const shipment = select("shipment");
  const transfer = select("transfer");
  const qualification = select("qualification");
  const used = new Set([
    ...supplierItems,
    ...qualityItems,
    ...[shipment, transfer, qualification].flatMap((entry) =>
      entry ? [entry.item] : [],
    ),
  ]);
  const other = all.filter((item) => !used.has(item));
  const sources = (items: EvidenceItem[], label: string) =>
    items.map((item, index) => (
      <EvidenceSource
        key={`${item.evidence_id}-${index}`}
        item={item}
        analysis={analysis}
        tenantSharePointHost={tenantSharePointHost}
        label={label}
      />
    ));
  const card = (title: string, content: ReactNode, items: EvidenceItem[], footerNote =
    "Snapshot used for this analysis. Separate source retrieval and check details are not recorded.") => (
    <article className="evidence-card">
      <h3>{title}</h3>
      {content}
      {items.length ? (
        <EvidenceFooters items={items} analysis={analysis} />
      ) : (
        <footer className="saved-analysis-footer">
          {footerNote}
        </footer>
      )}
    </article>
  );
  if (row === "disruption") {
    const inventory =
      d &&
      snapshot?.inventory?.filter(
        (position) =>
          position.part_id === d.part_id && position.plant_id === d.plant_id,
      );
    const total = (key: "on_hand" | "quality_hold" | "protected_allocation") =>
      inventory?.reduce((sum, item) => sum + item[key], 0) ?? 0;
    const usable =
      total("on_hand") - total("quality_hold") - total("protected_allocation");
    const safeTotals = [
      total("on_hand"),
      total("quality_hold"),
      total("protected_allocation"),
      usable,
    ].every(Number.isSafeInteger);
    const baselines = analysis.response_options.filter(
      (option) => option.option_kind === "no_mitigation",
    );
    const analysisTarget = {
      caseId: analysis.case_id, analysisId: analysis.analysis_id,
      runtimeMode: analysis.runtime_mode,
    };
    const stockUrl = runtime && snapshot && d && inventory?.length && safeTotals
      ? buildReportUrl(runtime, {...analysisTarget, page: "available-stock"}) : null;
    const hasLinkedOrders = snapshot?.customers?.some(customer =>
      snapshot.production?.some(production =>
        customer.production_order_id === production.production_order_id));
    const ordersUrl = runtime && snapshot && d && hasLinkedOrders
      && baselines.length === 1
      ? buildReportUrl(runtime, {...analysisTarget, page: "customer-orders"}) : null;
    return (
      <>
        {card(
          "What changed?",
          <>
            <p>
              {d
                ? supplier(d.supplier_id)
                : "Supplier details aren't available for this analysis"}
            </p>
            {d ? (
              <>
                <p>
                  Original delivery: {number(d.original_quantity)} component
                  units of {d.part_id} were due at {plant(d.plant_id)} on{" "}
                  {calendar(d.original_due_date)}.
                </p>
                <p>The original delivery is at risk in this disruption.</p>
                <p>{d.recovery_date === null
                  ? "No date recorded for full recovery"
                  : `Full recovery date recorded: ${calendar(d.recovery_date)}`}</p>
                <details>
                  <summary>Disruption source details</summary>
                  <p>
                    Partial quantity field: {number(d.partial_quantity)} component
                    units. Partial date field: {calendar(d.partial_due_date)}.
                  </p>
                  <p>The full original quantity remains affected. These fields do
                    not establish an on-time receipt and do not replace the
                    separate proposed expedite response.</p>
                  <p>
                    Source reference: {d.source_ref}. Purchase-order line:{" "}
                    {d.po_line_id}.
                  </p>
                </details>
              </>
            ) : (
              <p>Disruption details aren't available for this analysis</p>
            )}
            {supplierItems.length ? (
              sources(
                supplierItems,
                currentSupplierMapped
                  ? "Supplier email — RL-Supplier Alpha — Current supplier"
                  : "Supplier email",
              )
            ) : (
              <p>Supplier email unavailable for this analysis</p>
            )}
          </>,
          supplierItems,
        )}
        {card(
          "What do we have available?",
          <>
            {d && inventory?.length && safeTotals ? (
              <>
                <p>
                  {plant(d.plant_id)} · {d.part_id}
                </p>
                <p>
                  {number(usable)} component units available after holds and
                  protected allocations.
                </p>
                <dl className="compact-list">
                  <div>
                    <dt>On hand</dt>
                    <dd>{number(total("on_hand"))} component units</dd>
                  </div>
                  <div>
                    <dt>Quality holds</dt>
                    <dd>{number(total("quality_hold"))} component units</dd>
                  </div>
                  <div>
                    <dt>Protected allocations</dt>
                    <dd>
                      {number(total("protected_allocation"))} component units
                    </dd>
                  </div>
                </dl>
                {usable < 0 && (
                  <p className="warning">
                    Holds and protected allocations exceed on-hand stock in this
                    snapshot.
                  </p>
                )}
                <details>
                  <summary>Source details</summary>
                  <p>
                    Inventory records:{" "}
                    {inventory.map((item) => item.inventory_id).join(", ")}
                  </p>
                </details>
              </>
            ) : (
              <p>Stock details aren't available for this analysis</p>
            )}
            {stockUrl && <a href={stockUrl} target="_blank" rel="noopener noreferrer">
              Explore available stock in Power BI
            </a>}
          </>,
          [],
          "Stock amounts come from the snapshot used for this analysis. A separate inventory retrieval time is not recorded.",
        )}
        {card(
          "What does that put at risk?",
          <>
            <PredictionSummary
              predicted={baselines.length === 1 ? baselines[0].predicted : null}
              snapshot={snapshot}
              basis="baseline"
            />
            <details>
              <summary>Affected production and customer orders</summary>
              <p>
                Orders in this saved planning analysis; individual service
                outcomes are shown only by the saved prediction.
              </p>
              {snapshot?.production?.length ? (
                <ul>
                  {snapshot.production.map((order) => (
                    <li key={order.production_order_id}>
                      Production {order.production_order_id}:{" "}
                      {number(order.quantity)} finished-product units of{" "}
                      {order.product_id} at {plant(order.plant_id)}, due{" "}
                      {calendar(order.due_date)}.
                      {order.component_demand !== null && (
                        <>
                          {" "}
                          Component demand: {number(
                            order.component_demand,
                          )}{" "}
                          units.
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Production orders unavailable</p>
              )}
              {snapshot?.customers?.length ? (
                <ul>
                  {snapshot.customers.map((order) => (
                    <li key={order.customer_order_line_id}>
                      Customer line {order.customer_order_line_id}:{" "}
                      {number(order.quantity)} finished-product units of{" "}
                      {order.product_id}, due {calendar(order.due_date)}; unit
                      revenue {money(order.unit_revenue)}.
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Customer order lines unavailable</p>
              )}
            </details>
            {ordersUrl && <a href={ordersUrl} target="_blank" rel="noopener noreferrer">
              Explore affected customer orders in Power BI
            </a>}
          </>,
          [],
        )}
      </>
    );
  }
  const s =
    shipment?.result.status === "available" &&
    shipment.result.record.kind === "shipment"
      ? shipment.result.record
      : null;
  const t =
    transfer?.result.status === "available" &&
    transfer.result.record.kind === "transfer"
      ? transfer.result.record
      : null;
  const q =
    qualification?.result.status === "available" &&
    qualification.result.record.kind === "qualification"
      ? qualification.result.record
      : null;
  const qName =
    q?.supplier_id === "RL-SUP-BETA"
      ? "Supplier Beta"
      : q
        ? supplier(q.supplier_id)
        : "Supplier";
  const qStatus =
    q?.status === "approved"
      ? `${qName} qualification is approved in this snapshot`
      : q?.status === "pending"
        ? `${qName} is not yet qualified`
        : q?.status === "conditional"
          ? `${qName} qualification is conditional`
          : `${qName} qualification is not approved`;
  const qFlag = (flag: boolean | null) =>
    flag === null ? "Unavailable" : flag ? "Complete" : "Incomplete";
  return (
    <>
      {card(
        "What can Supplier Alpha still supply?",
        <>
          <p>
            {s
              ? supplier(s.supplier_id)
              : supportedScenario
                ? "RL-Supplier Alpha — Current supplier"
                : "Supplier identity unavailable"}
          </p>
          {s ? (
            <>
              <p>
                Proposed response: {number(s.quantity)} component units of{" "}
                {s.part_id} could arrive at {plant(s.plant_id)} on{" "}
                {calendar(s.due_date)}.
              </p>
              <p>
                Additional cost: {money(s.incremental_cost_per_unit)} per
                component unit.
              </p>
            </>
          ) : (
            <p>Shipment details aren't available for this analysis</p>
          )}
          <p>
            This proposed shipment is a response option under review, not an
            approved action.
          </p>
          {d && (
            <p>{d.recovery_date === null
              ? "No date recorded for full recovery"
              : `Full recovery date recorded: ${calendar(d.recovery_date)}`}</p>
          )}
          {supplierItems.length ? (
            sources(
              supplierItems,
              s
                ? "Supplier email — RL-Supplier Alpha — Current supplier"
                : "Supplier email",
            )
          ) : (
            <p>Supplier email unavailable for this analysis</p>
          )}
          {shipment && sources([shipment.item], "Shipment record")}
          <SupportingRecordDetails result={shipment?.result ?? unavailable} runtime={runtime} />
        </>,
        [...supplierItems, ...(shipment ? [shipment.item] : [])],
      )}
      {card(
        "Can another plant help?",
        <>
          {t ? (
            <>
              <p>
                {plant(t.source_plant_id)} to {plant(t.destination_plant_id)}
              </p>
              <p>
                {number(t.quantity)} {t.part_id} component units; arrival{" "}
                {calendar(t.arrival_date)}.
              </p>
              <p>
                Dispatch {calendar(t.dispatch_date)}; incremental cost{" "}
                {t.incremental_cost_per_unit} per unit (currency not specified).
              </p>
            </>
          ) : (
            <p>Plant transfer details aren't available for this analysis</p>
          )}
          {transfer && sources([transfer.item], "Transfer record")}
          <SupportingRecordDetails result={transfer?.result ?? unavailable} runtime={runtime} />
        </>,
        transfer ? [transfer.item] : [],
      )}
      {card(
        "Can we use the alternate supplier?",
        <>
          <p>
            {q
              ? supplier(q.supplier_id)
              : supportedScenario
                ? "RL-Supplier Beta — Alternate supplier"
                : "Supplier identity unavailable"}
          </p>
          {q ? (
            <>
              <p className={q.status === "approved" ? undefined : "warning"}>
                {qStatus}
              </p>
              <p>
                Audit: {qFlag(q.audit_complete)}. First article:{" "}
                {qFlag(q.first_article_complete)}.
              </p>
              <p>
                Expected qualification decision:{" "}
                {calendar(q.expected_decision_date)}. This is not an approval or
                delivery date.
              </p>
            </>
          ) : (
            <p>Supplier qualification details aren't available for this analysis</p>
          )}
          {qualification &&
            sources([qualification.item], "Qualification record")}
          {qualityItems.length ? (
            <>
              <p>Scenario contact: Jordan Lee — Quality Manager.</p>
              {sources(qualityItems, "Quality Teams post")}
            </>
          ) : (
            <p>Quality Teams post unavailable for this analysis</p>
          )}
          <SupportingRecordDetails
            result={qualification?.result ?? unavailable}
            runtime={runtime}
          />
          {other.map((item, index) => {
            const warning = evidenceStatus(item, {
              ...analysis,
              results: analysis.evidence_validation.item_results,
            }).warning;
            return warning ? (
              <p
                className="warning"
                role="alert"
                key={`${item.evidence_id}-${index}`}
              >
                Additional source context: {warning}
              </p>
            ) : null;
          })}
          {other.length > 0 && (
            <details>
              <summary>Additional source context</summary>
              {sources(other, "Unmatched source context — role unavailable")}
            </details>
          )}
        </>,
        [
          ...qualityItems,
          ...(qualification ? [qualification.item] : []),
          ...other,
        ],
      )}
    </>
  );
}
