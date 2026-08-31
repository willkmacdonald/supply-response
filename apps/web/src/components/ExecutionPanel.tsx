import type {Decision, DraftArtifact, ExecutionAction} from "../types";

interface ExecutionPanelProps {
  decision: Decision | null;
  actions: ExecutionAction[];
  drafts: DraftArtifact[];
  retrying: boolean;
  onRetry: () => void;
}

export function ExecutionPanel({decision, actions, drafts, retrying, onRetry}: ExecutionPanelProps) {
  if (!decision || decision.kind !== "approved") return null;
  return <section className="panel" aria-labelledby="execution-heading">
    <p className="step">05 · Execution</p>
    <h2 id="execution-heading">Execution plan</h2>
    {decision.action_planning_status === "failed" && <div className="failure-banner">
      <strong>Approved — action planning failed</strong>
      <button type="button" onClick={onRetry} disabled={retrying}>
        {retrying ? "Retrying action planning…" : "Retry action planning"}
      </button>
    </div>}
    {decision.action_planning_status === "pending" && <p>Action planning is pending.</p>}
    {actions.length > 0 && <ol className="action-list">
      {actions.map((action) => <li data-testid="execution-action" key={action.action_id}>
        <div><strong>{action.kind.replaceAll("_", " ")}</strong><span>{action.status}</span></div>
        <small>{action.action_id}</small>
      </li>)}
    </ol>}
    {drafts.map((draft) => <article className="draft" key={draft.artifact_id}>
      <span className="badge danger">Unsent draft</span>
      <h3>Draft Artifact</h3>
      <p>{draft.subject ?? "Supplier recovery request will be filled during simulated execution."}</p>
      {draft.body && <pre>{draft.body}</pre>}
    </article>)}
  </section>;
}
