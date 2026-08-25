import type { Disruption, SupplyResponseCase } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export async function createCase(disruption: Disruption): Promise<SupplyResponseCase> {
  return json(await fetch(`${API_BASE}/api/cases`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({disruption})}));
}

export async function getCase(caseId: string): Promise<SupplyResponseCase> {
  return json(await fetch(`${API_BASE}/api/cases/${caseId}`));
}
