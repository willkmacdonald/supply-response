import type {AnalysisVersion, RuntimeStatus} from "../types";
import {buildReportUrl, type ReportAnalysisContext} from "../reporting/reportNavigation";
import type {PlannerSnapshot} from "./plannerSnapshot";
import {optionDisplayName} from "./optionLabels";
import {PredictionSummary} from "./PredictionSummary";
import {blocker, role, rankingReason} from "./plannerFormatting";
export function ExposurePanel({analysis, snapshot = null, runtime = null, reportContext = null}: {analysis: AnalysisVersion | null; snapshot?: PlannerSnapshot | null; runtime?: RuntimeStatus | null; reportContext?: ReportAnalysisContext | null}) {
  if (!analysis) return null;
  const matches = analysis.response_options.filter(option => option.option_id === analysis.ranking.recommended_option_id);
  const option = matches.length === 1 && analysis.recommendation?.option_id === matches[0].option_id ? matches[0] : null;
  const matchingContext = reportContext?.caseId === analysis.case_id
    && reportContext?.analysisId === analysis.analysis_id
    && reportContext?.runtimeMode === analysis.runtime_mode;
  const reportUrl = runtime && reportContext && matchingContext && option
    ? buildReportUrl(runtime, {...reportContext, page: "response-options", optionId: option.option_id})
    : null;
  return <section className="panel investigation-card" aria-labelledby="exposure-heading"><h3 id="exposure-heading">Recommended response—and why.</h3>{option ? <>
    <p>Recommended for review: {optionDisplayName(option)}.</p><p>Recommendation does not mean approval or execution.</p>
    {analysis.ranking.stages.some(stage => stage.retained_option_ids.includes(option.option_id)) ? <ul aria-label="Reasons from the saved comparison">{analysis.ranking.stages.filter(stage => stage.retained_option_ids.includes(option.option_id)).map((stage, index) => <li key={index}>{rankingReason(stage, option.option_id)}</li>)}</ul> : <p>The saved analysis names this recommendation but contains no retained-stage explanation.</p>}
    <PredictionSummary predicted={option.predicted} snapshot={snapshot} basis="response" />{option.blocking_codes.length > 0 && <ul>{option.blocking_codes.map(code => <li key={code}>{blocker(code)}</li>)}</ul>}
    <p>Required roles: {option.prerequisite_roles.map(role).join(", ") || "No roles recorded"}.</p>{option.assumptions.length > 0 && <><h4>What remains uncertain</h4><ul>{option.assumptions.map((text, index) => <li key={index}>{text}</li>)}</ul></>}
    <details><summary>Why this option was retained</summary><ol>{analysis.ranking.stages.map((stage, index) => <li key={index}>{stage.comparator.replaceAll("_", " ")}: {stage.retained_option_ids.includes(option.option_id) ? "recommended option retained" : "see saved ranking"}; threshold {stage.threshold}.</li>)}</ol><p>Source records: {option.source_data_lineage.join(", ") || "Unavailable"}</p><p>Calculation version: {analysis.material.calculation_version}</p></details>
  </> : <p>No unambiguous recommendation is available in this saved analysis.</p>}{reportUrl && <a href={reportUrl} target="_blank" rel="noopener noreferrer">Explore recommended response in Power BI</a>}<footer className="saved-analysis-footer">Saved analysis recommendation; benefits are predictions.</footer></section>;
}
