import {CaseHeader} from "./components/CaseHeader";
import {ExecutionPanel} from "./components/ExecutionPanel";
import {InvestigationFlow} from "./components/InvestigationFlow";
import {OutcomePanel} from "./components/OutcomePanel";
import {PlanningRoutes} from "./components/PlanningRoutes";
import {ExistingCases} from "./components/ExistingCases";
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
    {workspace.operation === "reopening" && <p role="status" aria-live="polite">Reopening saved case…</p>}
    {workspace.error && <p className="error" role="alert">{workspace.error}</p>}
    <CaseHeader
      runtime={workspace.runtime}
      caseInstance={workspace.caseInstance}
      analysis={workspace.analysis}
      createPurpose={createPurpose}
      creating={workspace.operation !== null}
      analyzing={workspace.operation !== null}
      onCreate={workspace.create}
      onAnalyze={workspace.analyze}
    />
    <ExistingCases cases={workspace.existingCases} error={workspace.existingCasesError}
      busy={workspace.operation !== null}
      loading={workspace.operation === "listing"} reopening={workspace.operation === "reopening"}
      onLoad={workspace.loadExistingCases} onReopen={workspace.reopen} />
    {workspace.caseInstance && <p className="reopen-note">This workspace reads saved results and does not refresh evidence or change retrieval times.</p>}
    <PlanningRoutes
      runtime={workspace.runtime}
      caseInstance={workspace.caseInstance}
      analysis={workspace.analysis}
    />
    <InvestigationFlow state={workspace} />
    <ExecutionPanel
      busy={workspace.operation !== null}
      canRetryPlanning={workspace.caseInstance?.controls.retry_action_planning}
      decision={workspace.decision}
      actions={workspace.actions}
      drafts={workspace.drafts}
      retrying={workspace.operation === "planning"}
      onRetry={workspace.retryPlanning}
      onRetryAction={workspace.retryAction}
    />
    <OutcomePanel
      disabled={workspace.operation !== null || !workspace.caseInstance?.controls.start_playback}
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
