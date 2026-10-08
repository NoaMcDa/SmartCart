import { expect, test } from "@playwright/test";
import { mockApi } from "./core-helpers";
import { israelToday } from "./phase3-helpers";
import { noHorizontalScroll, seed } from "./secondary.helpers";

/**
 * Correcting and deleting a recorded shop in the monthly view (issue #70): "תיקון הסכום" with
 * validation, delete with a confirm step and a 5 s undo, all on the device when signed out. The
 * account side (PUT, DELETE, rollback) is covered by the unit tests against the same mock handlers.
 */

const today = israelToday();
const entry = (id: string, total: number, store = "רמי לוי · מודיעין") => ({
  id,
  client_id: `00000000-0000-4000-8000-${id.padStart(12, "0")}`,
  date: today,
  store_id: 101,
  store_name: store,
  total,
  item_count: 7,
  plan: "single",
});

const stored = (page: import("@playwright/test").Page) =>
  page.evaluate(
    () =>
      JSON.parse(localStorage.getItem("sc-spend-v1") ?? '{"entries":[]}') as {
        entries: { id: string; total: number; corrected?: boolean }[];
      },
  );

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
]) {
  test.describe(`spend correction at ${viewport.width} px`, () => {
    test.use({ viewport });

    test.beforeEach(async ({ page }) => {
      await mockApi(page);
      await seed(page, {
        "sc-budget-v1": { monthly: 1000 },
        "sc-spend-v1": {
          version: 1,
          entries: [entry("1", 300), entry("2", 200, "יוחננוף · מודיעין")],
          pending: [],
        },
      });
      await page.goto("/profile#budget");
    });

    test("תיקון הסכום validates, then replaces the estimate everywhere and survives a reload", async ({
      page,
    }) => {
      const section = page.getByTestId("budget-section");
      await expect(section.getByTestId("budget-spent")).toHaveText(/^₪\s500$/);
      const first = section.getByTestId("spend-entry").filter({ hasText: "רמי לוי" });
      await expect(first).toContainText("הערכה");

      await first.getByRole("button", { name: /^תיקון הסכום/ }).click();
      const field = section.getByLabel("הסכום שנגבה בפועל (₪)");
      await expect(field).toBeFocused();
      await field.fill("0");
      await section.getByRole("button", { name: "שמירת הסכום" }).click();
      await expect(section.getByRole("alert")).toContainText("הזיני סכום חיובי");
      expect((await stored(page)).entries[0]!.total).toBe(300);
      await noHorizontalScroll(page);

      await field.fill("274,50");
      await section.getByRole("button", { name: "שמירת הסכום" }).click();
      await expect(section.getByTestId("spend-notice")).toContainText("הסכום עודכן");
      await expect(first).toContainText("סכום בפועל");
      await expect(section.getByTestId("budget-spent")).toHaveText(/^₪\s474\.50$/);
      await expect(section.getByTestId("budget-remaining-value")).toHaveText(/^₪\s525\.50$/);

      await page.reload();
      await expect(page.getByTestId("budget-spent")).toHaveText(/^₪\s474\.50$/);
      expect((await stored(page)).entries[0]).toMatchObject({ total: 274.5, corrected: true });
    });

    test("delete asks first, then offers ביטול, which brings the shop back", async ({ page }) => {
      const section = page.getByTestId("budget-section");
      const second = section.getByTestId("spend-entry").filter({ hasText: "יוחננוף" });
      await second.getByRole("button", { name: /^מחיקת הקנייה/ }).click();
      await expect(second).toContainText("למחוק את הקנייה");
      await second.getByRole("button", { name: "ביטול" }).click();
      expect((await stored(page)).entries).toHaveLength(2);

      await second.getByRole("button", { name: /^מחיקת הקנייה/ }).click();
      await second.getByTestId("spend-delete-confirm").click();
      await expect(section.getByTestId("spend-entry")).toHaveCount(1);
      await expect(section.getByTestId("budget-spent")).toHaveText(/^₪\s300$/);
      const bar = page.getByTestId("spend-undo-bar");
      await expect(bar).toContainText("הקנייה נמחקה");
      await bar.getByRole("button", { name: "ביטול" }).click();
      await expect(section.getByTestId("spend-entry")).toHaveCount(2);
      await expect(section.getByTestId("budget-spent")).toHaveText(/^₪\s500$/);
      expect((await stored(page)).entries).toHaveLength(2);
    });

    test("without undo the snackbar goes after 5 seconds and the deletion stays", async ({
      page,
    }) => {
      await page.clock.install();
      await page.reload();
      const section = page.getByTestId("budget-section");
      const first = section.getByTestId("spend-entry").filter({ hasText: "רמי לוי" });
      await first.getByRole("button", { name: /^מחיקת הקנייה/ }).click();
      await first.getByTestId("spend-delete-confirm").click();
      const bar = page.getByTestId("spend-undo-bar");
      await expect(bar).toBeVisible();
      await page.clock.fastForward(4000);
      await expect(bar).toBeVisible();
      await page.clock.fastForward(1500);
      await expect(bar).toBeHidden();
      await page.reload();
      await expect(page.getByTestId("spend-entry")).toHaveCount(1);
      expect((await stored(page)).entries.map((e) => e.id)).toEqual(["2"]);
    });

    test("by keyboard: both buttons are reachable and the confirm step is operable", async ({
      page,
    }) => {
      const section = page.getByTestId("budget-section");
      const first = section.getByTestId("spend-entry").first();
      const correct = first.getByRole("button", { name: /^תיקון הסכום/ });
      await correct.focus();
      await page.keyboard.press("Tab");
      await expect(first.getByRole("button", { name: /^מחיקת הקנייה/ })).toBeFocused();
      await page.keyboard.press("Enter");
      // Focus lands on the safe choice.
      await expect(first.getByRole("button", { name: "ביטול" })).toBeFocused();
      await page.keyboard.press("Enter");
      expect((await stored(page)).entries).toHaveLength(2);
    });
  });
}
