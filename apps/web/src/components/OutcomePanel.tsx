import type {Decision, OutcomeObservation, Playback} from "../types";

interface OutcomePanelProps {
  decision: Decision | null;
  actionCount: number;
  playback: Playback | null;
  observations: OutcomeObservation[];
  starting: boolean;
  onStart: () => void;
}

const metricNames = new Map<string, string>([
  ["alpha_expedited_quantity", "Supplier Alpha expedited quantity"],
  ["dallas_transfer_quantity", "Dallas transfer quantity"],
  ["total_response_arranged_supply", "Total supply arranged by the response"],
  ["uncovered_part_demand", "Parts still needed"],
  ["response_cost", "Response cost"],
  ["protected_customer_orders", "Protected customer orders"],
  ["revenue_protected", "Revenue protected"],
  ["margin_protected", "Margin protected"],
  ["otif_loss_percentage", "Service-target exposure"],
  ["remaining_alpha_recovery_date", "Remaining Supplier Alpha recovery date"],
]);

export function OutcomePanel({decision, actionCount, playback, observations, starting, onStart}: OutcomePanelProps) {
  if (!decision || decision.kind !== "approved" || actionCount === 0) return null;
  return <section className="panel" aria-labelledby="outcomes-heading">
    <p className="step">5. Review outcomes</p>
    <h2 id="outcomes-heading">{playback ? "Simulated results" : "Recorded results"}</h2>
    {!playback && <button type="button" onClick={onStart} disabled={starting || actionCount !== 5}>
      {starting ? "Starting simulated execution…" : "Start simulated execution"}
    </button>}
    {playback?.status === "failed" && <p className="error" role="alert">Simulation failed. Another simulation cannot be started for this Case.</p>}
    {playback?.status === "in_progress" && observations.length === 0 && <p>Simulation in progress</p>}
    {observations.length > 0 && <div className="outcome-list">
      {observations.map((observation) => <article data-testid="outcome-observation" key={observation.observation_id}>
        <span className="badge accent">{observation.synthetic ? "Simulated" : observation.display_label}</span>
        <h3>{metricNames.get(observation.metric) ?? "Result metric not recognized"}</h3>
        <p><strong>{observation.observed_value}</strong> {observation.unit}</p>
        <small>Predicted: {observation.predicted_value} · {observation.source_reference}</small>
      </article>)}
    </div>}
  </section>;
}
