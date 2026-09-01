import type {Decision, OutcomeObservation, Playback} from "../types";

interface OutcomePanelProps {
  decision: Decision | null;
  actionCount: number;
  playback: Playback | null;
  observations: OutcomeObservation[];
  starting: boolean;
  onStart: () => void;
}

export function OutcomePanel({decision, actionCount, playback, observations, starting, onStart}: OutcomePanelProps) {
  if (!decision || decision.kind !== "approved" || actionCount === 0) return null;
  return <section className="panel" aria-labelledby="outcomes-heading">
    <p className="step">06 · Outcomes</p>
    <h2 id="outcomes-heading">{playback ? "Simulated outcomes" : "Outcome observations"}</h2>
    {!playback && <button type="button" onClick={onStart} disabled={starting || actionCount !== 5}>
      {starting ? "Starting simulated execution…" : "Start simulated execution"}
    </button>}
    {playback?.status === "failed" && <p className="error" role="alert">Simulated playback failed. Retry requires starting a new Case.</p>}
    {playback?.status === "in_progress" && observations.length === 0 && <p>Simulated playback started; observations are pending.</p>}
    {observations.length > 0 && <div className="outcome-list">
      {observations.map((observation) => <article data-testid="outcome-observation" key={observation.observation_id}>
        <span className="badge accent">{observation.synthetic ? "Simulated" : observation.display_label}</span>
        <h3>{observation.metric.replaceAll("_", " ")}</h3>
        <p><strong>{observation.observed_value}</strong> {observation.unit}</p>
        <small>Predicted: {observation.predicted_value} · {observation.source_reference}</small>
      </article>)}
    </div>}
  </section>;
}
