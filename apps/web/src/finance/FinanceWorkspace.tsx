import {useCallback, useEffect, useRef, useState} from "react";
import {api, safeErrorMessage} from "../api";
import type {FinanceReviewDetail, ResolveFinanceInput} from "../types";
import {commandKey, time, usd} from "./format";

type PendingCommand = {body: ResolveFinanceInput; key: string};

export function FinanceWorkspace({displayName, onSwitchAccount}: {displayName: string | null; onSwitchAccount: () => Promise<void>}) {
  const [reviews, setReviews] = useState<FinanceReviewDetail[] | null>(null);
  const [detail, setDetail] = useState<FinanceReviewDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef<PendingCommand | null>(null);
  const alive = useRef(true);
  const selectedReviewId = useRef<string | null>(null);
  const reviewId = new URLSearchParams(window.location.search).get("financeReviewId");

  const loadList = useCallback(async () => {
    try { const value = await api.financeReviews(); if (alive.current) {setReviews(value); setError(null);} }
    catch (caught) { if (alive.current) {setReviews(null); setError(`Finance requests could not be loaded. ${safeErrorMessage(caught)} Refresh and try again.`);} }
  }, []);
  const open = useCallback(async (id: string, clearReason = true) => {
    setError(null);
    try {
      const value = await api.financeReview(id); if (!alive.current) return;
      selectedReviewId.current = id;
      setDetail(value); if (clearReason) setReason("");
      const url = new URL(window.location.href); url.searchParams.set("financeReviewId", id); window.history.replaceState(window.history.state, "", url);
    } catch (caught) { if (alive.current) {setDetail(null); setError(`This Finance request could not be loaded. ${safeErrorMessage(caught)} Return to the inbox and refresh.`);} }
  }, []);
  useEffect(() => {
    alive.current = true; void loadList(); if (reviewId) void open(reviewId);
    const interval = window.setInterval(() => {void loadList(); if (selectedReviewId.current) void open(selectedReviewId.current, false);}, 5000);
    return () => {alive.current = false; window.clearInterval(interval);};
  }, [loadList, open, reviewId]);

  async function resolve(approved: boolean) {
    if (!detail || busy || (!approved && !reason.trim())) return;
    const body = {expected: detail.current_token, expected_review_revision: detail.review_revision, approved, ...(approved ? {} : {reason: reason.trim()})};
    const intent = pending.current?.body.approved === approved ? pending.current : {body, key: commandKey("finance-resolution")};
    pending.current = intent; setBusy(true); setError(null);
    try {
      await api.resolveFinanceReview(detail.review.review_id, intent.body, intent.key);
      pending.current = null;
      await open(detail.review.review_id); await loadList();
    } catch (caught) { setError(`The Finance decision was not completed. ${safeErrorMessage(caught)} Refresh the request, or retry this exact decision.`); }
    finally { if (alive.current) setBusy(false); }
  }

  return <main className="case-workspace finance-workspace">
    <header className="finance-header"><div><p className="eyebrow">Finance review</p><h1>Supply Response</h1><p>Signed in as {displayName ?? "Taylor"}. Review proposed spending independently from Alex's final response approval.</p></div><button type="button" onClick={() => void onSwitchAccount()}>Switch Microsoft account</button></header>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="finance-layout">
      <section className="panel" aria-labelledby="finance-inbox-heading"><h2 id="finance-inbox-heading">Finance requests</h2>
        {reviews === null && !error && <p role="status">Loading Finance requests…</p>}
        {reviews?.length === 0 && <p>No Finance requests are waiting.</p>}
        <div className="finance-list">{reviews?.map(item => <button type="button" key={item.review.review_id} onClick={() => void open(item.review.review_id)} aria-current={detail?.review.review_id === item.review.review_id}>
          <strong>{item.option.name}</strong><span>{usd(item.selection.proposal.response_cost)} · {item.review.status}</span><span>Submitted {time(item.selection.submitted_at)}</span>
        </button>)}</div>
      </section>
      <section className="panel finance-detail" aria-labelledby="finance-detail-heading">
        {!detail ? <><h2 id="finance-detail-heading">Review detail</h2><p>Select a request to inspect its bound response and evidence.</p></> : <>
          <p className={`status-pill status-${detail.review.status}`}>{detail.review.status}</p><h2 id="finance-detail-heading">{detail.option.name}</h2>
          <p className="finance-cost">{usd(detail.selection.proposal.response_cost)}</p>
          <dl><div><dt>Submitted</dt><dd>{time(detail.selection.submitted_at)}</dd></div><div><dt>Reviewed</dt><dd>{time(detail.review.reviewed_at)}</dd></div><div><dt>Current request</dt><dd>{detail.is_current ? "Yes" : "No—historical request"}</dd></div></dl>
          <h3>Expected impact</h3>{detail.option.predicted ? <ul><li>Uncovered demand: {detail.option.predicted.uncovered_part_demand.toLocaleString()} units</li><li>Revenue at risk: {usd(detail.option.predicted.revenue_at_risk)}</li><li>Margin at risk: {usd(detail.option.predicted.margin_at_risk)}</li></ul> : <p>Impact prediction is unavailable.</p>}
          <h3>Evidence and constraints</h3><ul>{detail.option.evidence_ids.map(id => {const evidence = detail.analysis.evidence_items.find(item => item.evidence_id === id); return <li key={id}>{evidence?.claim ?? id}</li>;})}{detail.option.assumptions.map(item => <li key={item}>{item}</li>)}</ul>
          {detail.review.reason && <p><strong>Reason:</strong> {detail.review.reason}</p>}
          {detail.review.status === "pending" && detail.is_current ? <div className="finance-actions"><label>Rejection reason<textarea value={reason} onChange={event => {setReason(event.target.value); pending.current = null;}} /></label><div><button disabled={busy} onClick={() => void resolve(true)}>Approve spending</button><button disabled={busy || !reason.trim()} onClick={() => void resolve(false)}>Reject spending</button></div></div>
            : <p>This historical or resolved request remains readable and is not actionable.</p>}
          <details><summary>Request details</summary><p>Review {detail.review.review_id}</p><p>Revision {detail.review_revision}</p></details>
        </>}
      </section>
    </div>
  </main>;
}
