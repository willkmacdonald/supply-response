import {chromium} from "@playwright/test";
import process from "node:process";

import {evaluateArtifactView} from "./citation-verification-policy.mjs";

const [storageState, tenantSharePointHost] = process.argv.slice(2);

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const {url, expectedExcerpt, sourceIdentity} = JSON.parse(
  Buffer.concat(chunks).toString("utf8"),
);

const browser = await chromium.launch({headless: true});
try {
  const context = await browser.newContext({storageState});
  const page = await context.newPage();
  const navigationUrls = [];
  let status = 0;
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) navigationUrls.push(frame.url());
  });
  page.on("response", (candidate) => {
    const request = candidate.request();
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) {
      status = candidate.status();
      navigationUrls.push(candidate.url());
    }
  });
  const response = await page.goto(url, {waitUntil: "domcontentloaded", timeout: 30_000});
  const serverRedirectChain = [];
  for (let request = response?.request(); request; request = request.redirectedFrom()) {
    serverRedirectChain.push(request.url());
  }
  navigationUrls.push(...serverRedirectChain.reverse());
  status ||= response?.status() ?? 0;
  try {
    await page.waitForFunction(
      (excerpt) => {
        const normalize = (value) =>
          String(value ?? "")
            .normalize("NFKC")
            .toLocaleLowerCase("en-US")
            .replace(/\s+/gu, " ")
            .trim();
        return normalize(document.body?.innerText).includes(normalize(excerpt));
      },
      expectedExcerpt,
      {timeout: 15_000},
    );
  } catch {
    // The pure policy below reports the precise fail-closed reason.
  }
  const finalUrl = page.url();
  const bodyText = await page.locator("body").innerText({timeout: 5_000}).catch(() => "");
  const result = evaluateArtifactView({
    status,
    navigationUrls: [...new Set(navigationUrls)],
    finalUrl,
    bodyText,
    expectedExcerpt,
    sourceIdentity,
    tenantSharePointHost,
  });
  process.stdout.write(JSON.stringify({...result, status, finalUrl}));
} finally {
  await browser.close();
}
