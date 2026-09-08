import type {EvidenceStatus} from "./evidenceStatus";

export function EvidenceFooter({status}: {status: EvidenceStatus}) {
  return <footer className="evidence-footer" aria-label="Source and evidence status">
    <span className="badge">{status.platform}</span>
    <p>{status.retrieval}{status.recordedAt && <> · <time dateTime={status.recordedAt}>
      {new Intl.DateTimeFormat("en-US", {
        year: "numeric", month: "short", day: "numeric", hour: "numeric",
        minute: "2-digit", timeZone: "UTC", timeZoneName: "short",
      }).format(new Date(status.recordedAt))}
    </time></>}</p>
    <p>{status.validation}</p>
  </footer>;
}
