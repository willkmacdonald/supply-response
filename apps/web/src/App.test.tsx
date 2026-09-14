// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {act, cleanup, render, renderHook, screen, waitFor, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {StrictMode} from "react";
import {afterEach, describe, expect, it, vi} from "vitest";
import App from "./App";
import {useCaseWorkspace} from "./hooks/useCaseWorkspace";
import {AuthProvider, type AuthClient} from "./auth/AuthProvider";

const scenarioTime = "2026-09-01T09:00:00-05:00";

it("keeps email discovery available beside an open analysis without replacing it on search", async () => {
  window.history.replaceState({}, "", "/?caseId=RL-CASE-1");
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), "http://localhost").pathname;
    if (path === "/api/runtime") return response({...runtime, runtime_mode: "live"});
    if (path === "/api/cases/RL-CASE-1") return response({...caseInstance, current_analysis_id: analysis.analysis_id});
    if (path === "/api/cases/RL-CASE-1/analysis") return response(analysis);
    if (path === "/api/inbox/check") return response({checked_at: scenarioTime, incomplete: false, messages: []});
    if (path === "/api/cases") return response([]);
    throw new Error(`Unexpected request: ${path}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  await screen.findByRole("tab", {name: "1. Understand the disruption"});
  await userEvent.click(screen.getByRole("button", {name: "Check email for disruptions"}));
  expect(await screen.findByText("No matching supplier emails found.")).toBeVisible();
  expect(screen.getByRole("tab", {name: "1. Understand the disruption"})).toBeVisible();
  expect(window.location.search).toContain("caseId=RL-CASE-1");
});

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
    acquireTokenSilent: vi.fn().mockResolvedValue({accessToken: "test-api-token"}),
    acquireTokenRedirect: vi.fn(),
  };
}

function authenticatedClient(): AuthClient {
  const client = unauthenticatedClient();
  client.getAllAccounts = vi.fn().mockReturnValue([{homeAccountId: "alex", name: "Alex Morgan"}]);
  return client;
}

async function selectDecisionStage() {
  await userEvent.click(await screen.findByRole("tab", {name: "3. Choose a response"}));
}
async function openOtherSavedCases() {
  const summary = screen.getByText("Other saved cases");
  if (!summary.closest("details")?.open) await userEvent.click(summary);
}
async function selectApprovalStage() {
  await userEvent.click(await screen.findByRole("tab", {name: "4. Review and approve"}));
}
async function selectExecutionStage() {
  await userEvent.click(await screen.findByRole("tab", {name: "5. Execute mitigation plan"}));
}

const runtime = {
  runtime_mode: "fallback",
  work_iq: "synthetic",
  operational_store: "sqlite",
  agent_runtime: "local",
  power_bi_available: false,
};

const caseInstance = {
  case_id: "RL-CASE-1",
  template_id: "RL-001",
  purpose: "showcase",
  runtime_mode: "fallback",
  scenario_effective_time: scenarioTime,
  scenario_timezone: "America/Chicago",
  status: "open",
  current_analysis_id: null,
  current_decision_id: null,
  display_status: null,
  recorded_at: "2026-08-31T14:00:00Z",
  projection_updated_at: "2026-08-31T14:00:00Z",
  controls: {
    new_analysis: true,
    decide: false,
    retry_action_planning: false,
    start_playback: false,
  },
};

const evidenceValidation = {
  policy_version: "evidence-policy-v3",
  blocking_codes: [],
  global_blocking_codes: [],
  item_results: [
    {
      evidence_id: "RL-EVIDENCE-ALPHA",
      requirement: "required_authoritative",
      validated_authority_scope: ["operational_quantity", "operational_date"],
      freshness: "current",
      business_validity: "valid",
      uncertainty_state: "certain",
      retrieval_health: "healthy",
      authoritative: true,
      blocking_codes: [],
    },
  ],
};

const combinedOption = {
  option_id: "RL-OPTION-COMBINED",
  option_kind: "combined",
  name: "Combine expedite, transfer, and resequencing",
  executable: true,
  active_mitigation: true,
  predicted: {
    uncovered_part_demand: 2300,
    otif_loss_percentage: 50,
    revenue_at_risk: "375000.00",
    margin_at_risk: "125000.00",
    response_cost: "24750.00",
    protected_customer_order_ids: ["RL-CO-DEMO-2"],
  },
  assumptions: ["Remaining supplier recovery date is unconfirmed."],
  evidence_ids: ["RL-EVIDENCE-ALPHA"],
  evidence_requirements: [
    {evidence_id: "RL-EVIDENCE-ALPHA", authority_scope: ["operational_date"]},
  ],
  blocking_codes: [],
  prerequisite_roles: ["material_planner", "finance_approver"],
  source_data_lineage: ["RL-EVIDENCE-ALPHA", "RL-TRANSFER-DAL-CHI-1500"],
  approval_burden: 2,
  execution_risk: 6,
  requested_side_effects: [],
};

const betaOption = {
  option_id: "RL-OPTION-BETA",
  option_kind: "alternate_source",
  name: "Source from Supplier Beta",
  executable: false,
  active_mitigation: true,
  predicted: null,
  assumptions: [],
  evidence_ids: ["RL-QUALITY-001"],
  evidence_requirements: [
    {evidence_id: "RL-QUALITY-001", authority_scope: ["qualification_state"]},
  ],
  blocking_codes: ["QUALITY_QUALIFICATION_PENDING"],
  prerequisite_roles: ["material_planner", "quality_approver"],
  source_data_lineage: ["RL-QUALITY-001"],
  approval_burden: 2,
  execution_risk: 2,
  requested_side_effects: [],
};

const analysis = {
  analysis_id: "RL-ANALYSIS-1",
  case_id: "RL-CASE-1",
  runtime_mode: "fallback",
  scenario_effective_time: scenarioTime,
  analysis_started_at: "2026-08-31T14:01:00Z",
  retrieval_window_ends_at: "2026-08-31T14:01:01Z",
  created_at: "2026-08-31T14:01:01Z",
  material_hash: "a".repeat(64),
  material: {
    case_id: "RL-CASE-1",
    template_id: "RL-001",
    case_purpose: "showcase",
    runtime_mode: "fallback",
    corpus: "demo_corpus",
    scenario_effective_time: scenarioTime,
    operational_snapshot_json: '{"case_id":"RL-CASE-1","part_id":"RL-MAT-10247"}',
    required_authority_scope: ["operational_quantity", "operational_date"],
    evidence: [],
    conflicts: [],
    conflict_resolutions: [],
    evidence_validation: evidenceValidation,
    response_options: [combinedOption, betaOption].map(({name: _name, ...option}) => option),
    standing_authorizations: [],
    approval_satisfactions: [],
    ranking: {
      policy_version: "thresholded-lexicographic-v1",
      eligible_option_ids: ["RL-OPTION-COMBINED"],
      infeasible_option_ids: ["RL-OPTION-BETA"],
      excluded_baseline_ids: ["RL-OPTION-NO-MITIGATION"],
      stages: [
        {
          comparator: "uncovered_part_demand",
          threshold: "500",
          lower_is_better: true,
          input_option_ids: ["RL-OPTION-COMBINED", "RL-OPTION-EXPEDITE"],
          values: [
            {option_id: "RL-OPTION-COMBINED", value: "2300"},
            {option_id: "RL-OPTION-EXPEDITE", value: "3800"},
          ],
          retained_option_ids: ["RL-OPTION-COMBINED"],
          eliminated_option_ids: ["RL-OPTION-EXPEDITE"],
        },
      ],
      recommended_option_id: "RL-OPTION-COMBINED",
      no_feasible_mitigation: false,
    },
    calculation_version: "rl001-options-v1",
    evidence_policy_version: "evidence-policy-v3",
    approval_policy_version: "standing-authorization-v1",
  },
  evidence_items: [
    {
      evidence_id: "RL-EVIDENCE-ALPHA",
      case_id: "RL-CASE-1",
      kind: "operational_fact",
      authority_scope: ["operational_quantity", "operational_date"],
      source_system: "synthetic_fixture",
      source_id: "RL-SOURCE-ALPHA",
      source_timestamp: "2026-08-31T14:00:00Z",
      retrieved_at: "2026-08-31T14:01:00Z",
      retrieved_for_analysis_id: "RL-ANALYSIS-1",
      retrieval_health: "healthy",
      effective_at: scenarioTime,
      expires_at: "2026-09-02T09:00:00-05:00",
      claim: "Alpha partial shipment quantity and date are confirmed.",
      excerpt: "3,000 units are available for expedited delivery.",
      citation_url: "https://rl.example/evidence/RL-EVIDENCE-ALPHA",
      runtime_mode: "fallback",
      synthetic: true,
      requirement: "required_authoritative",
      uncertainty_state: "certain",
    },
  ],
  evidence_validation: evidenceValidation,
  response_options: [combinedOption, betaOption],
  approval_satisfactions: [],
  ranking: {
    policy_version: "thresholded-lexicographic-v1",
    eligible_option_ids: ["RL-OPTION-COMBINED"],
    infeasible_option_ids: ["RL-OPTION-BETA"],
    excluded_baseline_ids: ["RL-OPTION-NO-MITIGATION"],
    stages: [
      {
        comparator: "uncovered_part_demand",
        threshold: "500",
        lower_is_better: true,
        input_option_ids: ["RL-OPTION-COMBINED", "RL-OPTION-EXPEDITE"],
        values: [
          {option_id: "RL-OPTION-COMBINED", value: "2300"},
          {option_id: "RL-OPTION-EXPEDITE", value: "3800"},
        ],
        retained_option_ids: ["RL-OPTION-COMBINED"],
        eliminated_option_ids: ["RL-OPTION-EXPEDITE"],
      },
    ],
    recommended_option_id: "RL-OPTION-COMBINED",
    no_feasible_mitigation: false,
  },
  recommendation: combinedOption,
};

const decision = {
  decision_id: "RL-DECISION-1",
  case_id: "RL-CASE-1",
  analysis_id: "RL-ANALYSIS-1",
  analysis_material_hash: "a".repeat(64),
  kind: "approved",
  selected_option_id: "RL-OPTION-COMBINED",
  rejection_reason: null,
  evidence_ids: ["RL-EVIDENCE-ALPHA"],
  assumptions: ["Remaining supplier recovery date is unconfirmed."],
  constraints: [],
  prerequisite_roles: ["material_planner", "finance_approver"],
  approval_satisfactions: [],
  calculation_version: "rl001-options-v1",
  evidence_policy_version: "evidence-policy-v3",
  approval_policy_version: "standing-authorization-v1",
  ranking_policy_version: "thresholded-lexicographic-v1",
  runtime_mode: "fallback",
  scenario_effective_time: scenarioTime,
  decided_at: "2026-08-31T14:02:00Z",
  projection_updated_at: "2026-08-31T14:02:00Z",
  action_planning_status: "complete",
  new_analysis_available: false,
};

const pendingDecision = {...decision, action_planning_status: "pending"};

const actions = [
  "prepare_alpha_recovery_draft",
  "coordinate_alpha_expedited_partial",
  "transfer_dallas_to_chicago",
  "resequence_priority_production",
  "update_disruption_status",
].map((kind, index) => ({
  action_id: `RL-ACTION-${index + 1}`,
  case_id: "RL-CASE-1",
  decision_id: "RL-DECISION-1",
  kind,
  owner_kind: "persona",
  owner_persona_id: "RL-PERSONA-ALEX",
  status: "planned",
  created_at: "2026-08-31T14:02:00Z",
  draft_artifact_id: index === 0 ? "RL-DRAFT-1" : null,
  runtime_mode: "fallback",
  scenario_effective_time: scenarioTime,
  projection_updated_at: "2026-08-31T14:02:01Z",
}));

const drafts = [
  {
    artifact_id: "RL-DRAFT-1",
    action_id: "RL-ACTION-1",
    decision_id: "RL-DECISION-1",
    artifact_kind: "supplier_recovery_request",
    created_at: "2026-08-31T14:02:00Z",
    subject: null,
    body: null,
    sent: false,
    runtime_mode: "fallback",
    scenario_effective_time: scenarioTime,
  },
];

const playback = {
  playback_id: "RL-PLAYBACK-1",
  case_id: "RL-CASE-1",
  decision_id: "RL-DECISION-1",
  status: "completed",
  started_at: "2026-08-31T14:03:00Z",
  completed_at: "2026-08-31T14:03:50Z",
  runtime_mode: "fallback",
  scenario_effective_time: scenarioTime,
};

const inProgressPlayback = {...playback, status: "in_progress", completed_at: null};

const observations = Array.from({length: 10}, (_, index) => ({
  observation_id: `RL-OBSERVATION-${index + 1}`,
  case_id: "RL-CASE-1",
  decision_id: "RL-DECISION-1",
  playback_id: "RL-PLAYBACK-1",
  action_id: `RL-ACTION-${Math.min(index + 1, 5)}`,
  metric: `simulated_metric_${index + 1}`,
  observed_value: String(index + 1),
  unit: "units",
  predicted_value: String(index + 1),
  scenario_effective_time: scenarioTime,
  scenario_timezone: "America/Chicago",
  recorded_at: "2026-08-31T14:03:50Z",
  source_reference: `RL-001 simulated playback:metric_${index + 1}`,
  kind: "simulated",
  synthetic: true,
  display_label: "Simulated",
  runtime_mode: "fallback",
}));

function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status,
    headers: {"Content-Type": "application/json"},
  }));
}

function mockFallbackCaseLifecycle(overrides: {
  analysis?: unknown | Promise<Response>;
  decision?: unknown;
  retryDecision?: unknown;
  actions?: unknown;
  runtimeFailure?: boolean;
  runtimeError?: Error;
} = {}) {
  let decisionPolls = 0;
  let playbackPolls = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const path = new URL(url, "http://localhost").pathname;
    const method = init?.method ?? "GET";
    if (path === "/api/runtime" && method === "GET") {
      if (overrides.runtimeError) throw overrides.runtimeError;
      return overrides.runtimeFailure
        ? response({detail: {code: "UNKNOWN_FAILURE", exception: "DatabaseError: password=secret"}}, 503)
        : response(runtime);
    }
    if (path === "/api/me" && method === "GET") return response({mode: "entra", persona_id: "RL-PERSONA-ALEX", display_name: "Alex", independent_finance_enabled: true});
    if (path === "/api/cases" && method === "POST") return response(caseInstance, 201);
    if (path === "/api/cases/RL-CASE-1/analysis" && method === "POST") {
      if (overrides.analysis instanceof Promise) return overrides.analysis;
      return response(overrides.analysis ?? analysis, 201);
    }
    if (path === "/api/cases/RL-CASE-1/decisions" && method === "POST") {
      return response(overrides.decision ?? pendingDecision, 201);
    }
    if (path === "/api/decisions/RL-DECISION-1" && method === "GET") {
      decisionPolls += 1;
      return response(decisionPolls === 1 ? pendingDecision : decision);
    }
    if (path === "/api/decisions/RL-DECISION-1/actions/retry" && method === "POST") {
      return response(overrides.retryDecision ?? decision);
    }
    if (path === "/api/decisions/RL-DECISION-1/actions" && method === "GET") {
      return response(overrides.actions ?? actions);
    }
    if (path === "/api/decisions/RL-DECISION-1/actions/RL-ACTION-1/retry" && method === "POST") {
      return response({...actions[0], status: "in_progress"});
    }
    if (path === "/api/decisions/RL-DECISION-1/drafts" && method === "GET") return response(drafts);
    if (path === "/api/decisions/RL-DECISION-1/playback" && method === "POST") return response(inProgressPlayback, 201);
    if (path === "/api/decisions/RL-DECISION-1/playback" && method === "GET") {
      playbackPolls += 1;
      return response(playbackPolls === 1 ? inProgressPlayback : playback);
    }
    if (path === "/api/decisions/RL-DECISION-1/observations" && method === "GET") return response(observations);
    throw new Error(`Unexpected API request: ${method} ${path}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
});

function savedReads(overrides: Record<string, unknown> = {}) {
  const savedCase = {...caseInstance, current_analysis_id: analysis.analysis_id};
  const bodies: Record<string, unknown> = {
    "/api/runtime": runtime, "/api/cases": [savedCase],
    "/api/cases/RL-CASE-1": savedCase, "/api/cases/RL-CASE-1/analysis": analysis,
    "/api/decisions/RL-DECISION-1": decision,
    "/api/decisions/RL-DECISION-1/actions": actions,
    "/api/decisions/RL-DECISION-1/drafts": drafts,
    "/api/decisions/RL-DECISION-1/playback": playback,
    "/api/decisions/RL-DECISION-1/observations": observations,
    ...overrides,
  };
  const mock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const body = bodies[String(input)];
    if (init?.method === "POST") throw new Error("Unexpected mutation");
    if (body instanceof Promise) return body.then(value => value.clone());
    if (body instanceof Response) return Promise.resolve(body.clone());
    return response(body ?? {detail: {code: "CASE_NOT_FOUND"}}, body === undefined ? 404 : 200);
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("reopening lifecycle and operation safety", () => {
  it.each(["approved", "rejected"])("reopens a newer analysis without attaching its retained earlier %s decision", async kind => {
    const savedCase = {...caseInstance, status: "awaiting_decision", current_analysis_id: analysis.analysis_id,
      current_decision_id: decision.decision_id, controls: {...caseInstance.controls, decide: true}};
    const mock = savedReads({"/api/cases/RL-CASE-1": savedCase,
      "/api/decisions/RL-DECISION-1": {...decision, kind, analysis_id: "RL-ANALYSIS-EARLIER",
        analysis_material_hash: "b".repeat(64), decided_at: "2026-08-31T14:00:30Z"}});
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1&analysisId=RL-ANALYSIS-1");
    const {result} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.operation).toBeNull());
    expect(result.current.error).toBeNull();
    expect(result.current.analysis).toEqual(analysis);
    expect(result.current.caseInstance).toEqual(savedCase);
    expect(result.current.decision).toBeNull();
    expect(result.current.actions).toEqual([]);
    expect(result.current.playback).toBeNull();
    expect(mock.mock.calls.some(([url]) => String(url).includes("/actions"))).toBe(false);
    expect(mock.mock.calls.every(([, init]) => !init?.method)).toBe(true);
  });

  it("rejects a decision projection with no analysis instead of dropping the decision", async () => {
    savedReads({"/api/cases/RL-CASE-1": {...caseInstance, current_decision_id: decision.decision_id}});
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1");
    const {result} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.operation).toBeNull());
    expect(result.current.error).toMatch(/Unable to reopen/);
    expect(result.current.caseInstance).toBeNull();
  });

  it("ignores StrictMode's abandoned startup response after a new startup completes", async () => {
    let resolveOld!: (value: Response) => void;
    const oldRuntime = new Promise<Response>(r => {resolveOld = r;});
    const mock = savedReads();
    const read = mock.getMockImplementation()!;
    let calls = 0;
    mock.mockImplementation((url, init) => url === "/api/runtime" && ++calls === 1 ? oldRuntime : read(url, init));
    const {result} = renderHook(useCaseWorkspace, {wrapper: StrictMode});
    await waitFor(() => expect(result.current.operation).toBeNull());
    expect(result.current.runtime).toEqual(runtime);
    await act(async () => {resolveOld(await response({...runtime, runtime_mode: "live"}));});
    expect(result.current.runtime).toEqual(runtime);
    expect(result.current.operation).toBeNull();
  });

  it("ignores a late list response after unmount", async () => {
    let resolveList!: (value: Response) => void;
    savedReads({"/api/cases": new Promise<Response>(r => {resolveList = r;})});
    const {result, unmount} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.operation).toBeNull());
    let listing!: Promise<void>;
    act(() => {listing = result.current.loadExistingCases();});
    unmount();
    await act(async () => {resolveList(await response([caseInstance])); await listing;});
    expect(result.current.existingCases).toBeNull();
  });

  it.each(["create", "analyze", "approve", "reject", "retryPlanning", "retryAction", "startPlayback"] as const)("holds the shared gate throughout %s", async action => {
    const needsDecision = ["retryPlanning", "retryAction", "startPlayback"].includes(action);
    const mock = savedReads({
      "/api/cases/RL-CASE-1": {...caseInstance, current_analysis_id: analysis.analysis_id,
        current_decision_id: needsDecision ? decision.decision_id : null,
        controls: {new_analysis: true, decide: !needsDecision, retry_action_planning: action === "retryPlanning", start_playback: action === "startPlayback"}},
      "/api/decisions/RL-DECISION-1": {...decision, action_planning_status: action === "retryPlanning" ? "failed" : "complete"},
      "/api/decisions/RL-DECISION-1/actions": [{...actions[0], status: "failed"}, ...actions.slice(1)],
      "/api/decisions/RL-DECISION-1/playback": await response({detail: {code: "PLAYBACK_NOT_FOUND"}}, 404),
      "/api/decisions/RL-DECISION-1/observations": [],
    });
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1&analysisId=RL-ANALYSIS-1");
    const {result} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.analysis).not.toBeNull());
    let resolveMutation!: (value: Response) => void;
    const pending = new Promise<Response>(r => {resolveMutation = r;});
    const read = mock.getMockImplementation()!;
    mock.mockImplementation((url, init) => init?.method === "POST" ? pending : read(url, init));
    let mutation!: Promise<void>;
    act(() => {
      mutation = action === "reject" ? result.current.reject("Wait") : action === "retryAction"
        ? result.current.retryAction(actions[0].action_id) : result.current[action]();
    });
    const count = mock.mock.calls.length;
    await act(async () => {
      await result.current.loadExistingCases(); await result.current.reopen("RL-CASE-2"); await result.current.create();
    });
    expect(result.current.operation).not.toBeNull();
    expect(result.current.error).toMatch(/wait/i);
    expect(mock.mock.calls.slice(count).filter(([, init]) => init?.method !== "POST")).toHaveLength(0);
    expect(mock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    await act(async () => {
      const body = action === "create" ? caseInstance : action === "analyze" ? analysis : action === "retryAction" ? actions[0]
        : action === "startPlayback" ? playback : decision;
      resolveMutation(await response(body)); await mutation;
    });
    expect(result.current.operation).toBeNull();
    expect(result.current.caseInstance?.case_id).toBe(caseInstance.case_id);
  });

  it.each(["retryPlanning", "startPlayback"] as const)("honors disabled saved %s in UI and handlers", async operation => {
    const mock = savedReads({
      "/api/cases/RL-CASE-1": {...caseInstance, current_analysis_id: analysis.analysis_id, current_decision_id: decision.decision_id},
      "/api/decisions/RL-DECISION-1": {...decision, action_planning_status: operation === "retryPlanning" ? "failed" : "complete"},
      "/api/decisions/RL-DECISION-1/playback": await response({detail: {code: "PLAYBACK_NOT_FOUND"}}, 404),
      "/api/decisions/RL-DECISION-1/observations": [],
    });
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1&analysisId=RL-ANALYSIS-1");
    const {result} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.decision).not.toBeNull());
    await act(async () => {await result.current[operation]();});
    expect(mock.mock.calls.every(([, init]) => !init?.method)).toBe(true);
    render(<App />);
    await selectExecutionStage();
    expect(await screen.findByRole("button", {name: operation === "retryPlanning" ? "Retry action planning" : "Start simulated execution"})).toBeDisabled();
  });

  it("ignores late mutation responses after unmount", async () => {
    const mock = savedReads();
    const {result, unmount} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.operation).toBeNull());
    let resolveMutation!: (value: Response) => void;
    mock.mockReturnValue(new Promise<Response>(r => {resolveMutation = r;}));
    let creating!: Promise<void>;
    act(() => {creating = result.current.create();});
    unmount();
    await act(async () => {resolveMutation(await response(caseInstance)); await creating;});
    expect(window.location.search).toBe("");
  });

  it("stops planning polling when the workspace unmounts", async () => {
    const mock = savedReads({"/api/cases/RL-CASE-1": {...caseInstance, current_analysis_id: analysis.analysis_id,
      controls: {...caseInstance.controls, decide: true}}});
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1");
    const {result, unmount} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.analysis).not.toBeNull());
    mock.mockResolvedValue(await response(pendingDecision));
    let approving!: Promise<void>;
    act(() => {approving = result.current.approve();});
    await waitFor(() => expect(result.current.operation).toBe("planning"));
    unmount();
    mock.mockResolvedValue(await response(decision));
    const calls = mock.mock.calls.length;
    await act(async () => {await approving;});
    expect(mock.mock.calls).toHaveLength(calls);
  });

  it.each([
    ["case", "/api/cases/RL-CASE-1", {...caseInstance, case_id: "other"}],
    ["analysis case", "/api/cases/RL-CASE-1/analysis", {...analysis, case_id: "other"}],
    ["analysis id", "/api/cases/RL-CASE-1/analysis", {...analysis, analysis_id: "other"}],
    ["material", "/api/cases/RL-CASE-1/analysis", {...analysis, material: {...analysis.material, case_id: "other"}}],
    ["evidence", "/api/cases/RL-CASE-1/analysis", {...analysis, evidence_items: [{...analysis.evidence_items[0], retrieved_for_analysis_id: "other"}]}],
    ["decision", "/api/decisions/RL-DECISION-1", {...decision, analysis_id: "other"}],
    ["action", "/api/decisions/RL-DECISION-1/actions", [{...actions[0], case_id: "other"}]],
    ["draft", "/api/decisions/RL-DECISION-1/drafts", [{...drafts[0], action_id: "other"}]],
    ["playback", "/api/decisions/RL-DECISION-1/playback", {...playback, decision_id: "other"}],
    ["observation", "/api/decisions/RL-DECISION-1/observations", [{...observations[0], playback_id: "other"}]],
  ])("rejects mismatched %s identity atomically", async (_label, path, value) => {
    const mock = savedReads({"/api/cases/RL-CASE-1": {...caseInstance, current_analysis_id: analysis.analysis_id, current_decision_id: decision.decision_id}, [String(path)]: value});
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1&analysisId=RL-ANALYSIS-1");
    const {result} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.operation).toBeNull());
    expect(result.current.error).toMatch(/Unable to reopen|saved analysis is no longer current/);
    expect(result.current.caseInstance).toBeNull();
    expect(result.current.analysis).toBeNull();
    expect(mock.mock.calls.every(([, init]) => !init?.method)).toBe(true);
  });

  it("refuses a case whose projection changes during restoration", async () => {
    const mock = savedReads();
    const original = mock.getMockImplementation()!;
    let reads = 0;
    mock.mockImplementation((url, init) => String(url) === "/api/cases/RL-CASE-1" && ++reads === 2
      ? response({...caseInstance, current_analysis_id: analysis.analysis_id, projection_updated_at: "2026-09-02T00:00:00Z"}) : original(url, init));
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1&analysisId=RL-ANALYSIS-1");
    const {result} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.operation).toBeNull());
    expect(result.current.error).toMatch(/Unable to reopen/);
    expect(result.current.caseInstance).toBeNull();
  });

  it.each(["RL-CASE-unknown", "../runtime?secret=x"])("fails unknown or malformed identity %s safely", async id => {
    const mock = savedReads();
    window.history.replaceState(null, "", `/?caseId=${encodeURIComponent(id)}`);
    const {result} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.operation).toBeNull());
    expect(result.current.error).toMatch(/Unable to reopen/);
    expect(result.current.caseInstance).toBeNull();
    expect(mock.mock.calls.map(([url]) => url)).toContain(`/api/cases/${encodeURIComponent(id)}`);
  });

  it("fails an analysis bookmark without a case without extra requests", async () => {
    const mock = savedReads();
    window.history.replaceState(null, "", "/?analysisId=RL-ANALYSIS-1");
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to initialize");
    expect(mock.mock.calls.map(([url]) => url)).toEqual(["/api/runtime"]);
  });

  it("restores refresh timestamps and controls exactly, including case-only bookmarks", async () => {
    const mock = savedReads();
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1&view=planner");
    const first = renderHook(useCaseWorkspace);
    await waitFor(() => expect(first.result.current.analysis).not.toBeNull());
    expect(first.result.current.analysis).toEqual(analysis);
    expect(first.result.current.caseInstance).toEqual({...caseInstance, current_analysis_id: analysis.analysis_id});
    first.unmount();
    const second = renderHook(useCaseWorkspace);
    await waitFor(() => expect(second.result.current.analysis).not.toBeNull());
    expect(second.result.current.analysis).toEqual(analysis);
    expect(new URLSearchParams(window.location.search).get("view")).toBe("planner");
    expect(mock.mock.calls.every(([, init]) => !init?.method)).toBe(true);
  });

  it("keeps picker loading, failure, retry and empty states explicit", async () => {
    let resolveList!: (value: Response) => void;
    const mock = savedReads({"/api/cases": new Promise<Response>(r => {resolveList = r;})});
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await openOtherSavedCases();
    await userEvent.click(screen.getByRole("button", {name: "Find existing cases"}));
    expect(screen.getByRole("button", {name: "Finding existing cases…"})).toBeDisabled();
    expect(screen.getByRole("button", {name: "Start a new demo"})).toBeDisabled();
    expect(screen.queryByText("Creating Case workspace…")).not.toBeInTheDocument();
    expect(screen.queryByText("Analyzing disruption…")).not.toBeInTheDocument();
    await act(async () => resolveList(await response({detail: {code: "READ_FAILED"}}, 503)));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to find existing cases");
    mock.mockResolvedValue(await response([]));
    await userEvent.click(screen.getByRole("button", {name: "Try finding cases again"}));
    expect(await screen.findByText("No existing cases are available.")).toBeVisible();
  });

  it("ignores a restoration response arriving after unmount", async () => {
    let resolveCase!: (value: Response) => void;
    savedReads({"/api/cases/RL-CASE-1": new Promise<Response>(r => {resolveCase = r;})});
    const view = renderHook(useCaseWorkspace);
    await waitFor(() => expect(view.result.current.operation).toBeNull());
    let opening!: Promise<void>;
    act(() => {opening = view.result.current.reopen("RL-CASE-1");});
    view.unmount();
    await act(async () => {resolveCase(await response(caseInstance)); await opening;});
    expect(window.location.search).toBe("");
  });

  it("keeps every mutation control and picker disabled during a listing", async () => {
    let resolveList!: (value: Response) => void;
    savedReads({"/api/cases/RL-CASE-1": {...caseInstance, current_analysis_id: analysis.analysis_id, controls: {...caseInstance.controls, decide: true}},
      "/api/cases": new Promise<Response>(r => {resolveList = r;})});
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1");
    render(<App />);
    await selectDecisionStage();
    await screen.findByText("Combined response");
    await openOtherSavedCases();
    await userEvent.click(screen.getByRole("button", {name: "Find existing cases"}));
    expect(screen.getByRole("button", {name: "Selected: Combined response"})).toBeDisabled();
    expect(screen.getByRole("button", {name: "Continue to review and approve"})).toBeDisabled();
    await selectApprovalStage();
    expect(screen.getByRole("button", {name: "Approve combined response"})).toBeDisabled();
    await act(async () => resolveList(await response([])));
  });

  it.each([false, true])("restores under StrictMode (bookmark=%s) using GET only", async bookmark => {
    const mock = savedReads();
    if (bookmark) window.history.replaceState(null, "", "/?caseId=RL-CASE-1&analysisId=RL-ANALYSIS-1&view=planner");
    render(<StrictMode><App /></StrictMode>);
    if (!bookmark) {
      await waitFor(() => expect(screen.getByRole("button", {name: "Find existing cases"})).toBeEnabled());
      await openOtherSavedCases();
    await userEvent.click(screen.getByRole("button", {name: "Find existing cases"}));
      await userEvent.click(await screen.findByRole("button", {name: "Reopen case RL-CASE-1"}));
    }
    await selectDecisionStage();
    expect(await screen.findByText("Combined response")).toBeVisible();
    expect(screen.queryByText("Reopening saved case…")).not.toBeInTheDocument();
    expect(mock.mock.calls.every(([, init]) => !init?.method)).toBe(true);
    expect(new URLSearchParams(window.location.search).get("analysisId")).toBe(analysis.analysis_id);
  });

  it("blocks synchronous operations during initialization and listing", async () => {
    let resolveRuntime!: (value: Response) => void;
    let resolveList!: (value: Response) => void;
    const mock = savedReads({"/api/runtime": new Promise<Response>(r => { resolveRuntime = r; }),
      "/api/cases": new Promise<Response>(r => { resolveList = r; })});
    const {result} = renderHook(useCaseWorkspace);
    await act(async () => { await result.current.loadExistingCases(); await result.current.create(); await result.current.reopen("RL-CASE-1"); });
    expect(mock.mock.calls.map(([url]) => url)).toEqual(["/api/runtime"]);
    await act(async () => resolveRuntime(await response(runtime)));
    let listing!: Promise<void>;
    act(() => { listing = result.current.loadExistingCases(); });
    await act(async () => { await result.current.create(); await result.current.reopen("RL-CASE-1"); });
    expect(result.current.operation).toBe("listing");
    expect(mock.mock.calls.map(([url]) => url)).toEqual(["/api/runtime", "/api/cases"]);
    await act(async () => { resolveList(await response([])); await listing; });
    expect(result.current.existingCases).toEqual([]);
  });

  it("coalesces the same identity and visibly refuses a distinct fast reopen", async () => {
    let resolveCase!: (value: Response) => void;
    savedReads({"/api/cases/RL-CASE-1": new Promise<Response>(r => {resolveCase = r;})});
    const {result} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.operation).toBeNull());
    let first!: Promise<void>;
    act(() => {
      first = result.current.reopen("RL-CASE-1");
      expect(result.current.reopen("RL-CASE-1")).toBe(first);
      expect(result.current.reopen("RL-CASE-2")).not.toBe(first);
    });
    expect(result.current.error).toMatch(/wait/i);
    await act(async () => { resolveCase(await response(caseInstance)); await first; });
    expect(result.current.caseInstance?.case_id).toBe("RL-CASE-1");
  });

  it("honors saved decision controls in the UI and direct handlers", async () => {
    const mock = savedReads();
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1&analysisId=RL-ANALYSIS-1");
    const {result} = renderHook(useCaseWorkspace);
    await waitFor(() => expect(result.current.analysis).not.toBeNull());
    await act(async () => { await result.current.approve(); await result.current.reject("no"); });
    expect(mock.mock.calls.every(([, init]) => !init?.method)).toBe(true);
    render(<App />);
    await selectApprovalStage();
    expect(await screen.findByRole("button", {name: "Approve combined response"})).toBeDisabled();
  });

  it.each(["PLAYBACK_NOT_FOUND", "DECISION_NOT_FOUND"])("handles optional playback specifically: %s", async code => {
    savedReads({"/api/cases/RL-CASE-1": {...caseInstance, current_analysis_id: analysis.analysis_id, current_decision_id: decision.decision_id},
      "/api/decisions/RL-DECISION-1/playback": await response({detail: {code}}, 404),
      "/api/decisions/RL-DECISION-1/observations": []});
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1&analysisId=RL-ANALYSIS-1");
    render(<App />);
    if (code === "PLAYBACK_NOT_FOUND") {
      await selectExecutionStage();
      expect(await screen.findByRole("button", {name: "Start simulated execution"})).toBeDisabled();
    } else {
      expect(await screen.findByRole("alert")).toHaveTextContent("Unable to reopen");
      expect(screen.queryByTestId("decision-receipt")).not.toBeInTheDocument();
    }
  });
});

describe("progressive Case workspace", () => {
  it("gates protected Case APIs until Alex signs in", async () => {
    const client = unauthenticatedClient();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<AuthProvider config={entraConfig} client={client}><App /></AuthProvider>);

    const signIn = await screen.findByRole("button", {name: "Sign in"});
    expect(fetchMock).not.toHaveBeenCalled();
    await userEvent.click(signIn);
    expect(client.loginRedirect).toHaveBeenCalledWith({
      scopes: [entraConfig.apiScope],
      redirectStartPage: "http://localhost:3000/",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders the Case workspace after Entra resolves Alex", async () => {
    const client = authenticatedClient();
    const fetchMock = mockFallbackCaseLifecycle();

    render(<AuthProvider config={entraConfig} client={client}><App /></AuthProvider>);

    expect(await screen.findByText("Fictional scenario · Uses predefined sample data")).toBeVisible();
    expect(screen.queryByRole("button", {name: "Sign in"})).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/runtime", {
      headers: {Authorization: "Bearer test-api-token"},
    });
  });

  it("verifies Taylor before mounting only the Finance inbox", async () => {
    const client = authenticatedClient();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/me") return response({mode: "entra", persona_id: "RL-PERSONA-TAYLOR", display_name: "Taylor", independent_finance_enabled: true});
      if (path === "/api/finance/reviews") return response([]);
      throw new Error(`Taylor must not request planner data: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AuthProvider config={entraConfig} client={client}><App /></AuthProvider>);

    expect(await screen.findByRole("heading", {name: "Finance requests"})).toBeVisible();
    expect(await screen.findByText("No Finance requests are waiting.")).toBeVisible();
    expect(fetchMock.mock.calls.map(([input]) => new URL(String(input), "http://localhost").pathname)).toEqual([
      "/api/me", "/api/finance/reviews",
    ]);
    expect(screen.queryByRole("button", {name: "Start a new demo"})).not.toBeInTheDocument();
  });

  it("shows session recovery instead of a misleading workspace failure", async () => {
    const client = authenticatedClient();
    client.acquireTokenSilent = vi.fn().mockRejectedValue(new Error("raw renewal timeout"));
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<AuthProvider config={entraConfig} client={client}><App /></AuthProvider>);

    expect(await screen.findByRole("alert", {name: "Sign-in required"})).toHaveTextContent(
      "We couldn't renew your sign-in. Sign in again to continue.",
    );
    await waitFor(() => expect(screen.getByText(/signed-in role could not be verified/)).not.toBeVisible());
    expect(screen.queryByText("raw renewal timeout")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("loads fallback provenance without silently creating a Case", async () => {
    let resolveCase!: (value: Response) => void;
    const created = new Promise<Response>((resolve) => { resolveCase = resolve; });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/runtime") return response(runtime);
      if (path === "/api/cases" && init?.method === "POST") return created;
      throw new Error(`Unexpected API request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    expect(await screen.findByText("Fictional scenario · Uses predefined sample data")).toBeVisible();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    expect(await screen.findByRole("status")).toHaveTextContent("Creating Case workspace…");
    await act(async () => resolveCase(await response(caseInstance, 201)));
    expect(await screen.findByText(/RL-CASE-1/)).toBeInTheDocument();
  });

  it("creates only one Case under the app's StrictMode development shell", async () => {
    const fetchMock = mockFallbackCaseLifecycle();
    render(<StrictMode><App /></StrictMode>);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await screen.findByText(/RL-CASE-1/);
    const createCalls = fetchMock.mock.calls.filter(([input, init]) =>
      new URL(String(input), "http://localhost").pathname === "/api/cases" && init?.method === "POST"
    );
    expect(createCalls).toHaveLength(1);
  });

  it("keeps provenance, decision, execution, and simulated outcomes visible", async () => {
    mockFallbackCaseLifecycle();
    render(<App />);
    expect(await screen.findByText("Fictional scenario · Uses predefined sample data")).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await screen.findByText(/RL-CASE-1/);
    expect(screen.getByText("Scenario time: Sep 1, 2026, 9:00 AM CDT")).toBeVisible();
    expect(screen.getByText("Power BI unavailable in fallback")).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await selectDecisionStage();
    expect(await screen.findByText("Combined response")).toBeVisible();
    await selectApprovalStage();
    await userEvent.click(screen.getByRole("button", {name: "Approve combined response"}));
    expect(await screen.findByRole("heading", {name: "Approved response"})).toBeVisible();
    expect(within(screen.getByTestId("decision-receipt")).getByText("Combined response")).toBeVisible();
    await selectExecutionStage();
    expect(await screen.findAllByTestId("execution-action")).toHaveLength(5);
    expect(screen.getByText("Unsent draft")).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Start simulated execution"}));
    expect(await screen.findByText("Simulated results")).toBeVisible();
    expect(await screen.findAllByTestId("outcome-observation")).toHaveLength(10);
    expect(screen.queryByText("Actual outcomes")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", {name: "1. Understand the disruption"})).toBeVisible();
    await selectDecisionStage();
    expect(screen.getByRole("button", {name: "Click here to understand why"})).toBeVisible();
    expect(screen.queryByRole("heading", {name: "Recommended response—and why."})).not.toBeInTheDocument();
    await selectApprovalStage();
    expect(screen.getByRole("heading", {name: "Review and approve."})).toBeVisible();
  });

  it("announces that evidence checks are pending while analysis is in progress", async () => {
    let resolveAnalysis!: (value: Response) => void;
    const delayedAnalysis = new Promise<Response>((resolve) => { resolveAnalysis = resolve; });
    mockFallbackCaseLifecycle({analysis: delayedAnalysis});
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    expect(await screen.findByRole("status")).toHaveTextContent("Analysis in progress. Source retrieval and evidence checks will be shown when the analysis completes.");
    await act(async () => resolveAnalysis(await response(analysis, 201)));
    await selectDecisionStage();
    expect(await screen.findByText("Combined response")).toBeVisible();
  });

  it("keeps the alternate supplier blocker visible and nonselectable", async () => {
    mockFallbackCaseLifecycle();
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await selectDecisionStage();
    const beta = await screen.findByRole("article", {name: "Use the alternate supplier"});
    expect(within(beta).getByText("Cannot use Supplier Beta yet: supplier qualification is incomplete")).toBeVisible();
    expect(within(beta).getByRole("button", {name: "Select Use the alternate supplier"})).toBeDisabled();
  });

  it("disables decision controls for stale or evidence-blocked analysis", async () => {
    const blockedAnalysis = {
      ...analysis,
      evidence_validation: {
        ...evidenceValidation,
        blocking_codes: ["REQUIRED_EVIDENCE_STALE"],
      },
    };
    mockFallbackCaseLifecycle({analysis: blockedAnalysis});
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await selectDecisionStage();
    await selectApprovalStage();
    expect(await screen.findByText("A planning requirement is unresolved")).toBeVisible();
    expect(screen.getByText("Decision details").closest("details")).toHaveTextContent("REQUIRED_EVIDENCE_STALE");
    expect(screen.getByRole("button", {name: "Approve combined response"})).toBeDisabled();
    expect(screen.getByRole("button", {name: "Reject recommendation"})).toBeDisabled();
  });

  it("disables decision controls when required evidence is stale", async () => {
    const staleAnalysis = {
      ...analysis,
      evidence_validation: {
        ...evidenceValidation,
        item_results: evidenceValidation.item_results.map((item) => ({...item, freshness: "stale"})),
      },
    };
    mockFallbackCaseLifecycle({analysis: staleAnalysis});
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await selectDecisionStage();
    await selectApprovalStage();
    expect(await screen.findByText("Required evidence is stale")).toBeVisible();
    expect(screen.getByRole("button", {name: "Approve combined response"})).toBeDisabled();
    expect(screen.getByRole("button", {name: "Reject recommendation"})).toBeDisabled();
  });

  it("surfaces planning failure exactly and retries action planning", async () => {
    const failedDecision = {...decision, action_planning_status: "failed"};
    mockFallbackCaseLifecycle({decision: failedDecision, retryDecision: decision});
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await selectDecisionStage();
    await screen.findByText("Combined response");
    await selectApprovalStage();
    await userEvent.click(screen.getByRole("button", {name: "Approve combined response"}));
    await selectExecutionStage();
    expect(await screen.findByText("Approved — action planning failed")).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Retry action planning"}));
    expect(await screen.findAllByTestId("execution-action")).toHaveLength(5);
    expect(screen.queryByText("Approved — action planning failed")).not.toBeInTheDocument();
  });

  it("surfaces a failed child action and retries only that action", async () => {
    mockFallbackCaseLifecycle({actions: [{...actions[0], status: "failed"}, ...actions.slice(1)]});
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await selectDecisionStage();
    await screen.findByText("Combined response");
    await selectApprovalStage();
    await userEvent.click(screen.getByRole("button", {name: "Approve combined response"}));
    await selectExecutionStage();
    const failedAction = await screen.findByTestId("execution-action-RL-ACTION-1");
    expect(within(failedAction).getByText("Failed")).toBeVisible();
    await userEvent.click(within(failedAction).getByRole("button", {name: "Retry prepare supplier recovery draft"}));
    expect(await within(failedAction).findByText("In progress")).toBeVisible();
    expect(screen.getAllByTestId("execution-action")).toHaveLength(5);
  });

  it("records a rejection with a nonblank reason and keeps prior analysis visible", async () => {
    const rejectedDecision = {
      ...decision,
      decision_id: "RL-DECISION-REJECTED",
      kind: "rejected",
      selected_option_id: null,
      rejection_reason: "Wait for refreshed supplier evidence.",
      action_planning_status: "not_applicable",
      new_analysis_available: true,
    };
    mockFallbackCaseLifecycle({decision: rejectedDecision});
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await selectDecisionStage();
    await screen.findByText("Combined response");
    await selectApprovalStage();
    await userEvent.type(screen.getByLabelText("Rejection reason"), "Wait for refreshed supplier evidence.");
    await userEvent.click(screen.getByRole("button", {name: "Reject recommendation"}));
    expect(await screen.findByRole("heading", {name: "Recommendation rejected"})).toBeVisible();
    expect(screen.getByText("Wait for refreshed supplier evidence.")).toBeVisible();
    expect(screen.getByRole("tab", {name: "1. Understand the disruption"})).toBeVisible();
    expect(screen.queryAllByTestId("execution-action")).toHaveLength(0);
  });

  it("does not relabel synthetic observations from server responses as actual", async () => {
    const fetchMock = mockFallbackCaseLifecycle();
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await selectDecisionStage();
    await screen.findByText("Combined response");
    await selectApprovalStage();
    await userEvent.click(screen.getByRole("button", {name: "Approve combined response"}));
    await selectExecutionStage();
    await screen.findAllByTestId("execution-action");
    const start = screen.getByRole("button", {name: "Start simulated execution"});
    start.click();
    start.click();
    const outcomeRows = await screen.findAllByTestId("outcome-observation");
    expect(outcomeRows).toHaveLength(10);
    outcomeRows.forEach((row) => expect(within(row).getByText("Simulated")).toBeVisible());
    expect(screen.queryByText("Actual")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([input, init]) =>
      input === "/api/decisions/RL-DECISION-1/playback"
      && (init as RequestInit | undefined)?.method === "POST"
    )).toHaveLength(1);
  });

  it("shows readable initialization failures", async () => {
    mockFallbackCaseLifecycle({runtimeFailure: true});
    render(<App />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Unable to initialize the Case workspace. The request could not be completed.");
    expect(alert).not.toHaveTextContent("DatabaseError");
    expect(alert).not.toHaveTextContent("password=secret");
  });

  it("does not display arbitrary client exception text", async () => {
    mockFallbackCaseLifecycle({runtimeError: new Error("token=secret internal fetch exception")});
    render(<App />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Unable to initialize the Case workspace. The request could not be completed.");
    expect(alert).not.toHaveTextContent("token=secret");
  });

  it("keeps the loaded analysis when entering assisted review", async () => {
    const fetchMock = mockFallbackCaseLifecycle();
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await userEvent.click(screen.getByRole("button", {name: "Start a new demo"}));
    await screen.findByText(/RL-CASE-1/);
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await screen.findByText("Combined response");
    const content = document.getElementById("assisted-review")!;
    expect(content).not.toBeNull();
    const beforeContent = content.textContent;
    const beforeCalls = fetchMock.mock.calls.length;
    await userEvent.click(screen.getByRole("link", {name: "Review with AI assistance"}));
    expect(fetchMock.mock.calls).toHaveLength(beforeCalls);
    expect(content.textContent).toBe(beforeContent);
  });

  it("collapses the picker after successful reopen and can find cases again using GET only", async () => {
    const analyzedCase = {...caseInstance, status: "awaiting_decision", current_analysis_id: analysis.analysis_id,
      controls: {...caseInstance.controls, new_analysis: false, decide: true}};
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/runtime") return response(runtime);
      if (path === "/api/cases") return response([analyzedCase]);
      if (path === "/api/cases/RL-CASE-1") return response(analyzedCase);
      if (path === "/api/cases/RL-CASE-1/analysis") return response(analysis);
      throw new Error(`Unexpected API request: ${init?.method ?? "GET"} ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/?view=planner");

    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await openOtherSavedCases();
    await userEvent.click(screen.getByRole("button", {name: "Find existing cases"}));
    expect(await screen.findByText(/Awaiting decision/)).toBeVisible();
    expect(screen.getByText(/RL-CASE-1/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Reopen case RL-CASE-1"}));

    await selectDecisionStage();
    expect(await screen.findByText("Combined response")).toBeVisible();
    expect(screen.queryByRole("button", {name: "Reopen case RL-CASE-1"})).not.toBeInTheDocument();
    expect(screen.queryByText("No existing cases are available.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", {name: "Find existing cases"})).toBeEnabled();
    expect(screen.getByText(/reads saved results and does not refresh evidence/i)).toBeVisible();
    expect(new URL(window.location.href).searchParams.get("caseId")).toBe("RL-CASE-1");
    expect(new URL(window.location.href).searchParams.get("analysisId")).toBe("RL-ANALYSIS-1");
    expect(new URL(window.location.href).searchParams.get("view")).toBe("planner");
    await openOtherSavedCases();
    await userEvent.click(screen.getByRole("button", {name: "Find existing cases"}));
    expect(await screen.findByRole("button", {name: "Reopen case RL-CASE-1"})).toBeEnabled();
    expect(screen.getByText("Combined response")).toBeVisible();
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
  });

  it("reopens a case without analysis and keeps server controls", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/runtime") return response(runtime);
      if (path === "/api/cases") return response([caseInstance]);
      if (path === "/api/cases/RL-CASE-1") return response(caseInstance);
      throw new Error(`Unexpected API request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/");
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await openOtherSavedCases();
    await userEvent.click(screen.getByRole("button", {name: "Find existing cases"}));
    await userEvent.click(await screen.findByRole("button", {name: "Reopen case RL-CASE-1"}));
    expect(await screen.findByRole("button", {name: "Analyze disruption"})).toBeEnabled();
    expect(screen.queryByRole("button", {name: "Reopen case RL-CASE-1"})).not.toBeInTheDocument();
    expect(new URL(window.location.href).searchParams.has("analysisId")).toBe(false);
  });

  it("fails a superseded analysis bookmark visibly without substituting the current analysis", async () => {
    const currentCase = {...caseInstance, current_analysis_id: "RL-ANALYSIS-2"};
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/runtime") return response(runtime);
      if (path === "/api/cases/RL-CASE-1") return response(currentCase);
      if (path === "/api/cases/RL-CASE-1/analysis") return response({...analysis, analysis_id: "RL-ANALYSIS-2"});
      throw new Error(`Unexpected API request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/?caseId=RL-CASE-1&analysisId=RL-ANALYSIS-1");
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/saved analysis is no longer current/i);
    expect(screen.queryByText("Combined response")).not.toBeInTheDocument();
  });

  it("restores a recorded decision and all related saved state without mutation", async () => {
    const decidedCase = {...caseInstance, status: "executing", current_analysis_id: analysis.analysis_id,
      current_decision_id: decision.decision_id,
      controls: {new_analysis: false, decide: false, retry_action_planning: false, start_playback: true}};
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/runtime") return response(runtime);
      if (path === "/api/cases") return response([decidedCase]);
      if (path === "/api/cases/RL-CASE-1") return response(decidedCase);
      if (path === "/api/cases/RL-CASE-1/analysis") return response(analysis);
      if (path === "/api/decisions/RL-DECISION-1") return response(decision);
      if (path === "/api/decisions/RL-DECISION-1/actions") return response(actions);
      if (path === "/api/decisions/RL-DECISION-1/drafts") return response(drafts);
      if (path === "/api/decisions/RL-DECISION-1/playback") return response(playback);
      if (path === "/api/decisions/RL-DECISION-1/observations") return response(observations);
      throw new Error(`Unexpected API request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/");
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await openOtherSavedCases();
    await userEvent.click(screen.getByRole("button", {name: "Find existing cases"}));
    await userEvent.click(await screen.findByRole("button", {name: "Reopen case RL-CASE-1"}));
    await selectApprovalStage();
    expect(await screen.findByRole("heading", {name: "Approved response"})).toBeVisible();
    await selectExecutionStage();
    expect(screen.getAllByTestId("execution-action")).toHaveLength(5);
    expect(screen.getByText("Simulated results")).toBeVisible();
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
  });

  it("leaves no actionable partial state when a related saved-state read fails", async () => {
    const decidedCase = {...caseInstance, status: "executing", current_analysis_id: analysis.analysis_id,
      current_decision_id: decision.decision_id};
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/runtime") return response(runtime);
      if (path === "/api/cases") return response([decidedCase]);
      if (path === "/api/cases/RL-CASE-1") return response(decidedCase);
      if (path === "/api/cases/RL-CASE-1/analysis") return response(analysis);
      if (path === "/api/decisions/RL-DECISION-1") return response(decision);
      if (path.endsWith("/actions")) return response({detail: {code: "READ_FAILED"}}, 503);
      if (path.endsWith("/drafts") || path.endsWith("/observations")) return response([]);
      if (path.endsWith("/playback")) return response({detail: {code: "PLAYBACK_NOT_FOUND"}}, 404);
      throw new Error(`Unexpected API request: ${path}`);
    }));
    window.history.replaceState(null, "", "/");
    render(<App />);
    await screen.findByText("Fictional scenario · Uses predefined sample data");
    await openOtherSavedCases();
    await userEvent.click(screen.getByRole("button", {name: "Find existing cases"}));
    await userEvent.click(await screen.findByRole("button", {name: "Reopen case RL-CASE-1"}));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to reopen this case");
    expect(screen.getByRole("button", {name: "Reopen case RL-CASE-1"})).toBeEnabled();
    expect(screen.queryByRole("button", {name: /Approve/})).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", {name: "Approved response"})).not.toBeInTheDocument();
  });
});
