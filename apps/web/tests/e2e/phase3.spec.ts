import { expect, test } from "@playwright/test";
import { mockApi, openWeeklyResults, pasteList, seedProfile } from "./core-helpers";
import {
  failSpeech,
  hear,
  installFakeSpeech,
  israelToday,
  removeSpeech,
  speechStarts,
} from "./phase3-helpers";
import { KEYS, noHorizontalScroll, seed, seedComparison } from "./secondary.helpers";

/**
 * Phase 3 web features that need no real data (unblock round): voice list input (#65), monthly
 * budget and spend (#70), the scan page reading its code from the URL, and recipe to list (#71).
 * The routes behind them (`/parse-recipe`, `/me/spend`) are answered by `mockApi` from
 * src/mocks/handlers.phase3.ts.
 */

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
]) {
  test.describe(`voice list at ${viewport.width} px`, () => {
    test.use({ viewport });

    test("dictate, see what was heard, fix it, and only then parse it like a pasted list", async ({
      page,
    }) => {
      const calls = await mockApi(page);
      await seedProfile(page);
      await installFakeSpeech(page);
      await page.goto("/");

      await page.getByTestId("voice-open").click();
      const dialog = page.getByRole("dialog", { name: "הכתבה קולית" });
      await expect(dialog).toBeVisible();
      // Explained first; the microphone is not touched until the tap.
      await expect(dialog.getByTestId("voice-privacy")).toContainText(
        "לא מקליטים ולא שומרים אודיו",
      );
      expect(await speechStarts(page)).toBe(0);

      await dialog.getByTestId("voice-start").click();
      await expect(dialog.getByTestId("voice-status")).toContainText("מקשיבה");
      expect(await speechStarts(page)).toBe(1);
      await hear(page, { text: "חלב" }, { text: "שתי רסק עגבניות" }, { text: "סלמ", final: false });
      await expect(dialog.getByTestId("voice-live")).toContainText("שתי רסק עגבניות");
      await noHorizontalScroll(page);

      await dialog.getByTestId("voice-stop").click();
      const draft = dialog.getByLabel(/מה שמענו/);
      await expect(draft).toHaveValue("חלב\nשתי רסק עגבניות\nסלמ");
      // Nothing was parsed while the person is still reading and fixing it.
      expect(calls.filter((c) => c.path === "/parse-list")).toHaveLength(0);
      await draft.fill("חלב\nשתי רסק עגבניות\nסלמון");
      await dialog.getByTestId("voice-add").click();

      await expect(dialog).toBeHidden();
      await expect(page.getByTestId("list-row")).toHaveCount(3);
      await expect(page.getByText(/נוספו 3 פריטים מההכתבה/)).toBeVisible();
      const parse = calls.filter((c) => c.path === "/parse-list");
      expect(parse).toHaveLength(1);
      expect(parse[0]!.body).toMatchObject({ text: "חלב\nשתי רסק עגבניות\nסלמון" });
      // "שתי" became a quantity of 2 in the same parser a pasted list uses.
      const paste = page.getByTestId("list-row").filter({ hasText: "רסק עגבניות" });
      await expect(paste.locator("output")).toHaveText("2");
    });

    test("a denied microphone is explained and typing still works", async ({ page }) => {
      await mockApi(page);
      await seedProfile(page);
      await installFakeSpeech(page);
      await page.goto("/");
      await page.getByTestId("voice-open").click();
      await page.getByTestId("voice-start").click();
      await failSpeech(page, "not-allowed");
      const error = page.getByTestId("voice-error");
      await expect(error).toContainText("הגישה למיקרופון נחסמה");
      await expect(error).toContainText("להקליד או להדביק");
      await page.getByRole("button", { name: "חזרה להקלדה" }).click();
      await expect(page.getByRole("dialog")).toBeHidden();
      await pasteList(page, "חלב, קוטג'");
      await expect(page.getByTestId("list-row")).toHaveCount(2);
    });
  });
}

test.describe("voice list, other cases", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("without speech recognition the mic is hidden and a hint says typing is the way", async ({
    page,
  }) => {
    await mockApi(page);
    await seedProfile(page);
    await removeSpeech(page);
    await page.goto("/");
    await expect(page.getByTestId("voice-unsupported")).toContainText("הכתבה קולית לא זמינה");
    await expect(page.getByTestId("voice-open")).toHaveCount(0);
    await pasteList(page, "חלב");
    await expect(page.getByTestId("list-row")).toHaveCount(1);
  });

  test("by keyboard: open, Escape closes and focus returns to the mic", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page);
    await installFakeSpeech(page);
    await page.goto("/");
    const mic = page.getByTestId("voice-open");
    await mic.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog", { name: "הכתבה קולית" })).toBeVisible();
    // Focus moved into the dialog (the sheet's close button is its first stop).
    await expect(page.getByRole("dialog").locator(":focus")).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(mic).toBeFocused();
    expect(await speechStarts(page)).toBe(0);
  });
});

const SPEND_DATE = israelToday();
const spendEntry = (total: number, over: Record<string, unknown> = {}) => ({
  id: `e2e-${total}`,
  date: SPEND_DATE,
  store_id: 101,
  store_name: "רמי לוי · מודיעין",
  total,
  item_count: 7,
  plan: "single",
  ...over,
});

test.describe("monthly budget", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("results show what is left of the month, before and after this plan", async ({ page }) => {
    await mockApi(page);
    await seed(page, {
      "sc-budget-v1": { monthly: 2500 },
      "sc-spend-v1": { version: 1, entries: [spendEntry(371.4)], pending: [] },
    });
    await openWeeklyResults(page);
    const box = page.getByTestId("budget-remaining");
    await expect(box).toContainText("נותר החודש");
    await expect(page.getByTestId("budget-left")).toHaveText(/^₪\s2,128\.60$/);
    await expect(page.getByTestId("budget-after")).toContainText(/₪\s1,739\.60/); // 2,128.60 - 389
    await expect(box).toContainText("לפי המחירים שהוצגו, לא לפי קבלות");
    await expect(box.locator("time[datetime]")).toBeVisible();
    await box.getByRole("link", { name: "לתקציב" }).click();
    await expect(page).toHaveURL(/\/profile#budget$/);
  });

  test("no budget, no card", async ({ page }) => {
    await mockApi(page);
    await openWeeklyResults(page);
    await expect(page.getByTestId("budget-remaining")).toHaveCount(0);
  });

  test("סיימתי לקנות records the shop, Profile shows the month and the six-month chart", async ({
    page,
  }) => {
    const calls = await seedComparison(page);
    await page.goto("/store-mode?store=101");
    await page.getByTestId("shop-item").first().waitFor();
    const unchecked = page.locator('[role="checkbox"][aria-checked="false"]');
    while ((await unchecked.count()) > 0) await unchecked.first().click();
    await page.getByRole("button", { name: "סיימתי לקנות" }).click();
    const sheet = page.getByRole("dialog", { name: "סיכום הקנייה" });
    await expect(sheet.getByRole("switch", { name: "לרשום בתקציב החודשי" })).toBeChecked();
    await expect(sheet).toContainText("לפי המחירים שהוצגו ולא לפי קבלה");
    await page.getByTestId("finish-confirm").click();
    await expect(page).toHaveURL(/\/$/);

    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("sc-spend-v1")!));
    expect(stored.entries).toHaveLength(1);
    expect(stored.entries[0]).toMatchObject({
      date: SPEND_DATE,
      store_id: 101,
      total: 389,
      item_count: 8,
      plan: "single",
    });
    expect(JSON.stringify(stored)).not.toMatch(/חלב|ביצים|סלמון/);
    // Signed out: nothing went to the server.
    expect(calls.some((c) => c.path === "/me/spend")).toBe(false);

    await page.goto("/profile#budget");
    const section = page.getByTestId("budget-section");
    await expect(section.getByTestId("budget-spent")).toHaveText(/^₪\s389$/);
    await expect(section).toContainText("לא הוגדר תקציב");
    await section.getByLabel(/כמה את רוצה להוציא/).fill("2500");
    await section.getByRole("button", { name: "שמירת תקציב" }).click();
    await expect(section.getByTestId("budget-remaining-value")).toHaveText(/^₪\s2,111$/);
    await expect(section.getByTestId("spend-bar")).toHaveCount(6);
    await expect(section.getByTestId("budget-line")).toHaveCount(1);
    await expect(section.getByRole("table").getByRole("row")).toHaveCount(7); // header + 6 months
    await expect(section.getByTestId("spend-entries")).toContainText("רמי לוי · מודיעין");
    await expect(section.getByTestId("budget-method")).toContainText("לא לפי קבלות");
    await noHorizontalScroll(page);

    await page.reload();
    await expect(page.getByTestId("budget-remaining-value")).toHaveText(/^₪\s2,111$/);
  });

  test("the switch in the finish sheet keeps a shop out of the budget", async ({ page }) => {
    await seedComparison(page);
    await page.goto("/store-mode?store=101");
    await page.getByTestId("shop-item").first().waitFor();
    await page.getByTestId("shop-item").first().click();
    await page.getByTestId("finish").click();
    await page.getByRole("switch", { name: "לרשום בתקציב החודשי" }).click();
    await page.getByTestId("finish-confirm").click();
    await expect(page).toHaveURL(/\/$/);
    expect(await page.evaluate(() => localStorage.getItem("sc-spend-v1"))).toBeNull();
    expect(await page.evaluate((k) => localStorage.getItem(k), KEYS.savings)).not.toBeNull(); // the saving is a separate record
  });

  test("delete my data removes the budget and the spend", async ({ page }) => {
    await mockApi(page);
    await seed(page, {
      "sc-budget-v1": { monthly: 2500 },
      "sc-spend-v1": { version: 1, entries: [spendEntry(100)], pending: [] },
    });
    await page.goto("/profile");
    await page.getByRole("button", { name: "מחקי את הנתונים שלי" }).click();
    await page.getByTestId("confirm-delete").click();
    await expect(page.getByTestId("delete-done")).toBeVisible();
    await expect
      .poll(() =>
        page.evaluate(() => [
          localStorage.getItem("sc-budget-v1"),
          localStorage.getItem("sc-spend-v1"),
        ]),
      )
      .toEqual([null, null]);
  });
});

test.describe("scan reads its code from the URL", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("/scan?code= looks the product up without opening the camera", async ({ page }) => {
    const calls = await mockApi(page);
    await seedProfile(page);
    await page.addInitScript(() => {
      const w = window as unknown as { __getUserMediaCalls: number };
      w.__getUserMediaCalls = 0;
      navigator.mediaDevices.getUserMedia = async () => {
        w.__getUserMediaCalls += 1;
        throw new DOMException("no camera in this test", "NotAllowedError");
      };
    });
    await page.goto("/scan?code=5901234123457");
    const card = page.getByTestId("scan-result");
    await expect(card).toBeVisible({ timeout: 10_000 });
    await expect(card.getByRole("heading", { level: 2 })).toHaveText("רסק עגבניות אסם 260 ג'");
    expect(
      await page.evaluate(() => (window as never as Record<string, number>).__getUserMediaCalls),
    ).toBe(0);
    await expect(page.getByRole("textbox", { name: /ברקוד \(13 ספרות/ })).toHaveValue(
      "5901234123457",
    );
    expect(calls.filter((c) => c.path.startsWith("/items/barcode/"))).toHaveLength(1);
    expect(calls.find((c) => c.path.startsWith("/items/barcode/"))?.search).toContain(
      "store_id=103",
    );
  });

  test("a code with a bad check digit gets the manual-entry error and no lookup", async ({
    page,
  }) => {
    const calls = await mockApi(page);
    await seedProfile(page);
    await page.goto("/scan?code=5901234123458");
    await expect(page.getByText("הספרות לא מרכיבות ברקוד תקין")).toBeVisible();
    expect(calls.some((c) => c.path.startsWith("/items/barcode/"))).toBe(false);
  });
});

test.describe("recipe to list", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("paste a recipe, pick the servings, and the rows join the list with the normal confirmations", async ({
    page,
  }) => {
    const calls = await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await page.getByTestId("recipe-open").click();
    const dialog = page.getByRole("dialog", { name: "מתכון לרשימה" });
    await dialog
      .getByLabel("המתכון או רשימת המצרכים")
      .fill("פסטה ברוטב עגבניות\n500 גרם פסטה\n2 רסק עגבניות\nעגבניות\nחופן בזיליקום");
    await dialog.getByTestId("recipe-read").click();

    await expect(dialog.getByTestId("recipe-title")).toHaveText("פסטה ברוטב עגבניות");
    expect(calls.filter((c) => c.path === "/parse-recipe")).toHaveLength(1);
    await expect(dialog.getByTestId("recipe-unresolved")).toContainText("חופן בזיליקום");
    const items = dialog.getByTestId("recipe-item");
    await expect(items).toHaveCount(3);

    // 4 -> 6 servings by keyboard: no request, quantities scale in the sheet.
    const plus = dialog.getByRole("button", { name: "הוסיפי כמות של מנות" });
    await plus.focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("Enter");
    await expect(items.nth(1)).toContainText("3");
    await expect(items.nth(2)).toContainText("1.5");
    expect(calls.filter((c) => c.path === "/parse-recipe")).toHaveLength(1);

    await dialog.getByTestId("recipe-add").click();
    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("list-row")).toHaveCount(3);
    await expect(page.getByTestId("not-found-row")).toContainText("חופן בזיליקום");
    await expect(page.getByText(/נוספו 4 פריטים מהמתכון/)).toBeVisible();
    await noHorizontalScroll(page);
  });

  test("a link is read by the server, and a bad one is refused before any request", async ({
    page,
  }) => {
    const calls = await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await page.getByTestId("recipe-open").click();
    const dialog = page.getByRole("dialog", { name: "מתכון לרשימה" });
    await dialog.getByRole("radio", { name: "קישור למתכון" }).click();
    const field = dialog.getByLabel("קישור למתכון");
    await field.fill("not a link");
    await dialog.getByTestId("recipe-read").click();
    await expect(dialog.getByRole("alert")).toContainText("https://");
    expect(calls.some((c) => c.path === "/parse-recipe")).toBe(false);

    await field.fill("https://example.com/pasta");
    await dialog.getByTestId("recipe-read").click();
    await expect(dialog.getByTestId("recipe-title")).toBeVisible();
    expect(calls.find((c) => c.path === "/parse-recipe")?.body).toEqual({
      url: "https://example.com/pasta",
    });
  });
});
