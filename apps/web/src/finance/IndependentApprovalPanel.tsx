import {useCallback, useEffect, useRef, useState} from "react";
import {api, safeErrorMessage} from "../api";
import type {Decision, ProposalState, ResponseOption, SubmitProposalInput, FinalizeProposalInput} from "../types";
import {commandKey, time, usd} from "./format";

type Command<T> = {body: T; key: string};
export function IndependentApprovalPanel({caseId, selectedOption, finalDecision, onFinalDecision}: {caseId: string; selectedOption: ResponseOption | null; finalDecision: Decision | null; onFinalDecision: (decision: Decision) => void}) {
  const [state, setState] = useState<ProposalState | null>(null); const [error, setError] = useState<string | null>(null); const [busy, setBusy] = useState(false); const [receipt, setReceipt] = useState<Decision | null>(finalDecision);
  const alive = useRef(true); const submitIntent = useRef<Command<SubmitProposalInput> | null>(null); const finalIntent = useRef<Command<FinalizeProposalInput> | null>(null);
  const refresh = useCallback(async () => {try {const value = await api.proposal(caseId); if (alive.current) {setState(value); setError(null);}} catch (caught) {if (alive.current) {setState(null); setError(`Approval status could not be refreshed. ${safeErrorMessage(caught)} Refresh the case and reselect the response.`);}}}, [caseId]);
  useEffect(() => {alive.current = true; void refresh(); const interval = window.setInterval(() => void refresh(), 5000); return () => {alive.current = false; window.clearInterval(interval);};}, [refresh]);
  useEffect(() => {submitIntent.current = null; finalIntent.current = null;}, [selectedOption?.option_id]);
  const currentSelection = Boolean(selectedOption && state?.selection?.proposal.option_id === selectedOption.option_id);
  const cost = selectedOption?.predicted?.response_cost;
  const requiresFinance = cost ? Number(cost) > 20000 : false;
  const financeSatisfied = currentSelection && (!requiresFinance || state?.review?.status === "approved");
  async function submit() {if (!selectedOption || !state || busy || !selectedOption.executable) return; const body = {option_id: selectedOption.option_id, expected: state.token}; const intent = submitIntent.current ?? {body, key: commandKey("proposal")}; submitIntent.current = intent; setBusy(true); setError(null); try {await api.submitProposal(caseId, intent.body, intent.key); submitIntent.current = null; await refresh();} catch(caught) {setError(`The response was not submitted. ${safeErrorMessage(caught)} Retry this exact submission, or refresh before changing it.`);} finally {if (alive.current) setBusy(false);}}
  async function finalize() {if (!state || !financeSatisfied || busy) return; const body: FinalizeProposalInput = {expected: state.token, kind: "approved"}; const intent = finalIntent.current ?? {body, key: commandKey("alex-final")}; finalIntent.current = intent; setBusy(true); setError(null); try {const decision = await api.finalizeProposal(caseId, intent.body, intent.key); finalIntent.current = null; setReceipt(decision); onFinalDecision(decision); await refresh();} catch(caught) {setError(`Final approval was not completed. ${safeErrorMessage(caught)} Refresh the approval state or retry this exact approval.`);} finally {if (alive.current) setBusy(false);}}
  return <section className="panel" aria-labelledby="independent-approval-heading"><h2 id="independent-approval-heading">Review and approve</h2>
    {!selectedOption ? <p>Choose a response before submitting it for approval.</p> : <><p className="eyebrow">Selected response</p><h3>{selectedOption.name}</h3><p className="finance-cost">{cost ? usd(cost) : "Cost unavailable"}</p>
      {!selectedOption.executable && <p className="error">This response is infeasible and cannot be submitted. Reselect an executable response.</p>}
      {!requiresFinance && <p>Finance review not required—within the spending threshold</p>}
      {state && !currentSelection && state.selection && <p>The saved approval belongs to a different response. This selection needs a fresh submission.</p>}
      {currentSelection && state?.review?.status === "pending" && <p>Waiting for Taylor to review the proposed spending. <a href={`?financeReviewId=${encodeURIComponent(state.review.review_id)}`}>Open Taylor review</a></p>}
      {currentSelection && state?.review?.status === "rejected" && <p>Taylor rejected this spending{state.review.reason ? `: ${state.review.reason}` : "."} Revise or explicitly resubmit the response.</p>}
      {currentSelection && state?.review?.status === "approved" && <p>Taylor approved the proposed spending at {time(state.review.reviewed_at)}. Alex's final approval is still required.</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {!receipt && (!currentSelection || state?.review?.status === "rejected") && <button disabled={busy || !state || !selectedOption.executable} onClick={() => void submit()}>{busy ? "Submitting…" : requiresFinance ? "Submit for Finance review" : "Submit response"}</button>}
      {!receipt && financeSatisfied && <button disabled={busy} onClick={() => void finalize()}>{busy ? "Recording final approval…" : "Give final Alex approval"}</button>}
      {receipt?.kind === "approved" && <div><h3>Alex approved this response</h3><p>Final decision recorded separately from Finance review.</p>{receipt.action_planning_status === "complete" ? <p>Execution planning is ready in the next stage.</p> : <p>Execution is not available in this milestone because independent action planning has not been enabled.</p>}</div>}
    </>}
    <p className="evidence-footer">Approval state from the current saved proposal; selection alone is not authorization.</p>
  </section>;
}
