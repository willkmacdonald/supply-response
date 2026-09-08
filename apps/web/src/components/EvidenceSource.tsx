import type {AnalysisVersion, EvidenceItem} from "../types";
import {trustedServerCitation} from "../security/trustedUrls";
import {EvidenceFooter} from "./EvidenceFooter";
import {evidenceStatus} from "./evidenceStatus";

type SourceProps = {item: EvidenceItem; analysis: AnalysisVersion; tenantSharePointHost?: string | null; label?: string};
export const statusFor = (item: EvidenceItem, analysis: AnalysisVersion) => evidenceStatus(item, {...analysis, results: analysis.evidence_validation?.item_results ?? []});
function citation(item: EvidenceItem, analysis: AnalysisVersion, host?: string | null) {
  if (analysis.runtime_mode !== "live" || item.source_system !== "work_iq" || item.citation_classification !== "work_iq") return null;
  return trustedServerCitation(item.navigable_citation_url, item.citation_classification, host);
}
function citationLabel(item: EvidenceItem, url: string) {
  const host = new URL(url).hostname;
  if (["outlook.office.com", "outlook.office365.com"].includes(host) && item.authority_scope.includes("supplier_statement")) return "Open supplier email";
  if (host === "teams.microsoft.com" && item.authority_scope.includes("collaboration_statement")) return "Open Quality Teams post";
  return "Open citation";
}
export function RequiredCitationWarning({analysis, tenantSharePointHost}: {analysis: AnalysisVersion; tenantSharePointHost?: string | null}) {
  const missing = analysis.runtime_mode === "live" && analysis.evidence_items.some(item => item.requirement === "required_authoritative" && !trustedServerCitation(item.navigable_citation_url, item.citation_classification, tenantSharePointHost));
  return missing ? <p className="warning" role="alert">Required live citation missing</p> : null;
}
export function EvidenceSource({item, analysis, tenantSharePointHost, label = "Source statement"}: SourceProps) {
  const status = statusFor(item, analysis); const url = citation(item, analysis, tenantSharePointHost);
  return <div className="source-evidence"><p className="source-role">{label}</p>
    {status.warning && <p className="warning" role="alert">{status.warning}</p>}
    {item.excerpt ? <details><summary>Read original {label.toLowerCase()} excerpt</summary><blockquote>{item.excerpt}</blockquote></details> : <p>Source excerpt unavailable</p>}
    <details><summary>Source details</summary><dl className="compact-list">
      <div><dt>Source record ID</dt><dd>{item.source_id?.trim() || "Unavailable"}</dd></div><div><dt>Evidence ID</dt><dd>{item.evidence_id}</dd></div>
      <div><dt>Technical authority scopes</dt><dd>{item.authority_scope.join(", ")}</dd></div><div><dt>Internal evidence classification</dt><dd>{item.uncertainty_state}</dd></div>
    </dl><p>Saved source claim: {item.claim}</p><p>The internal classification is not a probability or a guarantee of supplier performance.</p></details>
    {url && <a href={url} target="_blank" rel="noopener noreferrer">{citationLabel(item, url)}</a>}
  </div>;
}
export function EvidenceFooters({items, analysis}: {items: EvidenceItem[]; analysis: AnalysisVersion}) {
  return <div className="source-footers">{items.map((item, index) => <div key={`${item.evidence_id}-${index}`}><p className="footer-source">{item.kind === "operational_fact" ? "Supporting record" : "Source statement"}</p><EvidenceFooter status={statusFor(item, analysis)} /></div>)}</div>;
}
