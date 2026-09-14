import {useCallback, useEffect, useRef, useState} from "react";
import {ApiRequestError, api, safeErrorMessage} from "../api";
import {EvidenceFooters, EvidenceSource} from "../components/EvidenceSource";
import type {FinanceReviewDetail, ResolveFinanceInput} from "../types";
import {commandKey, time, usd} from "./format";

type PendingCommand = {reviewId: string; body: ResolveFinanceInput; key: string};
interface Props {displayName: string | null; onSwitchAccount: () => Promise<void>; independentFinanceEnabled: boolean}
function definitive(error: unknown) {return error instanceof ApiRequestError && [403, 404, 409, 422].includes(error.status);}

export function FinanceWorkspace({displayName, onSwitchAccount, independentFinanceEnabled}: Props) {
  const [reviews, setReviews] = useState<FinanceReviewDetail[] | null>(null);
  const [detail, setDetail] = useState<FinanceReviewDetail | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedReviewId = useRef<string | null>(null);
  const pending = useRef<PendingCommand | null>(null);
  const listGeneration = useRef(0);
  const detailGeneration = useRef(0);
  const deepLinkReviewId = new URLSearchParams(window.location.search).get("financeReviewId");

  const loadList = useCallback(async () => {
    const request = ++listGeneration.current;
    try {const value = await api.financeReviews(); if (request === listGeneration.current) {setReviews(value); setListError(null);}}
    catch (caught) {if (request === listGeneration.current) {setReviews(null); setListError(`Finance requests could not be loaded. ${safeErrorMessage(caught)} Refresh and try again.`);}}
  }, []);

  const open = useCallback(async (reviewId: string, userSelected = true) => {
    if (userSelected) {
      selectedReviewId.current = reviewId; pending.current = null; setReason(""); setCommandError(null); setDetail(null);
      const url = new URL(window.location.href); url.searchParams.set("financeReviewId", reviewId); window.history.replaceState(window.history.state, "", url);
    }
    const request = ++detailGeneration.current;
    setDetailError(null);
    try {
      const value = await api.financeReview(reviewId);
      if (request === detailGeneration.current && selectedReviewId.current === reviewId) setDetail(value);
    } catch (caught) {
      if (request === detailGeneration.current && selectedReviewId.current === reviewId) {setDetail(null); setDetailError(`This Finance request could not be loaded. ${safeErrorMessage(caught)} Return to the inbox and refresh.`);}
    }
  }, []);

  useEffect(() => {
    void loadList(); if (deepLinkReviewId) void open(deepLinkReviewId);
    const interval = window.setInterval(() => {void loadList(); if (selectedReviewId.current) void open(selectedReviewId.current, false);}, 5000);
    return () => {listGeneration.current += 1; detailGeneration.current += 1; window.clearInterval(interval);};
  }, [deepLinkReviewId, loadList, open]);

  async function resolve(approved: boolean) {
    if (!detail || busy || !independentFinanceEnabled || (!approved && !reason.trim())) return;
    const body = {expected: detail.current_token, expected_review_revision: detail.review_revision, approved, ...(approved ? {} : {reason: reason.trim()})};
    const existing = pending.current;
    const sameIntent = existing?.reviewId === detail.review.review_id && JSON.stringify(existing.body) === JSON.stringify(body);
    const intent = sameIntent ? existing : {reviewId: detail.review.review_id, body, key: commandKey("finance-resolution")};
    pending.current = intent; detailGeneration.current += 1; setBusy(true); setCommandError(null);
    try {
      await api.resolveFinanceReview(intent.reviewId, intent.body, intent.key);
      pending.current = null; await open(intent.reviewId, false); await loadList();
    } catch (caught) {
      if (definitive(caught)) {pending.current = null; selectedReviewId.current = null; setDetail(null);}
      setCommandError(`The Finance decision was not completed. ${safeErrorMessage(caught)} ${definitive(caught) ? "Refresh and reselect the request." : "Retry this exact decision, or select another request."}`);
    } finally {setBusy(false);}
  }

  async function returnToAlex() {
    if (!detail) return;
    const url = new URL(window.location.href);
    url.searchParams.set("caseId", detail.analysis.case_id);
    url.searchParams.set("analysisId", detail.analysis.analysis_id);
    url.searchParams.set("optionId", detail.option.option_id);
    url.searchParams.set("stage", "approval");
    url.searchParams.delete("financeReviewId");
    window.history.replaceState(window.history.state, "", url);
    await onSwitchAccount();
  }

  const evidence = detail?.option.evidence_ids.map(id => detail.analysis.evidence_items.find(item => item.evidence_id === id)).filter(item => item !== undefined) ?? [];
  const approvedCurrent = detail?.review.status === "approved" && detail.is_current;
  const reviewerName = detail?.review.reviewed_by?.display_name?.trim() || displayName?.trim() || "Taylor";
  const readOnlyMessage = detail?.review.status === "superseded" ? "This request was superseded by a newer proposal and remains readable but not actionable."
    : detail?.review.status === "rejected" ? "This request was rejected and remains readable but not actionable."
    : !detail?.is_current ? "This request is no longer current and remains readable but not actionable."
    : !independentFinanceEnabled ? "Independent Finance commands are disabled. This request remains readable and is not actionable."
    : "This request remains readable and is not actionable.";
  return <main className="case-workspace finance-workspace">
    <header className="finance-header"><div><p className="eyebrow">Finance review</p><h1>Supply Response</h1><p>Signed in as {displayName ?? "Taylor"}. Review proposed spending independently from Alex's final response approval.</p></div><button type="button" onClick={() => void onSwitchAccount()}>Switch Microsoft account</button></header>
    {!independentFinanceEnabled && <p className="error" role="alert">Independent Finance commands are not enabled. Existing review history remains readable.</p>}
    {commandError && <p className="error" role="alert">{commandError}</p>}
    <div className="finance-layout">
      <section className="panel" aria-labelledby="finance-inbox-heading"><h2 id="finance-inbox-heading">Finance requests</h2>
        {listError && <p className="error" role="alert">{listError}</p>}
        {reviews === null && !listError && <p role="status">Loading Finance requests…</p>}
        {reviews?.length === 0 && <p>No Finance requests are waiting.</p>}
        <div className="finance-list">{reviews?.map(item => <button disabled={busy} type="button" key={item.review.review_id} onClick={() => void open(item.review.review_id)} aria-current={detail?.review.review_id === item.review.review_id}><strong>{item.option.name}</strong><span>{usd(item.selection.proposal.response_cost)} · {item.review.status}</span><span>Submitted {time(item.selection.submitted_at)}</span></button>)}</div>
      </section>
      <section className="panel finance-detail" aria-labelledby="finance-detail-heading">
        {detailError && <p className="error" role="alert">{detailError}</p>}
        {!detail ? <><h2 id="finance-detail-heading">Review detail</h2><p>Select a request to inspect its bound response and evidence.</p></> : <>
          <div className="analysis-context"><p>{detail.analysis.material.corpus === "demo_corpus" ? "Demo corpus — fictional" : "Fictional provenance not established for this analysis"}</p><p>{detail.analysis.runtime_mode === "fallback" ? "Sample data — not a live retrieval" : "Live retrieval saved for this analysis"}</p><p>Analysis {detail.analysis.analysis_id}</p></div>
          <p className={`status-pill status-${detail.review.status}`}>{detail.review.status}</p><h2 id="finance-detail-heading">{detail.option.name}</h2><p className="finance-cost">{usd(detail.selection.proposal.response_cost)}</p>
          <dl><div><dt>Submitted</dt><dd>{time(detail.selection.submitted_at)}</dd></div><div><dt>Reviewed</dt><dd>{time(detail.review.reviewed_at)}</dd></div><div><dt>Current request</dt><dd>{detail.is_current ? "Yes" : "No—historical request"}</dd></div></dl>
          <h3>Expected impact</h3>{detail.option.predicted ? <ul><li>Uncovered demand: {detail.option.predicted.uncovered_part_demand.toLocaleString()} units</li><li>Revenue at risk: {usd(detail.option.predicted.revenue_at_risk)}</li><li>Margin at risk: {usd(detail.option.predicted.margin_at_risk)}</li></ul> : <p>Impact prediction is unavailable.</p>}
          <h3>Evidence and constraints</h3>{evidence.map(item => <EvidenceSource key={item.evidence_id} item={item} analysis={detail.analysis} label="Source record" />)}<ul>{detail.option.assumptions.map(item => <li key={item}>{item}</li>)}</ul>{evidence.length > 0 && <EvidenceFooters items={evidence} analysis={detail.analysis} />}
          {detail.review.reason && <p><strong>Reason:</strong> {detail.review.reason}</p>}
          {detail.review.status === "pending" && detail.is_current && independentFinanceEnabled ? <div className="finance-actions"><label>Rejection reason<textarea value={reason} onChange={event => {setReason(event.target.value); pending.current = null;}} /></label><div><button disabled={busy} onClick={() => void resolve(true)}>Approve spending</button><button disabled={busy || !reason.trim()} onClick={() => void resolve(false)}>Reject spending</button></div></div>
            : approvedCurrent ? independentFinanceEnabled ? <><p>{reviewerName} approved the spending on {time(detail.review.reviewed_at)}. Alex can now complete final approval.</p><div className="finance-actions"><button type="button" onClick={() => void returnToAlex()}>Return to Alex for final approval</button></div></> : <p>{reviewerName} approved the spending on {time(detail.review.reviewed_at)}. Independent Finance commands are disabled; this request remains readable and does not provide a handoff.</p>
            : <p>{readOnlyMessage}</p>}
          <details><summary>Request details</summary><p>Review {detail.review.review_id}</p><p>Revision {detail.review_revision}</p></details>
        </>}
      </section>
    </div>
  </main>;
}
