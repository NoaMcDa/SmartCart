import { expect, test, type Page } from "@playwright/test";
import { ACCEPTANCE_TEXT, mockApi, pasteList, seedProfile } from "./core-helpers";

const rows = (page: Page) => page.getByTestId("list-row");
const quantities = (page: Page) => rows(page).locator("output").allTextContents();
const estimate = (page: Page) => page.getByTestId("basket-estimate").locator('span[dir="ltr"]');

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
]) {
  test.describe(`list builder at ${viewport.width} px`, () => {
    test.use({ viewport });

    test.beforeEach(async ({ page }) => {
      await mockApi(page);
      await seedProfile(page);
    });

    test("pasting the acceptance list yields three grouped rows with chips, persisted", async ({
      page,
    }) => {
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1, name: "הקנייה השבועית" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "הרשימה ריקה" })).toBeVisible();

      await pasteList(page, ACCEPTANCE_TEXT);
      await expect(rows(page)).toHaveCount(3);
      expect(await quantities(page)).toEqual(["1", "2", "1"]);
      for (const dept of ["מוצרי חלב", "מזווה", "דגים ובשר"]) {
        await expect(page.getByRole("heading", { level: 2, name: new RegExp(dept) })).toBeVisible();
      }
      for (const row of await rows(page).all()) {
        const chip = row.getByRole("button", { name: /^רמת גמישות: / });
        await expect(chip).toBeVisible();
        await expect(chip.locator("svg")).toHaveCount(1);
      }
      const salmon = rows(page).filter({ hasText: "סלמון" });
      await expect(salmon.getByText("מחיר משוער · שקיל")).toBeVisible();
      await expect(salmon.locator('[data-variant="estimated"] svg')).toHaveCount(1);

      // The estimate is a range in one LTR island and follows the stepper.
      await expect(estimate(page)).toHaveText(/^₪\s[\d,]+–₪\s[\d,]+$/);
      const before = await estimate(page).textContent();
      await page.getByRole("button", { name: "הוסיפי כמות של חלב טרי 3%, 1 ליטר" }).click();
      await expect(estimate(page)).not.toHaveText(before!);

      // 44 px targets on the row controls.
      for (const button of await rows(page).first().getByRole("button").all()) {
        const label = await button.getAttribute("aria-label");
        if (label?.startsWith("רמת גמישות")) continue; // 30 px pill with a 44 px ::after hit area
        const box = (await button.boundingBox())!;
        expect(box.height, label ?? "").toBeGreaterThanOrEqual(44);
        expect(box.width, label ?? "").toBeGreaterThanOrEqual(44);
      }

      await page.reload();
      await expect(rows(page)).toHaveCount(3);
      expect(await quantities(page)).toEqual(["2", "2", "1"]);
      await expect(page.getByRole("link", { name: "השווי" })).toBeVisible();

      if (viewport.width === 390) {
        const { scrollWidth, clientWidth } = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
        }));
        expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
      } else {
        // Desktop: the estimate is a side card next to the list.
        await expect(page.getByRole("heading", { name: "גמישות ברשימה" })).toBeVisible();
        const list = (await page.getByLabel("הרשימה", { exact: true }).boundingBox())!;
        const aside = (await page.getByRole("complementary", { name: "הערכת סל" }).boundingBox())!;
        expect(aside.x + aside.width).toBeLessThanOrEqual(list.x + 1); // RTL: aside on the left
      }
    });

    test("flagged rows confirm inline, unknown rows stay explicit, Compare stays usable", async ({
      page,
    }) => {
      await page.goto("/");
      await pasteList(page, "שמן זית, קקטוס");
      const confirm = page.getByRole("group", { name: "אישור הפריט שמן זית" });
      await expect(confirm).toContainText('כתבת "שמן זית". התכוונת ל');
      await expect(page.getByRole("link", { name: "השווי" })).toBeVisible();
      await expect(page.getByTestId("not-found-row")).toContainText('לא מצאנו את "קקטוס"');

      await confirm.getByRole("button", { name: "בחרי אחר" }).click();
      await confirm.getByRole("button", { name: "שמן זית כתית, 1 ליטר" }).click();
      await expect(confirm).toBeHidden();
      await expect(rows(page).first()).toContainText("שמן זית כתית, 1 ליטר");

      await pasteList(page, "שמן זית");
      const again = page.getByRole("group", { name: "אישור הפריט שמן זית" });
      await again.getByRole("button", { name: /^כן/ }).click();
      await expect(again).toBeHidden();

      const mic = page.getByRole("button", { name: "הכתבה קולית" });
      await expect(mic).toHaveAttribute("aria-disabled", "true");
      await mic.hover();
      await expect(page.getByRole("tooltip", { name: "בקרוב" })).toBeVisible();
    });
  });
}

test.describe("flexibility sheet", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("preselects, cancels, saves and remembers the category default", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await pasteList(page, "חלב, רסק עגבניות");
    const milk = rows(page).filter({ hasText: "חלב טרי" });
    const chip = milk.getByRole("button", { name: /^רמת גמישות/ });
    await expect(chip).toHaveAccessibleName("רמת גמישות: כל מותג");

    await chip.click();
    const sheet = page.getByRole("dialog", { name: "חלב טרי 3%, 1 ליטר" });
    await expect(sheet.getByRole("radio", { name: /כל מותג/ })).toBeChecked();
    await expect(sheet.getByText("תנובה, טרה, יטבתה, מותג פרטי", { exact: false })).toBeVisible();
    await sheet.getByRole("radio", { name: /מוצר מדויק/ }).check();
    await sheet.getByRole("button", { name: "ביטול" }).click();
    await expect(sheet).toBeHidden();
    await expect(chip).toHaveAccessibleName("רמת גמישות: כל מותג");
    await expect(chip).toBeFocused();

    await chip.click();
    await sheet.getByRole("radio", { name: /תחליף קרוב/ }).check();
    await sheet.getByRole("checkbox", { name: "אחוז שומן אחר" }).check();
    await sheet.getByRole("switch", { name: "זכרי בחירה זו לכל סוגי החלב" }).click();
    await sheet.getByRole("button", { name: "שמרי" }).click();
    await expect(sheet).toBeHidden();
    await expect(chip).toHaveAccessibleName("רמת גמישות: תחליף קרוב");
    const stored = await page.evaluate(() =>
      JSON.parse(window.localStorage.getItem("sc-list-v1") ?? "{}"),
    );
    expect(stored.flexDefaults).toEqual({ "dairy.milk": "close" });
    expect(stored.items[0].allow).toEqual(["fat_pct"]);

    // Escape closes too.
    await chip.click();
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();

    // A new milk row picks up the remembered default.
    await milk.getByRole("button", { name: /^הסרת/ }).click();
    await pasteList(page, "חלב");
    await expect(
      rows(page)
        .filter({ hasText: "חלב טרי" })
        .getByRole("button", { name: /^רמת גמישות/ }),
    ).toHaveAccessibleName("רמת גמישות: תחליף קרוב");
  });
});
