import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mockApi, openWeeklyResults } from "./core-helpers";
import { noHorizontalScroll, seedComparison } from "./secondary.helpers";

/**
 * Cart handoff to the chain's own online store (issue #72). The mock API enables rami_levy,
 * osher_ad and shufersal (src/mocks/handlers.phase3.ts). The page only ever opens links: the specs
 * assert that no request leaves for the chain's host and that every link is a safe new-tab link.
 */

const ACTION = "המשך באתר הרשת";

/** Fails the test when the page itself requests anything from the chains' (placeholder) host. */
function watchChainRequests(page: Page): string[] {
  const hits: string[] = [];
  page.on("request", (req) => {
    if (new URL(req.url()).hostname === "chain-shop.example") hits.push(req.url());
  });
  return hits;
}

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
]) {
  test.describe(`cart handoff at ${viewport.width} px`, () => {
    test.use({ viewport });

    test("results: open the sheet, see the disclaimer, copy the list, follow safe links", async ({
      page,
      context,
    }) => {
      await context.grantPermissions(["clipboard-read", "clipboard-write"]);
      const chainRequests = watchChainRequests(page);
      await mockApi(page);
      await openWeeklyResults(page);

      const single = page.getByTestId("plan-single");
      await single.getByRole("button", { name: /המשך באתר של רמי לוי/ }).click();
      const dialog = page.getByRole("dialog", { name: /הרשימה שלך ברמי לוי/ });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByTestId("handoff-disclaimer")).toContainText("המחיר הקובע הוא בקופה");
      await expect(dialog.getByTestId("handoff-disclaimer")).toContainText("דמי המשלוח");
      await expect(dialog.getByTestId("handoff-referral-label")).toHaveCount(0);
      await noHorizontalScroll(page);

      const site = dialog.getByTestId("handoff-site");
      await expect(site).toHaveAttribute("href", "https://chain-shop.example/rami");
      await expect(site).toHaveAttribute("target", "_blank");
      await expect(site).toHaveAttribute("rel", "noopener noreferrer");

      const links = dialog.getByTestId("handoff-item-link");
      expect(await links.count()).toBeGreaterThan(3);
      const first = links.first();
      await expect(first).toHaveAttribute("rel", "noopener noreferrer");
      await expect(first).toHaveAttribute("target", "_blank");
      const href = (await first.getAttribute("href"))!;
      expect(href).toMatch(/^https:\/\/chain-shop\.example\/rami\/search\?q=%/);

      await dialog.getByTestId("handoff-copy").click();
      await expect(dialog.getByTestId("handoff-copied")).toBeVisible();
      const copied = await page.evaluate(() => navigator.clipboard.readText());
      expect(copied.split("\n").length).toBe(await links.count());
      expect(copied.split("\n")[0]).toMatch(/ × \d/);

      // The page itself requested nothing from the chain; opening a link is the browser's job.
      expect(chainRequests).toEqual([]);

      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
    });

    test("results: a chain with a referral labels it, the others do not", async ({ page }) => {
      await mockApi(page);
      await openWeeklyResults(page);
      await page
        .getByTestId("plan-minimum_effort")
        .getByRole("button", { name: /המשך באתר של שופרסל/ })
        .click();
      const dialog = page.getByRole("dialog");
      await expect(dialog.getByTestId("handoff-referral-label").first()).toHaveText("קישור שותפים");
      await expect(dialog.getByTestId("handoff-referral-note")).toContainText("לא משפיע על הדירוג");
    });

    test("split view: each store has its own action and list", async ({ page }) => {
      await seedComparison(page);
      await page.goto("/split");
      const rami = page.getByTestId("split-column-101");
      const osher = page.getByTestId("split-column-102");
      await expect(rami.getByText(ACTION)).toBeVisible();
      // On a phone the stores are tabs and only the active one is shown.
      if (!(await osher.isVisible())) await page.locator("#tab-102").click();
      await expect(osher.getByText(ACTION)).toBeVisible();

      await osher.getByRole("button", { name: /המשך באתר של אושר עד/ }).click();
      const dialog = page.getByRole("dialog", { name: /הרשימה שלך באושר עד/ });
      await expect(dialog).toBeVisible();
      // Osher Ad has no site search in the mock: the site link and the list, no per-item links.
      await expect(dialog.getByTestId("handoff-site")).toHaveAttribute(
        "href",
        "https://chain-shop.example/osherad",
      );
      await expect(dialog.getByTestId("handoff-item-link")).toHaveCount(0);
      const lines = (await dialog.getByTestId("handoff-text").inputValue()).split("\n");
      expect(lines).toHaveLength(await osher.getByTestId("split-item").count());
      await noHorizontalScroll(page);
    });

    test("a failed /chains/online hides the action and the results still work", async ({
      page,
    }) => {
      await mockApi(page);
      await page.route(
        (url) => url.pathname === "/chains/online",
        (route) =>
          route.fulfill({
            status: 500,
            headers: { "access-control-allow-origin": "*", "content-type": "application/json" },
            body: "{}",
          }),
      );
      await openWeeklyResults(page);
      await expect(page.getByTestId("plan-single-total")).toBeVisible();
      await expect(page.getByTestId("plan-split")).toBeVisible();
      await expect(page.getByText(ACTION)).toHaveCount(0);
    });
  });
}

for (const theme of ["light", "dark"] as const) {
  test(`the handoff sheet has no serious axe violation (${theme})`, async ({ page }) => {
    await page.addInitScript((value) => localStorage.setItem("sc-theme", value), theme);
    await page.emulateMedia({ colorScheme: theme });
    await mockApi(page);
    await openWeeklyResults(page);
    await page
      .getByTestId("plan-minimum_effort")
      .getByRole("button", { name: /המשך באתר של שופרסל/ })
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .include('[role="dialog"]')
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(
      results.violations.filter((v) => v.impact === "serious" || v.impact === "critical"),
    ).toEqual([]);
  });
}
