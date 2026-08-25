import type { NarrativeResponse } from '../types';

interface Props {
  narrative: NarrativeResponse;
}

export default function NarrativePanel({ narrative }: Props) {
  return (
    <section className="panel">
      <h3>
        Decision narrative
        <span className="narrative-source"> — {narrative.source}</span>
      </h3>
      <pre className="narrative">{narrative.narrative}</pre>
    </section>
  );
}
