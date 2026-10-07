import { expect, test } from "@playwright/test";
import {
  API_BASE_URL,
  DEMO_LIST,
  DEVICE_POSITION,
  DISCLAIMER,
  money,
  onboard,
  pasteList,
  stubSupabase,
} from "./helpers";

/**
 * The MVP path against the real API: onboarding, a pasted Hebrew list, the three plans with the
 * net saving versus the home store, and the split view. Numbers are asserted against the API's
 * own answer for the same request (the browser's /optimize response), never against constants
 * from the mocks, so a pricing change in the pipeline shows up as an inconsistency, not a typo.
 */
test.use({
  viewport: { width: 1280, height: 900 },
  geolocation: DEVICE_POSITION,
  permissions: ["geolocation"],
});

type Breakdown = {
  basket_saving: string;
  travel_cost: string;
  extra_stop_cost: string;
  net_saving: string;
};
type Plan = {
  kind: string;
  total: string;
  recommended: boolean;
  breakdown: Breakdown | null;
  stores: Array<{ store: { store_id: number; store_name: string; chain_name: string } }>;
};
type OptimizeResponse = { single: Plan; split: Plan | null; minimum_effort: Plan | null };

test("onboarding, a Hebrew list, three plans with the net saving versus my store, the split view", async ({
  page,
}, testInfo) => {
  await stubSupabase(page);
  const optimizeBodies: OptimizeResponse[] = [];
  page.on("response", async (res) => {
    if (res.url() === `${API_BASE_URL}/optimize` && res.request().method() === "POST") {
      optimizeBodies.push((await res.json()) as OptimizeResponse);
    }
  });

  // 1. Onboarding through its screens; the stored location is rounded to the neighborhood.
  await onboard(page);
  const profile = await page.evaluate(() => JSON.parse(localStorage.getItem("sc-profile") ?? "{}"));
  expect(profile).toMatchObject({
    onboardingDone: true,
    homeChainId: "shufersal",
    location: { lat: 32.085, lon: 34.82 },
  });

  // 2. The list: /parse-list resolves every Hebrew row, with quantities and weights.
  await pasteList(page, DEMO_LIST);
  const rows = page.getByTestId("list-row");
  await expect(rows).toHaveCount(8);
  for (const name of ["חלב טרי 3%", "קוטג' 5%", "לחם אחיד", "עגבניות שרי", "שמן קנולה"]) {
    await expect(rows.filter({ hasText: name })).toHaveCount(1);
  }
  await expect(rows.filter({ hasText: "עגבניות שרי" })).toContainText("מחיר משוער · שקיל");
  // The estimate comes from a real /compare: three stores within 5 km.
  await expect(page.getByText('הערכת סל ב-3 סניפים עד 5 ק"מ')).toBeVisible();

  // 3. Results. Against the real API the first comparison may not know the home store yet: the
  // onboarding stores a chain, and the web app turns it into a store id only on the split, map
  // and store screens (adoptHomeStore). Recorded, not hidden: docs/fullstack.md, known gaps.
  await page.getByRole("link", { name: "השווי" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "איפה הכי זול השבוע?" })).toBeVisible();
  await expect(page.getByTestId("plan-single")).toBeVisible();
  if (await page.getByTestId("no-home-store").isVisible()) {
    testInfo.annotations.push({
      type: "known gap",
      description:
        "first results after onboarding have no home store (no saving) until /split adopts one",
    });
  }

  // 4. The split view: both stores, subtotals, and the net saving versus the home store.
  await page.goto("/split");
  await expect(page.getByRole("heading", { level: 1, name: "פיצול סל" })).toBeVisible();
  const summary = page.getByTestId("split-summary");
  await expect(summary).toContainText("חיסכון נטו מול שופרסל");
  const splitNet = money(await page.getByTestId("net-saving").textContent());
  expect(splitNet).toBeGreaterThan(0);
  const columns = page.locator('[data-testid^="split-column-"]');
  await expect(columns).toHaveCount(2);
  await expect(page.getByTestId("waterfall")).toBeVisible();

  // 5. Back to the results, now with the home store: three plans and the hero number.
  optimizeBodies.length = 0;
  await page.goto("/compare");
  const split = page.getByTestId("plan-split");
  const single = page.getByTestId("plan-single");
  const home = page.getByTestId("plan-minimum_effort");
  await expect(split).toBeVisible();
  await expect(single).toBeVisible();
  await expect(home).toBeVisible();
  await expect(page.getByTestId("no-home-store")).toHaveCount(0);
  await expect(split).toHaveAttribute("data-recommended", "true");
  await expect(home).toContainText("מינימום מאמץ · הסופר שלך");

  await expect.poll(() => optimizeBodies.length).toBeGreaterThan(0);
  const opt = optimizeBodies[optimizeBodies.length - 1]!;
  expect(opt.split?.recommended).toBe(true);
  expect(opt.minimum_effort?.stores[0]?.store.chain_name).toBe("שופרסל");
  const b = opt.split!.breakdown!;
  const net = Number(b.net_saving);
  // The hero number: basket saving minus travel minus the extra stop, versus my store (D7).
  expect(net).toBeCloseTo(
    Number(b.basket_saving) - Number(b.travel_cost) - Number(b.extra_stop_cost),
    2,
  );
  expect(net).toBeGreaterThan(0);
  await expect(page.getByTestId("plan-split-saving")).toContainText("חוסך");
  await expect(page.getByTestId("plan-split-saving")).toContainText(
    `לעומת ${opt.minimum_effort!.stores[0]!.store.store_name}`,
  );
  expect(
    money(
      await page.getByTestId("plan-split-saving").locator('span[dir="ltr"]').first().textContent(),
    ),
  ).toBeCloseTo(net, 0);
  expect(money(await page.getByTestId("plan-split-total").textContent())).toBeCloseTo(
    Number(opt.split!.total),
    0,
  );
  // The split view showed the same saving (both follow the API arithmetic).
  expect(splitNet).toBeCloseTo(net, 0);

  // Trust signals: an update time on every plan, the checkout disclaimer, no "most expensive".
  for (const card of [split, single, home]) {
    await expect(card.locator("time[datetime]").first()).toBeVisible();
  }
  await expect(page.getByTestId("disclaimer")).toContainText(DISCLAIMER);
  expect(await page.locator("main").textContent()).not.toMatch(/היקר ביותר|הכי יקר/);
});
