import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mockApi, openWeeklyResults, seedProfile } from "../e2e/core-helpers";
import { hear, installFakeSpeech, israelToday } from "../e2e/phase3-helpers";
import { seed, seedComparison } from "../e2e/secondary.helpers";

/**
 * Accessibility of the phase 3 screens (unblock round): the voice sheet, the recipe sheet, the
 * budget on the results, the Profile budget section with its chart, and the finish sheet in store
 * mode. axe at 390 and 1280 px in both themes, 195 px (200% zoom) overflow, and keyboard-only use.
 */
const VIEWPORTS = [
  { name: "390 px", width: 390, height: 844 },
  { name: "1280 px", width: 1280, height: 900 },
] as const;
const THEMES = ["light", "dark"] as const;

async function animationsSettled(page: Page) {
  await page.evaluate(async () => {
    await Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    );
  });
}

async function expectNoBlockingViolations(page: Page, where: string) {
  await animationsSettled(page);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const blocking = results.violations.filter((v) =>
    ["serious", "critical"].includes(v.impact ?? ""),
  );
  expect(
    blocking.map((v) => ({
      id: v.id,
      help: v.help,
      targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
    })),
    where,
  ).toEqual([]);
}

async function assertFits(page: Page) {
  const result = await page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const outside = [...document.querySelectorAll("body *")]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0 || el.closest(".sr-only")) return false;
        return r.right > width + 0.5 || r.left < -0.5;
      })
      .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 40)}`);
    return {
      width,
      scroll: document.documentElement.scrollWidth,
      bodyScroll: document.body.scrollWidth,
      outside: outside.slice(0, 8),
    };
  });
  expect(result.outside, "elements outside the viewport").toEqual([]);
  expect(result.scroll, "document scrollWidth").toBeLessThanOrEqual(result.width);
  expect(result.bodyScroll, "body scrollWidth").toBeLessThanOrEqual(result.width);
}

const spend = (total: number, date = israelToday()) => ({
  id: `a11y-${total}-${date}`,
  date,
  store_id: 101,
  store_name: "רמי לוי · מודיעין",
  total,
  item_count: 7,
  plan: "single",
});

/** Entries in each of the last months so the chart has bars of different heights. */
function manyMonths() {
  const now = new Date();
  return [120, 0, 300, 450.5, 80, 200].map((total, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() - (5 - i), 12, 12);
    const date = d.toLocaleDateString("en-CA", { timeZone: "Asia/Jerusalem" });
    return total ? spend(total, date) : null;
  });
}

async function setTheme(page: Page, theme: (typeof THEMES)[number]) {
  await page.addInitScript((value) => localStorage.setItem("sc-theme", value), theme);
  await page.emulateMedia({ colorScheme: theme });
}

for (const viewport of VIEWPORTS) {
  for (const theme of THEMES) {
    test.describe(`phase 3 states, ${viewport.name}, ${theme} theme`, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } });

      test("voice sheet: intro, listening, review, denied", async ({ page }) => {
        await mockApi(page);
        await seedProfile(page);
        await installFakeSpeech(page);
        await setTheme(page, theme);
        await page.goto("/");
        await expectNoBlockingViolations(page, "list builder with the microphone");
        await page.getByTestId("voice-open").click();
        await expectNoBlockingViolations(page, "voice sheet, intro");
        await page.getByTestId("voice-start").click();
        await expect(page.getByTestId("voice-status")).toContainText("מקשיבה");
        await hear(page, { text: "חלב" }, { text: "שתי עגבניות", final: false });
        await expectNoBlockingViolations(page, "voice sheet, listening");
        await page.getByTestId("voice-stop").click();
        await expect(page.getByLabel(/מה שמענו/)).toBeVisible();
        await expectNoBlockingViolations(page, "voice sheet, review");
        await page.getByRole("button", { name: "הקלטה מחדש" }).click();
        await page.evaluate(() => {
          const rec = (
            window as unknown as {
              __speech: { onerror: (e: unknown) => void; onend: () => void };
            }
          ).__speech;
          rec.onerror({ error: "not-allowed" });
        });
        await expect(page.getByTestId("voice-error")).toBeVisible();
        await expectNoBlockingViolations(page, "voice sheet, microphone denied");
      });

      test("recipe sheet: input and preview", async ({ page }) => {
        await mockApi(page);
        await seedProfile(page);
        await setTheme(page, theme);
        await page.goto("/");
        await page.getByTestId("recipe-open").click();
        await expectNoBlockingViolations(page, "recipe sheet, input");
        const dialog = page.getByRole("dialog", { name: "מתכון לרשימה" });
        await dialog
          .getByLabel("המתכון או רשימת המצרכים")
          .fill("פסטה ברוטב עגבניות\n500 גרם פסטה\n2 רסק עגבניות\nחופן בזיליקום");
        await dialog.getByTestId("recipe-read").click();
        await expect(dialog.getByTestId("recipe-title")).toBeVisible();
        await expectNoBlockingViolations(page, "recipe sheet, preview");
      });

      test("results with a budget, and the Profile budget section with the chart", async ({
        page,
      }) => {
        await mockApi(page);
        await setTheme(page, theme);
        await seed(page, {
          "sc-budget-v1": { monthly: 500 },
          "sc-spend-v1": { version: 1, entries: manyMonths().filter(Boolean), pending: [] },
        });
        await openWeeklyResults(page);
        await expect(page.getByTestId("budget-remaining")).toBeVisible();
        await expectNoBlockingViolations(page, "results with the budget card (over budget)");
        await page.goto("/profile#budget");
        await expect(page.getByTestId("spend-chart")).toBeVisible();
        await expectNoBlockingViolations(page, "profile budget section");
      });

      test("store mode finish sheet with the budget switch", async ({ page }) => {
        await seedComparison(page);
        await setTheme(page, theme);
        await page.goto("/store-mode?store=101");
        await page.getByTestId("shop-item").first().click();
        await page.getByTestId("finish").click();
        await expect(page.getByRole("switch", { name: "לרשום בתקציב החודשי" })).toBeVisible();
        await expectNoBlockingViolations(page, "finish sheet");
      });
    });
  }
}

test.describe("phase 3, keyboard only", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("dictate and confirm without a pointer; the sheet traps focus and returns it", async ({
    page,
  }) => {
    await mockApi(page);
    await seedProfile(page);
    await installFakeSpeech(page);
    await page.goto("/");
    const mic = page.getByTestId("voice-open");
    await mic.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "הכתבה קולית" });
    await expect(dialog).toBeVisible();
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press("Tab");
      await expect(page.locator("[role=dialog] :focus, [role=dialog]:focus")).toHaveCount(1);
    }
    await dialog.getByTestId("voice-start").focus();
    await page.keyboard.press("Enter");
    await hear(page, { text: "חלב" });
    await dialog.getByTestId("voice-stop").focus();
    await page.keyboard.press("Enter");
    await expect(dialog.getByLabel(/מה שמענו/)).toHaveValue("חלב");
    await dialog.getByTestId("voice-add").focus();
    await page.keyboard.press("Enter");
    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("list-row")).toHaveCount(1);
  });

  test("recipe: reach the field, read, change servings and add with the keyboard", async ({
    page,
  }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await page.getByTestId("recipe-open").focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "מתכון לרשימה" });
    await expect(dialog).toBeVisible();
    await dialog.getByLabel("המתכון או רשימת המצרכים").focus();
    await page.keyboard.insertText("פסטה ברוטב עגבניות\n2 רסק עגבניות\nפסטה");
    await dialog.getByTestId("recipe-read").focus();
    await page.keyboard.press("Enter");
    await expect(dialog.getByTestId("recipe-title")).toBeVisible();
    await dialog.getByRole("button", { name: "הפחיתי כמות של מנות" }).focus();
    await page.keyboard.press("Enter");
    await expect(dialog.getByRole("group", { name: "כמות: מנות" }).locator("output")).toContainText(
      "3",
    );
    await dialog.getByTestId("recipe-add").focus();
    await page.keyboard.press("Enter");
    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("list-row")).toHaveCount(2);
  });

  test("budget: set it from the keyboard and read the result", async ({ page }) => {
    await mockApi(page);
    await page.goto("/profile");
    const field = page.getByLabel(/כמה את רוצה להוציא/);
    await field.focus();
    await page.keyboard.type("1800");
    await page.keyboard.press("Enter"); // submits the form
    await expect(page.getByRole("status").filter({ hasText: "התקציב נשמר" })).toBeVisible();
    await expect(page.getByTestId("budget-remaining-value")).toHaveText(/^₪\s1,800$/);
  });
});

test.describe("phase 3 at 195 px (200% zoom on a phone)", () => {
  test.use({ viewport: { width: 195, height: 844 } });

  test("voice sheet in each state", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page);
    await installFakeSpeech(page);
    await page.goto("/");
    await assertFits(page);
    await page.getByTestId("voice-open").click();
    await assertFits(page);
    await page.getByTestId("voice-start").click();
    await hear(page, { text: "חלב" }, { text: "שתי רסק עגבניות עם תוספת ארוכה מאוד של מילים" });
    await assertFits(page);
    await page.getByTestId("voice-stop").click();
    await expect(page.getByLabel(/מה שמענו/)).toBeVisible();
    await assertFits(page);
  });

  test("recipe sheet: input and preview", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await page.getByTestId("recipe-open").click();
    await assertFits(page);
    const dialog = page.getByRole("dialog", { name: "מתכון לרשימה" });
    await dialog
      .getByLabel("המתכון או רשימת המצרכים")
      .fill("פסטה ברוטב עגבניות\n500 גרם פסטה\n2 רסק עגבניות\nעגבניות\nחופן בזיליקום");
    await dialog.getByTestId("recipe-read").click();
    await expect(dialog.getByTestId("recipe-title")).toBeVisible();
    await assertFits(page);
  });

  test("results with the budget card, and the Profile budget section", async ({ page }) => {
    await mockApi(page);
    await seed(page, {
      "sc-budget-v1": { monthly: 500 },
      "sc-spend-v1": { version: 1, entries: manyMonths().filter(Boolean), pending: [] },
    });
    await openWeeklyResults(page);
    await expect(page.getByTestId("budget-after")).toBeVisible();
    await assertFits(page);
    await page.goto("/profile#budget");
    await expect(page.getByTestId("spend-chart")).toBeVisible();
    await assertFits(page);
  });

  test("the finish sheet with the budget switch", async ({ page }) => {
    await seedComparison(page);
    await page.goto("/store-mode?store=101");
    await page.getByTestId("shop-item").first().click();
    await page.getByTestId("finish").click();
    await expect(page.getByRole("switch", { name: "לרשום בתקציב החודשי" })).toBeVisible();
    await assertFits(page);
  });
});
