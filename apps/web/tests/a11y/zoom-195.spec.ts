import { expect, test, type Page } from "@playwright/test";
import { ROUTES } from "../e2e/routes";
import {
  mockApi,
  openWeeklyResults,
  pasteList,
  seedProfile,
  WEEKLY_TEXT,
} from "../e2e/core-helpers";

/**
 * 200% zoom on a 390 px phone leaves 195 CSS px (WCAG 1.4.4 and 1.4.10; issues #26 and #101).
 * Every route must fit: the document is not wider than the viewport, and no visible element sticks
 * out of it. Data tables scroll inside their own wrapper (the 1.4.10 exception) and the map clips
 * its own canvas, so elements inside those are skipped; the wrapper itself must still fit. The
 * second block does the same for the states a first paint does not show: a full list, open sheets,
 * the results, the substitution card, the shared list with its members and the scan result.
 */
async function assertFits(page: Page) {
  const result = await page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const outside = [...document.querySelectorAll("body *")]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0 || el.closest(".sr-only")) return false;
        const scroller = el.closest("[class*='tableWrap'], [class*='maplibregl-map']");
        if (scroller && scroller !== el) return false;
        return r.right > width + 0.5 || r.left < -0.5;
      })
      .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 40)}`);
    return {
      width,
      scroll: document.documentElement.scrollWidth,
      bodyScroll: document.body.scrollWidth,
      outside: outside.slice(0, 8),
    };
  });
  expect(result.width, "the viewport is the 200% zoom width").toBe(195);
  // The offending elements first: they say where to look when a width check then fails.
  expect(result.outside, "elements outside the viewport").toEqual([]);
  expect(result.scroll, "document scrollWidth").toBeLessThanOrEqual(result.width);
  expect(result.bodyScroll, "body scrollWidth").toBeLessThanOrEqual(result.width);
}

test.describe("195 px wide (200% zoom on a phone), every route", () => {
  test.use({ viewport: { width: 195, height: 844 } });

  for (const { path } of ROUTES) {
    test(`${path}: no horizontal overflow`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await assertFits(page);
    });
  }
});

test.describe("195 px wide, states behind a tap", () => {
  test.use({ viewport: { width: 195, height: 844 } });

  test("the list builder with nine items, and the flexibility sheet", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await pasteList(page, WEEKLY_TEXT);
    await expect(page.getByTestId("list-row")).toHaveCount(9);
    await assertFits(page);
    await page
      .getByTestId("list-row")
      .first()
      .getByRole("button", { name: /^רמת גמישות/ })
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await assertFits(page);
  });

  test("the results with the smart cart, and the substitution card", async ({ page }) => {
    await mockApi(page);
    await openWeeklyResults(page);
    await expect(page.getByTestId("smart-cart")).toBeVisible();
    await assertFits(page);
    await page.goto("/compare/substitution/10104?plan=single");
    await expect(page.getByTestId("sub-card")).toBeVisible();
    await assertFits(page);
  });

  test("the profile with a chain picked, and the onboarding steps", async ({ page }) => {
    await mockApi(page);
    await page.goto("/profile");
    await page.getByRole("button", { name: "הסופר שלי: יוחננוף" }).click();
    await assertFits(page);
    await page.goto("/onboarding");
    for (let step = 0; step < 3; step++) {
      await assertFits(page);
      await page.getByTestId("onboarding-next").click();
    }
  });

  test("the shared list with a pending invite and a checked item, and the share sheet", async ({
    page,
  }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await pasteList(page, "חלב, 2 רסק עגבניות");
    await page.getByRole("link", { name: "שיתוף" }).click();
    await page.getByRole("button", { name: "יצירת רשימה משותפת" }).click();
    await expect(page.getByTestId("shared-item")).toHaveCount(2);
    await page.getByTestId("shared-item").first().getByRole("checkbox").check();
    await page.getByRole("button", { name: "הזמנת בני משפחה" }).click();
    const sheet = page.getByRole("dialog", { name: "הזמנת בני משפחה" });
    await sheet.getByRole("button", { name: "יצירת קישור הזמנה" }).click();
    await expect(sheet.getByLabel(/קישור הזמנה/)).toBeVisible();
    await assertFits(page);
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("member")).toHaveCount(2);
    await assertFits(page);
  });

  test("the scan result card", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/scan");
    await page.getByRole("textbox", { name: /ברקוד \(13 ספרות/ }).fill("5901234123457");
    await page.getByRole("button", { name: "חיפוש" }).click();
    await expect(page.getByTestId("scan-result")).toBeVisible();
    await assertFits(page);
  });
});
