import { defineConfig, devices } from "@playwright/test";

/**
 * Full-stack end-to-end tests (docs/fullstack.md): the production build of the web app against
 * the REAL FastAPI and a real Postgres, both started by `scripts/demo/up.sh` on synthetic data.
 * Nothing is mocked except the Supabase Auth server, which the demo does not run (see
 * tests/fullstack/helpers.ts, `signIn`).
 *
 *   scripts/demo/up.sh                 # from the repo root: database, pipeline, API on :8000
 *   cd apps/web && npm run e2e:fullstack
 *
 * The web server builds the app first, because NEXT_PUBLIC_* values are inlined at build time
 * (the build replaces .next; run `npm run build` again before the mock e2e suite). Set
 * FULLSTACK_SKIP_BUILD=1 to reuse a build made with the same variables.
 *
 * Environment: DEMO_API_BASE_URL (default http://127.0.0.1:8000), FULLSTACK_WEB_PORT (3200),
 * SUPABASE_JWT_SECRET (the secret up.sh gave the API; default: the demo secret).
 */
const PORT = Number(process.env.FULLSTACK_WEB_PORT ?? 3200);
const API_BASE_URL = (process.env.DEMO_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const isCI = Boolean(process.env.CI);

/** Build-time variables of the app under test. */
const appEnv = {
  NEXT_TELEMETRY_DISABLED: "1",
  NEXT_PUBLIC_API_MOCK: "0",
  NEXT_PUBLIC_API_BASE_URL: API_BASE_URL,
  // A Supabase URL the tests answer themselves: the app reads the session from storage, so a
  // signed-in test only needs a stored session whose access token the real API accepts.
  NEXT_PUBLIC_SUPABASE_URL: "http://127.0.0.1:54321",
  NEXT_PUBLIC_SUPABASE_ANON_KEY: "demo-anon-key",
  // No service worker: every navigation must reach the server under test.
  NEXT_PUBLIC_DISABLE_SW: "1",
};

const build = process.env.FULLSTACK_SKIP_BUILD === "1" ? "" : "npm run build && ";

export default defineConfig({
  testDir: "./tests/fullstack",
  globalSetup: "./tests/fullstack/global-setup.ts",
  // One shared database: the specs run one after another, in file order.
  fullyParallel: false,
  workers: 1,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: isCI
    ? [["list"], ["html", { open: "never", outputFolder: "playwright-report/fullstack" }]]
    : [["list"]],
  outputDir: "test-results/fullstack",
  use: {
    baseURL: `http://localhost:${PORT}`,
    locale: "he-IL",
    timezoneId: "Asia/Jerusalem",
    trace: "retain-on-failure",
    launchOptions: process.env.PW_CHROMIUM_PATH
      ? { executablePath: process.env.PW_CHROMIUM_PATH }
      : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `${build}node node_modules/next/dist/bin/next start -p ${PORT}`,
    url: `http://localhost:${PORT}/manifest.webmanifest`,
    reuseExistingServer: !isCI,
    timeout: 600_000,
    env: appEnv,
  },
});
