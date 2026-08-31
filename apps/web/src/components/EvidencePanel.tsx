import type {AnalysisVersion} from "../types";

export function EvidencePanel({analysis}: {analysis: AnalysisVersion | null}) {
  if (!analysis) return null;
  return <section className="panel" aria-labelledby="evidence-heading">
    <div className="section-heading">
      <div>
        <p className="step">01 · Evidence</p>
        <h2 id="evidence-heading">Evidence items</h2>
      </div>
      <span className="badge">{analysis.evidence_items.length} cited</span>
    </div>
    <div className="card-grid">
      {analysis.evidence_items.map((item) => <article className="evidence-card" key={item.evidence_id}>
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
        {item.citation_url && <a href={item.citation_url} target="_blank" rel="noreferrer">Open citation</a>}
      </article>)}
    </div>
  </section>;
}
