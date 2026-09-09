import {mkdirSync} from "node:fs";
import {resolve} from "node:path";
import {expect, test, type Page, type Route} from "@playwright/test";

const artifacts = resolve(import.meta.dirname, "../../../.artifacts/planner-presentation");
const powerBi = "https://app.powerbi.com/groups/dc3ac590-d892-40a7-9388-65dec120d67a/reports/e7611c8c-c887-443f-858a-13b1044bb4b9";
const email = "https://outlook.office.com/mail/deeplink/read/fixture-alpha";
const teams = "https://teams.microsoft.com/l/message/19%3Ademo%40thread.tacv2/1788577543694?groupId=11111111-2222-3333-4444-555555555555&tenantId=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee&createdTime=1788577543694&parentMessageId=1788577543694";

function recordSource(id: string): string {
  if (id === "RL-ALPHA-OPTIONAL-3000") return "fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000";
  if (id === "RL-TRANSFER-DAL-CHI-1500") return "fabric.inventory_transfer/RL-TRANSFER-DAL-CHI-1500";
  return "fabric.qualification/RL-QUAL-BETA";
}

async function fixtureAnalysis(route: Route) {
  const response = await route.fetch();
  const analysis = await response.json();
  analysis.runtime_mode = "live";
  analysis.material.runtime_mode = "live";
  const snapshot = JSON.parse(analysis.material.operational_snapshot_json);
  snapshot.runtime_mode = "live";
  analysis.material.operational_snapshot_json = JSON.stringify(snapshot);
  const transformRecord = (item: Record<string, unknown>) => ({
    ...item, runtime_mode: "live", synthetic: false, source_system: "fabric",
    source_id: recordSource(String(item.evidence_id)), citation_url: powerBi,
    navigable_citation_url: powerBi, citation_classification: "fabric",
  });
  analysis.evidence_items = analysis.evidence_items.map(transformRecord);
  analysis.material.evidence = analysis.material.evidence.map(transformRecord);
  const at = analysis.analysis_started_at;
  const statement = (quality: boolean) => ({
    evidence_id: quality ? "RL-E-WORKIQ-BETA-1" : "RL-E-WORKIQ-ALPHA-1",
    case_id: analysis.case_id, kind: "source_statement",
    authority_scope: [quality ? "collaboration_statement" : "supplier_statement"],
    source_system: "work_iq", source_id: quality ? "fixture-source-beta-quality" : "fixture-source-alpha",
    source_timestamp: at, retrieved_at: at, retrieved_for_analysis_id: analysis.analysis_id,
    retrieval_health: "healthy", effective_at: analysis.scenario_effective_time, expires_at: null,
    claim: quality
      ? "RL-Supplier Beta qualification is pending; the audit and first article are incomplete; September 15 is the next fictional-scenario review date."
      : "RL-Supplier Alpha cannot deliver 8,000 units on Scenario Day 2 and offers 3,000 units by air on September 6 at $7.50 per unit; the remaining 5,000 units have no confirmed date.",
    excerpt: quality
      ? "Qualification remains pending. The audit and first article are incomplete. The next fictional-scenario review date is September 15."
      : "We cannot deliver the full 8,000 units on Scenario Day 2. We can offer 3,000 units by air on September 6 at $7.50 per unit.",
    citation_url: quality ? teams : email, navigable_citation_url: quality ? teams : email,
    citation_classification: "work_iq", citation_trusted_host: null,
    runtime_mode: "live", synthetic: false,
    requirement: quality ? "contextual" : "required_authoritative", uncertainty_state: "certain",
  });
  for (const item of [statement(false), statement(true)]) {
    analysis.evidence_items.push(item);
    analysis.material.evidence.push({...item, citation_present: true, source_metadata_complete: true});
    const validation = {
      evidence_id: item.evidence_id, requirement: item.requirement,
      validated_authority_scope: item.authority_scope, freshness: "current",
      business_validity: "valid", uncertainty_state: "certain", retrieval_health: "healthy",
      authoritative: item.requirement === "required_authoritative", blocking_codes: [],
    };
    analysis.evidence_validation.item_results.push(validation);
    analysis.material.evidence_validation.item_results.push(validation);
  }
  await route.fulfill({response, json: analysis});
}

async function openFixture(page: Page) {
  await page.route("**/api/runtime", route => route.fulfill({json: {
    runtime_mode: "live", work_iq: "work_iq", operational_store: "fabric_sql",
    agent_runtime: "foundry", power_bi_available: false, power_bi_url: null,
    deployment_contract: {tenant_sharepoint_host: "tenant.sharepoint.com"},
  }}));
  await page.route("**/api/cases", async route => {
    const response = await route.fetch();
    const body = await response.json();
    body.runtime_mode = "live";
    await route.fulfill({response, json: body});
  });
  await page.route("**/api/cases/*/analysis", fixtureAnalysis);
  await page.goto("/?purpose=automated_test");
  await page.getByRole("button", {name: "Create automated test case"}).click();
  await page.getByRole("button", {name: "Analyze disruption"}).click();
  await expect(page.getByRole("heading", {name: "Recommended response—and why.", exact: true})).toBeVisible();
}

async function verifyCard(page: Page, heading: string) {
  const card = page.locator("article.evidence-card").filter({has: page.getByRole("heading", {name: heading, exact: true})});
  const footer = card.locator(":scope > .source-footers");
  await expect(footer).toHaveCount(1);
  expect(await card.evaluate(node => node.lastElementChild?.classList.contains("source-footers"))).toBe(true);
  const title = await card.locator("h3").boundingBox();
  const status = await footer.boundingBox();
  expect(title).not.toBeNull(); expect(status).not.toBeNull();
  expect(status!.y).toBeGreaterThan(title!.y + title!.height);
  for (const link of await card.locator("a").all()) {
    const box = await link.boundingBox();
    if (box) expect(status!.y).toBeGreaterThanOrEqual(box.y + box.height);
  }
  const contentBottom = await card.locator(":scope > *:not(.source-footers)").evaluateAll(nodes =>
    Math.max(...nodes.filter(node => (node as HTMLElement).offsetParent !== null)
      .map(node => node.getBoundingClientRect().bottom)));
  expect(status!.y).toBeGreaterThanOrEqual(contentBottom);
  expect(await card.locator(".badge").evaluateAll(nodes =>
    nodes.every(node => Boolean(node.closest("footer"))))).toBe(true);
}

for (const viewport of [
  {name: "desktop", width: 1440, height: 1000},
  {name: "mobile", width: 390, height: 844},
]) {
  test(`business cards keep source status at the bottom on ${viewport.name}`, async ({page}) => {
    mkdirSync(artifacts, {recursive: true});
    await page.setViewportSize(viewport);
    await openFixture(page);
    await expect(page.getByText("Demo corpus — fictional", {exact: true}).first()).toBeVisible();
    const changed = page.locator("article.evidence-card").filter({has: page.getByRole("heading", {name: "What changed?", exact: true})});
    await expect(changed.getByText(/Original delivery: 8,000 component units of RL-MAT-10247 were due at Chicago plant on September 3, 2026/)).toBeVisible();
    await expect(changed.getByRole("link", {name: "Open supplier email"})).toBeVisible();
    await expect(changed.getByText(/Saved disruption:|Recorded partial supply:/)).toHaveCount(0);
    for (const label of ["View shipment record", "View transfer record", "View qualification record"]) {
      await page.getByText(label, {exact: true}).click();
    }
    for (const heading of [
      "What changed?", "What can Supplier Alpha still supply?",
      "Can another plant help?", "Can we use the alternate supplier?",
    ]) await verifyCard(page, heading);
    await expect(page.getByText("Work IQ", {exact: true}).first()).toBeVisible();
    await expect(page.getByText("Microsoft Fabric", {exact: true}).first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.getByRole("region", {name: "1. Understand the disruption", exact: true})
      .screenshot({path: resolve(artifacts, `${viewport.name}-understand-row.png`)});
    await changed.screenshot({path: resolve(artifacts, `${viewport.name}-original-delivery-card.png`)});
    await page.locator("article.evidence-card").filter({has: page.getByRole("heading", {name: "What can Supplier Alpha still supply?", exact: true})})
      .screenshot({path: resolve(artifacts, `${viewport.name}-recovery-card.png`)});
    await page.locator("article.evidence-card").filter({has: page.getByRole("heading", {name: "Can we use the alternate supplier?", exact: true})})
      .screenshot({path: resolve(artifacts, `${viewport.name}-qualification-card.png`)});
    await page.screenshot({path: resolve(artifacts, `${viewport.name}.png`), fullPage: true});
  });
}
