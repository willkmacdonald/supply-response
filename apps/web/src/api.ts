import type {
  InboxCheckResult,
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
  SessionInfo, ProposalState, SubmissionResult, FinanceReviewDetail, ResolutionResult,
  SubmitProposalInput, ResolveFinanceInput, FinalizeProposalInput,
} from "./types";

export const API_BASE = "";

const SAFE_ERROR_MESSAGES = new Map<string, string>([
  ["INBOX_CHECK_UNAVAILABLE", "Email checking is not available right now. Try again shortly."],
  ["INBOX_CHECK_FAILED", "Work IQ could not complete the email check. Please try again."],
  ["INBOUND_EMAIL_CHANGED", "The email changed since you reviewed it. Check email again before creating its case."],
  ["INBOUND_EMAIL_UNSUPPORTED", "This email does not contain a complete, supported disruption. Review its delivery quantity, dates, component, and partial-shipment offer."],
  ["INBOUND_EMAIL_CONFLICT", "The supplier email conflicts with the planning records or the email already used for this case. Review the source details before continuing."],
  ["INBOUND_EMAIL_UNAVAILABLE", "Work IQ could not verify this email. Check email again and retry."],
  ["LIVE_SOURCE_UNAVAILABLE", "The information needed for this analysis could not be retrieved."],
  ["FINANCE_WORKFLOW_DISABLED", "Independent Finance review is not enabled for new commands."],
  ["STALE_PROPOSAL", "The proposal changed. Refresh and reselect the response before continuing."],
  ["FINANCE_COMMAND_CONFLICT", "This Finance command conflicts with the current request. Refresh before continuing."],
  ["FINANCE_FINALIZATION_CONFLICT", "Final approval conflicts with the current proposal. Refresh before continuing."],
  ["ACTION_PLANNING_RETRY_NOT_AVAILABLE", "Independent action planning is not enabled for retry."],
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
  checkInbox: (): Promise<InboxCheckResult> => post("/api/inbox/check", {}),
  createCaseFromEmail: (internetMessageId: string, reviewFingerprint: string): Promise<CaseInstance> =>
    post("/api/inbox/cases", {internet_message_id: internetMessageId, review_fingerprint: reviewFingerprint}),
  me: (): Promise<SessionInfo> => get("/api/me"),
  runtime: (): Promise<RuntimeStatus> => get("/api/runtime"),
  cases: (): Promise<CaseInstance[]> => get("/api/cases"),
  case: (caseId: string): Promise<CaseInstance> => get(`/api/cases/${encodeURIComponent(caseId)}`),
  currentAnalysis: (caseId: string): Promise<AnalysisVersion> =>
    get(`/api/cases/${encodeURIComponent(caseId)}/analysis`),
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
  proposal: (caseId: string): Promise<ProposalState> =>
    get(`/api/cases/${encodeURIComponent(caseId)}/proposal`),
  submitProposal: (caseId: string, input: SubmitProposalInput, key: string): Promise<SubmissionResult> =>
    post(`/api/cases/${encodeURIComponent(caseId)}/proposals`, input, {"Idempotency-Key": key}),
  financeReviews: (): Promise<FinanceReviewDetail[]> => get("/api/finance/reviews"),
  financeReview: (reviewId: string): Promise<FinanceReviewDetail> =>
    get(`/api/finance/reviews/${encodeURIComponent(reviewId)}`),
  resolveFinanceReview: (reviewId: string, input: ResolveFinanceInput, key: string): Promise<ResolutionResult> =>
    post(`/api/finance/reviews/${encodeURIComponent(reviewId)}/resolutions`, input, {"Idempotency-Key": key}),
  finalizeProposal: (caseId: string, input: FinalizeProposalInput, key: string): Promise<Decision> =>
    post(`/api/cases/${encodeURIComponent(caseId)}/proposal-decisions`, input, {"Idempotency-Key": key}),
};
