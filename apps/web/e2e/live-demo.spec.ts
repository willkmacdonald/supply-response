import {execFileSync} from "node:child_process";
import {resolve} from "node:path";
import {expect, test} from "@playwright/test";

type Evidence = {source_system: string; source_id: string; excerpt: string; navigable_citation_url: string; citation_classification: string};

function verifyWorkIqArtifact(item: Evidence): void {
  const script = resolve(import.meta.dirname, "../scripts/verify-workiq-citations.mjs");
  const output = execFileSync("node", [script, process.env.SUPPLY_RESPONSE_ALEX_STORAGE_STATE!, process.env.SUPPLY_RESPONSE_TENANT_SHAREPOINT_HOST!], {
    encoding: "utf8",
    input: JSON.stringify({url: item.navigable_citation_url, expectedExcerpt: item.excerpt, sourceIdentity: item.source_id}),
    stdio: ["pipe", "pipe", "pipe"],
    timeout: 30_000,
  });
  expect(JSON.parse(output)).toMatchObject({ok: true, sourceIdentity: item.source_id});
}

test("canonical live showcase journey", async ({page, context}) => {
  // The configuration gate runs before servers/browser and disables every raw artifact.
  const runtime = await page.request.get("/api/runtime").then((response) => response.json());
  expect(runtime.runtime_mode).toBe("live");
  expect(runtime.capability_health).toEqual({
    operational_store: "ready",
    work_iq: "ready",
    agent_runtime: "ready",
    power_bi: "ready",
  });
  expect(runtime.deployment_contract).toMatchObject({
    scenario_effective_time: process.env.SUPPLY_RESPONSE_EXPECTED_SCENARIO_EFFECTIVE_TIME,
    corpus_version: process.env.SUPPLY_RESPONSE_EXPECTED_CORPUS_VERSION,
    supplier_source_id: process.env.SUPPLY_RESPONSE_EXPECTED_SUPPLIER_SOURCE_ID,
    quality_source_id: process.env.SUPPLY_RESPONSE_EXPECTED_QUALITY_SOURCE_ID,
    signal_agent_version: process.env.SUPPLY_RESPONSE_EXPECTED_SIGNAL_AGENT_VERSION,
    context_agent_version: process.env.SUPPLY_RESPONSE_EXPECTED_CONTEXT_AGENT_VERSION,
    decision_agent_version: process.env.SUPPLY_RESPONSE_EXPECTED_DECISION_AGENT_VERSION,
  });

  await page.goto("/?purpose=showcase");
  await expect(page.getByText("Live-service mode")).toBeVisible();
  await page.getByRole("button", {name: "Create showcase case"}).click();
  await page.getByRole("button", {name: "Analyze disruption"}).click();
  await expect(page.getByRole("heading", {name: "Evidence items"})).toBeVisible({timeout: 90_000});
  await expect(page.getByText("Required live citation missing")).toHaveCount(0);

  const caseId = (await page.locator(".case-id").textContent())!.trim();
  const analysis = await page.request.get(`/api/cases/${caseId}/analysis`).then((response) => response.json());
  expect(analysis.scenario_effective_time).toBe(process.env.SUPPLY_RESPONSE_EXPECTED_SCENARIO_EFFECTIVE_TIME);
  const supplier = analysis.evidence_items.find((item: Evidence) => item.source_id === process.env.SUPPLY_RESPONSE_EXPECTED_SUPPLIER_SOURCE_ID);
  const quality = analysis.evidence_items.find((item: Evidence) => item.source_id === process.env.SUPPLY_RESPONSE_EXPECTED_QUALITY_SOURCE_ID);
  expect(supplier?.citation_classification).toBe("work_iq");
  expect(quality?.citation_classification).toBe("work_iq");
  verifyWorkIqArtifact(supplier);
  verifyWorkIqArtifact(quality);
  for (const item of analysis.evidence_items.filter((value: Evidence) => value.citation_classification === "fabric")) {
    expect(new URL(item.navigable_citation_url).hostname).toBe("app.powerbi.com");
  }

  await page.getByRole("button", {name: /Approve combine/i}).click();
  const receipt = page.getByTestId("decision-receipt");
  await expect(receipt).toBeVisible({timeout: 15_000});
  const decisionId = (await receipt.getByText(/^Decision RL-DECISION-/).textContent())!.replace("Decision ", "");
  const decision = await page.request.get(`/api/decisions/${decisionId}`).then((response) => response.json());
  expect(decision.analysis_id).toBe(analysis.analysis_id);
  await expect(page.getByTestId("execution-action")).toHaveCount(5, {timeout: 15_000});
  const actions = await page.request.get(`/api/decisions/${decisionId}/actions`).then((response) => response.json());
  expect(actions).toHaveLength(5);
  expect(actions.every((item: {decision_id: string}) => item.decision_id === decisionId)).toBe(true);
  await page.getByRole("button", {name: /Start simulated playback/i}).click();
  await expect(page.getByText("Simulated", {exact: true}).first()).toBeVisible({timeout: 65_000});
  const observations = await page.request.get(`/api/decisions/${decisionId}/observations`).then((response) => response.json());
  expect(observations.every((item: {decision_id: string}) => item.decision_id === decisionId)).toBe(true);

  const report = page.getByRole("link", {name: "Open Power BI command center"});
  await expect(report).toBeVisible();
  const reportPagePromise = context.waitForEvent("page");
  await report.click();
  const reportPage = await reportPagePromise;
  await expect(reportPage.getByText(decisionId, {exact: false})).toBeVisible({timeout: 60_000});
});
