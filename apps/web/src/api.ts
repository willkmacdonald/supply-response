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

const SAFE_ERROR_MESSAGES = new Map<string, string>([
  ["LIVE_SOURCE_UNAVAILABLE", "The information needed for this analysis could not be retrieved."],
]);
const GENERIC_ERROR_MESSAGE = "The request could not be completed.";

function messageForCode(code: string | null): string {
  return code ? SAFE_ERROR_MESSAGES.get(code) ?? GENERIC_ERROR_MESSAGE : GENERIC_ERROR_MESSAGE;
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export function safeErrorMessage(error: unknown): string {
  return error instanceof ApiRequestError ? messageForCode(error.code) : GENERIC_ERROR_MESSAGE;
}

type AccessTokenProvider = () => Promise<string | null>;
let accessTokenProvider: AccessTokenProvider = async () => null;

export function setAccessTokenProvider(provider: AccessTokenProvider): void {
  accessTokenProvider = provider;
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null) as {detail?: unknown} | null;
    const detail = errorBody?.detail;
    const code = typeof detail === "object" && detail !== null && "code" in detail
      && typeof detail.code === "string" ? detail.code : null;
    throw new ApiRequestError(
      messageForCode(code),
      response.status,
      code,
    );
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

export const api = {
  runtime: (): Promise<RuntimeStatus> => get("/api/runtime"),
  cases: (): Promise<CaseInstance[]> => get("/api/cases"),
  case: (caseId: string): Promise<CaseInstance> => get(`/api/cases/${caseId}`),
  currentAnalysis: (caseId: string): Promise<AnalysisVersion> =>
    get(`/api/cases/${caseId}/analysis`),
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
};
