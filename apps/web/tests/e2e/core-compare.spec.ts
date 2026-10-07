import { expect, test, type Page } from "@playwright/test";
import { mockApi, openWeeklyResults, pasteList, seedProfile } from "./core-helpers";

const UPDATED = "2026-10-07T03:40:00Z"; // the mock's prices_updated_at (06:40 Israel time)
const NO_MAX_BASELINE = /היקר ביותר|הכי יקר|היקרה ביותר|הכי יקרה|most expensive/i;

const color = (page: Page, testId: string, prop: "borderColor" | "backgroundColor" | "color") =>
  page.getByTestId(testId).evaluate((el, p) => getComputedStyle(el)[p], prop);

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
]) {
  test.describe(`comparison results at ${viewport.width} px`, () => {
    test.use({ viewport });

    test("three plans with the mock numbers, net saving versus the home store", async ({
      page,
    }) => {
      await mockApi(page);
      await openWeeklyResults(page);
      await expect(
        page.getByRole("heading", { level: 1, name: "איפה הכי זול השבוע?" }),
      ).toBeVisible();

      const sub = page.getByTestId("results-subline");
      await expect(sub).toContainText("9 פריטים");
      await expect(sub).toContainText('עד 5 ק"מ ממודיעין');
      await expect(sub.locator(`time[datetime="${UPDATED}"]`)).toBeVisible();

      const single = page.getByTestId("plan-single");
      await expect(single).toHaveAttribute("data-recommended", "true");
      await expect(page.getByTestId("plan-single-total")).toHaveText(/^₪\s389$/);
      await expect(page.getByTestId("plan-single-saving")).toContainText(/חוסך ₪\s57/);
      await expect(page.getByTestId("plan-single-saving")).toContainText(
        "לעומת שופרסל דיל · מודיעין, הסופר שלך",
      );
      await expect(single).toContainText('4.2 ק"מ');
      expect(await color(page, "plan-single", "borderColor")).toBe("rgb(31, 95, 139)");
      expect(await color(page, "plan-single-saving", "backgroundColor")).toBe("rgb(227, 243, 234)");

      const split = page.getByTestId("plan-split");
      await expect(split).toHaveAttribute("data-recommended", "false");
      await expect(page.getByTestId("plan-split-total")).toHaveText(/^₪\s371$/);
      await expect(split).toContainText("+12 דק'");
      await expect(page.getByTestId("plan-split-saving")).toContainText("נטו");
      await expect(split).toContainText(/פחות ₪\s9 נסיעה/);

      const home = page.getByTestId("plan-minimum_effort");
      await expect(page.getByTestId("plan-minimum_effort-total")).toHaveText(/^₪\s446$/);
      await expect(home).toContainText("מינימום מאמץ · הסופר שלך");

      // Missing items: red, icon plus text, and the list of names.
      const missing = single.getByRole("button", { name: /פריט חסר/ });
      expect(await missing.evaluate((el) => getComputedStyle(el).color)).toBe("rgb(163, 45, 45)");
      await expect(missing.locator("svg")).toHaveCount(1);
      await missing.click();
      await expect(single.getByRole("list", { name: "פריטים חסרים" })).toContainText("קוטג'");

      // Trust: disclaimer, timestamps, labeled substitutes, estimated and club tags.
      await expect(page.getByTestId("disclaimer")).toContainText("המחיר הקובע הוא בקופה.");
      expect(await page.locator(`time[datetime="${UPDATED}"]`).count()).toBeGreaterThan(5);
      await page.getByText(/^פירוט הסל/).click();
      const details = page.getByTestId("basket-details");
      await expect(details.getByRole("link", { name: /^תחליף:/ })).toHaveCount(3);
      await expect(details.getByText("מבצע מועדון · רמי לוי")).toBeVisible();
      await expect(details.getByText("מחיר משוער · שקיל").first()).toBeVisible();
      expect(await page.locator("main").textContent()).not.toMatch(NO_MAX_BASELINE);

      if (viewport.width === 1280) {
        const ys = await Promise.all(
          ["plan-single", "plan-split", "plan-minimum_effort"].map(
            async (id) => (await page.getByTestId(id).boundingBox())!.y,
          ),
        );
        expect(new Set(ys).size).toBe(1);
      } else {
        const { scrollWidth, clientWidth } = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
        }));
        expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
      }
    });

    test("report a gap and the map toggle", async ({ page }) => {
      const calls = await mockApi(page);
      await openWeeklyResults(page);
      await page.getByRole("button", { name: "דיווח על פער במחיר" }).click();
      const sheet = page.getByRole("dialog", { name: "דיווח על פער" });
      await sheet.getByLabel("פריט").selectOption({ label: "חלב טרי 3%, 1 ליטר" });
      await expect(sheet).toContainText(/הצגנו: ₪\s5.90/);
      await sheet.getByLabel("המחיר שראית בפועל (₪)").fill("6.50");
      await sheet.getByRole("button", { name: "שליחת הדיווח" }).click();
      await expect(sheet.getByRole("status")).toContainText("תודה!");
      const gap = calls.find((c) => c.path === "/feedback/gap");
      if (calls.length) {
        expect(gap?.body).toMatchObject({
          store_id: 101,
          canonical_id: 1001,
          shown_price: "5.90",
          actual_price: 6.5,
        });
      }
      await sheet.getByRole("button", { name: "סגירה" }).first().click();

      await page.getByRole("radio", { name: "מפה" }).click();
      await expect(page).toHaveURL(/\/map$/);
    });
  });
}

test.describe("comparison results, dark theme", () => {
  test.use({ colorScheme: "dark", viewport: { width: 390, height: 844 } });

  test("tokens switch: accent border, green saving, red missing", async ({ page }) => {
    await mockApi(page);
    await openWeeklyResults(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await color(page, "plan-single", "borderColor")).toBe("rgb(127, 179, 227)");
    expect(await color(page, "plan-single-saving", "backgroundColor")).toBe("rgb(22, 53, 42)");
    expect(await color(page, "plan-single-saving", "color")).toBe("rgb(127, 212, 166)");
    const missing = page.getByTestId("plan-single").getByRole("button", { name: /פריט חסר/ });
    expect(await missing.evaluate((el) => getComputedStyle(el).color)).toBe("rgb(240, 140, 140)");
  });
});

test.describe("comparison results, states", () => {
  test("without a home store: prompt to set one, never a saving", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page, { home_store_id: null });
    await page.goto("/");
    await pasteList(page, "חלב, 2 רסק עגבניות");
    await page.getByRole("link", { name: "השווי" }).click();
    await expect(page.getByTestId("no-home-store")).toContainText("מה הסופר שלך?");
    await expect(page.getByTestId("plan-single")).toBeVisible();
    await expect(page.getByText(/חוסך/)).toHaveCount(0);
    await expect(page.getByTestId("plan-minimum_effort")).toHaveCount(0);
  });

  test("empty list", async ({ page }) => {
    await mockApi(page);
    await page.goto("/compare");
    await expect(page.getByRole("heading", { name: "אין עדיין מה להשוות" })).toBeVisible();
  });

  test("error state with retry", async ({ page }) => {
    test.skip(
      process.env.NEXT_PUBLIC_API_MOCK === "1",
      "the in-process mock never fails over the network",
    );
    await mockApi(page);
    let fail = true;
    await page.route(
      (url) => url.pathname === "/optimize",
      async (route) => {
        if (route.request().method() === "POST" && fail) {
          await route.fulfill({
            status: 500,
            headers: { "access-control-allow-origin": "*", "content-type": "application/json" },
            body: '{"detail":"boom"}',
          });
          return;
        }
        await route.fallback();
      },
    );
    await seedProfile(page);
    await page.goto("/");
    await pasteList(page, "חלב");
    await page.getByRole("link", { name: "השווי" }).click();
    await expect(page.getByRole("heading", { name: "לא הצלחנו לחשב את ההשוואה" })).toBeVisible();
    fail = false;
    await page.getByRole("button", { name: "נסי שוב" }).click();
    await expect(page.getByTestId("plan-single")).toBeVisible();
  });
});
