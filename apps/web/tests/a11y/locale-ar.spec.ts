import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/**
 * axe-core on the app shell in Arabic (#73), light and dark, at phone and desktop width. Same rules
 * as axe.spec.ts: WCAG 2.0 A and AA, serious or critical fails. Uses the test-only /locale-test
 * page, which renders the real shell plus the language switch.
 */
const VIEWPORTS = [
  { name: "390 px", width: 390, height: 844 },
  { name: "1280 px", width: 1280, height: 800 },
] as const;
const THEMES = ["light", "dark"] as const;
const BLOCKING = new Set(["serious", "critical"]);

for (const viewport of VIEWPORTS) {
  for (const theme of THEMES) {
    test(`Arabic shell at ${viewport.name}, ${theme} theme has no serious or critical violation`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.addInitScript((t) => {
        try {
          localStorage.setItem("sc-theme", t);
          localStorage.setItem("sc-locale", "ar");
        } catch {
          // storage blocked: the assertion on <html lang> below fails loudly
        }
      }, theme);
      await page.emulateMedia({ colorScheme: theme });
      const res = await page.goto("/locale-test");
      expect(res?.status()).toBe(200);
      await expect(page.locator("html")).toHaveAttribute("lang", "ar");
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await page.waitForLoadState("networkidle");

      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      const blocking = results.violations.filter((v) => BLOCKING.has(v.impact ?? ""));
      expect(
        blocking.map((v) => ({
          id: v.id,
          impact: v.impact,
          help: v.help,
          targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
        })),
      ).toEqual([]);
      const ran = [...results.passes, ...results.violations, ...results.incomplete];
      expect(ran.some((r) => r.id === "color-contrast")).toBe(true);
    });
  }
}
