import { expect, test } from "@playwright/test";
import { mockApi, openWeeklyResults } from "./core-helpers";

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
]) {
  test.describe(`substitution card at ${viewport.width} px`, () => {
    test.use({ viewport });

    test("why the swap is safe, continue to the next, keep the original", async ({ page }) => {
      const calls = await mockApi(page);
      await openWeeklyResults(page);
      await page
        .getByTestId("plan-single")
        .getByRole("link", { name: /3 פריטים הוחלפו/ })
        .click();
      await expect(page).toHaveURL(/\/compare\/substitution\/10101\?plan=single$/);
      await expect(page.getByRole("heading", { level: 1, name: "פרטי החלפה" })).toBeVisible();

      const card = page.getByTestId("sub-card");
      await expect(card).toContainText("החלפה 1 מתוך 3 · רמי לוי");
      await expect(card.getByRole("heading", { level: 2 })).toHaveText(
        "החלפנו את חלב טרי 3% תנובה, 1 ליטר ב-חלב טרי 3% יטבתה, 1 ליטר",
      );
      await expect(page.getByTestId("sub-original")).toContainText(/₪\s6.90/);
      await expect(page.getByTestId("sub-original")).toContainText(/₪\s0.69 ל-100 מ"ל/);
      await expect(page.getByTestId("sub-substitute")).toContainText(/₪\s5.90/);
      await expect(page.getByTestId("sub-saving")).toContainText(/₪\s1.00 × 2 יחידות/);
      await expect(page.getByTestId("sub-saving")).toContainText(/₪\s2.00/);
      await expect(page.getByTestId("sub-source")).toContainText("ביטחון 98%");
      await expect(page.getByTestId("sub-source").locator("time[datetime]")).toHaveCount(1);
      await expect(page.getByTestId("sub-disclaimer")).toHaveText("המחיר הקובע הוא בקופה.");
      const tags = card.getByRole("list", { name: "השוואת תכונות" }).locator("[data-variant]");
      await expect(tags).toHaveCount(4);
      for (const tag of await tags.all()) await expect(tag.locator("svg")).toHaveCount(1);
      await expect(card.locator('[data-variant="matched"]')).toHaveCount(3);
      await expect(card.locator('[data-variant="differs"]')).toHaveText("יטבתה במקום תנובה");
      for (const button of await card.getByRole("button").all()) {
        expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      }

      await card.getByRole("button", { name: "בסדר, להחלפה הבאה" }).click();
      await expect(page).toHaveURL(/\/compare\/substitution\/10103\?plan=single$/);
      await expect(page.getByTestId("sub-card")).toContainText("החלפה 2 מתוך 3");
      await expect(page.getByText("חלבון 3.3 ג' ל-100 מ\"ל · לא מאומת")).toBeVisible();

      await page.getByRole("button", { name: "השאירי את המקורי" }).click();
      await expect(page).toHaveURL(/\/compare$/);
      await expect(page.getByTestId("flash")).toContainText("השארנו את המוצר המקורי");
      await expect(page.getByTestId("plan-single")).toBeVisible();
      if (calls.length) {
        expect(calls.find((c) => c.path === "/feedback/substitution")?.body).toMatchObject({
          verdict: "accepted",
          substitute_item_id: 10101,
        });
        await expect
          .poll(() =>
            calls
              .filter((c) => c.path === "/optimize")
              .some((c) =>
                (c.body as { items: Array<Record<string, unknown>> }).items.some(
                  (i) => i.canonical_id === 1003 && i.flex_level === "exact",
                ),
              ),
          )
          .toBe(true);
      }

      await page.getByRole("link", { name: "חזרה לרשימה" }).click();
      await expect(
        page
          .getByTestId("list-row")
          .filter({ hasText: "משקה סויה" })
          .getByRole("button", { name: /^רמת גמישות/ }),
      ).toHaveAccessibleName("רמת גמישות: מוצר מדויק");
    });

    test("not a good substitute records feedback and reverts", async ({ page }) => {
      const calls = await mockApi(page);
      await openWeeklyResults(page);
      await page.goto("/compare/substitution/10104?plan=single");
      const card = page.getByTestId("sub-card");
      await expect(card).toContainText("החלפה 3 מתוך 3");
      await expect(page.getByTestId("sub-saving")).toContainText(/₪\s4.80/);
      const reject = card.getByRole("button", { name: "לא תחליף טוב" });
      expect(await reject.evaluate((el) => getComputedStyle(el).color)).toBe("rgb(163, 45, 45)");
      await reject.click();
      await expect(page).toHaveURL(/\/compare$/);
      await expect(page.getByTestId("flash")).toContainText("תודה, הדיווח נשמר");
      if (calls.length) {
        expect(calls.find((c) => c.path === "/feedback/substitution")?.body).toEqual({
          canonical_id: 1004,
          original_item_id: 901004,
          substitute_item_id: 10104,
          verdict: "not_good",
          source: "substitution_card",
        });
      }
      const stored = await page.evaluate(() =>
        JSON.parse(window.localStorage.getItem("sc-list-v1") ?? "{}"),
      );
      const paste = stored.items.find(
        (i: { canonical: { canonical_id: number } | null }) => i.canonical?.canonical_id === 1004,
      );
      expect(paste).toMatchObject({ flexLevel: "exact", exactItemId: 901004 });
    });
  });
}

test("an unknown substitution says so and links back", async ({ page }) => {
  await mockApi(page);
  await page.goto("/compare/substitution/42");
  await expect(page.getByTestId("sub-not-found")).toContainText("לא מצאנו את ההחלפה הזו");
});
