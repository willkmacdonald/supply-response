import {useState} from "react";
import {api, type WorkIQProbeResult} from "../api";

const checks: Array<[keyof WorkIQProbeResult, string]> = [
  ["authenticated_alex", "Authenticated Alex"],
  ["obo_succeeded", "OBO succeeded"],
  ["mcp_initialized", "MCP initialized"],
  ["fetch_succeeded", "Fetch succeeded"],
  ["exact_message_identity", "Exact message identity"],
  ["expected_author", "Expected author"],
  ["valid_source_timestamp", "Valid source timestamp"],
  ["nonempty_body", "Nonempty body"],
  ["expected_channel_identity", "Expected channel identity"],
  ["expected_source_link", "Expected source link"],
];

export function WorkIQProbe() {
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<WorkIQProbeResult | null>(null);
  const [failed, setFailed] = useState(false);

  async function run() {
    setPending(true);
    try {
      setResult(await api.invokeWorkIQProbe());
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  return <main className="case-workspace">
    <h1>Work IQ fetch diagnostic</h1>
    <button type="button" disabled={pending || result !== null || failed} onClick={() => void run()}>
      {pending ? "Running diagnostic…" : "Run diagnostic once"}
    </button>
    {failed && <p role="alert">The diagnostic could not be completed.</p>}
    {result && <section aria-label="Diagnostic result">
      <p>Stage: {result.stage}</p>
      <p>HTTP status: {result.http_status ?? "Unavailable"}</p>
      <dl>{checks.map(([key, label]) => <div key={key}>
        <dt>{label}</dt><dd>{result[key] === true ? "Yes" : "No"}</dd>
      </div>)}</dl>
    </section>}
  </main>;
}
