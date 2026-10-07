import { expect, test } from "@playwright/test";
import { API_BASE_URL } from "../../src/api/config";
import { resetMeMock } from "../../src/mocks/handlers";
import { resetPhase2Mock } from "../../src/mocks/handlers.phase2";
import { mockApi, openWeeklyResults, pasteList, seedProfile } from "./core-helpers";

test.beforeEach(() => {
  resetMeMock();
  resetPhase2Mock();
});

test.describe("shared lists", () => {
  test("share from my list, copy the invite, accept it on another device, see the same list and each other's edits", async ({
    page,
    browser,
  }) => {
    await mockApi(page);
    await seedProfile(page);
    await page.goto("/");
    await pasteList(page, "חלב, 2 רסק עגבניות");

    // Share: the first visit turns the device's list into a shared one and opens it.
    await page.goto("/lists/mine/share");
    await expect(page.getByRole("heading", { level: 1, name: "שיתוף הרשימה" })).toBeVisible();
    await page.getByRole("button", { name: "יצירת רשימה משותפת" }).click();
    await expect(page).toHaveURL(/\/lists\/1\/share$/);
    await expect(page.getByTestId("shared-name")).toHaveText("הקנייה השבועית");
    const items = page.getByTestId("shared-item");
    await expect(items).toHaveCount(2);
    await expect(items.first()).toContainText("חלב טרי 3%, 1 ליטר");
    await expect(page.getByTestId("sync-state")).toHaveAttribute("data-mode", "polling");

    // The sheet: role, invite link, copy.
    await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.getByRole("button", { name: "הזמנת בני משפחה" }).click();
    const sheet = page.getByRole("dialog", { name: "הזמנת בני משפחה" });
    await expect(sheet).toBeVisible();
    await sheet.getByRole("radio", { name: "עריכה" }).click();
    await sheet.getByRole("button", { name: "יצירת קישור הזמנה" }).click();
    const link = sheet.getByLabel(/קישור הזמנה/);
    await expect(link).toHaveValue(/\/lists\/accept\/inv-1-/);
    await sheet.getByRole("button", { name: "העתקת הקישור" }).click();
    await expect(sheet.getByTestId("invite-copied")).toBeVisible();
    const inviteUrl = await link.inputValue();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(inviteUrl);
    for (const button of await sheet.getByRole("button").all()) {
      expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(43.5);
    }
    await page.keyboard.press("Escape");

    // The member list shows the owner and the pending invite.
    const members = page.getByTestId("member");
    await expect(members).toHaveCount(2);
    await expect(members.nth(0)).toContainText("הבעלים של הרשימה");
    await expect(members.nth(1)).toContainText("הזמנה ממתינה");
    await expect(members.nth(1)).toContainText("עריכה");

    // Another device opens the link: nothing happens until the tap, then the list opens.
    const other = await browser.newContext({ locale: "he-IL", timezoneId: "Asia/Jerusalem" });
    const page2 = await other.newPage();
    await mockApi(page2);
    await page2.goto(new URL(inviteUrl).pathname);
    await expect(
      page2.getByRole("heading", { level: 1, name: "הצטרפות לרשימה משותפת" }),
    ).toBeVisible();
    await expect(page2.getByTestId("accept")).toContainText("הוזמנת לרשימת קניות משותפת");
    await expect(page2.getByTestId("accept")).toContainText("לא תראה את המיקום או ההעדפות שלך");
    await page2.getByRole("button", { name: "הצטרפות לרשימה" }).click();
    await expect(page2).toHaveURL(/\/lists\/1\/share$/);
    await expect(page2.getByTestId("shared-item")).toHaveCount(2);

    // An edit on the second device reaches the first without a refresh.
    const second = page2.getByTestId("shared-item").nth(1);
    await second.getByRole("button", { name: /הוסיפי כמות/ }).click();
    await expect(second.getByRole("group")).toContainText("3");
    await expect(page.getByTestId("shared-item").nth(1).getByRole("group")).toContainText("3", {
      timeout: 15_000,
    });
    // And a removal on the first reaches the second.
    await page.getByTestId("shared-item").first().getByRole("button", { name: /הסרת/ }).click();
    await expect(page2.getByTestId("shared-item")).toHaveCount(1, { timeout: 15_000 });
    await other.close();
  });

  test("an invalid or expired invite says so", async ({ page }) => {
    await mockApi(page);
    await page.route(
      (url) =>
        url.origin === new URL(API_BASE_URL).origin && url.pathname.startsWith("/lists/accept/"),
      (route) => {
        if (route.request().method() === "OPTIONS") {
          return route.fulfill({
            status: 204,
            headers: {
              "access-control-allow-origin": "*",
              "access-control-allow-headers": "*",
              "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
            },
          });
        }
        return route.fulfill({
          status: 410,
          headers: { "access-control-allow-origin": "*", "content-type": "application/json" },
          body: JSON.stringify({ detail: "expired" }),
        });
      },
    );
    await page.goto("/lists/accept/old-token");
    await page.getByRole("button", { name: "הצטרפות לרשימה" }).click();
    await expect(page.getByTestId("accept-error")).toContainText("פג תוקפו");
    await expect(page).toHaveURL(/\/lists\/accept\/old-token$/);
  });
});

test.describe("smart cart", () => {
  for (const viewport of [
    { width: 390, height: 844 },
    { width: 1280, height: 900 },
  ]) {
    test.describe(`results at ${viewport.width} px`, () => {
      test.use({ viewport });

      test("3 swaps with the mock total, the biggest one first; dismiss, apply and undo", async ({
        page,
      }) => {
        const calls = await mockApi(page);
        await openWeeklyResults(page);
        const card = page.getByTestId("smart-cart");
        await expect(card).toBeVisible();
        // The mock's three swaps are 5.00, 4.80 and 1.20, which add up to ₪11.
        await expect(page.getByTestId("smart-cart-title")).toContainText("3 החלפות יחסכו לך");
        await expect(page.getByTestId("smart-cart-title")).toContainText(/₪\s11$/);
        await expect(card).toContainText("עגלה חכמה");
        const top = page.getByTestId("smart-cart-top");
        await expect(top).toContainText("משקה סויה ללא סוכר, מותג פרטי, 1 ל'");
        await expect(top).toContainText(/חיסכון\s*₪\s5/);
        await expect(top).toContainText("ביטחון בהתאמה 88%");
        await expect(page.getByTestId("smart-cart-why")).toContainText("למה:");
        for (const tag of await top.locator("[data-variant]").all()) {
          await expect(tag.locator("svg")).toHaveCount(1);
        }
        await expect(top.locator('[data-variant="matched"]').first()).toBeVisible();
        await expect(top.locator('[data-variant="differs"]')).toContainText("מותג פרטי");
        await expect(card.locator("time[datetime]")).toHaveCount(1);
        await expect(card).toContainText("המחיר הקובע הוא בקופה");
        for (const button of await card.getByRole("button").all()) {
          expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(43.5);
        }
        if (calls.length) {
          const req = calls.find((c) => c.path === "/optimize/swaps");
          expect(req).toBeDefined();
        }

        // Dismiss the top swap: two left, the next one is on top, and it is not offered again.
        await card.getByRole("button", { name: "לא עכשיו" }).click();
        await expect(page.getByTestId("smart-cart-title")).toContainText("2 החלפות יחסכו לך");
        await expect(page.getByTestId("smart-cart-title")).toContainText(/₪\s6$/);
        await expect(top).toContainText("רסק עגבניות שופרסל 260 ג'");
        if (calls.length) {
          await expect
            .poll(() => calls.find((c) => c.path === "/feedback/substitution")?.body)
            .toMatchObject({ verdict: "not_good", substitute_item_id: 10142 });
        }
        await page.reload();
        await expect(page.getByTestId("smart-cart-title")).toContainText("2 החלפות יחסכו לך");

        // Apply: the list row changes only after the tap, the swap shows as applied, undo reverts.
        await expect(page.getByTestId("smart-cart-applied")).toHaveCount(0);
        await card.getByRole("button", { name: /החליפי לרסק עגבניות/ }).click();
        await expect(page.getByTestId("smart-cart-applied")).toContainText(
          "הוחלף: רסק עגבניות שופרסל 260 ג'",
        );
        await expect(page.getByTestId("smart-cart-title")).toContainText("החלפה אחת תחסוך לך");
        await page
          .getByTestId("smart-cart-applied")
          .getByRole("button", { name: "ביטול ההחלפה" })
          .click();
        await expect(page.getByTestId("smart-cart-undone")).toBeVisible();
        await expect(page.getByTestId("smart-cart-title")).toContainText("2 החלפות יחסכו לך");
      });
    });
  }
});
