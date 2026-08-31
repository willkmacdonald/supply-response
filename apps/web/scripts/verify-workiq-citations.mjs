import {chromium} from "@playwright/test";
import process from "node:process";

const [storageState, tenantSharePointHost] = process.argv.slice(2);
const approvedHosts = new Set([
  "teams.microsoft.com",
  "outlook.office.com",
  "outlook.office365.com",
  tenantSharePointHost?.toLowerCase(),
]);

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const {url} = JSON.parse(Buffer.concat(chunks).toString("utf8"));

function trusted(rawUrl) {
  try {
    const parsed = new URL(rawUrl);
    return parsed.protocol === "https:" && approvedHosts.has(parsed.hostname.toLowerCase());
  } catch {
    return false;
  }
}

const browser = await chromium.launch({headless: true});
try {
  const context = await browser.newContext({storageState});
  const page = await context.newPage();
  const response = await page.goto(url, {waitUntil: "domcontentloaded", timeout: 30_000});
  const chain = [];
  for (let request = response?.request(); request; request = request.redirectedFrom()) {
    chain.push(request.url());
  }
  const status = response?.status() ?? 0;
  const finalUrl = page.url();
  const ok = status >= 200 && status < 300 && trusted(finalUrl) && chain.every(trusted);
  process.stdout.write(JSON.stringify({ok, status, finalUrl}));
} finally {
  await browser.close();
}
