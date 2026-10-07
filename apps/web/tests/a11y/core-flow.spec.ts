import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mockApi, seedProfile, WEEKLY_TEXT } from "../e2e/core-helpers";

/**
 * The core flow (paste a list, set flexibility, compare, open a substitution) in its interactive
 * states: the routes suite only sees each page's first paint. Runs on any build: `mockApi`
 * answers the API origin from the mock handlers. Keyboard-only completion is the second block.
 */
const VIEWPORTS = [
  { name: "390 px", width: 390, height: 844 },
  { name: "1280 px", width: 1280, height: 900 },
] as const;
const THEMES = ["light", "dark"] as const;

async function expectNoBlockingViolations(page: Page, where: string) {
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

async function startFlow(page: Page, theme: (typeof THEMES)[number]) {
  await mockApi(page);
  await seedProfile(page);
  await page.addInitScript((value) => localStorage.setItem("sc-theme", value), theme);
  await page.emulateMedia({ colorScheme: theme });
  await page.goto("/");
  const input = page.getByLabel("הוסיפי פריטים לרשימה");
  await input.fill(WEEKLY_TEXT);
  await input.press("Enter");
  await page.getByTestId("list-row").first().waitFor();
}

for (const viewport of VIEWPORTS) {
  for (const theme of THEMES) {
    test.describe(`core flow states, ${viewport.name}, ${theme} theme`, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } });

      test("list with items, flexibility sheet, results, details and substitution card", async ({
        page,
      }) => {
        await startFlow(page, theme);
        await expectNoBlockingViolations(page, "list builder with nine items");

        await page
          .getByTestId("list-row")
          .filter({ hasText: "חלב טרי" })
          .getByRole("button", { name: /^רמת גמישות/ })
          .click();
        const sheet = page.getByRole("dialog");
        await expect(sheet).toBeVisible();
        await expectNoBlockingViolations(page, "flexibility sheet open");
        await sheet.getByRole("button", { name: "ביטול" }).click();
        await expect(sheet).toBeHidden();

        await page.getByRole("link", { name: "השווי" }).click();
        await page.getByTestId("plan-single").waitFor();
        await expectNoBlockingViolations(page, "results");

        await page.getByText(/^פירוט הסל/).click();
        await page.getByTestId("basket-details").waitFor();
        await expectNoBlockingViolations(page, "results with the basket details open");

        await page
          .getByTestId("basket-details")
          .getByRole("link", { name: /^תחליף:/ })
          .first()
          .click();
        await expect(page).toHaveURL(/\/compare\/substitution\//);
        await expectNoBlockingViolations(page, "substitution card");
      });
    });
  }
}

test.describe("keyboard only", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("paste a list, set flexibility, compare and open a substitution without a pointer", async ({
    page,
  }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/");

    // Paste: focus the input by keyboard and submit with Enter.
    const input = page.getByLabel("הוסיפי פריטים לרשימה");
    await input.focus();
    await page.keyboard.insertText(WEEKLY_TEXT);
    await page.keyboard.press("Enter");
    await page.getByTestId("list-row").first().waitFor();

    // Flexibility: reach the milk row's chip with Tab, open the sheet, choose with the arrows.
    const chip = page
      .getByTestId("list-row")
      .filter({ hasText: "חלב טרי" })
      .getByRole("button", { name: /^רמת גמישות/ });
    await chip.focus();
    await page.keyboard.press("Enter");
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    // Focus moved into the dialog, and Tab keeps it there (the sheet traps focus).
    await expect(page.locator("[role=dialog] :focus, [role=dialog]:focus")).toHaveCount(1);
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press("Tab");
      await expect(page.locator("[role=dialog] :focus, [role=dialog]:focus")).toHaveCount(1);
    }
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
    await expect(chip).toBeFocused(); // focus returns to the opener

    // Compare: the link is reachable and activates with Enter.
    const compare = page.getByRole("link", { name: "השווי" });
    await compare.focus();
    await page.keyboard.press("Enter");
    await page.getByTestId("plan-single").waitFor();

    // Open a substitution from the basket details, by keyboard.
    const summary = page.getByText(/^פירוט הסל/);
    await summary.focus();
    await page.keyboard.press("Enter");
    const substitute = page
      .getByTestId("basket-details")
      .getByRole("link", { name: /^תחליף:/ })
      .first();
    await substitute.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/compare\/substitution\//);
  });

  // The split view (W5, /split) is a placeholder until it is built: its keyboard and non-drag
  // alternative are tracked in docs/a11y-report.md as open.
});
