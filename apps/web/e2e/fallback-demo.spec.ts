import {expect, test} from "@playwright/test";

test("RL-001 fallback journey reaches simulated outcomes", async ({page}) => {
  await page.goto("/");
  await expect(page.getByText("Fallback mode")).toBeVisible();
  await page.getByRole("button", {name: "Create showcase case"}).click();
  await page.getByRole("button", {name: "Analyze disruption"}).click();
  await expect(page.getByRole("heading", {name: "Combined response"})).toBeVisible();
  await page.getByRole("button", {name: "Approve combined response"}).click();
  await expect(page.getByText("Action planning is pending.")).toBeVisible();
  await expect(page.getByTestId("decision-receipt")).toContainText("RL-DECISION-");
  await expect(page.getByTestId("execution-action")).toHaveCount(5);
  await expect(page.getByText("Not sent")).toBeVisible();
  await page.getByRole("button", {name: "Run simulated coordination"}).click();
  await expect(page.getByText("Simulated results")).toBeVisible({timeout: 65_000});
  await expect(page.getByTestId("outcome-observation")).toHaveCount(5, {timeout: 65_000});
  await expect(page.getByText("Power BI unavailable in fallback")).toBeVisible();
});
