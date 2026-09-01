import type {AnalysisVersion} from "../types";
import {trustedServerCitation} from "../security/trustedUrls";

export function EvidencePanel({analysis}: {analysis: AnalysisVersion | null}) {
  if (!analysis) return null;
  const missingRequiredLiveCitation = analysis.runtime_mode === "live" && analysis.evidence_items.some((item) =>
    item.requirement === "required_authoritative" && !trustedServerCitation(item.navigable_citation_url, item.citation_classification, item.citation_trusted_host)
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
          ? trustedServerCitation(item.navigable_citation_url, item.citation_classification, item.citation_trusted_host)
          : item.citation_url;
        return <article className="evidence-card" key={item.evidence_id}>
        <div className="card-labels">
          <span className="badge">{item.synthetic ? "Synthetic fixture" : item.source_system}</span>
          <span className="badge">{item.retrieval_health}</span>
        </div>
        <h3>{item.claim}</h3>
        {item.excerpt && <p>{item.excerpt}</p>}
        <dl className="compact-list">
          <div><dt>Evidence ID</dt><dd>{item.evidence_id}</dd></div>
          <div><dt>Authority</dt><dd>{item.authority_scope.join(", ")}</dd></div>
          <div><dt>Uncertainty</dt><dd>{item.uncertainty_state}</dd></div>
        </dl>
        {citation && <a href={citation} target="_blank" rel="noopener noreferrer">Open citation</a>}
      </article>})}
    </div>
  </section>;
}
