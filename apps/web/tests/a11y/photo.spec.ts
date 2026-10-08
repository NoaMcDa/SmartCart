import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { mockApi, seedProfile } from "../e2e/core-helpers";
import { imageFile, mockPhotoApi, type PhotoApi } from "../e2e/photo-helpers";

/**
 * Accessibility of the photo to list sheet (receipts #61, handwritten lists #68): axe in every
 * state at 390 and 1280 px in both themes, 195 px (200% zoom) reflow, 44 px targets, and a
 * keyboard-only run that also checks where focus goes at each step.
 */
const VIEWPORTS = [
  { name: "390 px", width: 390, height: 844 },
  { name: "1280 px", width: 1280, height: 900 },
] as const;
const THEMES = ["light", "dark"] as const;
const CONSENT_KEY = "sc-image-consent-v1";

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

async function setTheme(page: Page, theme: (typeof THEMES)[number]) {
  await page.addInitScript((value) => localStorage.setItem("sc-theme", value), theme);
  await page.emulateMedia({ colorScheme: theme });
}

async function setup(page: Page, options: { consent?: boolean } = {}): Promise<PhotoApi> {
  await mockApi(page);
  const photo = await mockPhotoApi(page);
  await seedProfile(page);
  if (options.consent !== false) {
    await page.addInitScript((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
  }
  await page.goto("/");
  return photo;
}

async function choose(page: Page, kind: "receipt" | "list", name: string) {
  const chooser = page.waitForEvent("filechooser");
  await page.getByTestId(`photo-${kind}-file`).click();
  await (await chooser).setFiles(imageFile(name));
}

/** Every button, switch, checkbox row and text field in the sheet is at least 44 px tall. */
async function expectTargets(scope: Locator, where: string) {
  const small = await scope
    .locator("button, [role=switch], input[type=text], label:has(input[type=checkbox])")
    .evaluateAll((els) =>
      els
        .map((el) => ({ el, r: el.getBoundingClientRect() }))
        .filter(({ r }) => r.width > 0 && r.height > 0 && r.height < 43.5)
        .map(({ el, r }) => `${el.tagName.toLowerCase()} ${Math.round(r.height)}px`),
    );
  expect(small, `targets under 44 px: ${where}`).toEqual([]);
}

for (const viewport of VIEWPORTS) {
  for (const theme of THEMES) {
    test.describe(`photo sheet, ${viewport.name}, ${theme} theme`, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } });

      test("the entry, the choices and a refused file", async ({ page }) => {
        await setTheme(page, theme);
        await setup(page);
        await expectNoBlockingViolations(page, "list builder with the photo entry");
        await page.getByTestId("photo-open").click();
        const dialog = page.getByRole("dialog", { name: "צילום לרשימה" });
        await expect(dialog).toBeVisible();
        await expectNoBlockingViolations(page, "photo sheet, choices");
        await expectTargets(dialog, "choices");
        const chooser = page.waitForEvent("filechooser");
        await page.getByTestId("photo-list-file").click();
        await (await chooser).setFiles(imageFile("a.pdf", "application/pdf"));
        await expect(page.getByTestId("photo-problem")).toBeVisible();
        await expectNoBlockingViolations(page, "photo sheet, refused file");
      });

      test("consent step", async ({ page }) => {
        await setTheme(page, theme);
        await setup(page, { consent: false });
        await page.getByTestId("photo-open").click();
        await choose(page, "receipt", "r.png");
        await expect(page.getByTestId("photo-consent")).toBeVisible();
        await expectNoBlockingViolations(page, "photo sheet, consent");
        await expectTargets(page.getByRole("dialog"), "consent");
      });

      test("progress, receipt preview and list preview", async ({ page }) => {
        await setTheme(page, theme);
        const photo = await setup(page);
        await page.getByTestId("photo-open").click();
        photo.hold();
        await choose(page, "receipt", "r.png");
        await expect(page.getByTestId("photo-reading")).toBeVisible();
        await expectNoBlockingViolations(page, "photo sheet, reading");
        photo.release();
        await expect(page.getByTestId("photo-preview")).toBeVisible();
        await expectNoBlockingViolations(page, "photo sheet, receipt preview");
        await expectTargets(page.getByRole("dialog"), "receipt preview");

        await page.getByTestId("photo-back").click();
        await choose(page, "list", "l.png");
        await expect(page.getByTestId("photo-preview")).toBeVisible();
        await page.getByTestId("photo-unresolved-row").first().getByRole("textbox").fill("קוטג");
        await expectNoBlockingViolations(page, "photo sheet, list preview with an edited line");
      });

      test("errors and an empty read", async ({ page }) => {
        await setTheme(page, theme);
        await setup(page);
        await page.getByTestId("photo-open").click();
        await choose(page, "receipt", "x-429.png");
        await expect(page.getByTestId("photo-error")).toBeVisible();
        await expectNoBlockingViolations(page, "photo sheet, monthly cap");
        await page.getByTestId("photo-type").click();
        await page.getByTestId("photo-open").click();
        await choose(page, "receipt", "x-503.png");
        await expect(page.getByTestId("photo-error")).toBeVisible();
        await expectTargets(page.getByRole("dialog"), "error with retry");
        await expectNoBlockingViolations(page, "photo sheet, no OCR provider");
        await page.getByRole("button", { name: "סגירה" }).click();
        await page.getByTestId("photo-open").click();
        await choose(page, "list", "empty.png");
        await expect(page.getByTestId("photo-empty")).toBeVisible();
        await expectNoBlockingViolations(page, "photo sheet, nothing read");
      });

      test("Profile consent switch", async ({ page }) => {
        await setTheme(page, theme);
        await mockApi(page);
        await page.addInitScript((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
        await page.goto("/profile");
        await expect(
          page.getByRole("switch", { name: "קריאת תמונות של קבלות ורשימות" }),
        ).toBeChecked();
        await expectNoBlockingViolations(page, "profile with the photo consent switch");
      });
    });
  }
}

test.describe("photo sheet at 195 px (200% zoom on a phone)", () => {
  test.use({ viewport: { width: 195, height: 844 } });

  test("every step fits without sideways scrolling", async ({ page }) => {
    const photo = await setup(page, { consent: false });
    await assertFits(page);
    await page.getByTestId("photo-open").click();
    await assertFits(page);
    await choose(page, "receipt", "r.png");
    await expect(page.getByTestId("photo-consent")).toBeVisible();
    await assertFits(page);
    await page.getByTestId("photo-consent-agree").click();
    await expect(page.getByTestId("photo-preview")).toBeVisible();
    await assertFits(page);
    await page
      .getByTestId("photo-unresolved-row")
      .first()
      .getByRole("textbox")
      .fill("שורה ארוכה מאוד שהשתנתה בידי המשתמש עם הרבה מילים");
    await assertFits(page);
    await page.getByTestId("photo-back").click();
    photo.hold();
    await choose(page, "list", "l.png");
    await expect(page.getByTestId("photo-reading")).toBeVisible();
    await assertFits(page);
    photo.release();
    await expect(page.getByTestId("photo-preview")).toBeVisible();
    await page.getByTestId("photo-back").click();
    await choose(page, "list", "x-429.png");
    await expect(page.getByTestId("photo-error")).toBeVisible();
    await assertFits(page);
  });

  test("Profile consent switch fits", async ({ page }) => {
    await mockApi(page);
    await page.goto("/profile");
    await expect(page.getByRole("switch", { name: "קריאת תמונות של קבלות ורשימות" })).toBeVisible();
    await assertFits(page);
  });
});

test.describe("photo sheet, keyboard only", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("open, pick, consent, review and add without a pointer; focus follows each step", async ({
    page,
  }) => {
    await setup(page, { consent: false });
    const entry = page.getByTestId("photo-open");
    await entry.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "צילום לרשימה" });
    await expect(dialog).toBeVisible();

    // Tab stays inside the sheet.
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press("Tab");
      await expect(page.locator("[role=dialog] :focus, [role=dialog]:focus")).toHaveCount(1);
    }

    // The receipt's file button, by Enter; the browser's file dialog is answered by the test.
    const chooser = page.waitForEvent("filechooser");
    await page.getByTestId("photo-receipt-file").focus();
    await page.keyboard.press("Enter");
    await (await chooser).setFiles(imageFile("kb.png"));

    // Consent: focus lands on its heading, "מסכים/ה" by Enter.
    await expect(page.getByTestId("photo-consent")).toBeVisible();
    await expect(page.getByRole("heading", { name: "לפני שמצלמים" })).toBeFocused();
    await page.getByTestId("photo-consent-agree").focus();
    await page.keyboard.press("Enter");

    // Preview: focus lands on its heading; Space ticks the amber row; Enter adds.
    await expect(page.getByTestId("photo-preview")).toBeVisible();
    await expect(page.getByRole("heading", { name: "מה זוהה בקבלה" })).toBeFocused();
    const amber = page.getByTestId("photo-unsure").getByRole("checkbox");
    await amber.focus();
    await page.keyboard.press("Space");
    await expect(amber).toBeChecked();
    await page.getByTestId("photo-add").focus();
    await page.keyboard.press("Enter");

    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("list-row")).toHaveCount(4);
    await expect(entry).toBeFocused(); // the sheet returned focus to its opener
  });

  test("Escape closes the sheet at any step and focus returns to the entry", async ({ page }) => {
    await setup(page);
    const entry = page.getByTestId("photo-open");
    await entry.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(entry).toBeFocused();

    await page.keyboard.press("Enter");
    await choose(page, "list", "x-503.png");
    await expect(page.getByTestId("photo-error")).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(entry).toBeFocused();
  });
});
