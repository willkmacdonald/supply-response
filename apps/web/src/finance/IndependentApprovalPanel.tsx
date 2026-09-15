import {useCallback, useEffect, useRef, useState} from "react";
import {ApiRequestError, api, safeErrorMessage} from "../api";
import type {Decision, FinalizeProposalInput, ProposalState, ResponseOption, SubmitProposalInput} from "../types";
import {commandKey, time, usd} from "./format";

type DisplayedAnalysis = {analysis_id: string; material_hash: string};
type Command<T> = {body: T; key: string};
interface Props {caseId: string; displayedAnalysis: DisplayedAnalysis; selectedOption: ResponseOption | null; finalDecision: Decision | null; onFinalDecision: (decision: Decision) => void; independentFinanceEnabled: boolean}

function hasAnalysis(state: ProposalState, analysis: DisplayedAnalysis) {
  return state.token.analysis_id === analysis.analysis_id && state.token.analysis_material_hash === analysis.material_hash;
}
function hasSelection(state: ProposalState, caseId: string, analysis: DisplayedAnalysis, option: ResponseOption | null) {
  const selection = state.selection;
  return Boolean(option && selection && hasAnalysis(state, analysis)
    && state.token.selection_id === selection.selection_id && selection.proposal.case_id === caseId
    && selection.proposal.analysis_id === analysis.analysis_id && selection.proposal.analysis_material_hash === analysis.material_hash
    && selection.proposal.option_id === option.option_id && selection.proposal.response_cost === option.predicted?.response_cost);
}
function matchesReceipt(decision: Decision | null, state: ProposalState | null, caseId: string, analysis: DisplayedAnalysis, option: ResponseOption | null): decision is Decision {
  if (!decision || !state || !hasSelection(state, caseId, analysis, option)) return false;
  return decision.kind === "approved" && decision.case_id === caseId && decision.analysis_id === analysis.analysis_id
    && decision.analysis_material_hash === analysis.material_hash && decision.selected_option_id === option?.option_id
    && decision.proposal_approval_evidence?.selection.selection_id === state.selection?.selection_id;
}
function definitive(error: unknown) {return error instanceof ApiRequestError && [403, 404, 409, 422].includes(error.status);}

export function IndependentApprovalPanel({caseId, displayedAnalysis, selectedOption, finalDecision, onFinalDecision, independentFinanceEnabled}: Props) {
  const [proposalState, setProposalState] = useState<ProposalState | null>(null);
  const [localReceipt, setLocalReceipt] = useState<Decision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const submitIntent = useRef<Command<SubmitProposalInput> | null>(null);
  const finalIntent = useRef<Command<FinalizeProposalInput> | null>(null);

  const refresh = useCallback(async (): Promise<ProposalState | null> => {
    const request = ++generation.current;
    try {
      const value = await api.proposal(caseId);
      if (request !== generation.current) return null;
      setProposalState(value); setError(null); return value;
    } catch (caught) {
      if (request !== generation.current) return null;
      setProposalState(null); setError(`Approval status could not be refreshed. ${safeErrorMessage(caught)} Refresh the case and reselect the response.`); return null;
    }
  }, [caseId]);

  useEffect(() => {
    void refresh(); const interval = window.setInterval(() => void refresh(), 5000);
    return () => {generation.current += 1; window.clearInterval(interval);};
  }, [refresh]);
  useEffect(() => {submitIntent.current = null; finalIntent.current = null; setLocalReceipt(null);}, [selectedOption?.option_id, displayedAnalysis.analysis_id, displayedAnalysis.material_hash]);

  const analysisCurrent = proposalState ? hasAnalysis(proposalState, displayedAnalysis) : true;
  const selectionCurrent = proposalState ? hasSelection(proposalState, caseId, displayedAnalysis, selectedOption) : false;
  const cost = selectedOption?.predicted?.response_cost;
  const requiresFinance = cost ? Number(cost) > 20000 : false;
  const financeSatisfied = selectionCurrent && (!requiresFinance || proposalState?.review?.status === "approved");
  const receipt = matchesReceipt(localReceipt, proposalState, caseId, displayedAnalysis, selectedOption) ? localReceipt
    : matchesReceipt(finalDecision, proposalState, caseId, displayedAnalysis, selectedOption) ? finalDecision : null;

  async function submit() {
    if (!selectedOption || !proposalState || busy || !selectedOption.executable || !analysisCurrent || !independentFinanceEnabled) return;
    const body = {option_id: selectedOption.option_id, expected: proposalState.token};
    const intent = submitIntent.current ?? {body, key: commandKey("proposal")};
    submitIntent.current = intent; generation.current += 1; setBusy(true); setError(null);
    try {await api.submitProposal(caseId, intent.body, intent.key); submitIntent.current = null; await refresh();}
    catch (caught) {if (definitive(caught)) {submitIntent.current = null; setProposalState(null);} setError(`The response was not submitted. ${safeErrorMessage(caught)} Retry this exact submission, or refresh before changing it.`);}
    finally {setBusy(false);}
  }
  async function finalize() {
    if (!proposalState || !financeSatisfied || busy || !independentFinanceEnabled) return;
    const body: FinalizeProposalInput = {expected: proposalState.token, kind: "approved"};
    const intent = finalIntent.current ?? {body, key: commandKey("alex-final")};
    finalIntent.current = intent; generation.current += 1; setBusy(true); setError(null);
    try {
      const decision = await api.finalizeProposal(caseId, intent.body, intent.key); const current = await refresh();
      if (matchesReceipt(decision, current, caseId, displayedAnalysis, selectedOption)) {finalIntent.current = null; setLocalReceipt(decision); onFinalDecision(decision);}
      else if (current) {finalIntent.current = null; setError("The final receipt does not match the proposal now displayed. Reopen the current analysis before continuing.");}
    } catch (caught) {if (definitive(caught)) {finalIntent.current = null; setProposalState(null);} setError(`Final approval was not completed. ${safeErrorMessage(caught)} Refresh the approval state or retry this exact approval.`);}
    finally {setBusy(false);}
  }

  return <section className="panel" aria-labelledby="independent-approval-heading"><h2 id="independent-approval-heading">Review and approve</h2>
    {!selectedOption ? <p>Choose a response before submitting it for approval.</p> : <><p className="eyebrow">Selected response</p><h3>{selectedOption.name}</h3><p className="finance-cost">{cost ? usd(cost) : "Cost unavailable"}</p>
      {!independentFinanceEnabled && <p className="error" role="alert">Independent Finance commands are not enabled. Existing approval history remains readable.</p>}
      {!analysisCurrent && <p className="error" role="alert">The displayed analysis is no longer current. Reopen the current analysis before submitting or approving a response.</p>}
      {!selectedOption.executable && <p className="error">This response is infeasible and cannot be submitted. Reselect an executable response.</p>}
      {!requiresFinance && <p>Finance review not required—within the spending threshold</p>}
      {analysisCurrent && proposalState?.selection && !selectionCurrent && <p>The saved approval belongs to a different response. This selection needs a fresh submission.</p>}
      {selectionCurrent && proposalState?.review?.status === "pending" && <p>Waiting for Taylor to review the proposed spending. <a href={`?financeReviewId=${encodeURIComponent(proposalState.review.review_id)}`}>Open Taylor review</a></p>}
      {selectionCurrent && proposalState?.review?.status === "rejected" && <p>Taylor rejected this spending{proposalState.review.reason ? `: ${proposalState.review.reason}` : "."} Revise or explicitly resubmit the response.</p>}
      {selectionCurrent && proposalState?.review?.status === "approved" && <p>Taylor approved the proposed spending at {time(proposalState.review.reviewed_at)}.{!receipt && " Alex's final approval is still required."}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {!receipt && independentFinanceEnabled && analysisCurrent && (!selectionCurrent || proposalState?.review?.status === "rejected") && <button disabled={busy || !proposalState || !selectedOption.executable} onClick={() => void submit()}>{busy ? "Submitting…" : requiresFinance ? "Submit for Finance review" : "Submit response"}</button>}
      {!receipt && independentFinanceEnabled && financeSatisfied && <button disabled={busy} onClick={() => void finalize()}>{busy ? "Recording final approval…" : "Give final Alex approval"}</button>}
      {receipt && <div><h3>Alex approved this response</h3><p>Final decision recorded separately from Finance review.</p><p>Continue to Execute mitigation plan to review the approved action plan.</p></div>}
    </>}
    <p className="evidence-footer">Approval state from the current saved proposal; selection alone is not authorization.</p></section>;
}
