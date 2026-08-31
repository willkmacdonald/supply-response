import {CaseHeader} from "./components/CaseHeader";
import {DecisionPanel} from "./components/DecisionPanel";
import {EvidencePanel} from "./components/EvidencePanel";
import {ExecutionPanel} from "./components/ExecutionPanel";
import {ExposurePanel} from "./components/ExposurePanel";
import {OptionComparison} from "./components/OptionComparison";
import {OutcomePanel} from "./components/OutcomePanel";
import {useCaseWorkspace} from "./hooks/useCaseWorkspace";
import "./styles.css";

export default function App() {
  const workspace = useCaseWorkspace();
  return <main className="case-workspace">
    {workspace.operation === "initializing" && <p role="status">Initializing Case workspace…</p>}
    {workspace.error && <p className="error" role="alert">{workspace.error}</p>}
    <CaseHeader
      runtime={workspace.runtime}
      caseInstance={workspace.caseInstance}
      analyzing={workspace.operation === "analyzing"}
      onAnalyze={workspace.analyze}
    />
    <EvidencePanel analysis={workspace.analysis} />
    <ExposurePanel analysis={workspace.analysis} />
    <OptionComparison
      analysis={workspace.analysis}
      selectedOption={workspace.selectedOption}
      onSelect={workspace.selectOption}
    />
    <DecisionPanel state={workspace} onApprove={workspace.approve} onReject={workspace.reject} />
    <ExecutionPanel
      decision={workspace.decision}
      actions={workspace.actions}
      drafts={workspace.drafts}
      retrying={workspace.operation === "planning"}
      onRetry={workspace.retryPlanning}
    />
    <OutcomePanel
      decision={workspace.decision}
      actionCount={workspace.actions.length}
      playback={workspace.playback}
      observations={workspace.observations}
      starting={workspace.operation === "playback"}
      onStart={workspace.startPlayback}
    />
  </main>;
}
