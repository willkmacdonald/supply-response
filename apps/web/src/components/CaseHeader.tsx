import { currency } from '../api';
import type { CaseDetail } from '../types';

export default function CaseHeader({ detail }: { detail: CaseDetail }) {
  return (
    <section className="panel">
      <h2>
        {detail.case_id} · {detail.title}
      </h2>
      <p>{detail.summary}</p>
      <div className="metrics">
        <div className="metric">
          <span>Status</span>
          <strong>{detail.status}</strong>
        </div>
        <div className="metric">
          <span>Severity</span>
          <strong>{detail.severity}</strong>
        </div>
        <div className="metric">
          <span>Revenue at risk</span>
          <strong>{currency(detail.revenue_at_risk)}</strong>
        </div>
        <div className="metric">
          <span>Margin at risk</span>
          <strong>{currency(detail.margin_at_risk)}</strong>
        </div>
        <div className="metric">
          <span>OTIF lines at risk</span>
          <strong>{detail.otif_lines_at_risk}</strong>
        </div>
      </div>
    </section>
  );
}
