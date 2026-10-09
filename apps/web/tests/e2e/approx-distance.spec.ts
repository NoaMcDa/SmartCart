import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { API_BASE_URL } from "../../src/api/config";
import { optimizeFixture } from "../../src/mocks/fixtures";
import { mockApi, openWeeklyResults } from "./core-helpers";
import { noHorizontalScroll, seedComparison, stubTiles } from "./secondary.helpers";

/**
 * Approximate distances (trust): the API sends `distance_approximate` and `geo_precision` on every
 * store. A store at locality precision (the mock's store 104, יוחננוף) is shown with "כ־" and the
 * words "מיקום משוער" wherever a distance appears, and on the map as a hollow dashed marker with
 * an area and a legend, never as an exact pin.
 */

const APPROX_HE = 'כ־3.6 ק"מ · מיקום משוער';

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
};

async function overridePost(page: Page, path: string, body: unknown) {
  const origin = new URL(API_BASE_URL).origin;
  await page.route(
    (url) => url.origin === origin && url.pathname === path,
    async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 200,
        headers: { ...CORS, "content-type": "application/json" },
        body: JSON.stringify(body),
      });
    },
  );
}

/** The optimize result with the recommended single store moved to a town-centre point. */
function optimizeWithApproximateSingle() {
  const res = optimizeFixture();
  const store = res.single!.stores[0]!.store;
  store.distance_m = 3600;
  store.distance_approximate = true;
  store.geo_precision = "locality";
  return res;
}

for (const viewport of [
  { width: 390, height: 844 },
  { width: 195, height: 800 },
]) {
  test.describe(`results at ${viewport.width} px`, () => {
    test.use({ viewport });

    test("an exact distance is unchanged", async ({ page }) => {
      await mockApi(page);
      await openWeeklyResults(page);
      const exact = page.getByTestId("plan-single").getByTestId("plan-distance");
      await expect(exact).toHaveText('4.2 ק"מ');
      await expect(exact).toHaveAttribute("data-approximate", "false");
    });

    test("a town-centre store shows its distance as approximate, and nothing overflows", async ({
      page,
    }) => {
      await mockApi(page);
      await overridePost(page, "/optimize", optimizeWithApproximateSingle());
      await openWeeklyResults(page);
      const distance = page.getByTestId("plan-single").getByTestId("plan-distance");
      await expect(distance).toHaveText(APPROX_HE);
      await expect(distance).toHaveAttribute("data-approximate", "true");
      await noHorizontalScroll(page);
    });
  });
}

test.describe("map", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("a town-centre store is a hollow dashed marker with the words, the others stay solid, and a legend explains it", async ({
    page,
  }) => {
    await seedComparison(page);
    await stubTiles(page);
    await page.goto("/map");
    const pins = page.getByTestId("map-pin");
    await expect(pins).toHaveCount(5);

    const approx = pins.filter({ has: page.getByTestId("pin-approximate") });
    await expect(approx).toHaveCount(1);
    await expect(approx).toContainText("יוחננוף");
    await expect(approx).toContainText("מיקום משוער");
    await expect(approx).toHaveAttribute("data-approximate", "true");
    // Distinct from the solid pins, by outline and by words (not by colour alone).
    expect(await approx.evaluate((el) => getComputedStyle(el).borderTopStyle)).toBe("dashed");
    const solid = pins.filter({ hasNot: page.getByTestId("pin-approximate") });
    await expect(solid).toHaveCount(4);
    for (const pin of await solid.all()) {
      expect(await pin.evaluate((el) => getComputedStyle(el).borderTopStyle)).toBe("solid");
    }

    const legend = page.getByTestId("map-legend");
    await expect(legend).toBeVisible();
    await expect(legend).toContainText("חלול ומקווקו");
    await expect(legend).toContainText("המרחק אליו הוא הערכה");
    // On the schematic map (no WebGL) the area is a DOM element; on MapLibre it is a layer.
    if (await page.getByTestId("map-fallback").isVisible()) {
      await expect(page.getByTestId("map-approx-area")).toHaveCount(1);
    }

    const row = page.getByTestId("map-store-list").getByRole("button", { name: /יוחננוף/ });
    await expect(row).toContainText(APPROX_HE);
    await expect(row).toHaveAccessibleName(/כ־3\.6 ק"מ · מיקום משוער/);
    const exactRow = page.getByTestId("map-store-list").getByRole("button", { name: /רמי לוי/ });
    await expect(exactRow).toContainText('4.2 ק"מ');
    await expect(exactRow).not.toContainText("מיקום משוער");

    await row.click();
    const sheet = page.getByRole("dialog", { name: "יוחננוף · מודיעין" });
    await expect(sheet.getByTestId("sheet-distance")).toContainText(APPROX_HE);
    await expect(sheet.getByTestId("sheet-distance")).toContainText("מרכז היישוב");
    await noHorizontalScroll(page);
  });

  test("the legend and the hollow marker pass axe in both themes", async ({ page }) => {
    await seedComparison(page);
    await stubTiles(page);
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/map");
      await expect(page.getByTestId("map-legend")).toBeVisible();
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .include('[data-testid="map-legend"]')
        .include('[data-testid="map-store-list"]')
        .analyze();
      expect(
        results.violations.filter((v) => v.impact === "serious" || v.impact === "critical"),
        scheme,
      ).toEqual([]);
    }
  });

  test("in Arabic: chains in Latin letters, cities in Arabic, the note and the legend in Arabic", async ({
    page,
    baseURL,
  }) => {
    await page.context().addCookies([{ name: "sc-locale", value: "ar", url: baseURL! }]);
    await seedComparison(page);
    await stubTiles(page);
    await page.goto("/map");
    await expect(page.getByTestId("map-pin")).toHaveCount(5);
    const list = page.getByTestId("map-store-list");
    await expect(list).toContainText("Yochananof");
    await expect(list).toContainText("نحو 3.6 كم · الموقع تقريبي");
    await expect(page.getByTestId("map-legend")).toContainText("موقع تقريبي");
    const hebrew = await page
      .locator("main")
      .evaluate((main) => /[֐-׿]/.test(main.textContent ?? ""));
    expect(hebrew).toBe(false);
  });
});
