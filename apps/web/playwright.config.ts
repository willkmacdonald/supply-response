import {randomUUID} from "node:crypto";
import {mkdirSync} from "node:fs";
import {resolve} from "node:path";
import {defineConfig, devices} from "@playwright/test";

const repositoryRoot = resolve(import.meta.dirname, "../..");
const temporaryDirectory = resolve(repositoryRoot, ".tmp");
const databasePath = resolve(temporaryDirectory, `e2e-${randomUUID()}.db`);

mkdirSync(temporaryDirectory, {recursive: true});

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 80_000,
  expect: {timeout: 15_000},
  outputDir: resolve(repositoryRoot, ".artifacts/playwright"),
  reporter: "list",
  metadata: {e2eDatabasePath: databasePath},
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "scripts/run_e2e_api.sh",
      cwd: repositoryRoot,
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: false,
      timeout: 30_000,
      gracefulShutdown: {signal: "SIGTERM", timeout: 5_000},
      env: {
        SUPPLY_RESPONSE_RUNTIME_MODE: "fallback",
        SUPPLY_RESPONSE_DATABASE_URL: `sqlite:///${databasePath}`,
        SUPPLY_RESPONSE_AUTOMATED_TEST_FAULTS_ENABLED: "true",
        SUPPLY_RESPONSE_E2E_DATABASE_PATH: databasePath,
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort",
      cwd: import.meta.dirname,
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
