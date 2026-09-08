import type {AnalysisVersion, EvidenceItem} from "../types";
import {trustedServerCitation} from "../security/trustedUrls";
import {EvidenceFooter} from "./EvidenceFooter";
import {evidenceStatus} from "./evidenceStatus";

function citationLabel(item: EvidenceItem, citation: string): string {
  if (item.source_system === "work_iq") {
    try {
      const host = new URL(citation).hostname;
      if (["outlook.office.com", "outlook.office365.com"].includes(host) && item.authority_scope.includes("supplier_statement")) {
        return "Open supplier email";
      }
      if (host === "teams.microsoft.com" && item.authority_scope.includes("collaboration_statement")) {
        return "Open Quality Teams post";
      }
    } catch { /* Non-URL fallback citations retain their generic label. */ }
  }
  return "Open citation";
}

export function EvidencePanel({analysis, tenantSharePointHost}: {analysis: AnalysisVersion | null; tenantSharePointHost?: string | null}) {
  if (!analysis) return null;
  const missingRequiredLiveCitation = analysis.runtime_mode === "live" && analysis.evidence_items.some((item) =>
    item.requirement === "required_authoritative" && !trustedServerCitation(item.navigable_citation_url, item.citation_classification, tenantSharePointHost)
  );
  return <section className="panel" aria-labelledby="evidence-heading">
    <div className="section-heading">
      <div>
        <p className="step">01 · Evidence</p>
        <h2 id="evidence-heading">Evidence items</h2>
      </div>
      <span className="badge">{analysis.evidence_items.length} cited</span>
    </div>
    {missingRequiredLiveCitation && <p className="warning" role="alert">Required live citation missing</p>}
    <div className="card-grid">
      {analysis.evidence_items.map((item) => {
        const citation = analysis.runtime_mode === "live"
          ? trustedServerCitation(item.navigable_citation_url, item.citation_classification, tenantSharePointHost)
          : item.citation_url;
        const status = evidenceStatus(item, {
          ...analysis, results: analysis.evidence_validation?.item_results ?? [],
        });
        return <article className="evidence-card" key={item.evidence_id}>
        <h3>{item.claim}</h3>
        {status.warning && <p className="warning" role="alert">{status.warning}</p>}
        {item.excerpt && <p>{item.excerpt}</p>}
        <details>
          <summary>Source details</summary>
          <dl className="compact-list">
            <div><dt>Source record ID</dt><dd>{item.source_id?.trim() || "Unavailable"}</dd></div>
            <div><dt>Evidence ID</dt><dd>{item.evidence_id}</dd></div>
            <div><dt>Technical authority scopes</dt><dd>{item.authority_scope.join(", ")}</dd></div>
            <div><dt>Internal evidence classification</dt><dd>{item.uncertainty_state}</dd></div>
          </dl>
          <p>The internal classification is not a probability or a guarantee of supplier performance.</p>
        </details>
        {citation && <a href={citation} target="_blank" rel="noopener noreferrer">{citationLabel(item, citation)}</a>}
        <EvidenceFooter status={status} />
      </article>})}
    </div>
  </section>;
}
