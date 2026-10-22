import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { doc, regularDoc, signal, trip, MILK, EGGS } from "../../src/features/personal/fixtures";
import { mockApi, seedProfile } from "../e2e/core-helpers";
import { seed } from "../e2e/secondary.helpers";

/**
 * Accessibility of the personalization screens (phase 3): "buy again", "my usual", the exact-brand
 * offer, the value-pack card, the "you usually take" line and the Profile section. axe at 390 and
 * 1280 px in both themes, keyboard-only use with focus that never falls to the page, the status
 * line that announces what changed, and accessibility-tree snapshots of the new screens (the same
 * literal whole-tree compare as `aria-flows.spec.ts`; update on purpose with
 * `ARIA_SNAPSHOTS=update npm run a11y -- personal`).
 *
 * The browser clock is frozen at noon in Israel on 8 October 2026, like the other tree snapshots.
 */

const BASE = new Date("2026-10-08T09:00:00Z");
const KEY = "sc-personal-v1";
const DIR = fileURLToPath(new URL("./aria-snapshots/", import.meta.url));
const UPDATE = process.env.ARIA_SNAPSHOTS === "update";
const mask = (tree: string) => tree.replace(/\b\d{1,2}:\d{2}\b/g, "HH:MM");

async function expectAria(target: Locator, name: string) {
  const read = async () => `${mask(await target.ariaSnapshot())}\n`;
  const file = `${DIR}${name}.aria.yml`;
  if (UPDATE) {
    let tree = await read();
    await expect.poll(async () => (tree = await read()) === (await read())).toBe(true);
    mkdirSync(DIR, { recursive: true });
    writeFileSync(file, tree);
    return;
  }
  if (!existsSync(file)) {
    throw new Error(
      `No accessibility snapshot "${name}". Create it with: ARIA_SNAPSHOTS=update npm run a11y -- personal`,
    );
  }
  const expected = readFileSync(file, "utf8");
  await expect
    .poll(read, { message: `accessibility tree of "${name}" (${file})`, timeout: 10_000 })
    .toBe(expected);
}

const THEMES = ["light", "dark"] as const;
const VIEWPORTS = [
  { name: "390 px", width: 390, height: 844 },
  { name: "1280 px", width: 1280, height: 900 },
] as const;

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

async function setTheme(page: Page, theme: (typeof THEMES)[number]) {
  await page.addInitScript((value) => localStorage.setItem("sc-theme", value), theme);
  await page.emulateMedia({ colorScheme: theme });
}

/** Every card at once: buy again (cottage), usual (milk, cottage), the milk offer, value packs on. */
function everything() {
  const history = regularDoc(BASE);
  return {
    ...history,
    refs: [...history.refs, EGGS],
    signals: [
      signal(40, "dairy.milk", "kept_brand", BASE),
      signal(20, "dairy.milk", "rejected_substitute", BASE),
      signal(2, "dairy.milk", "kept_brand", BASE),
    ],
    prefs: { learn: true, value_packs: true, updated_at: BASE.toISOString() },
  };
}

async function start(page: Page, personal: unknown) {
  await page.clock.setFixedTime(BASE);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockApi(page);
  await seedProfile(page);
  await seed(page, { [KEY]: personal });
}

async function addEggs(page: Page) {
  const input = page.getByLabel("הוסיפי פריטים לרשימה");
  await input.fill("ביצים");
  await input.press("Enter");
  await expect(page.getByTestId("value-pack")).toBeVisible();
}

test.describe("axe", () => {
  for (const viewport of VIEWPORTS) {
    for (const theme of THEMES) {
      test.describe(`${viewport.name}, ${theme}`, () => {
        test.use({ viewport: { width: viewport.width, height: viewport.height } });

        test("home with every card, a value pack and a status line", async ({ page }) => {
          await setTheme(page, theme);
          await start(page, everything());
          await page.goto("/");
          await expect(page.getByTestId("brand-offer")).toBeVisible();
          await addEggs(page);
          await page.getByRole("button", { name: /לא עכשיו: קוטג/ }).click();
          await expect(
            page.getByTestId("personal-suggestions").getByTestId("personal-status"),
          ).toContainText("הסתרנו");
          await expectNoBlockingViolations(page, `home ${viewport.name} ${theme}`);
        });

        test("the Profile section, learning off", async ({ page }) => {
          await setTheme(page, theme);
          await start(page, {
            ...everything(),
            prefs: { learn: false, value_packs: true, updated_at: BASE.toISOString() },
          });
          await page.goto("/profile");
          await expect(page.getByTestId("learn-off-note")).toBeVisible();
          await expectNoBlockingViolations(page, `profile ${viewport.name} ${theme}`);
        });
      });
    }
  }
});

test.describe("keyboard and screen reader", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("a suggestion is added with the keyboard, focus stays in the page and the change is announced", async ({
    page,
  }) => {
    await start(page, regularDoc(BASE));
    await page.goto("/");
    const add = page.getByRole("button", { name: /הוסיפי קוטג.*לקנות שוב/ });
    await add.focus();
    await expect(add).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("list-row")).toHaveCount(1);
    // The card went away with the button that had focus: focus did not fall to <body>.
    await expect
      .poll(() => page.evaluate(() => document.activeElement?.tagName.toLowerCase()))
      .not.toBe("body");
    const status = page.getByTestId("personal-status");
    await expect(status).toHaveAttribute("role", "status");
    await expect(status).toContainText("נוסף לרשימה");
  });

  test("the exact-brand offer: apply and undo are reachable by keyboard, with their own names", async ({
    page,
  }) => {
    await start(
      page,
      doc(
        {
          trips: [trip(2, [[MILK]], "finished", BASE)],
          signals: [
            signal(40, "dairy.milk", "kept_brand", BASE),
            signal(20, "dairy.milk", "rejected_substitute", BASE),
            signal(2, "dairy.milk", "kept_brand", BASE),
          ],
        },
        [MILK],
      ),
    );
    await page.goto("/");
    await page.getByTestId("brand-apply").focus();
    await page.keyboard.press("Enter");
    const undo = page.getByTestId("personal-status").getByRole("button", { name: "ביטול" });
    await expect(undo).toBeVisible();
    await undo.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("personal-status")).toContainText("חזרה למה שהייתה");
  });

  test("the usual-quantity button is a named button inside its row and focus survives using it", async ({
    page,
  }) => {
    await start(page, regularDoc(BASE));
    await page.goto("/");
    await page.getByRole("button", { name: /הוסיפי חלב טרי/ }).click();
    const milk = page.getByTestId("list-row").filter({ hasText: "חלב טרי" });
    await milk.getByRole("button", { name: /^הפחיתי כמות של/ }).click();
    const set = milk.getByRole("button", { name: /קבעי את הכמות של חלב טרי.*ל-2/ });
    await set.focus();
    await page.keyboard.press("Enter");
    await expect(milk.locator("output")).toHaveText("2");
    await expect
      .poll(() => page.evaluate(() => document.activeElement?.tagName.toLowerCase()))
      .not.toBe("body");
  });
});

test.describe("accessibility trees", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("home: buy again, my usual and the exact-brand offer", async ({ page }) => {
    await start(page, everything());
    await page.goto("/");
    await expect(page.getByTestId("brand-offer")).toBeVisible();
    await expectAria(page.getByTestId("personal-suggestions"), "personal-suggestions");
  });

  test("home: a value pack with both unit prices and the status line", async ({ page }) => {
    await start(page, { ...everything(), signals: [], trips: [], refs: [] });
    await page.goto("/");
    await addEggs(page);
    await expectAria(page.getByTestId("value-packs"), "personal-value-pack");
  });

  test("a list row with its 'you usually take' line", async ({ page }) => {
    await start(page, regularDoc(BASE));
    await page.goto("/");
    await page.getByRole("button", { name: /הוסיפי חלב טרי/ }).click();
    const milk = page.getByTestId("list-row").filter({ hasText: "חלב טרי" });
    await milk.getByRole("button", { name: /^הפחיתי כמות של/ }).click();
    await expect(milk.getByTestId("usual-quantity")).toContainText("בדרך כלל את לוקחת 2");
    await expectAria(milk, "personal-usual-quantity");
  });

  test("Profile: the personalization section", async ({ page }) => {
    await start(page, everything());
    await page.goto("/profile");
    await expectAria(page.getByRole("region", { name: "התאמה אישית" }), "personal-profile-section");
  });
});
