import type { AnalysisVersion, CaseInstance, RuntimeStatus } from "../types";
import { buildTraditionalReportUrl } from "../reporting/reportNavigation";

export function PlanningRoutes({ runtime, caseInstance, analysis }: {
  runtime: RuntimeStatus | null;
  caseInstance: Pick<CaseInstance, "case_id" | "runtime_mode"> | null;
  analysis: Pick<AnalysisVersion, "analysis_id" | "case_id" | "runtime_mode"> | null;
}) {
  if (!runtime || !caseInstance || !analysis
    || caseInstance.case_id !== analysis.case_id
    || caseInstance.runtime_mode !== analysis.runtime_mode) return null;
  const url = buildTraditionalReportUrl(runtime, {
    caseId: caseInstance.case_id, analysisId: analysis.analysis_id,
    runtimeMode: analysis.runtime_mode,
  });
  return <nav aria-label="Planning routes" className="panel">
    <div className="planning-route-actions">
      {url && <a href={url} target="_blank" rel="noopener noreferrer">Explore in Power BI</a>}
      <a href="#assisted-review">Review with AI assistance</a>
    </div>
    <p>{url
      ? "Power BI opens a broad fictional operational reporting snapshot in a new tab. AI assistance uses the exact evidence captured for this analysis; keep this tab open for the original email, Teams sources, and assisted review."
      : "The Power BI comparison is not available for this analysis. You can still review the saved evidence and AI assistance here."}</p>
    <p>Showing saved evidence; no new source retrieval is running.</p>
  </nav>;
}
