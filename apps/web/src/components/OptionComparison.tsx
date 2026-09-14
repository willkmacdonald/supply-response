import {useEffect, useState} from "react";
import type {AnalysisVersion, ResponseOption, RuntimeStatus} from "../types";
import {buildReportUrl, type ReportAnalysisContext} from "../reporting/reportNavigation";
import type {PlannerSnapshot} from "./plannerSnapshot";
import {optionDisplayName} from "./optionLabels";
import {blocker, rankingThreshold} from "./plannerFormatting";
import {PredictionSummary} from "./PredictionSummary";
import {ExposurePanel} from "./ExposurePanel";
import {RecommendationSheet} from "./RecommendationSheet";
import {recommendedOption} from "./recommendationState";
export function OptionComparison({analysis, selectedOption, onSelect, onContinue, snapshot = null, runtime = null, reportContext = null, disabled = false}: {analysis: AnalysisVersion | null; selectedOption: ResponseOption | null; onSelect: (option: ResponseOption) => void; onContinue?: () => void; snapshot?: PlannerSnapshot | null; runtime?: RuntimeStatus | null; reportContext?: ReportAnalysisContext | null; disabled?: boolean}) {
  const identity = analysis ? `${analysis.case_id}\u0000${analysis.analysis_id}` : null;
  const [openIdentity, setOpenIdentity] = useState<string | null>(null);
  useEffect(() => {setOpenIdentity(null);}, [identity]);
  if (!analysis) return null;
  const recommendation = recommendedOption(analysis);
  const matchesSelection = selectedOption === null
    || analysis.response_options.filter(option => option.option_id === selectedOption.option_id).length === 1;
  const matchingContext = reportContext?.caseId === analysis.case_id
    && reportContext?.analysisId === analysis.analysis_id
    && reportContext?.runtimeMode === analysis.runtime_mode;
  const reportUrl = runtime && reportContext && matchingContext && matchesSelection
    ? buildReportUrl(runtime, {
        ...reportContext, page: "response-options",
        ...(selectedOption ? {optionId: selectedOption.option_id} : {}),
      }) : null;
  const options = [...analysis.response_options].sort((a, b) => Number(b.option_kind === "no_mitigation") - Number(a.option_kind === "no_mitigation"));
  return <section className="panel investigation-card" aria-labelledby="options-heading"><h3 id="options-heading">Compare the options.</h3>
    {!options.some(option => option.option_kind === "no_mitigation") && <p>Do-nothing comparison unavailable for this analysis</p>}
    <div className="planner-options">{options.map(option => { const name = optionDisplayName(option); const baseline = option.option_kind === "no_mitigation"; const selected = matchesSelection && option.executable && selectedOption?.option_id === option.option_id; return <article aria-label={name} className={`option-card ${!option.executable ? "blocked" : ""} ${selected ? "selected" : ""}`} key={option.option_id}>
      <h4>{name}</h4>{option.option_id === recommendation?.option_id && <div className="recommendation-actions"><span className="badge accent">Recommended for review</span><button aria-label="Click here to understand why" className="recommendation-trigger" type="button" onClick={() => setOpenIdentity(identity)}>ⓘ <span>Click here to understand why</span></button></div>}
      <p>{baseline ? "Comparison only" : option.executable ? "Meets the planning requirements" : "Does not meet the planning requirements"}</p>
      {option.blocking_codes.length > 0 && <ul>{option.blocking_codes.map(code => <li key={code}>{blocker(code)}</li>)}</ul>}
      <PredictionSummary predicted={option.predicted} snapshot={snapshot} basis={baseline ? "baseline" : "response"} compact />
      <details><summary>Full option metrics, assumptions, and calculation details</summary><PredictionSummary predicted={option.predicted} snapshot={snapshot} basis={baseline ? "baseline" : "response"} />{option.assumptions.length > 0 && <><h5>Assumptions and unresolved questions</h5><ul>{option.assumptions.map((text, index) => <li key={index}>{text}</li>)}</ul></>}<p>Execution coordination comparison score: {option.execution_risk}. Each unconfirmed external commitment counts 2 points; each cross-plant movement and schedule change counts 1 point; each coordinated action after the first counts 1 point. Lower scores mean fewer or lower-weighted coordination factors. This score is not a probability of failure.</p><p>Source records: {option.source_data_lineage.join(", ") || "Unavailable"}</p></details>
      <button type="button" disabled={disabled || !option.executable} aria-label={selected ? `Selected: ${name}` : `Select ${name}`} aria-pressed={selected} onClick={() => onSelect(option)}>{selected ? "✓ Selected" : `Select ${name}`}</button>
      <div role="status" className="option-selection-status">{selected ? `Selected: ${name}. Selecting a response does not submit it for approval.` : ""}</div>
      {selected && onContinue && <button type="button" className="option-continue" disabled={disabled} onClick={onContinue}>Continue to review and approve</button>}
    </article>;})}</div>
    {!recommendation && <p>{analysis.ranking.no_feasible_mitigation && analysis.ranking.recommended_option_id === null
      ? "No option meets the planning requirements" : "Recommendation unavailable for this analysis"}</p>}
    <details className="trace"><summary>How the options were compared</summary>{analysis.ranking.stages.length === 0 ? <p>No options were eliminated by comparison stages.</p> : <ol>{analysis.ranking.stages.map((stage, index) => <li key={`${stage.comparator}-${index}`}>{stage.comparator.replaceAll("_", " ")}: threshold {rankingThreshold(stage)}; eliminated {stage.eliminated_option_ids.join(", ") || "none"}</li>)}</ol>}</details>
    {reportUrl && <a href={reportUrl} target="_blank" rel="noopener noreferrer">Explore response options in Power BI</a>}
    <footer className="saved-analysis-footer">Comparison from this analysis; selection is not approval or execution.</footer>
    {openIdentity === identity && recommendation && <RecommendationSheet onClose={() => setOpenIdentity(null)}><ExposurePanel analysis={analysis} snapshot={snapshot} runtime={runtime} reportContext={reportContext} /></RecommendationSheet>}
  </section>;
}
