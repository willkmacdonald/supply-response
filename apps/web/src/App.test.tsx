// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {act, cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {StrictMode} from "react";
import {afterEach, describe, expect, it, vi} from "vitest";
import App from "./App";
import {AuthProvider, type AuthClient} from "./auth/AuthProvider";

const scenarioTime = "2026-09-01T09:00:00-05:00";

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
} = {}) {
  let decisionPolls = 0;
  let playbackPolls = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const path = new URL(url, "http://localhost").pathname;
    const method = init?.method ?? "GET";
    if (path === "/api/runtime" && method === "GET") {
      return overrides.runtimeFailure
        ? response({detail: "runtime unavailable"}, 503)
        : response(runtime);
    }
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
  vi.unstubAllGlobals();
});

describe("progressive Case workspace", () => {
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

  it("renders the Case workspace after Entra resolves Alex", async () => {
    const client = authenticatedClient();
    const fetchMock = mockFallbackCaseLifecycle();

    render(<AuthProvider config={entraConfig} client={client}><App /></AuthProvider>);

    expect(await screen.findByText("Fallback mode")).toBeVisible();
    expect(screen.queryByRole("button", {name: "Sign in as Alex"})).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/runtime", undefined);
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
    expect(await screen.findByText("Fallback mode")).toBeVisible();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    expect(await screen.findByRole("status")).toHaveTextContent("Creating Case workspace…");
    await act(async () => resolveCase(await response(caseInstance, 201)));
    expect(await screen.findByText("RL-CASE-1")).toBeVisible();
  });

  it("creates only one Case under the app's StrictMode development shell", async () => {
    const fetchMock = mockFallbackCaseLifecycle();
    render(<StrictMode><App /></StrictMode>);
    await screen.findByText("Fallback mode");
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await screen.findByText("RL-CASE-1");
    const createCalls = fetchMock.mock.calls.filter(([input, init]) =>
      new URL(String(input), "http://localhost").pathname === "/api/cases" && init?.method === "POST"
    );
    expect(createCalls).toHaveLength(1);
  });

  it("keeps provenance, decision, execution, and simulated outcomes visible", async () => {
    mockFallbackCaseLifecycle();
    render(<App />);
    expect(await screen.findByText("Fallback mode")).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await screen.findByText("RL-CASE-1");
    expect(screen.getByText("Scenario time: Sep 1, 2026, 9:00 AM CDT")).toBeVisible();
    expect(screen.getByText("Power BI unavailable in fallback")).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    expect(await screen.findByText("Combined response")).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Approve combined response"}));
    expect(await screen.findByText(/Decision RL-DECISION-/)).toBeVisible();
    expect(await screen.findAllByTestId("execution-action")).toHaveLength(5);
    expect(screen.getByText("Unsent draft")).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Start simulated execution"}));
    expect(await screen.findByText("Simulated outcomes")).toBeVisible();
    expect(await screen.findAllByTestId("outcome-observation")).toHaveLength(10);
    expect(screen.queryByText("Actual outcomes")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", {name: "Evidence items"})).toBeVisible();
    expect(screen.getByRole("heading", {name: "Exposure and lineage"})).toBeVisible();
    expect(screen.getByRole("heading", {name: "Decision receipt"})).toBeVisible();
  });

  it("announces that evidence checks are pending while analysis is in progress", async () => {
    let resolveAnalysis!: (value: Response) => void;
    const delayedAnalysis = new Promise<Response>((resolve) => { resolveAnalysis = resolve; });
    mockFallbackCaseLifecycle({analysis: delayedAnalysis});
    render(<App />);
    await screen.findByText("Fallback mode");
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    expect(await screen.findByRole("status")).toHaveTextContent("Analysis in progress. Source retrieval and evidence checks will be shown when the analysis completes.");
    await act(async () => resolveAnalysis(await response(analysis, 201)));
    expect(await screen.findByText("Combined response")).toBeVisible();
  });

  it("keeps blocked Beta visible and nonselectable with its exact code", async () => {
    mockFallbackCaseLifecycle();
    render(<App />);
    await screen.findByText("Fallback mode");
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    const beta = await screen.findByRole("article", {name: "Source from Supplier Beta"});
    expect(within(beta).getByText("QUALITY_QUALIFICATION_PENDING")).toBeVisible();
    expect(within(beta).getByRole("button", {name: "Select Source from Supplier Beta"})).toBeDisabled();
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
    await screen.findByText("Fallback mode");
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    expect(await screen.findByText("REQUIRED_EVIDENCE_STALE")).toBeVisible();
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
    await screen.findByText("Fallback mode");
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    expect(await screen.findByText("Required evidence is stale")).toBeVisible();
    expect(screen.getByRole("button", {name: "Approve combined response"})).toBeDisabled();
    expect(screen.getByRole("button", {name: "Reject recommendation"})).toBeDisabled();
  });

  it("surfaces planning failure exactly and retries action planning", async () => {
    const failedDecision = {...decision, action_planning_status: "failed"};
    mockFallbackCaseLifecycle({decision: failedDecision, retryDecision: decision});
    render(<App />);
    await screen.findByText("Fallback mode");
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await screen.findByText("Combined response");
    await userEvent.click(screen.getByRole("button", {name: "Approve combined response"}));
    expect(await screen.findByText("Approved — action planning failed")).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name: "Retry action planning"}));
    expect(await screen.findAllByTestId("execution-action")).toHaveLength(5);
    expect(screen.queryByText("Approved — action planning failed")).not.toBeInTheDocument();
  });

  it("surfaces a failed child action and retries only that action", async () => {
    mockFallbackCaseLifecycle({actions: [{...actions[0], status: "failed"}, ...actions.slice(1)]});
    render(<App />);
    await screen.findByText("Fallback mode");
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await screen.findByText("Combined response");
    await userEvent.click(screen.getByRole("button", {name: "Approve combined response"}));
    const failedAction = await screen.findByTestId("execution-action-RL-ACTION-1");
    expect(within(failedAction).getByText("failed")).toBeVisible();
    await userEvent.click(within(failedAction).getByRole("button", {name: "Retry prepare alpha recovery draft"}));
    expect(await within(failedAction).findByText("in_progress")).toBeVisible();
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
    await screen.findByText("Fallback mode");
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await screen.findByText("Combined response");
    await userEvent.type(screen.getByLabelText("Rejection reason"), "Wait for refreshed supplier evidence.");
    await userEvent.click(screen.getByRole("button", {name: "Reject recommendation"}));
    expect(await screen.findByText("Rejected")).toBeVisible();
    expect(screen.getByRole("heading", {name: "Evidence items"})).toBeVisible();
    expect(screen.queryAllByTestId("execution-action")).toHaveLength(0);
  });

  it("does not relabel synthetic observations from server responses as actual", async () => {
    const fetchMock = mockFallbackCaseLifecycle();
    render(<App />);
    await screen.findByText("Fallback mode");
    await userEvent.click(screen.getByRole("button", {name: "Create showcase case"}));
    await userEvent.click(screen.getByRole("button", {name: "Analyze disruption"}));
    await screen.findByText("Combined response");
    await userEvent.click(screen.getByRole("button", {name: "Approve combined response"}));
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
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to initialize the Case workspace");
  });
});
