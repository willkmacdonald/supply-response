import {statSync} from "node:fs";
import {resolve} from "node:path";

const required = [
  "SUPPLY_RESPONSE_LIVE_E2E",
  "SUPPLY_RESPONSE_LIVE_BASE_URL",
  "SUPPLY_RESPONSE_EXPECTED_DEPLOYMENT_ORIGIN",
  "SUPPLY_RESPONSE_ALEX_STORAGE_STATE",
  "SUPPLY_RESPONSE_EXPECTED_SCENARIO_EFFECTIVE_TIME",
  "SUPPLY_RESPONSE_EXPECTED_CORPUS_VERSION",
  "SUPPLY_RESPONSE_EXPECTED_SUPPLIER_SOURCE_ID",
  "SUPPLY_RESPONSE_EXPECTED_QUALITY_SOURCE_ID",
  "SUPPLY_RESPONSE_EXPECTED_SIGNAL_AGENT_VERSION",
  "SUPPLY_RESPONSE_EXPECTED_CONTEXT_AGENT_VERSION",
  "SUPPLY_RESPONSE_EXPECTED_DECISION_AGENT_VERSION",
  "SUPPLY_RESPONSE_TENANT_SHAREPOINT_HOST",
] as const;

export interface ResolvedLiveGate {baseURL: string; storageState: string}

export function resolveLiveGate(env: NodeJS.ProcessEnv): ResolvedLiveGate {
  const missing = required.filter((name) => !env[name]);
  if (env.SUPPLY_RESPONSE_LIVE_E2E !== "1" || missing.length) {
    throw new Error(`live preflight failed: ${missing.join(", ")}`);
  }
  const base = new URL(env.SUPPLY_RESPONSE_LIVE_BASE_URL!);
  const expected = new URL(env.SUPPLY_RESPONSE_EXPECTED_DEPLOYMENT_ORIGIN!);
  if (base.origin !== expected.origin || base.href !== `${base.origin}/` || expected.href !== `${expected.origin}/` || base.protocol !== "https:" || base.username || base.password || base.port) {
    throw new Error("live preflight failed: deployment origin is not exact");
  }
  if (env.SUPPLY_RESPONSE_EXPECTED_SCENARIO_EFFECTIVE_TIME !== "2026-09-01T09:00:00-05:00") {
    throw new Error("live preflight failed: Scenario Effective Time is not pinned");
  }
  const storageState = resolve(env.SUPPLY_RESPONSE_ALEX_STORAGE_STATE!);
  const stat = statSync(storageState);
  if (!stat.isFile() || (stat.mode & 0o077) !== 0) {
    throw new Error("live preflight failed: Alex storage state must be owner-only");
  }
  return {baseURL: base.href, storageState};
}
