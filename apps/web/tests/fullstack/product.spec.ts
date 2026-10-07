import { expect, test, type APIRequestContext } from "@playwright/test";
import {
  API_BASE_URL,
  DISCLAIMER,
  SHUFERSAL,
  mintToken,
  nearestStore,
  putServerProfile,
  seedShopper,
  signIn,
  stubSupabase,
} from "./helpers";

/**
 * Product detail with real prices and the real price history, and price-drop alerts. The milk's
 * history at the home store has two prices: 7.12 from the fixtures' day and 7.45 from the demo's
 * second day (scripts/demo/neighborhood.py), both from loaded files.
 */
test.use({ viewport: { width: 1280, height: 900 } });

const MILK = "חלב טרי 3%";

async function canonicalId(request: APIRequestContext, name: string): Promise<number> {
  const res = await request.get(`${API_BASE_URL}/search?q=${encodeURIComponent(name)}&limit=5`);
  const body = (await res.json()) as {
    hits: Array<{ canonical: { canonical_id: number; display_name_he: string } }>;
  };
  const hit = body.hits.find((h) => h.canonical.display_name_he === name);
  expect(hit, `no search hit for ${name}`).toBeDefined();
  return hit!.canonical.canonical_id;
}

test("product detail: every store's price with its time, and 90 days of price history", async ({
  page,
  request,
}) => {
  const home = await nearestStore(request, SHUFERSAL);
  const milk = await canonicalId(request, MILK);
  await stubSupabase(page);
  await seedShopper(page, home.store_id);
  await page.goto(`/product/${milk}?name=${encodeURIComponent(MILK)}`);

  await expect(page.getByRole("heading", { level: 1, name: MILK })).toBeVisible();
  // Variants by unit price: two milk brands in the radius (the second only at Machsanei Hashuk).
  const variants = page.getByTestId("variants").locator("li");
  await expect(variants).toHaveCount(2);
  // One row per store in the radius, each with its update time.
  const prices = page.getByTestId("store-prices").locator("tbody tr");
  await expect(prices).toHaveCount(3);
  for (const row of await prices.all()) await expect(row).toContainText("עודכן");
  await expect(prices.filter({ hasText: "שופרסל שלי תל אביב" })).toContainText(/₪\s7\.45/);

  // History at my store (the default): a real series from change events, with the change.
  const history = page.getByTestId("price-history");
  await expect(page.getByRole("heading", { level: 2, name: "היסטוריית מחירים" })).toBeVisible();
  await expect(page.getByTestId("history-chart")).toBeVisible();
  await expect(page.getByTestId("history-store").locator("option").first()).toContainText(
    "הסניף שלי",
  );
  await page.getByRole("radio", { name: "מדף" }).click();
  await expect(page.getByTestId("history-chart")).toContainText("מחיר מדף");
  const table = page.getByTestId("history-table");
  await expect(table).toContainText("7.12");
  await expect(table).toContainText("7.45");
  expect(await table.getByRole("row").count()).toBeGreaterThanOrEqual(3);
  await expect(history.locator("time[datetime]").first()).toBeVisible();
  await expect(history).toContainText(DISCLAIMER);

  // Signed out (the build has Supabase configured), alerts ask for sign-in instead of failing.
  const alertMe = page.getByTestId("alert-me");
  await expect(alertMe.getByRole("button", { name: "התחברות" })).toBeVisible();
});

test("signed in: an alert from product detail reaches the API, is listed on /alerts and deleted", async ({
  page,
  request,
}) => {
  const home = await nearestStore(request, SHUFERSAL);
  const milk = await canonicalId(request, MILK);
  const token = await signIn(page);
  // The server profile carries the consented neighborhood alerts are stored with.
  await putServerProfile(request, token, home.store_id);
  await seedShopper(page, home.store_id);
  const auth = { authorization: `Bearer ${mintToken()}` };
  const existing = (await (
    await request.get(`${API_BASE_URL}/me/alerts`, { headers: auth })
  ).json()) as Array<{ id: number }>;
  for (const a of existing) {
    await request.delete(`${API_BASE_URL}/me/alerts/${a.id}`, { headers: auth });
  }

  await page.goto(`/product/${milk}?name=${encodeURIComponent(MILK)}`);
  await page.getByTestId("variants").waitFor();
  const region = page.getByRole("region", { name: "התראה כשהמחיר יורד" });
  await region.getByRole("textbox", { name: /התריעי לי מתחת ל-₪/ }).fill("0.55");
  await region.getByRole("button", { name: "יצירת התראה" }).click();
  await expect(region.getByTestId("alert-created")).toContainText(/₪\s0\.55/);
  await expect(region.getByTestId("alert-existing")).toHaveCount(1);

  // The alert is the API's: stored for the demo user, under row-level security.
  const stored = (await (
    await request.get(`${API_BASE_URL}/me/alerts`, { headers: auth })
  ).json()) as Array<{ id: number; canonical_id: number; threshold_unit_price: string }>;
  expect(stored).toHaveLength(1);
  expect(stored[0]).toMatchObject({ canonical_id: milk });
  expect(Number(stored[0]!.threshold_unit_price)).toBe(0.55);

  await page.goto("/alerts");
  await expect(page.getByRole("heading", { level: 1, name: "התראות" })).toBeVisible();
  const item = page.getByTestId("alert-item");
  await expect(item).toHaveCount(1);
  await expect(item).toContainText(MILK);
  await item.getByRole("button", { name: `מחיקת ההתראה על ${MILK}` }).click();
  await expect(page.getByTestId("alerts-empty")).toBeVisible();
  const after = (await (
    await request.get(`${API_BASE_URL}/me/alerts`, { headers: auth })
  ).json()) as unknown[];
  expect(after).toHaveLength(0);
});

test("signed out: /alerts asks to sign in", async ({ page, request }) => {
  const home = await nearestStore(request, SHUFERSAL);
  await stubSupabase(page);
  await seedShopper(page, home.store_id);
  await page.goto("/alerts");
  await expect(page.getByTestId("alerts-signin")).toBeVisible();
});
