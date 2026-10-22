import AxeBuilder from "@axe-core/playwright";
import { mkdirSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { mockApi, pasteList, seedProfile, WEEKLY_TEXT } from "../e2e/core-helpers";

/**
 * The kosher filter's screens: the Profile setting and the labels on the results, as a screen
 * reader and axe see them. The accessibility-tree files follow tests/a11y/aria-flows.spec.ts (same
 * folder, same literal whole-tree compare, same update command):
 *
 *   npm run build && ARIA_SNAPSHOTS=update npm run a11y -- kosher
 *
 * Only these two screens' trees are new; no existing snapshot changes (without a filter a screen
 * has no kosher text).
 */

const DIR = fileURLToPath(new URL("./aria-snapshots/", import.meta.url));
const UPDATE = process.env.ARIA_SNAPSHOTS === "update";
const NOW = new Date("2026-10-08T09:00:00Z");
const BLOCKING = new Set(["serious", "critical"]);
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
      `No accessibility snapshot "${name}". Create it with: ARIA_SNAPSHOTS=update npm run a11y -- kosher`,
    );
  }
  await expect
    .poll(read, { message: `accessibility tree of "${name}" (${file})`, timeout: 10_000 })
    .toBe(`${readFileSync(file, "utf8")}`);
}

async function noBlockingViolations(page: Page, what: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(
    results.violations
      .filter((v) => BLOCKING.has(v.impact ?? ""))
      .map((v) => ({
        id: v.id,
        help: v.help,
        targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
      })),
    what,
  ).toEqual([]);
}

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(NOW);
  await page.emulateMedia({ reducedMotion: "reduce" });
});

for (const theme of ["light", "dark"] as const) {
  test.describe(`phone, 390 px, ${theme} theme`, () => {
    test.use({ viewport: { width: 390, height: 844 }, colorScheme: theme });

    test("the Profile setting, with a level and both switches on", async ({ page }) => {
      await mockApi(page);
      await seedProfile(page);
      await page.goto("/profile");
      const diet = page.getByRole("region", { name: "כשרות ותזונה" });
      await diet.getByRole("radio", { name: 'בד"ץ' }).click();
      await diet.getByLabel("השגחה מסוימת").selectOption({ label: 'בד"ץ העדה החרדית' });
      await diet.getByRole("switch", { name: "כשר לפסח" }).click();
      await diet.getByRole("switch", { name: /רק מוצרים שהכשרות/ }).click();
      await noBlockingViolations(page, `profile kosher setting, ${theme}`);
      if (theme === "light")
        await expectAria(diet.getByTestId("kosher-controls"), "profile-kosher");
    });

    test("results under a filter: the note, the labels and the unknown warning", async ({
      page,
    }) => {
      await mockApi(page);
      await seedProfile(page, { kosher_level: "mehadrin" });
      await page.goto("/");
      await pasteList(page, WEEKLY_TEXT);
      await page.getByRole("link", { name: "השווי" }).click();
      await page.getByTestId("plan-single").waitFor();
      await page.getByText(/^פירוט הסל/).click();
      await page.getByTestId("basket-details").waitFor();
      await expect(page.getByTestId("kosher-active")).toBeVisible();
      await noBlockingViolations(page, `results under a kosher filter, ${theme}`);
      if (theme === "light") {
        await expectAria(page.getByTestId("kosher-active"), "results-kosher-note");
        await expectAria(page.getByTestId("basket-details"), "results-basket-details-kosher");
      }
    });
  });
}
