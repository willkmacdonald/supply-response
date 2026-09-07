import type {
  AnalysisVersion,
  CaseInstance,
  CasePurpose,
  Decision,
  DecisionInput,
  DraftArtifact,
  ExecutionAction,
  OutcomeObservation,
  Playback,
  RuntimeStatus,
} from "./types";

export const API_BASE = "";

type AccessTokenProvider = () => Promise<string | null>;
let accessTokenProvider: AccessTokenProvider = async () => null;

export function setAccessTokenProvider(provider: AccessTokenProvider): void {
  accessTokenProvider = provider;
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null) as {detail?: unknown} | null;
    const detail = errorBody?.detail ? ` ${JSON.stringify(errorBody.detail)}` : "";
    throw new Error(`API request failed: ${response.status}${detail}`);
  }
  return response.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const token = await accessTokenProvider();
  const options = token ? {headers: {Authorization: `Bearer ${token}`}} : undefined;
  return json(await fetch(`${API_BASE}${path}`, options));
}

async function post<T>(path: string, body: object, headers: Record<string, string> = {}): Promise<T> {
  const token = await accessTokenProvider();
  if (token) headers = {...headers, Authorization: `Bearer ${token}`};
  return json(await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json", ...headers},
    body: JSON.stringify(body),
  }));
}

export type WorkIQProbeResult = {
  stage: string;
  http_status: number | null;
  authenticated_alex: boolean;
  obo_succeeded: boolean;
  mcp_initialized: boolean;
  fetch_succeeded: boolean;
  exact_message_identity: boolean;
  expected_author: boolean;
  valid_source_timestamp: boolean;
  nonempty_body: boolean;
  expected_channel_identity: boolean;
  expected_source_link: boolean;
};

async function invokeWorkIQProbe(): Promise<WorkIQProbeResult> {
  const token = await accessTokenProvider();
  const headers = token ? {Authorization: `Bearer ${token}`} : undefined;
  return json(await fetch(`${API_BASE}/api/diagnostics/workiq-fetch`, {
    method: "POST",
    headers,
  }));
}

export const api = {
  runtime: (): Promise<RuntimeStatus> => get("/api/runtime"),
  createCase: (purpose: CasePurpose): Promise<CaseInstance> =>
    post("/api/cases", {template_id: "RL-001", purpose}),
  analyze: (caseId: string): Promise<AnalysisVersion> =>
    post(`/api/cases/${caseId}/analysis`, {}),
  decide: (caseId: string, input: DecisionInput, key: string): Promise<Decision> =>
    post(`/api/cases/${caseId}/decisions`, input, {"Idempotency-Key": key}),
  decision: (decisionId: string): Promise<Decision> =>
    get(`/api/decisions/${decisionId}`),
  actions: (decisionId: string): Promise<ExecutionAction[]> =>
    get(`/api/decisions/${decisionId}/actions`),
  retryAction: (decisionId: string, actionId: string): Promise<ExecutionAction> =>
    post(`/api/decisions/${decisionId}/actions/${actionId}/retry`, {}),
  drafts: (decisionId: string): Promise<DraftArtifact[]> =>
    get(`/api/decisions/${decisionId}/drafts`),
  retryPlanning: (decisionId: string): Promise<Decision> =>
    post(`/api/decisions/${decisionId}/actions/retry`, {}),
  startPlayback: (decisionId: string): Promise<Playback> =>
    post(`/api/decisions/${decisionId}/playback`, {}),
  playback: (decisionId: string): Promise<Playback> =>
    get(`/api/decisions/${decisionId}/playback`),
  observations: (decisionId: string): Promise<OutcomeObservation[]> =>
    get(`/api/decisions/${decisionId}/observations`),
  invokeWorkIQProbe,
};
