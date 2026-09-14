import {useEffect, useRef, useState} from "react";
import {api, safeErrorMessage} from "../api";
import type {InboxCheckResult} from "../types";
import {SourceActionIcon} from "./SourceActionIcon";

function outlookLink(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      && ["outlook.office365.com", "outlook.office.com", "outlook.cloud.microsoft"].includes(url.hostname)
      ? url.href : undefined;
  } catch { return undefined; }
}

export function InboxCheck({disabled = false, onBusyChange}: {
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
}) {
  const [result, setResult] = useState<InboxCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {mounted.current = true; return () => {mounted.current = false;};}, []);
  async function check() {
    if (disabled || pending.current) return;
    pending.current = true; setChecking(true); onBusyChange?.(true);
    setResult(null); setError(null);
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
  return <section className="panel inbox-check" aria-labelledby="inbox-heading">
    <h2 id="inbox-heading">Supplier email</h2>
    <button type="button" className="source-action" disabled={disabled || checking} onClick={() => void check()}>
      <SourceActionIcon product="outlook"/>{checking ? "Checking email…" : "Check email for disruptions"}
    </button>
    {checking && <p role="status">Searching Alex’s mailbox through Work IQ…</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {result && <div aria-live="polite">
      {result.incomplete && <p role="status">Work IQ could not check every matching email. You can review any results below or try again.</p>}
      {!result.incomplete && result.messages.length === 0 && <p role="status">No matching supplier emails found.</p>}
      {result.messages.map(message => <article className="panel" key={message.message_id}>
        <h3>Supplier Alpha email found</h3>
        <p><strong>{message.subject}</strong></p>
        <p>From {message.sender} · Received {new Date(message.received_at).toLocaleString()}</p>
        <details><summary>Review email</summary><p style={{whiteSpace:"pre-wrap", overflowWrap:"anywhere"}}>{message.excerpt}</p></details>
        {outlookLink(message.citation_url) && <a className="source-action" href={outlookLink(message.citation_url)} target="_blank" rel="noopener noreferrer">
          <SourceActionIcon product="outlook"/>Open supplier email
        </a>}
      </article>)}
      <p>Work IQ · Checked {new Date(result.checked_at).toLocaleString()}</p>
    </div>}
  </section>;
}
