import {expect, test, type Page, type Response} from "@playwright/test";

async function createAutomatedTestCase(page: Page): Promise<string> {
  await page.goto("/?purpose=automated_test");
  await page.waitForLoadState("networkidle");
  await expect(page.getByText("Fallback mode")).toBeVisible();
  await expect(page.getByText("Power BI unavailable in fallback")).toBeVisible();
  await page.getByRole("button", {name: "Create automated test case"}).click();
  const caseId = await page.locator(".case-id").textContent();
  expect(caseId).toMatch(/^RL-CASE-/);
  return caseId!;
}

async function analyze(page: Page): Promise<void> {
  await page.getByRole("button", {name: "Analyze disruption"}).click();
  await expect(page.getByRole("heading", {name: "Combined response"})).toBeVisible();
}

async function approve(page: Page): Promise<void> {
  await page.getByRole("button", {name: "Approve combined response"}).click();
  await expect(page.getByTestId("decision-receipt")).toContainText("RL-DECISION-");
}

async function armFault(page: Page, caseId: string, fault: string): Promise<void> {
  const response = await page.request.post(`/api/test/cases/${caseId}/faults/${fault}`);
  expect(response.status()).toBe(204);
}

test("rejection keeps evidence visible and permits reanalysis", async ({page}) => {
  await createAutomatedTestCase(page);
  await analyze(page);
  await page.getByLabel("Rejection reason").fill("Refresh the supplier evidence before deciding.");
  await page.getByRole("button", {name: "Reject recommendation"}).click();
  await expect(page.getByTestId("decision-receipt")).toContainText("Rejected");
  await expect(page.getByRole("heading", {name: "Evidence items"})).toBeVisible();

  await page.getByRole("button", {name: "Analyze disruption"}).click();
  await expect(page.getByRole("heading", {name: "Decision"})).toBeVisible();
  await expect(page.getByRole("button", {name: "Approve combined response"})).toBeEnabled();
  await expect(page.getByTestId("decision-receipt")).toHaveCount(0);
});

test("the server blocks a stale analysis without recording a Decision", async ({page}) => {
  const caseId = await createAutomatedTestCase(page);
  await analyze(page);
  const newerAnalysis = await page.request.post(`/api/cases/${caseId}/analysis`, {data: {}});
  expect(newerAnalysis.status()).toBe(201);

  await page.getByRole("button", {name: "Approve combined response"}).click();
  await expect(page.getByRole("alert")).toContainText("STALE_ANALYSIS");
  await expect(page.getByTestId("decision-receipt")).toHaveCount(0);
});

test("planning failure is visible and the one-shot retry creates five actions", async ({page}) => {
  const caseId = await createAutomatedTestCase(page);
  await armFault(page, caseId, "planning_failure");
  await analyze(page);
  await approve(page);
  await expect(page.getByText("Approved — action planning failed")).toBeVisible();

  await page.getByRole("button", {name: "Retry action planning"}).click();
  await expect(page.getByTestId("execution-action")).toHaveCount(5);
  await expect(page.getByText("Approved — action planning failed")).toHaveCount(0);
});

test("a failed child action retries without replacing sibling actions", async ({page}) => {
  const caseId = await createAutomatedTestCase(page);
  await armFault(page, caseId, "first_action_failure");
  await analyze(page);
  await approve(page);
  await expect(page.getByTestId("execution-action")).toHaveCount(5);
  const actionIdsBefore = await page.getByTestId("execution-action").locator("small").allTextContents();
  expect(new Set(actionIdsBefore).size).toBe(5);

  const failedAction = page.getByTestId(/execution-action-RL-ACTION-/).filter({hasText: "failed"});
  await expect(failedAction).toHaveCount(1);
  const actionTestId = await failedAction.getAttribute("data-testid");
  expect(actionTestId).toBeTruthy();
  await failedAction.getByRole("button", {name: /Retry prepare alpha recovery draft/}).click();
  await expect(page.getByTestId(actionTestId!)).toContainText("in_progress");
  await expect(page.getByTestId("execution-action")).toHaveCount(5);
  const actionIdsAfter = await page.getByTestId("execution-action").locator("small").allTextContents();
  expect(new Set(actionIdsAfter).size).toBe(5);
  expect(actionIdsAfter.sort()).toEqual(actionIdsBefore.sort());
});

test("duplicate playback clicks coalesce into one operation and no duplicate outcomes", async ({page}) => {
  await createAutomatedTestCase(page);
  await analyze(page);
  await approve(page);
  await expect(page.getByTestId("execution-action")).toHaveCount(5);

  const responses: Response[] = [];
  page.on("response", (response) => {
    if (response.request().method() === "POST" && response.url().endsWith("/playback")) {
      responses.push(response);
    }
  });
  const start = page.getByRole("button", {name: "Start simulated execution"});
  await start.evaluate((button: HTMLButtonElement) => {
    button.click();
    button.click();
  });
  await expect.poll(() => responses.length).toBe(1);
  await expect(page.getByTestId("outcome-observation")).toHaveCount(10, {timeout: 65_000});
});
