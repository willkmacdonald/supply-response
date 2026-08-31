import type {CaseInstance, CasePurpose, RuntimeStatus} from "../types";

interface CaseHeaderProps {
  runtime: RuntimeStatus | null;
  caseInstance: CaseInstance | null;
  createPurpose: CasePurpose;
  creating: boolean;
  analyzing: boolean;
  onCreate: (purpose: CasePurpose) => void;
  onAnalyze: () => void;
}

function scenarioLabel(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/Chicago",
    timeZoneName: "short",
  }).format(new Date(value));
}

export function CaseHeader({
  runtime,
  caseInstance,
  createPurpose,
  creating,
  analyzing,
  onCreate,
  onAnalyze,
}: CaseHeaderProps) {
  return <header className="case-header panel">
    <div>
      <p className="eyebrow">RL-001 · Supply disruption response</p>
      <h1>Progressive Case workspace</h1>
      {caseInstance && <p className="case-id">{caseInstance.case_id}</p>}
    </div>
    <div className="provenance" aria-label="Runtime provenance">
      {runtime && <span className={`badge badge-${runtime.runtime_mode}`}>
        {runtime.runtime_mode === "live" ? "Live mode" : "Fallback mode"}
      </span>}
      {caseInstance && <span>Scenario time: {scenarioLabel(caseInstance.scenario_effective_time)}</span>}
      {runtime && !runtime.power_bi_available && <span>Power BI unavailable in fallback</span>}
    </div>
    {runtime && !caseInstance && <button type="button" onClick={() => onCreate(createPurpose)} disabled={creating}>
      {creating
        ? "Creating Case workspace…"
        : `Create ${createPurpose === "automated_test" ? "automated test" : createPurpose} case`}
    </button>}
    {caseInstance?.controls.new_analysis && <button type="button" onClick={onAnalyze} disabled={analyzing}>
      {analyzing ? "Analyzing disruption…" : "Analyze disruption"}
    </button>}
  </header>;
}
