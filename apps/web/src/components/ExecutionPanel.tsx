import type {Decision, DraftArtifact, ExecutionAction} from "../types";

interface ExecutionPanelProps {
  decision: Decision | null;
  actions: ExecutionAction[];
  drafts: DraftArtifact[];
  retrying: boolean;
  busy?: boolean;
  canRetryPlanning?: boolean;
  onRetry: () => void;
  onRetryAction: (actionId: string) => void;
}

const actionNames = new Map<string, string>([
  ["prepare_alpha_recovery_draft", "Prepare supplier recovery draft"],
  ["coordinate_alpha_expedited_partial", "Coordinate expedited partial shipment"],
  ["transfer_dallas_to_chicago", "Transfer stock from Dallas to Chicago"],
  ["resequence_priority_production", "Prioritize production for customer needs"],
  ["update_disruption_status", "Update disruption status"],
]);

const actionStates = new Map<string, string>([
  ["planned", "Planned"],
  ["in_progress", "In progress"],
  ["completed", "Completed"],
  ["failed", "Failed"],
]);

function actionName(kind: string): string {
  return actionNames.get(kind) ?? "Action type not recognized";
}

function draftName(kind: string): string {
  return kind === "alpha_recovery_request" || kind === "supplier_recovery_request"
    ? "Supplier recovery request draft"
    : "Draft for review";
}

function ownerName(kind: string): string {
  if (kind === "system") return "System";
  if (kind === "persona") return "Alex";
  return "Owner not recognized";
}

export function ExecutionPanel({decision, actions, drafts, retrying, busy, canRetryPlanning = false, onRetry, onRetryAction}: ExecutionPanelProps) {
  if (!decision || decision.kind !== "approved") return null;
  return <section className="panel" aria-labelledby="execution-heading">
    <p className="step">5. Execute mitigation plan</p>
    <h2 id="execution-heading">Execution plan</h2>
    {decision.action_planning_status === "failed" && <div className="failure-banner">
      <strong>Approved — action planning failed</strong>
      <button type="button" onClick={onRetry} disabled={busy || retrying || !canRetryPlanning}>
        {retrying ? "Retrying action planning…" : "Retry action planning"}
      </button>
    </div>}
    {decision.action_planning_status === "pending" && <p>Action planning is pending.</p>}
    {actions.length > 0 && <ol className="action-list">
      {actions.map((action) => <li data-testid="execution-action" key={action.action_id}>
        <div data-testid={`execution-action-${action.action_id}`}>
          <div><strong>{actionName(action.kind)}</strong><span>{actionStates.get(action.status) ?? "Status not recognized"}</span></div>
          {action.purpose && <p>{action.purpose}</p>}
          <p>{action.owner_kind === "system" || action.owner_kind === "persona" ? "Owner: " : ""}{ownerName(action.owner_kind)}</p>
          {action.expected_result && <p>Expected result: {action.expected_result}</p>}
          <p>What happens here: {action.execution_mode === "communication_preparation"
            ? "Draft prepared for Alex to review"
            : "Simulated coordination"}</p>
          <details><summary>Action details</summary><p>Action {action.action_id}</p><p>Recorded kind: {action.kind}</p></details>
          {action.status === "failed" && <button type="button" disabled={busy || retrying} onClick={() => onRetryAction(action.action_id)}>
            Retry {actionName(action.kind).toLowerCase()}
          </button>}
        </div>
      </li>)}
    </ol>}
    {drafts.map((draft) => <article className="draft" key={draft.artifact_id}>
      <span className="badge danger">Not sent</span>
      <h3>{draftName(draft.artifact_kind)}</h3>
      <p>{draft.subject ?? "No draft subject recorded."}</p>
      {draft.body && <pre>{draft.body}</pre>}
      <details><summary>Draft details</summary><p>Draft {draft.artifact_id}</p><p>Recorded kind: {draft.artifact_kind}</p></details>
    </article>)}
  </section>;
}
