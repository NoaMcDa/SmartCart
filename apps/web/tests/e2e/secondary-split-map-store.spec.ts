import { expect, test, type Page } from "@playwright/test";
import {
  KEYS,
  noHorizontalScroll,
  offlineProxy,
  seedComparison,
  stubTiles,
} from "./secondary.helpers";

const money = (text: string | null) => Number((text ?? "").replace(/[^\d.]/g, ""));
const subtotal = async (page: Page, storeId: number) =>
  money(await page.getByTestId(`subtotal-${storeId}`).textContent());

test.describe("split view, desktop", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("both stores side by side with correct subtotals, the waterfall sums to the net saving", async ({
    page,
  }) => {
    await seedComparison(page);
    await page.goto("/split");
    await expect(page.getByRole("heading", { level: 1, name: "פיצול סל" })).toBeVisible();
    await expect(page.getByTestId("split-column-101")).toBeVisible();
    await expect(page.getByTestId("split-column-102")).toBeVisible();
    expect(await subtotal(page, 101)).toBe(334.4);
    expect(await subtotal(page, 102)).toBe(36.6);
    expect(money(await page.getByTestId("net-saving").textContent())).toBe(41);
    await expect(page.getByTestId("split-summary")).toContainText("חיסכון נטו מול שופרסל");

    const steps = page.getByTestId("waterfall").locator("li");
    await expect(steps).toHaveCount(7); // base, chain, brand, promos, travel, extra stop, net
    // Each step is a signed number in one LTR island: "+₪ 48.40" or "−₪ 9".
    const value = async (step: string) => {
      const text = (await page
        .locator(`[data-step="${step}"] span[dir="ltr"]`)
        .first()
        .textContent())!;
      return (text.startsWith("\u2212") ? -1 : 1) * money(text);
    };
    const sum =
      (await value("chain")) +
      (await value("brand")) +
      (await value("promo")) +
      (await value("travel")) +
      (await value("stop"));
    expect(Math.round(sum * 100) / 100).toBe(41);
    await noHorizontalScroll(page);
  });

  test("moving an item with the keyboard updates subtotals, net saving and the waterfall; reset restores", async ({
    page,
  }) => {
    await seedComparison(page);
    await page.goto("/split");
    const move = page.getByRole("button", { name: "העברת חלב טרי 3% יטבתה, 1 ליטר לאושר עד" });
    await move.focus();
    await page.keyboard.press("Enter");
    expect(await subtotal(page, 101)).toBe(322.6);
    expect(await subtotal(page, 102)).toBe(48);
    expect(money(await page.getByTestId("net-saving").textContent())).toBe(41.4);
    await expect(page.locator('[data-step="net"]')).toContainText("41.40");
    await expect(page.getByTestId("split-announcer")).toContainText("הועבר לאושר עד");

    await page.getByRole("button", { name: "איפוס לפיצול המומלץ" }).click();
    expect(await subtotal(page, 101)).toBe(334.4);
    expect(money(await page.getByTestId("net-saving").textContent())).toBe(41);
  });

  test("an item the other store does not stock cannot move, and says why", async ({ page }) => {
    await seedComparison(page);
    await page.goto("/split");
    const row = page.getByTestId("split-column-102").locator('[data-canonical="1002"]');
    await expect(row.getByTestId("move-reason")).toContainText("לא נמצא ברמי לוי");
    const button = row.getByRole("button", { name: /העברת קוטג/ });
    await expect(button).toHaveAttribute("aria-disabled", "true");
    // aria-disabled stays clickable, so activating it explains instead of doing nothing.
    await button.click({ force: true });
    await expect(page.getByTestId("split-announcer")).toContainText("לא ניתן להעביר");
    expect(await subtotal(page, 102)).toBe(36.6);
  });

  test("dragging an item to the other store with the pointer moves it", async ({ page }) => {
    await seedComparison(page);
    await page.goto("/split");
    // The first row of the first column; scroll it into view so the mouse stays inside the viewport.
    const handle = page
      .getByTestId("split-column-101")
      .locator('[data-canonical="1001"] > span')
      .first();
    const target = page.getByTestId("split-column-102");
    await handle.scrollIntoViewIfNeeded();
    const from = (await handle.boundingBox())!;
    const to = (await target.boundingBox())!;
    expect(to.y).toBeGreaterThan(0); // the other column's header is on screen too
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
    await page.mouse.down();
    await page.mouse.move(to.x + to.width / 2, to.y + 30, { steps: 12 });
    await expect(target).toHaveAttribute("data-over", "true");
    await page.mouse.up();
    await expect(
      page.getByTestId("split-column-102").locator('[data-canonical="1001"]'),
    ).toBeVisible();
    expect(await subtotal(page, 101)).toBe(322.6);
    expect(await subtotal(page, 102)).toBe(48);
    expect(money(await page.getByTestId("net-saving").textContent())).toBe(41.4);
  });
});

test.describe("split view, phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("two tabs, one per store, 44 px targets, no horizontal scroll, moves by button", async ({
    page,
  }) => {
    await seedComparison(page);
    await page.goto("/split");
    const tabs = page.getByRole("tab");
    await expect(tabs).toHaveCount(2);
    await expect(page.getByTestId("split-column-101")).toBeVisible();
    await expect(page.getByTestId("split-column-102")).toBeHidden();
    for (const tab of await tabs.all()) {
      expect((await tab.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    await tabs.nth(1).click();
    await expect(page.getByTestId("split-column-102")).toBeVisible();
    await expect(page.getByTestId("split-column-101")).toBeHidden();
    await noHorizontalScroll(page);
    // Olive oil sits at Osher in the recommended split and Rami stocks it too.
    await page
      .getByTestId("split-column-102")
      .getByRole("button", { name: /העברת שמן זית/ })
      .click();
    await expect(page.getByTestId("split-column-102").getByTestId("split-item")).toHaveCount(2);
    for (const b of await page
      .getByTestId("split-column-102")
      .getByRole("button", { name: /העברת/ })
      .all()) {
      expect((await b.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
  });
});

test.describe("split view, empty", () => {
  test("without a cached comparison it is read-only with an empty state", async ({ page }) => {
    await page.goto("/split");
    await expect(page.getByTestId("split-empty")).toBeVisible();
    await expect(page.getByRole("link", { name: "חזרה להשוואה" })).toBeVisible();
  });
});

test.describe("map", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("a pin per store with the basket total, the sheet for the selected store, attribution visible", async ({
    page,
  }) => {
    await seedComparison(page);
    await stubTiles(page);
    await page.goto("/map");
    await expect(page.getByRole("heading", { level: 1, name: "מפת סניפים" })).toBeVisible();
    const pins = page.getByTestId("map-pin");
    await expect(pins).toHaveCount(5);
    const prices = await pins.getByTestId("pin-price").allTextContents();
    expect(prices.map((p) => p.replace(/ /g, " "))).toEqual(
      expect.arrayContaining(["₪ 389", "₪ 402", "₪ 418", "₪ 446"]),
    );
    const rami = pins.filter({ hasText: "רמי לוי" });
    await expect(rami).toContainText("מומלץ");
    expect((await rami.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expect(page.getByRole("img", { name: "המיקום שלי, מעוגל לשכונה" })).toBeVisible();
    await expect(page.getByRole("link", { name: "תורמי OpenStreetMap" })).toBeVisible();
    await noHorizontalScroll(page);

    await rami.click();
    const sheet = page.getByRole("dialog", { name: "רמי לוי · מודיעין" });
    await expect(sheet).toBeVisible();
    await expect(sheet.getByTestId("store-sheet")).toContainText("חיסכון נטו מול שופרסל");
    await expect(sheet.getByTestId("store-sheet")).toContainText("₪ 57");
    await expect(sheet.getByTestId("store-sheet")).toContainText("חסרים 1 פריטים");
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();

    // The list is the accessible alternative and opens the same sheet.
    await page
      .getByTestId("map-store-list")
      .getByRole("button", { name: /יוחננוף/ })
      .click();
    await expect(page.getByRole("dialog", { name: "יוחננוף · מודיעין" })).toBeVisible();
  });

  test("the map renders (WebGL canvas or the schematic fallback) in light and dark themes", async ({
    page,
  }) => {
    await seedComparison(page);
    await stubTiles(page);
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/map");
      await expect(page.getByTestId("map-pin")).toHaveCount(5);
      const surface = page.getByTestId("map-canvas").or(page.getByTestId("map-fallback"));
      await expect(surface.first()).toBeVisible();
      const box = (await surface.first().boundingBox())!;
      expect(box.width).toBeGreaterThan(300);
      expect(box.height).toBeGreaterThan(250);
    }
  });

  test("only the map route downloads the map library", async ({ page }) => {
    await seedComparison(page);
    await stubTiles(page);
    const jsBytes = async (path: string) => {
      await page.goto(path);
      // networkidle never settles on the map (tile requests); load plus a pause is enough here.
      await page.waitForLoadState("load");
      if (path === "/map") await page.getByTestId("map-pin").first().waitFor();
      await page.waitForTimeout(800);
      return page.evaluate(() =>
        performance
          .getEntriesByType("resource")
          .filter((e) => e.name.endsWith(".js"))
          .reduce((sum, e) => sum + (e as PerformanceResourceTiming).decodedBodySize, 0),
      );
    };
    const split = await jsBytes("/split");
    const profile = await jsBytes("/profile");
    const map = await jsBytes("/map");
    // MapLibre is several hundred kB; no other screen pays for it.
    expect(map - split).toBeGreaterThan(250_000);
    expect(map - profile).toBeGreaterThan(250_000);
  });

  test("without a cached comparison it shows an empty state", async ({ page }) => {
    await page.goto("/map");
    await expect(page.getByTestId("map-empty")).toBeVisible();
  });
});

test.describe("store mode", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("the chosen store's items by department with large checkmarks, progress and a summary", async ({
    page,
  }) => {
    await seedComparison(page);
    await page.goto("/store-mode?store=101");
    await expect(page.getByRole("heading", { level: 1, name: "מצב חנות" })).toBeVisible();
    await expect(page.getByTestId("shop-item")).toHaveCount(8);
    const headings = await page.getByRole("heading", { level: 2 }).allTextContents();
    expect(headings).toEqual(["פירות וירקות", "מוצרי חלב וביצים", "דגים", "מזון יבש ובישול"]);
    const milk = page.getByRole("checkbox", { name: /חלב טרי 3% יטבתה/ });
    await expect(milk).toContainText("תחליף");
    await expect(milk).toContainText("עודכן");
    expect((await milk.boundingBox())!.height).toBeGreaterThanOrEqual(64);
    await expect(page.getByTestId("progress-count")).toContainText("נאספו 0 מתוך 8");

    await milk.click();
    await expect(milk).toHaveAttribute("aria-checked", "true");
    await expect(page.getByTestId("progress-count")).toContainText("נאספו 1 מתוך 8");
    // Strikethrough as well as dimming.
    await expect(milk.getByText("חלב טרי 3% יטבתה, 1 ליטר", { exact: true })).toHaveCSS(
      "text-decoration-line",
      "line-through",
    );
    // Undo an accidental tick.
    await page.getByTestId("undo-bar").getByRole("button", { name: "ביטול" }).click();
    await expect(milk).toHaveAttribute("aria-checked", "false");
    await milk.click();
    await noHorizontalScroll(page);

    // Survives a reload.
    await page.reload();
    await expect(page.getByRole("checkbox", { name: /חלב טרי 3% יטבתה/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    // Finish: summary, record the saving, clean the cache.
    // Checked rows sink, so always take the first unchecked one until none is left.
    const unchecked = page.locator('[role="checkbox"][aria-checked="false"]');
    while ((await unchecked.count()) > 0) await unchecked.first().click();
    await page.getByTestId("finish").click();
    await expect(page.getByRole("dialog", { name: "סיכום הקנייה" })).toContainText("₪ 389");
    await page.getByTestId("finish-confirm").click();
    await expect(page).toHaveURL(/\/$/);
    const state = await page.evaluate(
      (keys) => ({
        shopping: localStorage.getItem(keys.shopping),
        savings: JSON.parse(localStorage.getItem(keys.savings) ?? "[]"),
      }),
      KEYS,
    );
    expect(state.shopping).toBeNull();
    expect(state.savings).toHaveLength(1);
    expect(state.savings[0].net).toBeGreaterThan(0);
    await page.goto("/profile");
    await expect(page.getByTestId("savings-total")).toContainText("₪");
  });

  test("works with the network off, including after a reload, and checkmarks persist", async ({
    browser,
    baseURL,
  }) => {
    const proxy = await offlineProxy(baseURL!);
    const context = await proxy.newContext(browser);
    try {
      const page = await context.newPage();
      await seedComparison(page);
      await page.goto(`${proxy.base}/store-mode?store=101`);
      await expect(page.getByTestId("shop-item")).toHaveCount(8);
      await page.evaluate(async () => {
        await navigator.serviceWorker.ready;
      });
      await page.reload();
      await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
      await expect(page.getByTestId("shop-item")).toHaveCount(8);
      await page.getByRole("checkbox", { name: /ביצים L/ }).click();
      await expect(page.getByTestId("progress-count")).toContainText("נאספו 1 מתוך 8");

      // The page itself is in the worker's cache.
      await expect
        .poll(() =>
          page.evaluate(async () => {
            const urls: string[] = [];
            for (const n of await caches.keys())
              for (const r of await (await caches.open(n)).keys())
                urls.push(new URL(r.url).pathname);
            return urls.includes("/store-mode");
          }),
        )
        .toBe(true);

      proxy.setOffline(true);
      expect(
        await fetch(`${proxy.base}/`).then(
          () => "online",
          () => "offline",
        ),
      ).toBe("offline");
      await page.reload();
      await expect(page.getByRole("heading", { level: 1, name: "מצב חנות" })).toBeVisible();
      await expect(page.getByTestId("shop-item")).toHaveCount(8);
      await expect(page.getByRole("checkbox", { name: /ביצים L/ })).toHaveAttribute(
        "aria-checked",
        "true",
      );
      await expect(page.getByTestId("progress-count")).toContainText("נאספו 1 מתוך 8");
      // Still usable offline.
      await page.getByRole("checkbox", { name: /פסטה פנה/ }).click();
      await expect(page.getByTestId("progress-count")).toContainText("נאספו 2 מתוך 8");
    } finally {
      await context.close();
      await proxy.close();
    }
  });

  test("without a session it shows an empty state", async ({ page }) => {
    await page.goto("/store-mode");
    await expect(page.getByTestId("store-empty")).toBeVisible();
  });
});

test.describe("gap report from a price", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("one tap plus send reports the captured price; the user sees a confirmation", async ({
    page,
  }) => {
    const calls = await seedComparison(page);
    await page.goto("/store-mode?store=101");
    await page.getByRole("button", { name: /דיווח: חלב טרי 3% יטבתה/ }).click();
    const dialog = page.getByRole("dialog", { name: "חלב טרי 3% יטבתה, 1 ליטר" });
    await expect(dialog).toContainText("עודכן");
    await dialog.getByRole("button", { name: "המחיר שונה" }).click();
    await dialog.getByRole("button", { name: "שליחה" }).click();
    await expect(page.getByTestId("gap-sent")).toBeVisible();
    const reports = calls.filter((c) => c.path === "/feedback/gap");
    expect(reports).toHaveLength(1);
    expect(reports[0]!.body).toMatchObject({
      store_id: 101,
      canonical_id: 1001,
      shown_price: 11.8,
    });
  });
});
