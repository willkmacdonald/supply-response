import type {CaseInstance} from "../types";

interface Props {
  cases: CaseInstance[] | null;
  loading: boolean;
  reopening: boolean;
  busy?: boolean;
  error: string | null;
  onLoad: () => void;
  onReopen: (caseId: string) => void;
}

const statusLabels: Record<CaseInstance["status"], string> = {
  open: "Open", analyzing: "Analysis in progress", awaiting_decision: "Awaiting decision",
  decision_rejected: "Decision rejected", action_planning: "Action planning", executing: "Executing",
  monitoring: "Monitoring", reanalysis_required: "New analysis required", closed: "Closed",
};

function recordedLabel(value: string): string {
  return new Intl.DateTimeFormat("en-US", {dateStyle: "medium", timeStyle: "short", timeZone: "America/Chicago"})
    .format(new Date(value));
}

export function ExistingCases({cases, loading, reopening, busy, error, onLoad, onReopen}: Props) {
  return <section className="panel existing-cases" aria-labelledby="existing-cases-heading">
    <h2 id="existing-cases-heading">Reopen existing case</h2>
    <p>Open saved planning work without creating a case or refreshing its evidence.</p>
    <button type="button" className="secondary" disabled={busy || loading || reopening} onClick={onLoad}>
      {loading ? "Finding existing cases…" : error ? "Try finding cases again" : "Find existing cases"}
    </button>
    {error && <p className="error" role="alert">{error}</p>}
    {cases?.length === 0 && <p>No existing cases are available.</p>}
    {cases && cases.length > 0 && <ul className="existing-case-list">
      {cases.map(item => <li key={item.case_id}>
        <div><strong>{statusLabels[item.status]}</strong><span>Recorded {recordedLabel(item.recorded_at)}</span>
          <span className="case-id">{item.case_id}</span></div>
        <button type="button" disabled={busy || loading || reopening} onClick={() => onReopen(item.case_id)}
          aria-label={`Reopen case ${item.case_id}`}>Reopen</button>
      </li>)}
    </ul>}
  </section>;
}
