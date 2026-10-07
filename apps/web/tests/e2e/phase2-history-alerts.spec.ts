import { expect, test } from "@playwright/test";
import { resetPhase2Mock } from "../../src/mocks/handlers.phase2";
import { mockApi, seedProfile } from "./core-helpers";

const PRODUCT = "/product/1001?name=" + encodeURIComponent("חלב טרי 3%, 1 ליטר");

test.beforeEach(() => resetPhase2Mock());

for (const theme of ["light", "dark"] as const) {
  test.describe(`price history, ${theme} theme`, () => {
    test.use({ viewport: { width: 390, height: 844 } });

    test("90 days of unit prices, promo windows, markers with tooltips and a table for screen readers", async ({
      page,
    }) => {
      const calls = await mockApi(page);
      await seedProfile(page);
      await page.addInitScript((t) => localStorage.setItem("sc-theme", t), theme);
      await page.emulateMedia({ colorScheme: theme });
      await page.goto(PRODUCT);

      const chart = page.getByTestId("history-chart");
      await expect(chart).toBeVisible();
      await expect(page.getByRole("heading", { level: 2, name: "היסטוריית מחירים" })).toBeVisible();
      if (calls.length) expect(calls.some((c) => c.path === "/history/1001")).toBe(true);

      // Promo windows shaded, promo days marked, the legend says what each is in words.
      expect(await page.getByTestId("history-promo").count()).toBeGreaterThan(0);
      const markers = page.getByTestId("history-marker");
      expect(await markers.count()).toBeGreaterThan(0);
      await markers.first().hover({ force: true });
      await expect(page.getByTestId("history-tooltip")).toContainText(/מבצע: 1\+1 על המוצר/);
      await expect(page.getByRole("list", { name: "מקרא" })).toContainText("תקופת מבצע");

      // Unit price is the default axis (D6); the numbers are LTR islands inside the Hebrew sentence.
      await expect(chart).toContainText(/מחיר ליחידה \(ל-100 מ"ל\)/);
      await expect(
        page.getByTestId("history-summary").locator('span[dir="ltr"]').first(),
      ).toContainText("₪");
      await expect(page.getByText(/ימים ללא נתונים מוצגים כרווח/)).toBeVisible();
      await expect(page.getByText("המחיר הקובע הוא בקופה.").first()).toBeVisible();
      await expect(page.getByTestId("price-history").locator("time[datetime]")).toBeVisible();

      // Accessible text alternative: a real table, visually hidden, one row per point.
      const table = page.getByTestId("history-table");
      await expect(table).toHaveCount(1);
      const box = await table.locator("xpath=..").boundingBox(); // the visually hidden wrapper
      expect(box!.width).toBeLessThanOrEqual(2);
      expect(await table.getByRole("row").count()).toBeGreaterThan(20);
      await expect(chart.locator("svg[aria-hidden='true']")).toBeVisible();

      // The chart follows the theme: its line uses the accent token for that theme.
      const stroke = await page
        .locator("polyline")
        .first()
        .evaluate((el) => getComputedStyle(el).stroke);
      expect(stroke).toBe(theme === "dark" ? "rgb(127, 179, 227)" : "rgb(31, 95, 139)");
      // Time runs in reading direction: the page is RTL and the price axis is on its right.
      const svg = await chart.locator("svg").boundingBox();
      const tick = await chart.locator("svg text").first().boundingBox();
      expect(tick!.x + tick!.width).toBeGreaterThan(svg!.x + svg!.width * 0.8);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    });
  });
}

test.describe("price history controls", () => {
  test("30 days, shelf price and the chain base price refetch with the right query", async ({
    page,
  }) => {
    const calls = await mockApi(page);
    await seedProfile(page);
    await page.goto(PRODUCT);
    await expect(page.getByTestId("history-chart")).toBeVisible();

    await page.getByRole("radio", { name: "30 יום" }).click();
    await expect(page.getByTestId("history-summary")).toContainText("ב-30 הימים האחרונים");
    await page.getByRole("radio", { name: "מדף" }).click();
    await expect(page.getByTestId("history-chart")).toContainText("מחיר מדף");

    const select = page.getByTestId("history-store");
    await expect(select.locator("option")).toHaveText([
      /הסניף שלי/,
      /הכי זול בקרבתך/,
      "מחיר בסיס של הרשת",
    ]);
    await select.selectOption("base");
    await expect(page.getByTestId("history-chart")).toBeVisible();
    if (calls.length) {
      const history = calls.filter((c) => c.path === "/history/1001");
      expect(history.length).toBeGreaterThanOrEqual(3);
    }
  });
});

test.describe("alerts", () => {
  test("create from product detail, list on /alerts, delete", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto(PRODUCT);
    await page.getByTestId("variants").waitFor(); // the unit label comes from the loaded prices

    const region = page.getByRole("region", { name: "התראה כשהמחיר יורד" });
    await expect(region).toBeVisible();
    await region.getByRole("radio", { name: "תחליף קרוב" }).click();
    await region.getByRole("textbox", { name: /התריעי לי מתחת ל-₪/ }).fill("0.55");
    await region.getByRole("button", { name: "יצירת התראה" }).click();
    await expect(region.getByTestId("alert-created")).toContainText(/₪\s0\.55/);
    await expect(region.getByTestId("alert-existing")).toHaveCount(1);
    // Push is feature-detected: in this browser it is either offered or explained, never broken.
    await expect(region.getByTestId("push-panel")).toBeVisible();

    await page
      .getByTestId("bottom-nav")
      .or(page.getByTestId("top-nav"))
      .getByRole("link", { name: "התראות" })
      .first()
      .click();
    await expect(page).toHaveURL(/\/alerts$/);
    await expect(page.getByRole("heading", { level: 1, name: "התראות" })).toBeVisible();
    const item = page.getByTestId("alert-item");
    await expect(item).toHaveCount(1);
    await expect(item).toContainText("חלב טרי 3%, 1 ליטר");
    await expect(item).toContainText(/מתחת ל-₪\s0\.55 ל-100 מ"ל/);
    await expect(item).toContainText("תחליף קרוב");
    await expect(item).toContainText("עוד לא הופעלה");
    await expect(item.getByRole("link", { name: "חלב טרי 3%, 1 ליטר" })).toHaveAttribute(
      "href",
      /^\/product\/1001\?name=/,
    );
    for (const button of await item.getByRole("button").all()) {
      expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(43.5);
    }

    await item.getByRole("button", { name: "מחיקת ההתראה על חלב טרי 3%, 1 ליטר" }).click();
    await expect(page.getByTestId("alerts-empty")).toBeVisible();
    await page.reload();
    await expect(page.getByTestId("alerts-empty")).toBeVisible();
  });

  test("pause, resume and edit an alert (PUT /me/alerts/{id})", async ({ page }) => {
    await mockApi(page);
    // The shared mock has no PUT yet: answer it here, applying the body to the stored alert.
    const puts: Array<Record<string, unknown>> = [];
    await page.route(
      (url) => url.port === "8000" && /^\/me\/alerts\/\d+$/.test(url.pathname),
      async (route) => {
        const req = route.request();
        const cors = {
          "access-control-allow-origin": "*",
          "access-control-allow-headers": "*",
          "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
        };
        if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
        if (req.method() !== "PUT") return route.fallback();
        const body = req.postDataJSON() as Record<string, unknown>;
        puts.push(body);
        return route.fulfill({
          status: 200,
          headers: { ...cors, "content-type": "application/json" },
          body: JSON.stringify({
            id: 1,
            last_fired_at: null,
            created_at: "2026-10-07T00:00:00Z",
            ...body,
            threshold_unit_price: String(body.threshold_unit_price),
          }),
        });
      },
    );
    await seedProfile(page);
    await page.goto(PRODUCT);
    const region = page.getByRole("region", { name: "התראה כשהמחיר יורד" });
    await region.getByRole("textbox", { name: /התריעי לי מתחת ל-₪/ }).fill("0.55");
    await region.getByRole("button", { name: "יצירת התראה" }).click();
    await region.getByTestId("alert-created").waitFor();
    await page.goto("/alerts");
    const item = page.getByTestId("alert-item");

    await item.getByRole("button", { name: /השהיית ההתראה/ }).click();
    await expect(item).toContainText("מושהית");
    expect(puts[0]).toMatchObject({ active: false, canonical_id: 1001 });
    await item.getByRole("button", { name: /הפעלה מחדש/ }).click();
    await expect(item).not.toContainText("מושהית");

    await item.getByRole("button", { name: /עריכת ההתראה/ }).click();
    const sheet = page.getByRole("dialog");
    await sheet.getByRole("textbox").fill("0.45");
    await sheet.getByRole("radio", { name: "מוצר מדויק" }).click();
    await sheet.getByRole("button", { name: "שמירה" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(item).toContainText(/מתחת ל-₪\s0\.45/);
    await expect(item).toContainText("מוצר מדויק");
    expect(puts.at(-1)).toMatchObject({ threshold_unit_price: "0.45", flex_level: "exact" });
    for (const button of await item.getByRole("button").all()) {
      expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(43.5);
    }
  });

  test("a denied notification permission is explained and nothing breaks", async ({ page }) => {
    await mockApi(page);
    await page.addInitScript(() => {
      // A browser that has push but where the user said no.
      Object.defineProperty(window, "PushManager", { value: class {}, configurable: true });
      Object.defineProperty(window, "Notification", {
        value: { permission: "denied", requestPermission: async () => "denied" },
        configurable: true,
      });
    });
    await page.goto("/alerts");
    // Without the VAPID key in this build the panel says push is not configured; with it, denied.
    const panel = page.getByTestId("push-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText(/לא מוגדרת|חסומות בדפדפן/);
    await expect(page.getByTestId("alerts-empty")).toBeVisible();
  });
});
