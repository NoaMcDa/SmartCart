import { mkdirSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { mockApi, pasteList, seedProfile, WEEKLY_TEXT } from "../e2e/core-helpers";
import { seedComparison } from "../e2e/secondary.helpers";

/**
 * Accessibility-tree snapshots of the core flows (#26). Each screen's tree, as Playwright's
 * `locator.ariaSnapshot()` writes it (roles, accessible names, order, link targets, states), is
 * compared with a committed file in `aria-snapshots/`. They pin what a screen reader announces: a
 * renamed button, a lost label, a changed heading level or a reordered section is a diff in CI, so
 * the human screen-reader pass (VoiceOver, TalkBack; docs/a11y-report.md) only has to verify the
 * experience once instead of re-reading every screen after every change.
 *
 * Why a file compare and not `toMatchAriaSnapshot`: that matcher is a partial match (extra nodes
 * pass) and rewrites digits into regular expressions when it updates. A whole-tree, literal
 * compare is what makes an inserted, removed or reordered element visible.
 *
 * The snapshots are the Hebrew UI (the default locale). Stable by construction: the API is the
 * in-process mock (`mockApi`, `seedComparison`), the browser clock is frozen, motion is reduced,
 * the Israel time zone comes from the config, and the only clock-dependent text, the "HH:MM" of an
 * update stamp, is masked. Update them on purpose, after reading the diff:
 *
 *   npm run build && ARIA_SNAPSHOTS=update npm run a11y -- aria-flows
 */

const DIR = fileURLToPath(new URL("./aria-snapshots/", import.meta.url));
const UPDATE = process.env.ARIA_SNAPSHOTS === "update";

/** 2026-10-08 12:00 in Israel: the mock's fixed update stamps read "yesterday" against it. */
const NOW = new Date("2026-10-08T09:00:00Z");

/** The clock time inside an update stamp depends on the time zone of whoever updates the file. */
const mask = (tree: string) => tree.replace(/\b\d{1,2}:\d{2}\b/g, "HH:MM");

async function expectAria(target: Locator, name: string) {
  const read = async () => `${mask(await target.ariaSnapshot())}\n`;
  const file = `${DIR}${name}.aria.yml`;
  if (UPDATE) {
    // Two equal reads in a row: the screen has stopped changing.
    let tree = await read();
    await expect.poll(async () => (tree = await read()) === (await read())).toBe(true);
    mkdirSync(DIR, { recursive: true });
    writeFileSync(file, tree);
    return;
  }
  if (!existsSync(file)) {
    throw new Error(
      `No accessibility snapshot "${name}". Create it with: ARIA_SNAPSHOTS=update npm run a11y -- aria-flows`,
    );
  }
  const expected = readFileSync(file, "utf8");
  await expect
    .poll(read, { message: `accessibility tree of "${name}" (${file})`, timeout: 10_000 })
    .toBe(expected);
}

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(NOW);
  await page.emulateMedia({ reducedMotion: "reduce" });
});

/** `main` is the screen's content; the shell around it has its own snapshots below. */
const screen = (page: Page) => page.locator("main");

test.describe("phone, 390 px", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the shell: skip link, top bar and the bottom tabs in reading order", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectAria(page.getByRole("link", { name: "דילוג לתוכן" }), "shell-skip-link");
    await expectAria(page.getByRole("banner"), "shell-top-bar");
    await expectAria(page.getByRole("navigation", { name: "ניווט ראשי" }), "shell-tabs");
  });

  test("onboarding, step 1: location", async ({ page }) => {
    await mockApi(page);
    await page.goto("/onboarding");
    await expect(page.getByTestId("step-count")).toContainText("שלב 1 מתוך 3");
    await expectAria(screen(page), "onboarding-1-location");
  });

  test("onboarding, steps 2 and 3: my store, travel", async ({ page }) => {
    await mockApi(page);
    await page.goto("/onboarding");
    await page.getByTestId("onboarding-skip").click();
    await expect(page.getByTestId("step-count")).toContainText("שלב 2 מתוך 3");
    await expectAria(screen(page), "onboarding-2-store");
    await page.getByTestId("onboarding-skip").click();
    await expect(page.getByTestId("step-count")).toContainText("שלב 3 מתוך 3");
    await expectAria(screen(page), "onboarding-3-travel");
  });

  test("list builder: empty, with a pasted list, and the flexibility sheet", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "הרשימה ריקה" })).toBeVisible();
    await expectAria(screen(page), "list-empty");
    await pasteList(page, WEEKLY_TEXT);
    await expectAria(screen(page), "list-pasted");

    await page
      .getByTestId("list-row")
      .filter({ hasText: "חלב טרי" })
      .getByRole("button", { name: /^רמת גמישות/ })
      .click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    await expectAria(sheet, "flexibility-sheet");
  });

  test("results, the basket details and the substitution card", async ({ page }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await pasteList(page, WEEKLY_TEXT);
    await page.getByRole("link", { name: "השווי" }).click();
    await page.getByTestId("plan-single").waitFor();
    await expectAria(screen(page), "results");

    await page.getByText(/^פירוט הסל/).click();
    await page.getByTestId("basket-details").waitFor();
    await expectAria(page.getByTestId("basket-details"), "results-basket-details");

    await page
      .getByTestId("basket-details")
      .getByRole("link", { name: /^תחליף:/ })
      .first()
      .click();
    await expect(page).toHaveURL(/\/compare\/substitution\//);
    await expect(page.getByRole("heading", { level: 1, name: "פרטי החלפה" })).toBeVisible();
    await expectAria(screen(page), "substitution-card");
  });

  test("store mode: the checklist by department", async ({ page }) => {
    await seedComparison(page);
    await page.goto("/store-mode?store=101");
    await expect(page.getByTestId("shop-item")).toHaveCount(8);
    await expectAria(screen(page), "store-mode");
  });

  test("profile: the delete-my-data confirmation dialog", async ({ page }) => {
    await mockApi(page);
    await page.goto("/profile");
    await page.getByRole("button", { name: "מחקי את הנתונים שלי" }).click();
    const dialog = page.getByRole("dialog", { name: "למחוק את כל הנתונים שלי?" });
    await expect(dialog).toBeVisible();
    await expectAria(dialog, "profile-delete-dialog");
  });
});

test.describe("desktop, 1280 px", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("split view: both stores side by side, each item with its move button", async ({ page }) => {
    await seedComparison(page);
    await page.goto("/split");
    await expect(page.getByTestId("split-column-101")).toBeVisible();
    await expect(page.getByTestId("split-column-102")).toBeVisible();
    await expectAria(screen(page), "split-view");
  });

  test("split view after moving an item with the button", async ({ page }) => {
    await seedComparison(page);
    await page.goto("/split");
    await page.getByRole("button", { name: "העברת חלב טרי 3% יטבתה, 1 ליטר לאושר עד" }).click();
    await expect(page.getByTestId("split-announcer")).toContainText("הועבר לאושר עד");
    await expectAria(screen(page), "split-view-moved");
  });
});
