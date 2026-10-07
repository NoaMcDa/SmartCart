import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { ROUTES } from "../e2e/routes";

/**
 * axe-core on every route in tests/e2e/routes.ts, at phone and desktop width, in both themes.
 * Israeli standard 5568 is WCAG 2.0 AA, so the rules run are the wcag2a and wcag2aa tags; a
 * serious or critical violation fails the test. Moderate and minor findings are attached to the
 * report and listed in the test output but do not fail it (docs/a11y-report.md).
 */
const VIEWPORTS = [
  { name: "390 px", width: 390, height: 844 },
  { name: "1280 px", width: 1280, height: 800 },
] as const;
const THEMES = ["light", "dark"] as const;
const BLOCKING = new Set(["serious", "critical"]);

async function openWithTheme(page: Page, path: string, theme: (typeof THEMES)[number]) {
  // The theme script in <head> reads this key before first paint (docs/web.md, "Dark mode").
  await page.addInitScript((value) => {
    try {
      localStorage.setItem("sc-theme", value);
    } catch {
      // storage blocked: the OS preference below still decides
    }
  }, theme);
  await page.emulateMedia({ colorScheme: theme });
  const res = await page.goto(path);
  expect(res?.status()).toBe(200);
  await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
  await page.waitForLoadState("networkidle");
}

for (const viewport of VIEWPORTS) {
  for (const theme of THEMES) {
    test.describe(`${viewport.name}, ${theme} theme`, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } });

      for (const { path } of ROUTES) {
        test(`${path} has no serious or critical WCAG 2.0 AA violation`, async ({ page }, info) => {
          await openWithTheme(page, path, theme);
          const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
          const blocking = results.violations.filter((v) => BLOCKING.has(v.impact ?? ""));
          const rest = results.violations.filter((v) => !BLOCKING.has(v.impact ?? ""));
          if (rest.length > 0) {
            await info.attach("non-blocking-violations.json", {
              body: JSON.stringify(
                rest.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })),
                null,
                2,
              ),
              contentType: "application/json",
            });
          }
          expect(
            blocking.map((v) => ({
              id: v.id,
              impact: v.impact,
              help: v.help,
              targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
            })),
            `${path} at ${viewport.name} in the ${theme} theme`,
          ).toEqual([]);
          // The checks must actually have run: contrast is one of them.
          const ran = [...results.passes, ...results.violations, ...results.incomplete];
          expect(ran.some((r) => r.id === "color-contrast")).toBe(true);
        });
      }
    });
  }
}
