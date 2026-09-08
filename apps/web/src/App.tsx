import {CaseHeader} from "./components/CaseHeader";
import {DecisionPanel} from "./components/DecisionPanel";
import {EvidencePanel} from "./components/EvidencePanel";
import {ExecutionPanel} from "./components/ExecutionPanel";
import {ExposurePanel} from "./components/ExposurePanel";
import {OptionComparison} from "./components/OptionComparison";
import {OutcomePanel} from "./components/OutcomePanel";
import {useAuth} from "./auth/AuthProvider";
import {useCaseWorkspace} from "./hooks/useCaseWorkspace";
import "./styles.css";

function CaseWorkspace() {
  const workspace = useCaseWorkspace();
  const createPurpose = new URLSearchParams(window.location.search).get("purpose") === "automated_test"
    ? "automated_test"
    : "showcase";
  return <main className="case-workspace">
    {(workspace.operation === "initializing" || workspace.operation === "creating") && (
      <p role="status" aria-live="polite">
        {workspace.operation === "creating" ? "Creating Case workspace…" : "Initializing Case workspace…"}
      </p>
    )}
    {workspace.operation === "analyzing" && (
      <p role="status" aria-live="polite">Analysis in progress. Source retrieval and evidence checks will be shown when the analysis completes.</p>
    )}
    {workspace.error && <p className="error" role="alert">{workspace.error}</p>}
    <CaseHeader
      runtime={workspace.runtime}
      caseInstance={workspace.caseInstance}
      createPurpose={createPurpose}
      creating={workspace.operation === "creating"}
      analyzing={workspace.operation === "analyzing"}
      onCreate={workspace.create}
      onAnalyze={workspace.analyze}
    />
    <EvidencePanel analysis={workspace.analysis} tenantSharePointHost={workspace.runtime?.deployment_contract?.tenant_sharepoint_host} />
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
      onRetryAction={workspace.retryAction}
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

export default function App() {
  const auth = useAuth();
  if (auth.mode === "entra" && auth.account === null) {
    return <main className="case-workspace">
      <h1>Supply Response</h1>
      <p>Sign in with the Alex demo account to open the live Case workspace.</p>
      <button type="button" onClick={() => void auth.signIn()}>Sign in as Alex</button>
    </main>;
  }
  return <CaseWorkspace />;
}
