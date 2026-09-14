import {CaseHeader} from "./components/CaseHeader";
import {InvestigationFlow} from "./components/InvestigationFlow";
import {PlanningRoutes} from "./components/PlanningRoutes";
import {ExistingCases} from "./components/ExistingCases";
import {useAuth} from "./auth/AuthProvider";
import {useCaseWorkspace} from "./hooks/useCaseWorkspace";
import {useEffect, useState} from "react";
import {api, safeErrorMessage} from "./api";
import type {SessionInfo} from "./types";
import {FinanceWorkspace} from "./finance/FinanceWorkspace";
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
      creating={workspace.operation === "creating"}
      analyzing={workspace.operation === "analyzing"}
      busy={workspace.operation !== null}
      onCreate={workspace.create}
      onAnalyze={workspace.analyze}
    />
    <ExistingCases cases={workspace.existingCases} error={workspace.existingCasesError}
      busy={workspace.operation !== null}
      loading={workspace.operation === "listing"} reopening={workspace.operation === "reopening"}
      onLoad={workspace.loadExistingCases} onReopen={workspace.reopen} />
    {workspace.caseInstance && <p className="reopen-note">This workspace reads saved results and does not refresh evidence or change retrieval times.</p>}
    {workspace.analysis && workspace.caseInstance?.current_decision_id && !workspace.decision &&
      <p className="reopen-note">The previous decision applies to an earlier analysis. Its approval and actions do not apply to the analysis shown here.</p>}
    <PlanningRoutes
      runtime={workspace.runtime}
      caseInstance={workspace.caseInstance}
      analysis={workspace.analysis}
    />
    <InvestigationFlow state={workspace} />
  </main>;
}

export default function App() {
  const auth = useAuth();
  if (auth.mode === "entra" && auth.account === null) {
    return <main className="case-workspace">
      <h1>Supply Response</h1>
      <p>Sign in with your Microsoft account to open your authorized workspace.</p>
      <button type="button" onClick={() => void auth.signIn()}>Sign in</button>
    </main>;
  }
  if (auth.mode === "fallback") return <CaseWorkspace />;
  return <VerifiedWorkspace key={auth.account!.homeAccountId} />;
}

function VerifiedWorkspace() {
  const auth = useAuth(); const [session, setSession] = useState<SessionInfo | null>(null); const [error, setError] = useState<string | null>(null);
  useEffect(() => {let active = true; setSession(null); setError(null); void api.me().then(value => {if (active) setSession(value);}).catch(caught => {if (active) setError(`Your signed-in role could not be verified. ${safeErrorMessage(caught)} Switch account or sign in again.`);}); return () => {active = false;};}, [auth.account?.homeAccountId]);
  if (error) return <main className="case-workspace"><h1>Supply Response</h1><p role="alert" className="error">{error}</p><button onClick={() => void auth.switchAccount()}>Switch Microsoft account</button></main>;
  if (!session) return <main className="case-workspace"><p role="status">Verifying your Supply Response access…</p></main>;
  if (session.persona_id === "RL-PERSONA-TAYLOR") return <FinanceWorkspace displayName={session.display_name} onSwitchAccount={auth.switchAccount} />;
  if (session.persona_id === "RL-PERSONA-ALEX") return <><div className="account-strip"><span>Signed in as {session.display_name ?? "Alex"}</span><button onClick={() => void auth.switchAccount()}>Switch Microsoft account</button></div><CaseWorkspace /></>;
  return <main className="case-workspace"><h1>Supply Response</h1><p role="alert">This account is not authorized for a Supply Response workspace.</p><button onClick={() => void auth.switchAccount()}>Switch Microsoft account</button></main>;
}
