import type {AnalysisVersion, CaseInstance, CasePurpose, RuntimeStatus} from "../types";
import {buildReportUrl} from "../reporting/reportNavigation";
import {parseSnapshotEnvelope} from "./snapshotValidation";

interface CaseHeaderProps {
  runtime: RuntimeStatus | null;
  caseInstance: CaseInstance | null;
  analysis: AnalysisVersion | null;
  createPurpose: CasePurpose;
  creating: boolean;
  analyzing: boolean;
  busy?: boolean;
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
  analysis,
  createPurpose,
  creating,
  analyzing,
  busy,
  onCreate,
  onAnalyze,
}: CaseHeaderProps) {
  const matchingAnalysis = caseInstance && analysis
    ? parseSnapshotEnvelope({caseInstance, analysis}) !== null
    : false;
  const powerBiUrl = runtime && caseInstance && (!analysis || matchingAnalysis)
    ? buildReportUrl(runtime, {
        page: "command-center",
        caseId: caseInstance.case_id,
        runtimeMode: caseInstance.runtime_mode,
        ...(analysis ? {analysisId: analysis.analysis_id} : {}),
      })
    : null;
  return <header className="case-header panel">
    <div className="case-header-intro">
      <p className="eyebrow">RL-001 · Supply Disruption Response</p>
      <h1>Respond to supply disruptions with AI</h1>
      <p className="case-header-summary">AI brings together supplier messages, inventory, and customer orders to assess the impact of a delay, compare recovery options, and support the planner's decision.</p>
      {caseInstance && <details><summary>Case details</summary><p>Case {caseInstance.case_id}</p></details>}
    </div>
    <div className="provenance" aria-label="Runtime provenance">
      {caseInstance && <span>Scenario time: {scenarioLabel(caseInstance.scenario_effective_time)}</span>}
      {runtime && !runtime.power_bi_available && <span>
        {runtime.runtime_mode === "fallback"
          ? "Power BI unavailable in fallback"
          : "Power BI report is not available"}
      </span>}
      {powerBiUrl && <a href={powerBiUrl} target="_blank" rel="noopener noreferrer">Open case dashboard</a>}
    </div>
    {runtime && !caseInstance && <button type="button" onClick={() => onCreate(createPurpose)} disabled={busy || creating}>
      {creating
        ? "Creating Case workspace…"
        : `Create ${createPurpose === "automated_test" ? "automated test" : createPurpose} case`}
    </button>}
    {caseInstance?.controls.new_analysis && <button type="button" onClick={onAnalyze} disabled={busy || analyzing}>
      {analyzing ? "Analyzing disruption…" : "Analyze disruption"}
    </button>}
    <p className="case-header-mode">
      {runtime?.runtime_mode === "live"
        ? "Fictional scenario · Uses live Microsoft services"
        : runtime?.runtime_mode === "fallback"
          ? "Fictional scenario · Uses predefined sample data"
          : "Fictional scenario · Service mode not yet available"}
    </p>
  </header>;
}
