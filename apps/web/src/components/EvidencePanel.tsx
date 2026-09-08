import type {AnalysisVersion} from "../types";
import {EvidenceFooter} from "./EvidenceFooter";
import {EvidenceSource, RequiredCitationWarning, statusFor} from "./EvidenceSource";
export function EvidencePanel({analysis, tenantSharePointHost}: {analysis: AnalysisVersion | null; tenantSharePointHost?: string | null}) {
  if (!analysis) return null;
  return <section className="panel" aria-labelledby="evidence-heading"><h2 id="evidence-heading">Evidence items</h2>
    <RequiredCitationWarning analysis={analysis} tenantSharePointHost={tenantSharePointHost} />
    <div className="card-grid">{analysis.evidence_items.map((item, index) => <article className="evidence-card" key={`${item.evidence_id}-${index}`}>
      <h3>{item.claim}</h3><EvidenceSource item={item} analysis={analysis} tenantSharePointHost={tenantSharePointHost} />
      <EvidenceFooter status={statusFor(item, analysis)} />
    </article>)}</div>
  </section>;
}
