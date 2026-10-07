import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { resetMeMock } from "../../src/mocks/handlers";
import { resetPhase2Mock } from "../../src/mocks/handlers.phase2";
import { mockApi, openWeeklyResults, pasteList, seedProfile } from "./core-helpers";

/**
 * axe-core (WCAG 2.0 A and AA, the level of Israeli standard 5568) on the phase 2 screens in the
 * states the route-level suite cannot reach: the price history chart, a scan result, alerts with
 * data, the share sheet and the smart cart card, in both themes. Serious and critical findings fail.
 */
const THEMES = ["light", "dark"] as const;

async function axe(page: Page, context: string, include?: string) {
  let builder = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]);
  if (include) builder = builder.include(include);
  const results = await builder.analyze();
  const blocking = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(
    blocking.map((v) => ({
      id: v.id,
      help: v.help,
      targets: v.nodes.slice(0, 4).map((n) => n.target.join(" ")),
    })),
    context,
  ).toEqual([]);
}

for (const theme of THEMES) {
  test.describe(`phase 2 states, ${theme} theme`, () => {
    test.use({ viewport: { width: 390, height: 844 } });

    test.beforeEach(async ({ page }) => {
      resetMeMock();
      resetPhase2Mock();
      await mockApi(page);
      await seedProfile(page);
      await page.addInitScript((t) => localStorage.setItem("sc-theme", t), theme);
      await page.emulateMedia({ colorScheme: theme });
    });

    test("product detail: history chart and the alert form", async ({ page }) => {
      await page.goto("/product/1001?name=" + encodeURIComponent("חלב טרי 3%, 1 ליטר"));
      await page.getByTestId("history-chart").waitFor();
      await page.getByTestId("alert-me").waitFor();
      await axe(page, "history and alert form", "main");
      // With a created alert, the push panel and the existing-alert row.
      const region = page.getByTestId("alert-me");
      await region.getByRole("textbox").fill("0.55");
      await region.getByRole("button", { name: "יצירת התראה" }).click();
      await region.getByTestId("alert-created").waitFor();
      await axe(page, "alert created", "main");
    });

    test("scan: result card and not-found", async ({ page }) => {
      await page.goto("/scan");
      await page.getByRole("textbox", { name: /ברקוד \(13 ספרות/ }).fill("5901234123457");
      await page.getByRole("button", { name: "חיפוש" }).click();
      await page.getByTestId("scan-result").waitFor();
      await page.getByLabel(/המחיר שראית על המדף/).fill("12.90");
      await axe(page, "scan result with a price gap", "main");
      await page.getByRole("textbox", { name: /ברקוד \(13 ספרות/ }).fill("5901234000000");
      await page.getByRole("button", { name: "חיפוש" }).click();
      await page.getByTestId("scan-notfound").waitFor();
      await axe(page, "scan not found", "main");
    });

    test("alerts with data, and the shared list with its share sheet", async ({ page }) => {
      await page.goto("/product/1001?name=" + encodeURIComponent("חלב טרי 3%, 1 ליטר"));
      const region = page.getByTestId("alert-me");
      await region.getByRole("textbox").fill("0.55");
      await region.getByRole("button", { name: "יצירת התראה" }).click();
      await region.getByTestId("alert-created").waitFor();
      await page.goto("/alerts");
      await page.getByTestId("alert-item").waitFor();
      await axe(page, "alerts list", "main");

      await page.goto("/");
      await pasteList(page, "חלב, 2 רסק עגבניות");
      await page.goto("/lists/mine/share");
      await page.getByRole("button", { name: "יצירת רשימה משותפת" }).click();
      await page.getByTestId("shared-item").first().waitFor();
      await axe(page, "shared list", "main");
      await page.getByRole("button", { name: "הזמנת בני משפחה" }).click();
      await page.getByRole("button", { name: "יצירת קישור הזמנה" }).click();
      await page.getByTestId("invite").waitFor();
      await axe(page, "share sheet", "[role=dialog]");
    });

    test("results: the smart cart card", async ({ page }) => {
      await openWeeklyResults(page);
      await page.getByTestId("smart-cart").waitFor();
      await axe(page, "smart cart", "[data-testid=smart-cart]");
      await page.getByRole("button", { name: "לא עכשיו" }).click();
      await page.getByRole("button", { name: /החליפי ל/ }).click();
      await page.getByTestId("smart-cart-applied").waitFor();
      await axe(page, "smart cart after applying", "[data-testid=smart-cart]");
    });
  });
}
