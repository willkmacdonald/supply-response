import {statSync} from "node:fs";
import {resolve} from "node:path";
import {expect, test} from "@playwright/test";

const required = [
  "SUPPLY_RESPONSE_LIVE_E2E",
  "SUPPLY_RESPONSE_LIVE_BASE_URL",
  "SUPPLY_RESPONSE_ALEX_STORAGE_STATE",
  "SUPPLY_RESPONSE_EXPECTED_CORPUS_VERSION",
  "SUPPLY_RESPONSE_EXPECTED_SIGNAL_AGENT_VERSION",
  "SUPPLY_RESPONSE_EXPECTED_CONTEXT_AGENT_VERSION",
  "SUPPLY_RESPONSE_EXPECTED_DECISION_AGENT_VERSION",
] as const;

function liveGate(): {ready: true; storageState: string} | {ready: false; reason: string} {
  const missing = required.filter((name) => !process.env[name]);
  if (missing.length || process.env.SUPPLY_RESPONSE_LIVE_E2E !== "1") {
    return {ready: false, reason: `live prerequisites are incomplete: ${missing.join(", ")}`};
  }
  const base = new URL(process.env.SUPPLY_RESPONSE_LIVE_BASE_URL!);
  if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash) {
    return {ready: false, reason: "live base URL is not exact trusted HTTPS"};
  }
  const state = resolve(process.env.SUPPLY_RESPONSE_ALEX_STORAGE_STATE!);
  try {
    if ((statSync(state).mode & 0o077) !== 0) {
      return {ready: false, reason: "Alex storage state must be owner-only"};
    }
  } catch {
    return {ready: false, reason: "Alex storage state is unavailable"};
  }
  return {ready: true, storageState: state};
}

const gate = liveGate();
test.skip(!gate.ready, gate.ready ? undefined : gate.reason);

test("canonical live showcase journey", async ({page, context}) => {
  // This project disables trace, screenshot and video collection so bearer-bearing
  // request headers can never enter Playwright artifacts.
  await page.goto("/?purpose=showcase");
  await expect(page.getByText("Live mode")).toBeVisible();
  await page.getByRole("button", {name: "Create showcase case"}).click();
  await page.getByRole("button", {name: "Analyze disruption"}).click();
  await expect(page.getByRole("heading", {name: "Evidence items"})).toBeVisible({timeout: 90_000});
  await expect(page.getByText("Required live citation missing")).toHaveCount(0);

  for (const citation of await page.getByRole("link", {name: "Open citation"}).all()) {
    const target = await citation.getAttribute("href");
    expect(target).toMatch(new RegExp("^https://(?:teams\\.microsoft\\.com|outlook\\.office(?:365)?\\.com|[^.]+\\.sharepoint\\.com)/"));
  }

  await page.getByRole("button", {name: /Approve combine/i}).click();
  const receipt = page.getByTestId("decision-receipt");
  await expect(receipt).toBeVisible({timeout: 15_000});
  const decisionId = (await receipt.getByText(/^Decision RL-DECISION-/).textContent())!.replace("Decision ", "");
  await expect(page.getByTestId("execution-action")).toHaveCount(5, {timeout: 15_000});
  await page.getByRole("button", {name: /Start simulated playback/i}).click();
  await expect(page.getByText("Simulated", {exact: true}).first()).toBeVisible({timeout: 65_000});

  const report = page.getByRole("link", {name: "Open Power BI command center"});
  await expect(report).toBeVisible();
  const reportPagePromise = context.waitForEvent("page");
  await report.click();
  const reportPage = await reportPagePromise;
  await expect(reportPage.getByText(decisionId, {exact: false})).toBeVisible({timeout: 60_000});
});
