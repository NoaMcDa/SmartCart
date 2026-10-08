import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mockBetaFeedback, resetBetaMock, setBetaMockMember } from "../../src/mocks/handlers.beta";
import { mockApi, type ApiCall } from "./core-helpers";

/**
 * Closed beta (issue #40): the join page behind an invite link, joining, sending feedback, leaving.
 * The API is answered by the beta MSW handlers (src/mocks/handlers.beta.ts; BETA-KOSHER joins the
 * kosher segment). The consent screen only exists in a build with NEXT_PUBLIC_BETA_EVENTS=1 against
 * a real API, so it is covered by the unit tests (src/features/beta/beta.test.tsx).
 */
test.use({ viewport: { width: 390, height: 844 } });

let calls: ApiCall[];

test.beforeEach(async ({ page }) => {
  resetBetaMock();
  calls = await mockApi(page);
});

const beta = () => calls.filter((c) => /\/beta|\/me\/beta/.test(c.path));

async function axe(page: Page, context: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const blocking = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(
    blocking.map((v) => ({
      id: v.id,
      help: v.help,
      targets: v.nodes.slice(0, 4).map((n) => n.target.join(" ")),
    })),
    context,
  ).toEqual([]);
}

test.describe("join page", () => {
  test("explains the beta, joins only on a tap, and shows the group", async ({ page }) => {
    await page.goto("/beta/join/BETA-KOSHER");
    await expect(page.getByRole("heading", { level: 1, name: "הבטא של SmartCart" })).toBeVisible();
    const body = page.locator("main");
    await expect(body).toContainText("מה אנחנו מודדים");
    await expect(body).toContainText("אירועי שימוש והסכמה");
    await expect(body).toContainText("איך יוצאים");
    await expect(page.getByRole("link", { name: "למדיניות הפרטיות" })).toHaveAttribute(
      "href",
      "/privacy",
    );

    await expect(page.getByTestId("beta-join")).toBeEnabled();
    expect(beta().some((c) => c.method === "POST")).toBe(false); // opening the link joined nobody

    await page.getByTestId("beta-join").click();
    await expect(page.getByTestId("beta-member")).toContainText("שומרי כשרות");
    const join = beta().find((c) => c.method === "POST" && c.path === "/beta/join");
    expect(join?.body).toEqual({ code: "BETA-KOSHER" });

    // Membership is kept: the page asks the API again after a reload.
    await page.reload();
    await expect(page.getByTestId("beta-member")).toContainText("שומרי כשרות");
  });

  test("a code that does not work says so", async ({ page }) => {
    await page.goto("/beta/join/BETA-EXPIRED");
    await page.getByTestId("beta-join").click();
    await expect(page.getByTestId("beta-error")).toContainText("פג תוקף");
    await page.goto("/beta/join/WRONG-CODE");
    await page.getByTestId("beta-join").click();
    await expect(page.getByTestId("beta-error")).toContainText("לא מוכר");
    await expect(page.getByTestId("beta-member")).toHaveCount(0);
  });

  test("a link that cannot be a code is a 404", async ({ page }) => {
    const res = await page.goto("/beta/join/ab");
    expect(res?.status()).toBe(404);
  });

  test("the invite link is kept out of search results", async ({ page }) => {
    await page.goto("/beta/join/BETA-KOSHER");
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  });

  test("a member sends feedback from the page: rating and text, no user attached", async ({
    page,
  }) => {
    await page.goto("/beta/join/BETA-FAMILY");
    await page.getByTestId("beta-join").click();
    await page.getByTestId("beta-open-feedback").click();
    const dialog = page.getByRole("dialog", { name: "משוב על הבטא" });
    await dialog.getByRole("button", { name: "שליחה" }).click();
    await expect(dialog.getByRole("alert")).toContainText("בחרי דירוג");
    await dialog.getByText("5", { exact: true }).click();
    await dialog.getByLabel("מה עבד ומה לא? (לא חובה)").fill("ההחלפות היו מדויקות");
    await dialog.getByRole("button", { name: "שליחה" }).click();
    await expect(page.getByTestId("beta-feedback-sent")).toBeVisible();
    const sent = beta().find((c) => c.path === "/beta/feedback");
    expect(sent?.body).toEqual({ rating: 5, text: "ההחלפות היו מדויקות" });
    expect(mockBetaFeedback()).toEqual([
      { rating: 5, text: "ההחלפות היו מדויקות", segment: "large_family" },
    ]);
  });

  test("leaving asks first, then deletes the membership", async ({ page }) => {
    setBetaMockMember("periphery");
    await page.goto("/beta");
    await expect(page.getByTestId("beta-member")).toContainText("תושבי הפריפריה");
    await page.getByTestId("beta-leave").click();
    expect(beta().some((c) => c.method === "DELETE")).toBe(false);
    await page.getByTestId("beta-leave-confirm").click();
    await expect(page.getByTestId("beta-left")).toBeVisible();
    expect(beta().some((c) => c.method === "DELETE" && c.path === "/me/beta")).toBe(true);
    await page.reload();
    await expect(page.getByTestId("beta-no-invite")).toBeVisible();
    await expect(page.getByTestId("beta-member")).toHaveCount(0);
  });

  test("no horizontal scroll at 390 px", async ({ page }) => {
    await page.goto("/beta/join/BETA-KOSHER");
    await expect(page.getByTestId("beta-join")).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

for (const theme of ["light", "dark"] as const) {
  test.describe(`accessibility, ${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((t) => localStorage.setItem("sc-theme", t), theme);
      await page.emulateMedia({ colorScheme: theme });
    });

    test("join page, member page, leave question and feedback sheet have no serious violation", async ({
      page,
    }) => {
      await page.goto("/beta/join/BETA-KOSHER");
      await expect(page.getByTestId("beta-join")).toBeVisible();
      await axe(page, "join page");
      await page.getByTestId("beta-join").click();
      await expect(page.getByTestId("beta-member")).toBeVisible();
      await axe(page, "member");
      await page.getByTestId("beta-leave").click();
      await expect(page.getByTestId("beta-leave-confirm")).toBeVisible();
      await axe(page, "leave question");
      await page.getByRole("button", { name: "ביטול" }).click();
      await page.getByTestId("beta-open-feedback").click();
      await expect(page.getByRole("dialog", { name: "משוב על הבטא" })).toBeVisible();
      await axe(page, "feedback sheet");
    });
  });
}
