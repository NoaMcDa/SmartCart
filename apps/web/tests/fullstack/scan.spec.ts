import { expect, test } from "@playwright/test";
import {
  API_BASE_URL,
  DISCLAIMER,
  MILK_BARCODE,
  SHUFERSAL,
  nearestStore,
  seedShopper,
  stubSupabase,
} from "./helpers";

/**
 * Barcode result against the real lookup. /scan has no URL parameter for a code (the camera or
 * the manual field are the inputs), so the test types the barcode, which runs the same lookup as
 * a camera read. A fixture barcode every chain sells: the price here (the home store, the default
 * store), the cheapest nearby, and a cheaper any-brand substitute, labeled.
 */
test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

test("a typed barcode shows the price here, the cheapest nearby and a labeled substitute", async ({
  page,
  request,
}) => {
  const home = await nearestStore(request, SHUFERSAL);
  await stubSupabase(page);
  await seedShopper(page, home.store_id);
  const lookups: string[] = [];
  page.on("request", (req) => {
    if (req.url().startsWith(`${API_BASE_URL}/items/barcode/`)) lookups.push(req.url());
  });

  await page.goto("/scan");
  await expect(page.getByRole("heading", { level: 1, name: "סריקת ברקוד" })).toBeVisible();
  // The store picker comes from /stores/nearest; the home store is pre-selected.
  await expect(page.getByTestId("scan-store")).toHaveValue(String(home.store_id));

  // A wrong check digit never reaches the API.
  const field = page.getByLabel(/ברקוד \(13 ספרות/);
  await field.fill("7290004131075");
  await page.getByRole("button", { name: "חיפוש" }).click();
  await expect(page.getByText("הספרות לא מרכיבות ברקוד תקין")).toBeVisible();
  expect(lookups).toHaveLength(0);

  await field.fill(MILK_BARCODE);
  await page.getByRole("button", { name: "חיפוש" }).click();
  const card = page.getByTestId("scan-result");
  await expect(card).toBeVisible();
  expect(lookups[0]).toContain(`/items/barcode/${MILK_BARCODE}`);
  expect(lookups[0]).toContain(`store_id=${home.store_id}`);
  await expect(card.getByRole("heading", { level: 2 })).toContainText("חלב תנובה 3%");
  await expect(page.getByTestId("scan-here")).toContainText(/₪\s7\.45/);
  await expect(page.getByTestId("scan-cheapest")).toContainText(/₪\s4\.90/);
  await expect(page.getByTestId("scan-cheapest")).toContainText("מחסני השוק");
  const substitute = page.getByTestId("scan-substitute");
  await expect(substitute).toContainText(/₪\s4\.60/);
  await expect(substitute.locator('[data-variant="substitute"]')).toHaveText("תחליף");
  for (const row of ["scan-here", "scan-cheapest", "scan-substitute"]) {
    await expect(page.getByTestId(row).locator("time[datetime]")).toHaveCount(1);
  }
  await expect(card).toContainText(DISCLAIMER.replace(/\.$/, ""));

  // An unknown but valid code: no guess (D5).
  await page.getByRole("button", { name: "סריקת מוצר נוסף" }).click();
  await field.fill("5901234123457");
  await page.getByRole("button", { name: "חיפוש" }).click();
  await expect(page.getByTestId("scan-notfound")).toContainText("לא ננחש מוצר");
});
