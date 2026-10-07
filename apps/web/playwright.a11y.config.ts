import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.A11Y_PORT ?? 3101);
const isCI = Boolean(process.env.CI);

/**
 * Accessibility suite (issue #26): axe-core on every route at 390 px and 1280 px in both themes,
 * plus keyboard, focus, target-size and reflow checks. Runs against the production build like
 * the e2e suite (`npm run build` first) but on its own port and config, so `npm run e2e` stays
 * fast. `npm run a11y` runs it; CI has a separate `a11y` job.
 */
export default defineConfig({
  testDir: "./tests/a11y",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  workers: isCI ? 2 : undefined,
  timeout: 45_000,
  reporter: isCI
    ? [["list"], ["html", { open: "never", outputFolder: "playwright-report-a11y" }]]
    : [["list"]],
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
    command: `node node_modules/next/dist/bin/next start -p ${PORT}`,
    url: `http://localhost:${PORT}/manifest.webmanifest`,
    reuseExistingServer: !isCI,
    timeout: 60_000,
    env: { NEXT_TELEMETRY_DISABLED: "1" },
  },
});
