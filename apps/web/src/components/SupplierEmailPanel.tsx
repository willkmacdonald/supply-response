import {useEffect, useRef, useState} from "react";
import {safeErrorMessage} from "../api";
import type {SupplierEmailState} from "../types";

export interface SupplierEmailPanelProps {
  email: SupplierEmailState;
  busy: boolean;
  sendEnabled: boolean;
  onSave: (input: {revision: number; subject: string; body: string}) => Promise<SupplierEmailState>;
  onReview: (revision: number) => Promise<SupplierEmailState>;
  onSend: (revision: number) => Promise<SupplierEmailState>;
  onCheckStatus: () => Promise<SupplierEmailState>;
}

const statusLabels = new Map<SupplierEmailState["send_status"], string>([
  ["draft", "Not sent"],
  ["submitting", "Sending…"],
  ["accepted", "Email submitted to Microsoft 365"],
  ["sent-confirmed", "Sent"],
  ["failed", "Send failed"],
  ["uncertain", "Send status uncertain"],
]);

type PendingAction = "save" | "review" | "send";

export function SupplierEmailPanel({
  email,
  busy,
  sendEnabled,
  onSave,
  onReview,
  onSend,
}: SupplierEmailPanelProps) {
  const [current, setCurrent] = useState(email);
  const [subject, setSubject] = useState(email.subject);
  const [body, setBody] = useState(email.body);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const pendingRef = useRef(false);

  useEffect(() => {
    setCurrent(email);
    setSubject(email.subject);
    setBody(email.body);
  }, [email]);

  const dirty = subject !== current.subject || body !== current.body;
  const reviewed = current.reviewed_revision === current.revision;
  const editable = current.send_status === "draft" || current.send_status === "failed";
  const actionDisabled = busy || pending !== null;

  async function run(
    action: PendingAction,
    startingNotice: string,
    complete: (next: SupplierEmailState) => string,
    operation: () => Promise<SupplierEmailState>,
  ) {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(action);
    setNotice(startingNotice);
    try {
      const next = await operation();
      setCurrent(next);
      setSubject(next.subject);
      setBody(next.body);
      setNotice(complete(next));
    } catch (error) {
      setNotice(`This email action could not be completed. ${safeErrorMessage(error)}`);
    } finally {
      pendingRef.current = false;
      setPending(null);
    }
  }

  const status = pending === "send" ? "Sending…" : statusLabels.get(current.send_status) ?? "Send status unavailable";

  return <section className="panel supplier-email-panel" aria-labelledby="supplier-email-heading">
    <div className="supplier-email-header">
      <div>
        <p className="step">Supplier email</p>
        <h2 id="supplier-email-heading">Review the supplier email</h2>
      </div>
      <span className={`badge mail-status mail-status-${current.send_status}`}>{status}</span>
    </div>
    <p>From: Alex — {current.from_address}</p>
    <p>To: Supplier Alpha (demo) — {current.to_address}</p>
    <label className="email-field">Subject
      <input value={subject} maxLength={255} disabled={!editable || actionDisabled}
        onChange={event => {setSubject(event.target.value); setNotice(null);}} />
    </label>
    <label className="email-field">Message
      <textarea value={body} maxLength={10_000} rows={10} disabled={!editable || actionDisabled}
        onChange={event => {setBody(event.target.value); setNotice(null);}} />
    </label>
    <div className="supplier-email-actions">
      {dirty && <button type="button" disabled={actionDisabled || !subject.trim() || !body.trim()}
        onClick={() => void run("save", "Saving changes…", () => "Changes saved. Review this email before sending.",
          () => onSave({revision: current.revision, subject, body}))}>
        {pending === "save" ? "Saving…" : "Save changes"}
      </button>}
      {!dirty && editable && !reviewed && <button type="button" disabled={actionDisabled}
        onClick={() => void run("review", "Recording your review…", () => "Email reviewed. It is ready to send.",
          () => onReview(current.revision))}>
        {pending === "review" ? "Reviewing…" : "Review this email"}
      </button>}
      {editable && <button type="button" disabled={actionDisabled || dirty || !reviewed || !sendEnabled}
        onClick={() => void run("send", "Sending…", next => statusLabels.get(next.send_status) ?? "Send status unavailable",
          () => onSend(current.revision))}>
        {pending === "send" ? "Sending…" : "Send email"}
      </button>}
    </div>
    {!sendEnabled && <p>Email sending is not enabled for this demo environment.</p>}
    {notice && <p className="mail-notice" role="status" aria-live="polite">{notice}</p>}
    <p className="mail-boundary">This status reflects Microsoft 365 submission and send evidence only. It does not confirm receipt.</p>
  </section>;
}
