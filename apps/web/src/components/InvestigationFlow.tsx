import {useRef, useState} from "react";
import type {KeyboardEvent, ReactNode} from "react";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {InvestigationEvidence} from "./InvestigationEvidence";
import {RequiredCitationWarning} from "./EvidenceSource";
import {OptionComparison} from "./OptionComparison";
import {DecisionPanel} from "./DecisionPanel";
import {IndependentApprovalPanel} from "../finance/IndependentApprovalPanel";
import {ExecutionPanel} from "./ExecutionPanel";
import {OutcomePanel} from "./OutcomePanel";
import {readPlannerSnapshot} from "./plannerSnapshot";
import {instant} from "./plannerFormatting";
export function InvestigationFlow({state, independentFinanceEnabled = true}: {state: CaseWorkspaceState; independentFinanceEnabled?: boolean}) {
  const {caseInstance, analysis} = state; if (!analysis) return null; if (!caseInstance) return <p className="warning">Case details aren't available for this analysis</p>;
  return <InvestigationPresentation key={caseInstance.case_id} state={state} independentFinanceEnabled={independentFinanceEnabled} />;
}

const stages = [
  {id: "understand", label: "1. Understand the disruption"},
  {id: "responses", label: "2. Investigate responses"},
  {id: "decision", label: "3. Choose a response"},
  {id: "approval", label: "4. Review and approve"},
  {id: "execution", label: "5. Execute mitigation plan"},
] as const;

function stageFromLocation(): number {
  const stage = new URLSearchParams(window.location.search).get("stage");
  const index = stages.findIndex(candidate => candidate.id === stage);
  return index >= 0 ? index : 0;
}

function StagePanel({index, activeStage, children}: {index: number; activeStage: number; children: ReactNode}) {
  const stage = stages[index]; const active = activeStage === index;
  return <section role="tabpanel" aria-labelledby={`investigation-tab-${stage.id}`}
    id={`investigation-panel-${stage.id}`} className="investigation-panel"
    hidden={!active} inert={!active} tabIndex={0}>
    <div className="investigation-cards">{children}</div>
  </section>;
}

function InvestigationPresentation({state, independentFinanceEnabled}: {state: CaseWorkspaceState; independentFinanceEnabled: boolean}) {
  const {caseInstance, analysis} = state;
  const [activeStage, setActiveStage] = useState(stageFromLocation);
  const [focusedStage, setFocusedStage] = useState(stageFromLocation);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  if (!analysis || !caseInstance) return null;
  const props = {caseInstance, analysis, runtime: state.runtime, tenantSharePointHost: state.runtime?.deployment_contract?.tenant_sharepoint_host}; const snapshot = readPlannerSnapshot(props);
  const reportContext = snapshot ? {
    caseId: analysis.case_id,
    analysisId: analysis.analysis_id,
    runtimeMode: analysis.runtime_mode,
  } : null;
  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number | null = null;
    if (event.key === "ArrowRight") next = (index + 1) % stages.length;
    if (event.key === "ArrowLeft") next = (index - 1 + stages.length) % stages.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = stages.length - 1;
    if (next === null) return;
    event.preventDefault();
    setFocusedStage(next);
    tabRefs.current[next]?.focus();
  }
  function continueToApproval() {
    setActiveStage(3);
    setFocusedStage(3);
    tabRefs.current[3]?.focus();
  }
  return <div id="assisted-review" className="investigation-flow"><div className="analysis-context">
    {analysis.runtime_mode === "fallback" && <p>Sample data — not a live retrieval</p>}<details><summary>Analysis source details</summary><p>Case {analysis.case_id}</p><p>Analysis {analysis.analysis_id}</p>
      <p>Scenario snapshot: {instant(analysis.scenario_effective_time)}</p><p>Analysis saved at {instant(analysis.created_at)}</p>
    </details>
  </div><RequiredCitationWarning analysis={analysis} tenantSharePointHost={props.tenantSharePointHost} />
    <div className="investigation-tabs" role="tablist" aria-label="Investigation stages">
      {stages.map((stage, index) => <button key={stage.id} type="button" role="tab"
        id={`investigation-tab-${stage.id}`} aria-controls={`investigation-panel-${stage.id}`}
        aria-selected={activeStage === index} tabIndex={focusedStage === index ? 0 : -1}
        ref={element => { tabRefs.current[index] = element; }}
        onFocus={() => setFocusedStage(index)} onKeyDown={event => moveFocus(event, index)}
        onClick={() => { setFocusedStage(index); setActiveStage(index); }}>
        {stage.label}
      </button>)}
    </div>
    <StagePanel index={0} activeStage={activeStage}><InvestigationEvidence {...props} row="disruption" /></StagePanel>
    <StagePanel index={1} activeStage={activeStage}><InvestigationEvidence {...props} row="responses" /></StagePanel>
    <StagePanel index={2} activeStage={activeStage}><OptionComparison disabled={state.operation !== null} analysis={analysis} selectedOption={state.selectedOption} onSelect={state.selectOption} onContinue={continueToApproval} snapshot={snapshot} runtime={state.runtime} reportContext={reportContext} /></StagePanel>
    <StagePanel index={3} activeStage={activeStage}>{caseInstance.workflow_version === "independent-finance-v1"
      ? <IndependentApprovalPanel caseId={caseInstance.case_id} displayedAnalysis={analysis} selectedOption={state.selectedOption} finalDecision={state.decision} onFinalDecision={state.acceptFinalDecision ?? (() => undefined)} independentFinanceEnabled={independentFinanceEnabled} />
      : <DecisionPanel state={state} onApprove={state.approve} onReject={state.reject} />}</StagePanel>
    <StagePanel index={4} activeStage={activeStage}>
      {!state.decision || state.decision.kind !== "approved" ? (
        <section className="panel" aria-labelledby="execution-waiting-heading">
          <h2 id="execution-waiting-heading">Execute mitigation plan</h2>
          <p>{state.decision?.kind === "rejected"
            ? "This response was rejected. Choose a response and obtain approval before starting a mitigation plan."
            : "Approve a response in Review and approve before starting its mitigation plan."}</p>
        </section>
      ) : <>
        <ExecutionPanel busy={state.operation !== null}
          canRetryPlanning={state.caseInstance?.controls.retry_action_planning}
          decision={state.decision} actions={state.actions} drafts={state.drafts}
          retrying={state.operation === "planning"} onRetry={state.retryPlanning} onRetryAction={state.retryAction} />
        <OutcomePanel disabled={state.operation !== null || !state.caseInstance?.controls.start_playback}
          decision={state.decision} actionCount={state.actions.length} playback={state.playback}
          observations={state.observations} starting={state.operation === "playback"} onStart={state.startPlayback} />
      </>}
    </StagePanel>
  </div>;
}
