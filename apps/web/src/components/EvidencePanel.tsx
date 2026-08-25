import type { CaseDetail } from '../types';

export default function EvidencePanel({ detail }: { detail: CaseDetail }) {
  return (
    <section className="panel">
      <h3>Confirmed facts</h3>
      <ul>
        {detail.facts.map((fact) => (
          <li key={fact}>{fact}</li>
        ))}
      </ul>

      <h3>Unresolved uncertainties</h3>
      <ul>
        {detail.uncertainties.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>

      <h3>Evidence</h3>
      <ul>
        {detail.evidence.map((item) => (
          <li key={item.evidence_id}>
            <strong>
              {item.source} · {item.reference}
            </strong>
            <div>{item.content}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
