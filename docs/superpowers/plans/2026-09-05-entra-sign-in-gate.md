# Entra Sign-In Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a fresh live browser session explicitly sign in as Alex before the application initializes any protected Case workspace API calls.

**Architecture:** Keep `AuthProvider` as the sole owner of MSAL and token acquisition. Split the current workspace body into an authenticated child component, and have the exported `App` consult `useAuth()` first so the protected `useCaseWorkspace()` hook is never mounted while Entra mode has no active account. Fallback mode continues directly to the existing workspace.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, MSAL Browser, Vite, FastAPI, Azure Container Apps

## Global Constraints

- In fallback mode, render the Case workspace exactly as it does today.
- In Entra mode with no active account, render `Sign in as Alex` and do not initialize or call protected Case APIs.
- Use the existing `AuthProvider.signIn()` redirect flow and existing API scope.
- Do not automatically redirect, inject tokens, introduce test-only authentication shortcuts, or alter tenant, role, API authorization, or domain-workflow behavior.
- Keep the authentication decision outside the component that invokes `useCaseWorkspace()`.

---

### Task 1: Gate the Case workspace on an active Entra account

**Files:**
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/App.tsx`

**Interfaces:**
- Consumes: `useAuth(): { mode: "fallback" | "entra"; account: AuthAccount | null; signIn(): Promise<void>; getAccessToken(): Promise<string | null> }` from `apps/web/src/auth/AuthProvider.tsx`.
- Produces: exported `App()` that renders an unauthenticated Entra gate or the existing `CaseWorkspace()` UI; `CaseWorkspace()` remains internal and is the only component that calls `useCaseWorkspace()`.

- [x] **Step 1: Write the failing unauthenticated-Entra tests**

Add an Entra test configuration and a no-account `AuthClient` to `apps/web/src/App.test.tsx`, then render the real provider around `App`:

```tsx
import {AuthProvider, type AuthClient} from "./auth/AuthProvider";

const entraConfig = {
  tenantId: "11111111-1111-4111-8111-111111111111",
  webClientId: "22222222-2222-4222-8222-222222222222",
  apiScope: "api://33333333-3333-4333-8333-333333333333/access_as_user",
  redirectUri: "http://localhost:5173/auth/callback",
};

function unauthenticatedClient(): AuthClient {
  return {
    initialize: vi.fn().mockResolvedValue(undefined),
    handleRedirectPromise: vi.fn().mockResolvedValue(null),
    getAllAccounts: vi.fn().mockReturnValue([]),
    getActiveAccount: vi.fn().mockReturnValue(null),
    setActiveAccount: vi.fn(),
    loginRedirect: vi.fn().mockResolvedValue(undefined),
    acquireTokenSilent: vi.fn(),
    acquireTokenRedirect: vi.fn(),
  };
}
```

Add one test that asserts the gate appears after provider initialization, `fetch` has not been called, and clicking the action calls the existing redirect interface with only the configured API scope:

```tsx
it("gates protected Case APIs until Alex signs in", async () => {
  const client = unauthenticatedClient();
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(<AuthProvider config={entraConfig} client={client}><App /></AuthProvider>);

  const signIn = await screen.findByRole("button", {name: "Sign in as Alex"});
  expect(fetchMock).not.toHaveBeenCalled();
  await userEvent.click(signIn);
  expect(client.loginRedirect).toHaveBeenCalledWith({scopes: [entraConfig.apiScope]});
  expect(fetchMock).not.toHaveBeenCalled();
});
```

Add a second test using a client whose `getAllAccounts()` returns Alex. Stub the existing Case lifecycle, assert the workspace renders, the sign-in action is absent, and `/api/runtime` is requested:

```tsx
it("renders the Case workspace after Entra resolves Alex", async () => {
  const client = authenticatedClient();
  const fetchMock = mockFallbackCaseLifecycle();

  render(<AuthProvider config={entraConfig} client={client}><App /></AuthProvider>);

  expect(await screen.findByText("Fallback mode")).toBeVisible();
  expect(screen.queryByRole("button", {name: "Sign in as Alex"})).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/runtime", undefined);
});
```

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
npm --prefix apps/web test -- --run App.test.tsx -t "gates protected Case APIs until Alex signs in"
```

Expected: FAIL because the current `App` mounts `useCaseWorkspace()` and invokes `/api/runtime` instead of rendering `Sign in as Alex`.

- [x] **Step 3: Implement the minimal authentication gate**

Import `useAuth`, move the current workspace body unchanged into `CaseWorkspace`, and gate it from `App`:

```tsx
import {useAuth} from "./auth/AuthProvider";

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
```

- [x] **Step 4: Run the focused test to verify it passes**

Run:

```bash
npm --prefix apps/web test -- --run App.test.tsx -t "gates protected Case APIs until Alex signs in"
```

Expected: PASS, with no `fetch` call before or after invoking the redirect client.

- [x] **Step 5: Run the complete web unit suite and production build**

Run:

```bash
npm --prefix apps/web test
npm --prefix apps/web run build
```

Expected: all Vitest tests pass; TypeScript and Vite production build complete successfully; existing fallback tests remain green.

- [ ] **Step 6: Commit the independently deployable change**

```bash
git add apps/web/src/App.tsx apps/web/src/App.test.tsx docs/superpowers/plans/2026-09-05-entra-sign-in-gate.md
git commit -m "fix(web): gate live workspace on Entra sign-in"
```

Expected: one commit containing the approved plan, failing-first regression coverage, and minimal implementation.

### Task 2: Redeploy and validate the live Alex entry point

**Files:**
- No repository files are modified by this validation task.

**Interfaces:**
- Consumes: committed production web bundle from Task 1; existing `supply-response-personal` azd environment; existing Container App `ca-sr-demo` in `rg-supply-response-demo`.
- Produces: a ready immutable Container App revision whose fresh browser entry point shows the Alex sign-in gate and whose health contract still reports live Fabric SQL schema version 12, Power BI available, and pinned Foundry readiness.

- [ ] **Step 1: Run the read-only deployment preflight**

Select the existing environment and export its nonsecret values exactly as recorded by azd and `docs/local/supply-response-personal-environment.md`, then run:

```bash
azd env select supply-response-personal
./scripts/deploy_personal_tenant.sh
```

Expected: preflight confirms subscription, tenant `9492545f-58bd-4fe2-974e-7124c38e4c2b`, East US 2, resource group `rg-supply-response-demo`, Container App `ca-sr-demo`, Entra registrations, and deployment identity without changing Azure.

- [ ] **Step 2: Apply the approved immutable deployment**

With the same validated environment and exact confirmation variables set, run:

```bash
./scripts/deploy_personal_tenant.sh --apply
```

Expected: ACR build succeeds, an immutable digest is deployed, the latest revision becomes ready, and the prior healthy revision remains available until replacement succeeds.

- [ ] **Step 3: Run the user-context-free live readiness gate**

```bash
./scripts/deploy_personal_tenant.sh --smoke
```

Expected: `Live Fabric and Foundry readiness gate passed; no delegated user operation was invoked.`

- [ ] **Step 4: Verify the fresh-browser sign-in boundary**

Open `https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io` in a fresh in-app browser session.

Expected: the page shows `Sign in as Alex`; it does not show `Unable to initialize the Case workspace`, and no protected Case request occurs before the button is selected.

- [ ] **Step 5: Complete the approved Alex-authenticated live journey**

Select `Sign in as Alex`, authenticate as `agent@willmacdonald.com` if Microsoft requests interaction, and complete the existing live journey: create the showcase Case, analyze the disruption, inspect Work IQ citations, approve the recommended option, verify execution actions use the decision ledger entry, start simulated execution, and inspect outcomes plus the Power BI report.

Expected: the deployed journey uses live Work IQ, Fabric SQL, pinned Foundry agents, and Power BI; every displayed source and downstream action traces to the same current Case, analysis, and decision identifiers.
