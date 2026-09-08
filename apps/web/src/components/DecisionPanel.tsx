import {useState} from "react";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {optionDisplayName} from "./optionLabels";
import {blocker, role, decisionContext} from "./plannerFormatting";

interface DecisionPanelProps {
  state: CaseWorkspaceState;
  onApprove: () => void;
  onReject: (reason: string) => void;
}

export function DecisionPanel({state, onApprove, onReject}: DecisionPanelProps) {
  const [reason, setReason] = useState("");
  if (!state.analysis) return null;
  const stale = state.analysis.evidence_validation.item_results.some((item) => item.freshness === "stale");
  const blockingCodes = [
    ...state.analysis.evidence_validation.global_blocking_codes,
    ...state.analysis.evidence_validation.blocking_codes,
  ];
  const disabled = state.decisionBlocked || Boolean(state.decision) || state.operation === "deciding";
  return <section className="panel investigation-card" aria-labelledby="decision-heading">
    <h3 id="decision-heading">Review and approve.</h3>
    <p>{decisionContext(state.caseInstance, state.analysis.analysis_id, Boolean(state.decision))}</p>
    {state.decision ? <div className="receipt" data-testid="decision-receipt">
      <p className="receipt-id">Decision {state.decision.decision_id}</p>
      <p>{state.decision.kind === "approved" ? "Approved" : "Rejected"}</p>
      <dl className="compact-list">
        <div><dt>Analysis</dt><dd>{state.decision.analysis_id}</dd></div>
        <div><dt>Selected option</dt><dd>{state.decision.selected_option_id ?? "None"}</dd></div>
        <div><dt>Runtime</dt><dd>{state.decision.runtime_mode}</dd></div>
      </dl>
    </div> : <>
      {stale && <p className="warning">Required evidence is stale</p>}
      {blockingCodes.length > 0 && <ul className="blocking-codes">
        {blockingCodes.map((code, index) => <li key={`${code}-${index}`}>{blocker(code)}</li>)}
      </ul>}
      <p>Selected option: {state.selectedOption ? optionDisplayName(state.selectedOption) : "None"}</p>
      {state.selectedOption && <ul aria-label="Required approval roles">{state.selectedOption.prerequisite_roles.map(required => {
        const satisfied = state.analysis!.approval_satisfactions.some(item => item.analysis_id === state.analysis!.analysis_id && item.option_id === state.selectedOption!.option_id && item.role === required && item.satisfied);
        return <li key={required}>{role(required)}: {satisfied ? "Recorded authorization satisfied" : "No satisfied authorization recorded"}</li>;
      })}</ul>}
      <div className="decision-controls">
        <button type="button" disabled={disabled || !state.selectedOption} onClick={onApprove}>
          Approve {state.selectedOption ? optionDisplayName(state.selectedOption).toLowerCase() : "selected response"}
        </button>
        <label htmlFor="rejection-reason">Rejection reason</label>
        <textarea
          id="rejection-reason"
          value={reason}
          disabled={disabled}
          onChange={(event) => setReason(event.target.value)}
        />
        <button type="button" className="secondary" disabled={disabled || !reason.trim()} onClick={() => onReject(reason)}>
          Reject recommendation
        </button>
      </div>
    </>}
    <footer className="saved-analysis-footer">Approval remains an explicit user action. Any execution shown afterward is separately labeled.</footer>
  </section>;
}
