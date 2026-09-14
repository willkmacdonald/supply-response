import {useEffect, useRef, useState} from "react";
import {api, messageForCode, safeErrorMessage} from "../api";
import type {InboxCheckResult, InboxMessage, SupplierDisruptionFacts} from "../types";
import {SourceActionIcon} from "./SourceActionIcon";

function outlookLink(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      && ["outlook.office365.com", "outlook.office.com", "outlook.cloud.microsoft"].includes(url.hostname)
      ? url.href : undefined;
  } catch { return undefined; }
}

function scenarioDate(value: string): string {
  return new Date(`${value}T12:00:00Z`).toLocaleDateString("en-US", {month:"long",day:"numeric",year:"numeric",timeZone:"UTC"});
}

function DisruptionFacts({facts}: {facts: SupplierDisruptionFacts}) {
  const quantity = (value: number) => value.toLocaleString("en-US");
  const cost = Number(facts.additional_cost_per_unit).toLocaleString("en-US", {style:"currency",currency:"USD",minimumFractionDigits:2,maximumFractionDigits:2});
  return <div className="inbox-facts">
    <h4>Disruption reported by Supplier Alpha</h4>
    <p><strong>Original delivery:</strong> {quantity(facts.original_quantity)} units of {facts.part_id} due at {facts.plant_name} plant on {scenarioDate(facts.original_due_date)} cannot be delivered as planned.</p>
    <p><strong>Partial shipment offered:</strong> {quantity(facts.partial_quantity)} units by air on {scenarioDate(facts.partial_due_date)}, at an additional {cost} per component unit.</p>
    <p><strong>Remaining supply:</strong> {quantity(facts.remaining_quantity)} units{facts.recovery_date ? ` due ${scenarioDate(facts.recovery_date)}.` : " — no confirmed delivery date."}</p>
  </div>;
}

export function InboxCheck({disabled = false, onBusyChange, onCaseCreated}: {
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
  onCaseCreated?: (caseId: string) => void | Promise<void>;
}) {
  const [result, setResult] = useState<InboxCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [creating, setCreating] = useState<string | null>(null);
  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null);
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {mounted.current = true; return () => {mounted.current = false;};}, []);
  async function check() {
    if (disabled || pending.current) return;
    pending.current = true; setChecking(true); onBusyChange?.(true);
    setResult(null); setError(null); setCreatedCaseId(null);
    try {
      const found = await api.checkInbox();
      if (mounted.current) setResult(found);
    } catch (caught) {
      if (mounted.current) setError(safeErrorMessage(caught));
    } finally {
      pending.current = false;
      if (mounted.current) {setChecking(false); onBusyChange?.(false);}
    }
  }
  async function create(message: InboxMessage) {
    if (disabled || pending.current || !onCaseCreated || !message.internet_message_id || !message.review_fingerprint || !message.facts || message.creation_blocker) return;
    pending.current = true; setCreating(message.message_id); setError(null); onBusyChange?.(true);
    try {
      const created = await api.createCaseFromEmail(message.internet_message_id, message.review_fingerprint);
      if (!created.current_analysis_id) await api.analyze(created.case_id);
      if (mounted.current) {
        await onCaseCreated(created.case_id);
        setCreatedCaseId(created.case_id);
        document.getElementById("assisted-review")?.scrollIntoView({behavior: "smooth", block: "start"});
      }
    } catch (caught) {
      if (mounted.current) setError(safeErrorMessage(caught));
    } finally {
      pending.current = false;
      if (mounted.current) setCreating(null);
      onBusyChange?.(false);
    }
  }
  return <section className="panel inbox-check" aria-labelledby="inbox-heading">
    <h2 id="inbox-heading">Supplier email</h2>
    <button type="button" className="source-action" disabled={disabled || checking || creating !== null} onClick={() => void check()}>
      <SourceActionIcon product="outlook"/>{checking ? "Checking email…" : "Check email for disruptions"}
    </button>
    {checking && <p role="status">Searching Alex’s mailbox through Work IQ…</p>}
    {creating !== null && <p role="status">Analyzing the supplier disruption…</p>}
    {createdCaseId && <p role="status">Disruption analysis is ready below.</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {result && <div aria-live="polite">
      {result.incomplete && <p role="status">Work IQ could not check every matching email. You can review any results below or try again.</p>}
      {!result.incomplete && result.messages.length === 0 && <p role="status">No matching supplier emails found.</p>}
      {result.messages.map(message => <article className="panel" key={message.message_id}>
        <h3>Supplier Alpha email found</h3>
        <p><strong>{message.subject}</strong></p>
        <p>From {message.sender} · Received {new Date(message.received_at).toLocaleString()}</p>
        <p style={{whiteSpace:"pre-wrap", overflowWrap:"anywhere"}}>{message.excerpt}</p>
        <details><summary>Review disruption</summary>
          {message.facts && <DisruptionFacts facts={message.facts}/>}
          {message.creation_blocker && <p>{messageForCode(message.creation_blocker)}</p>}
          {onCaseCreated && message.facts && message.internet_message_id && message.review_fingerprint && !message.creation_blocker &&
            <button type="button" disabled={disabled || checking || creating !== null} onClick={() => void create(message)}>
              {creating === message.message_id ? "Analyzing disruption…" : "Analyze this disruption"}
            </button>}
        </details>
        {outlookLink(message.citation_url) && <a className="source-action" href={outlookLink(message.citation_url)} target="_blank" rel="noopener noreferrer">
          <SourceActionIcon product="outlook"/>Open supplier email
        </a>}
      </article>)}
      <p>Work IQ · Checked {new Date(result.checked_at).toLocaleString()}</p>
    </div>}
  </section>;
}
