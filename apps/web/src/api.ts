import type { AnalyzeResponse, CaseDetail, DashboardSummary, DecisionResponse } from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }
  return (await response.json()) as T;
}

export const api = {
  createCase: (disruptionId = 'RL-001') =>
    request<CaseDetail>('/api/cases', {
      method: 'POST',
      body: JSON.stringify({ disruption_id: disruptionId })
    }),

  getCase: (caseId: string) => request<CaseDetail>(`/api/cases/${caseId}`),

  analyze: (caseId: string) =>
    request<AnalyzeResponse>(`/api/cases/${caseId}/analyze`, { method: 'POST' }),

  approve: (caseId: string, scenarioId: string, rationale: string) =>
    request<DecisionResponse>(`/api/cases/${caseId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ scenario_id: scenarioId, decided_by: 'Alex Morgan', rationale })
    }),

  reject: (caseId: string, scenarioId: string, rationale: string) =>
    request<DecisionResponse>(`/api/cases/${caseId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ scenario_id: scenarioId, decided_by: 'Alex Morgan', rationale })
    }),

  dashboard: () => request<DashboardSummary>('/api/dashboard/summary')
};

export const currency = (value: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
