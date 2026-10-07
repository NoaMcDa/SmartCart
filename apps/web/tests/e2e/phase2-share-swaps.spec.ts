import { expect, test, type Page } from "@playwright/test";
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

/** From the list builder's "שיתוף" action to a shared copy of the pasted list (list 1). */
async function openSharedList(page: Page) {
  const calls = await mockApi(page);
  await seedProfile(page);
  await page.goto("/");
  await pasteList(page, "חלב, 2 רסק עגבניות");
  await page.getByTestId("share-entry").click();
  await expect(page).toHaveURL(/\/lists\/mine\/share$/);
  await page.getByRole("button", { name: "יצירת רשימה משותפת" }).click();
  await expect(page).toHaveURL(/\/lists\/1\/share$/);
  await expect(page.getByTestId("shared-item")).toHaveCount(2);
  return calls;
}

test.describe("share entry point in the list builder", () => {
  for (const viewport of [
    { width: 390, height: 844 },
    { width: 1280, height: 900 },
  ]) {
    test(`a visible שיתוף action at ${viewport.width} px opens the share screen of this list`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      await mockApi(page);
      await page.goto("/");
      const share = page.getByRole("link", { name: "שיתוף" });
      await expect(share).toBeVisible();
      expect((await share.boundingBox())!.height).toBeGreaterThanOrEqual(43.5);
      await expect(share).toHaveAttribute("href", "/lists/mine/share");
      await share.click();
      await expect(page).toHaveURL(/\/lists\/mine\/share$/);
      await expect(page.getByRole("heading", { level: 1, name: "שיתוף הרשימה" })).toBeVisible();
      // Once shared, the same action leads straight to the shared list.
      await pasteListAndShare(page);
    });
  }
});

async function pasteListAndShare(page: Page) {
  await page.goto("/");
  await pasteList(page, "חלב");
  await page.getByRole("link", { name: "שיתוף" }).click();
  await page.getByRole("button", { name: "יצירת רשימה משותפת" }).click();
  await expect(page).toHaveURL(/\/lists\/1\/share$/);
  await page.goto("/");
  await page.getByRole("link", { name: "שיתוף" }).click();
  await expect(page).toHaveURL(/\/lists\/1\/share$/);
}

test.describe("pending invites and members", () => {
  test("an invite can be revoked with the share id, and a member removed, both at once", async ({
    page,
    browser,
  }) => {
    const calls = await openSharedList(page);
    await page.getByRole("button", { name: "הזמנת בני משפחה" }).click();
    const sheet = page.getByRole("dialog", { name: "הזמנת בני משפחה" });
    await sheet.getByRole("button", { name: "יצירת קישור הזמנה" }).click();
    const inviteUrl = await sheet.getByLabel(/קישור הזמנה/).inputValue();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("member")).toHaveCount(2);

    // Revoke the pending invite: it leaves the list, and the API got DELETE .../shares/{share_id}.
    const pending = page.getByTestId("member").filter({ hasText: "הזמנה ממתינה" });
    await pending.getByRole("button", { name: /ביטול הזמנה ממתינה/ }).click();
    await expect(page.getByTestId("member")).toHaveCount(1);
    await expect
      .poll(() => calls.find((c) => c.method === "DELETE" && /\/shares\/\d+$/.test(c.path))?.path)
      .toBe("/me/lists/1/shares/1");
    // The revoked link no longer adds a member: a new invite, accepted by another device, does.
    await page.getByRole("button", { name: "הזמנת בני משפחה" }).click();
    await sheet.getByRole("button", { name: "יצירת קישור הזמנה" }).click();
    const second = await sheet.getByLabel(/קישור הזמנה/).inputValue();
    expect(second).not.toBe(inviteUrl);
    await page.keyboard.press("Escape");
    const other = await browser.newContext({ locale: "he-IL", timezoneId: "Asia/Jerusalem" });
    const page2 = await other.newPage();
    await mockApi(page2);
    await page2.goto(new URL(second).pathname);
    await page2.getByRole("button", { name: "הצטרפות לרשימה" }).click();
    await expect(page2).toHaveURL(/\/lists\/1\/share$/);
    await other.close();

    // The owner now sees a member with "remove" and no pending invite.
    const joined = page.getByTestId("member").filter({ hasText: "חברה ברשימה" });
    await expect(joined).toHaveCount(1, { timeout: 15_000 });
    await expect(page.getByText("הזמנה ממתינה")).toHaveCount(0);
    await joined.getByRole("button", { name: /הסרת חברה מהרשימה/ }).click();
    await expect(page.getByTestId("member")).toHaveCount(1);
  });

  test("a refused revoke puts the invite back and says so", async ({ page }) => {
    await openSharedList(page);
    await page.getByRole("button", { name: "הזמנת בני משפחה" }).click();
    const sheet = page.getByRole("dialog", { name: "הזמנת בני משפחה" });
    await sheet.getByRole("button", { name: "יצירת קישור הזמנה" }).click();
    await sheet.getByLabel(/קישור הזמנה/).waitFor();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("member")).toHaveCount(2);
    const origin = new URL(API_BASE_URL).origin;
    await page.route(
      (url) => url.origin === origin && /\/shares\/\d+$/.test(url.pathname),
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
          status: 500,
          headers: { "access-control-allow-origin": "*", "content-type": "application/json" },
          body: "{}",
        });
      },
    );
    await page
      .getByTestId("member")
      .filter({ hasText: "הזמנה ממתינה" })
      .getByRole("button", { name: /ביטול הזמנה ממתינה/ })
      .click();
    await expect(page.getByTestId("shared-message")).toContainText("ההזמנה לא בוטלה");
    await expect(page.getByTestId("member")).toHaveCount(2);
    await expect(page.getByText("הזמנה ממתינה")).toBeVisible();
  });
});

test.describe("checked items and offline edits on a shared list", () => {
  test("ticking an item is saved on the list and the other device sees it", async ({
    page,
    browser,
  }) => {
    await openSharedList(page);
    const first = page.getByTestId("shared-item").first();
    await first.getByRole("checkbox").check();
    await expect(first).toHaveAttribute("data-checked", "true");
    expect((await first.getByRole("checkbox").boundingBox())!.height).toBeGreaterThanOrEqual(23);
    await expect(page.getByTestId("pending-sync")).toHaveCount(0);

    const other = await browser.newContext({ locale: "he-IL", timezoneId: "Asia/Jerusalem" });
    const page2 = await other.newPage();
    await mockApi(page2);
    await page2.goto("/lists/1/share");
    const items2 = page2.getByTestId("shared-item");
    await expect(items2).toHaveCount(2);
    await expect(items2.first().getByRole("checkbox")).toBeChecked();
    await expect(items2.nth(1).getByRole("checkbox")).not.toBeChecked();
    // And an untick on the second device reaches the first without a refresh.
    await items2.first().getByRole("checkbox").uncheck();
    await expect(first.getByRole("checkbox")).not.toBeChecked({ timeout: 15_000 });
    await other.close();
  });

  test("edits made offline wait with ממתין לסנכרון and are sent when the connection is back", async ({
    page,
  }) => {
    await openSharedList(page);
    const items = page.getByTestId("shared-item");
    const origin = new URL(API_BASE_URL).origin;
    // The connection drops: every write to the API fails like a lost network.
    const down = (url: URL) => url.origin === origin && url.pathname.startsWith("/me/lists/");
    await page.route(down, (route) => {
      if (route.request().method() === "OPTIONS") return route.fallback();
      return route.abort("internetdisconnected");
    });
    await items.first().getByRole("checkbox").check();
    await items
      .nth(1)
      .getByRole("button", { name: /הוסיפי כמות/ })
      .click();
    const pending = page.getByTestId("pending-sync");
    await expect(pending).toContainText("ממתין לסנכרון");
    await expect(pending).toContainText("2");
    await expect(items.first().getByRole("checkbox")).toBeChecked();
    await expect(items.nth(1).getByRole("group")).toContainText("3");
    const queue = await page.evaluate(() => localStorage.getItem("sc-shared-queue-v1"));
    expect(JSON.parse(queue!).lists["1"]).toHaveLength(2);

    // The connection is back: the browser says so, and the queue is sent and emptied.
    await page.unroute(down);
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
    await expect(pending).toHaveCount(0);
    expect(
      JSON.parse((await page.evaluate(() => localStorage.getItem("sc-shared-queue-v1")))!).lists,
    ).toEqual({});
    await page.reload();
    await expect(items.first().getByRole("checkbox")).toBeChecked();
    await expect(items.nth(1).getByRole("group")).toContainText("3");
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
        // The three signals of the swap, in order: dismissed, applied, undone (source "swap").
        await expect
          .poll(() => calls.filter((c) => c.path === "/feedback/substitution").map((c) => c.body))
          .toEqual([
            expect.objectContaining({ verdict: "not_good", source: "swap", canonical_id: 1002 }),
            expect.objectContaining({ verdict: "accepted", source: "swap", canonical_id: 1004 }),
            {
              canonical_id: 1004,
              original_item_id: 10104,
              substitute_item_id: 10144,
              verdict: "kept_original",
              source: "swap",
              flex_level: "any_brand",
              match_confidence: 0.96,
            },
          ]);
      });

      test("an applied swap can still be undone after a reload, and a dismissal survives it", async ({
        page,
      }) => {
        const calls = await mockApi(page);
        await openWeeklyResults(page);
        const card = page.getByTestId("smart-cart");
        const stored = () =>
          page.evaluate(() => {
            const list = JSON.parse(window.localStorage.getItem("sc-list-v1") ?? "{}");
            const row = list.items.find(
              (i: { canonical: { canonical_id: number } | null }) =>
                i.canonical?.canonical_id === 1002,
            );
            return { flexLevel: row.flexLevel, swaps: window.localStorage.getItem("sc-swaps-v1") };
          });
        const before = (await stored()).flexLevel;

        // The top swap is the soy drink (1002, "close"): apply it, then reload the page.
        await card.getByRole("button", { name: /החליפי למשקה סויה/ }).click();
        await expect(page.getByTestId("smart-cart-applied")).toContainText("הוחלף: משקה סויה");
        expect((await stored()).flexLevel).toBe("close");
        await page.reload();
        await expect(page.getByTestId("smart-cart-applied")).toContainText("הוחלף: משקה סויה");

        // Undo after the reload restores the row as it was and sends kept_original.
        await page
          .getByTestId("smart-cart-applied")
          .getByRole("button", { name: "ביטול ההחלפה" })
          .click();
        await expect(page.getByTestId("smart-cart-undone")).toBeVisible();
        expect((await stored()).flexLevel).toBe(before);
        await expect
          .poll(() =>
            calls
              .filter((c) => c.path === "/feedback/substitution")
              .map((c) => (c.body as { verdict: string; source: string }).verdict),
          )
          .toEqual(["accepted", "kept_original"]);
        // The swap is offered again at the top; dismiss it, reload: it stays hidden.
        await expect(page.getByTestId("smart-cart-top")).toContainText("משקה סויה");
        await card.getByRole("button", { name: "לא עכשיו" }).click();
        await expect(page.getByTestId("smart-cart-top")).not.toContainText("משקה סויה");
        await page.reload();
        await expect(page.getByTestId("smart-cart-title")).toContainText("2 החלפות יחסכו לך");
        await expect(page.getByTestId("smart-cart-top")).not.toContainText("משקה סויה");
      });
    });
  }
});
