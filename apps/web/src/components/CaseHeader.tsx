import type {CaseInstance, RuntimeStatus} from "../types";

interface CaseHeaderProps {
  runtime: RuntimeStatus | null;
  caseInstance: CaseInstance | null;
  analyzing: boolean;
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

export function CaseHeader({runtime, caseInstance, analyzing, onAnalyze}: CaseHeaderProps) {
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
    {caseInstance?.controls.new_analysis && <button type="button" onClick={onAnalyze} disabled={analyzing}>
      {analyzing ? "Analyzing disruption…" : "Analyze disruption"}
    </button>}
  </header>;
}
