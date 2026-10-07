import { expect, test, type Page } from "@playwright/test";
import { API_BASE_URL } from "../../src/api/config";
import { compareFixture, optimizeFixture } from "../../src/mocks/fixtures";
import { mockApi, openWeeklyResults, seedProfile } from "./core-helpers";
import { KEYS, noHorizontalScroll, seedComparison, stubTiles } from "./secondary.helpers";

/**
 * Phase 2 web follow-ups (issue #91 and the UI halves of #12, #30, #55, #59): the design-system
 * page, the 195 px top bar, the methodology links, promo confidence, real map pins and account
 * deletion. The beta consent sheet needs a build with NEXT_PUBLIC_BETA_EVENTS=1, which this suite
 * is not built with; it is covered by the unit tests (src/features/consent) and checked here only
 * to be absent from a default build.
 */

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
};

/** Answers `POST path` with `body`, on top of `mockApi` (later routes win; preflights fall through). */
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

/** Adds real coordinates to every store in a response, except those in `skip` (which get null). */
function withCoords(value: unknown, skip: number[] = []): unknown {
  if (Array.isArray(value)) return value.map((v) => withCoords(v, skip));
  if (value && typeof value === "object") {
    const obj = Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, withCoords(v, skip)]),
    ) as Record<string, unknown>;
    if ("store_id" in obj && "distance_m" in obj && "items" in obj) {
      const id = obj.store_id as number;
      return skip.includes(id)
        ? { ...obj, lat: null, lon: null }
        : { ...obj, lat: 31.9 + (id - 100) * 0.002, lon: 35.01 + (id - 100) * 0.003 };
    }
    return obj;
  }
  return value;
}

test.describe("/design-system shows the trust components in both themes", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("UpdatedAt, TrustedPrice, CheckChip, the substitute and club tags, promo confidence and Price", async ({
    page,
  }) => {
    await page.goto("/design-system");
    const substituteBg: string[] = [];
    for (const theme of ["light", "dark"] as const) {
      const panel = page.getByTestId(`ds-panel-${theme}`);

      const updated = panel.getByTestId(`ds-updated-${theme}`);
      await expect(updated).toContainText("מחירים עודכנו היום 06:40");
      await expect(updated).toContainText("עודכן אתמול 18:20");
      await expect(updated).toContainText("עודכן לפני 3 ימים");
      await expect(updated).toContainText("מועד העדכון לא ידוע");
      await expect(updated.locator("time[datetime]")).toHaveCount(3);

      const trusted = panel.getByTestId(`ds-trusted-${theme}`);
      await expect(trusted.locator('[data-trust-scope="price"]')).toHaveCount(2);
      await expect(trusted.locator("time[datetime]")).toHaveCount(2);
      await expect(trusted).toContainText(/₪\s12\.90/);
      await expect(trusted).toContainText(/₪\s4\.50/);

      const tags = panel.getByTestId(`ds-trust-tags-${theme}`);
      await expect(tags.locator('[data-variant="substitute"]')).toHaveText("תחליף");
      await expect(tags.locator('[data-variant="club"]')).toHaveText("מבצע מועדון");
      await expect(tags.getByText("ביטחון 96%")).toBeVisible();
      await expect(tags.getByText("ביטחון 72%")).toBeVisible();
      await expect(tags.getByText("לא נבדק")).toBeVisible();
      for (const tag of await tags.locator("[data-variant]").all()) {
        await expect(tag.locator("svg")).toHaveCount(1); // never color alone
      }
      substituteBg.push(
        await tags
          .locator('[data-variant="substitute"]')
          .evaluate((el) => getComputedStyle(el).backgroundColor),
      );

      const allow = panel.getByRole("group", { name: "אפשר לוותר על" });
      await expect(allow.getByRole("checkbox", { name: "מותג אחר" })).toBeChecked();
      await allow.getByText("טעם אחר").click();
      await expect(allow.getByRole("checkbox", { name: "טעם אחר" })).toBeChecked();
      await expect(allow.getByRole("checkbox", { name: "לא זמין" })).toBeDisabled();

      const sizes = panel.getByTestId(`ds-price-sizes-${theme}`).locator('span[dir="ltr"]');
      await expect(sizes).toHaveCount(7);
      for (const price of await sizes.all()) await expect(price).toContainText("₪");
    }
    expect(substituteBg[0]).not.toBe(substituteBg[1]); // the tag follows the theme tokens
  });
});

test.describe("top bar at 195 px (200% zoom on a phone)", () => {
  test.use({ viewport: { width: 195, height: 700 } });

  for (const path of ["/", "/compare", "/design-system"]) {
    test(`${path}: the bar has no horizontal overflow and keeps its 44 px targets`, async ({
      page,
    }) => {
      await page.goto(path);
      const bar = page.locator('header:has([data-testid="top-nav"])');
      await expect(bar).toBeVisible();
      const m = await bar.evaluate((header) => ({
        scroll: header.scrollWidth,
        client: header.clientWidth,
        boxes: [...header.querySelectorAll<HTMLElement>("a, [role=switch]")]
          .filter((el) => el.getClientRects().length > 0)
          .map((el) => {
            const r = el.getBoundingClientRect();
            return { left: r.left, right: r.right, height: r.height };
          }),
      }));
      expect(m.scroll).toBeLessThanOrEqual(m.client);
      expect(m.boxes.length).toBeGreaterThanOrEqual(2);
      for (const b of m.boxes) {
        expect(b.left).toBeGreaterThanOrEqual(-0.5);
        expect(b.right).toBeLessThanOrEqual(195.5);
        expect(b.height).toBeGreaterThanOrEqual(44);
      }
    });
  }
});

test.describe("methodology links", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the results footer links it next to the checkout disclaimer", async ({ page }) => {
    await mockApi(page);
    await openWeeklyResults(page);
    const footer = page.getByTestId("disclaimer");
    await expect(footer).toContainText("המחיר הקובע הוא בקופה");
    await footer.getByRole("link", { name: "איך אנחנו משווים מחירים" }).click();
    await expect(page).toHaveURL(/\/methodology$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "איך אנחנו משווים מחירים" }),
    ).toBeVisible();
  });

  test("the substitution card links it", async ({ page }) => {
    await mockApi(page);
    await openWeeklyResults(page);
    await page
      .getByTestId("plan-single")
      .getByRole("link", { name: /3 פריטים הוחלפו/ })
      .click();
    await expect(page.getByTestId("sub-card")).toBeVisible();
    await page
      .getByTestId("sub-methodology")
      .getByRole("link", { name: "איך אנחנו מחליטים מה תחליף מתאים" })
      .click();
    await expect(page).toHaveURL(/\/methodology$/);
  });
});

test.describe("promo confidence", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the line details show the score when the API gives one, otherwise not checked", async ({
    page,
  }) => {
    await mockApi(page);
    const res = optimizeFixture();
    let scored = false;
    for (const plan of [res.single, res.split, res.minimum_effort]) {
      for (const { store } of plan?.stores ?? []) {
        for (const item of store.items) {
          if (!scored && item.promo_description && plan === res.single) {
            item.promo_confidence = 0.96;
            scored = true;
          }
        }
      }
    }
    expect(scored).toBe(true);
    await overridePost(page, "/optimize", res);
    await openWeeklyResults(page);
    await page.getByText(/^פירוט הסל/).click();
    const details = page.getByTestId("basket-details");
    await expect(details.getByText("ביטחון 96%")).toHaveCount(1);
    await expect(details.getByText("לא נבדק").first()).toBeVisible();
  });
});

test.describe("map pins use real store coordinates", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("no approximation note once every store has lat and lon", async ({ page }) => {
    await seedComparison(page);
    await overridePost(page, "/compare", withCoords(compareFixture()));
    await overridePost(page, "/optimize", withCoords(optimizeFixture()));
    await stubTiles(page);
    await page.goto("/map");
    await expect(page.getByTestId("map-pin")).toHaveCount(5);
    await expect(page.getByTestId("map-approx")).toHaveCount(0);
    await noHorizontalScroll(page);
  });

  test("the existing note stays while a store has null coordinates", async ({ page }) => {
    await seedComparison(page);
    await overridePost(page, "/compare", withCoords(compareFixture(), [102]));
    await overridePost(page, "/optimize", withCoords(optimizeFixture(), [102]));
    await stubTiles(page);
    await page.goto("/map");
    await expect(page.getByTestId("map-pin")).toHaveCount(5);
    await expect(page.getByTestId("map-approx")).toContainText("הכיוון שלו על המפה מוצג בקירוב");
  });

  test("without coordinates in the response (today's mock) the note is shown", async ({ page }) => {
    await seedComparison(page);
    await stubTiles(page);
    await page.goto("/map");
    await expect(page.getByTestId("map-pin")).toHaveCount(5);
    await expect(page.getByTestId("map-approx")).toBeVisible();
  });
});

test.describe("delete my data", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("signed out it clears the device, never calls /me, and shows no hosted-account notice", async ({
    page,
  }) => {
    const calls = await mockApi(page);
    await seedProfile(page);
    await page.goto("/profile");
    await page.getByRole("button", { name: "מחקי את הנתונים שלי" }).click();
    await page.getByTestId("confirm-delete").click();
    await expect(page.getByTestId("delete-done")).toBeVisible();
    await expect(page.getByTestId("account-remains")).toHaveCount(0);
    expect(calls.filter((c) => c.path === "/me" || c.path.startsWith("/me/"))).toEqual([]);
    const leftovers = await page.evaluate(
      (keys) => keys.filter((k) => localStorage.getItem(k) !== null),
      [KEYS.profile, KEYS.list, KEYS.shopper],
    );
    expect(leftovers).toEqual([]);
  });
});

test.describe("beta events in a default build", () => {
  test("no consent sheet, no usage-events switch and no /events request without the beta flag", async ({
    page,
  }) => {
    const requests: string[] = [];
    page.on("request", (r) => {
      if (new URL(r.url()).pathname === "/events") requests.push(r.url());
    });
    await mockApi(page);
    await openWeeklyResults(page);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.goto("/profile");
    await expect(page.getByRole("switch", { name: "אירועי שימוש לבדיקת הבטא" })).toHaveCount(0);
    expect(requests).toEqual([]);
    expect(await page.evaluate(() => localStorage.getItem("sc-events-consent"))).toBeNull();
  });
});
