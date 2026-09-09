import type {ReactNode} from "react";
import type {CaseWorkspaceState} from "../hooks/useCaseWorkspace";
import {InvestigationEvidence} from "./InvestigationEvidence";
import {RequiredCitationWarning} from "./EvidenceSource";
import {ExposurePanel} from "./ExposurePanel";
import {OptionComparison} from "./OptionComparison";
import {DecisionPanel} from "./DecisionPanel";
import {readPlannerSnapshot} from "./plannerSnapshot";
import {instant} from "./plannerFormatting";
function Row({id, label, children}: {id: string; label: string; children: ReactNode}) { return <section className="investigation-row" aria-labelledby={id}><h2 id={id}>{label}</h2><div className="investigation-cards">{children}</div></section>; }
export function InvestigationFlow({state}: {state: CaseWorkspaceState}) {
  const {caseInstance, analysis} = state; if (!analysis) return null; if (!caseInstance) return <p className="warning">Case context unavailable for this saved analysis</p>;
  const props = {caseInstance, analysis, runtime: state.runtime, tenantSharePointHost: state.runtime?.deployment_contract?.tenant_sharepoint_host}; const snapshot = readPlannerSnapshot(props);
  const reportContext = snapshot ? {
    caseId: analysis.case_id,
    analysisId: analysis.analysis_id,
    runtimeMode: analysis.runtime_mode,
  } : null;
  return <div className="investigation-flow"><div className="analysis-context">
    <p>{analysis.material.corpus === "demo_corpus" ? "Demo corpus — fictional" : "Fictional provenance not established for this analysis"}</p>
    <p>Snapshot used for this analysis · In this scenario, as of {instant(analysis.scenario_effective_time)}</p><p>Analysis saved at {instant(analysis.created_at)}. Saved records do not indicate ongoing monitoring.</p>
    {analysis.runtime_mode === "fallback" && <p>Demo fixture — not a live retrieval</p>}<details><summary>Analysis source details</summary><p>Case {analysis.case_id}</p><p>Analysis {analysis.analysis_id}</p></details>
  </div><RequiredCitationWarning analysis={analysis} tenantSharePointHost={props.tenantSharePointHost} />
    <Row id="understand-row" label="1. Understand the disruption"><InvestigationEvidence {...props} row="disruption" /></Row>
    <Row id="responses-row" label="2. Investigate responses"><InvestigationEvidence {...props} row="responses" /></Row>
    <Row id="decision-row" label="3. Make the decision"><OptionComparison analysis={analysis} selectedOption={state.selectedOption} onSelect={state.selectOption} snapshot={snapshot} runtime={state.runtime} reportContext={reportContext} /><ExposurePanel analysis={analysis} snapshot={snapshot} runtime={state.runtime} reportContext={reportContext} /><DecisionPanel state={state} onApprove={state.approve} onReject={state.reject} /></Row>
  </div>;
}
