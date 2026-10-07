import { expect, test, type Page } from "@playwright/test";
import { mockApi, seedProfile } from "./core-helpers";

const FOUND = "5901234123457";
const NOT_FOUND = "5901234000000"; // valid EAN-13 whose chain code the mock does not know

/**
 * A stubbed camera and detector, so the scan flow runs in headless Chromium: getUserMedia returns
 * a canvas stream (no device, no permission prompt) and BarcodeDetector "sees" the code the test
 * sets. The real camera and real detectors are checked by hand (docs/web.md, "Phase 2 screens").
 */
async function stubCamera(page: Page, code: string | null) {
  await page.addInitScript((value) => {
    const w = window as unknown as Record<string, unknown>;
    w.__getUserMediaCalls = 0;
    navigator.mediaDevices.getUserMedia = async () => {
      w.__getUserMediaCalls = (w.__getUserMediaCalls as number) + 1;
      const canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = 240;
      canvas.getContext("2d")!.fillRect(0, 0, 320, 240);
      return canvas.captureStream(5);
    };
    w.BarcodeDetector = class {
      static getSupportedFormats = async () => ["ean_13", "ean_8"];
      detect = async () => (value ? [{ rawValue: value, format: "ean_13" }] : []);
    };
  }, code);
}

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
]) {
  test.describe(`scan at ${viewport.width} px`, () => {
    test.use({ viewport });

    test("camera on tap, stubbed detector, result card with here, cheapest and the labeled substitute, add to list", async ({
      page,
    }) => {
      const calls = await mockApi(page);
      await seedProfile(page);
      await stubCamera(page, FOUND);
      await page.goto("/scan");
      await expect(page.getByRole("heading", { level: 1, name: "סריקת ברקוד" })).toBeVisible();

      // The permission is explained first and nothing is requested on load.
      await expect(page.getByText(/לא נשמרות תמונות/)).toBeVisible();
      expect(
        await page.evaluate(() => (window as never as Record<string, number>).__getUserMediaCalls),
      ).toBe(0);
      await expect(page.getByTestId("scan-store")).toHaveValue("103");

      await page.getByRole("button", { name: "הפעלת המצלמה" }).click();
      const card = page.getByTestId("scan-result");
      await expect(card).toBeVisible({ timeout: 10_000 });
      // The camera is off once the code is read.
      await expect(page.getByTestId("scan-video")).toHaveCount(0);

      await expect(card.getByRole("heading", { level: 2 })).toHaveText("רסק עגבניות אסם 260 ג'");
      await expect(page.getByTestId("scan-here")).toContainText(/כאן\s*₪\s14\.90/);
      await expect(page.getByTestId("scan-cheapest")).toContainText(/₪\s11\.50/);
      await expect(page.getByTestId("scan-cheapest")).toContainText("אושר עד");
      await expect(page.getByTestId("scan-substitute")).toContainText(/₪\s8\.90/);
      await expect(
        page.getByTestId("scan-substitute").locator('[data-variant="substitute"]'),
      ).toHaveText("תחליף");
      await expect(page.getByTestId("scan-reason")).toContainText("למה זה תחליף");
      for (const row of ["scan-here", "scan-cheapest", "scan-substitute"]) {
        await expect(page.getByTestId(row).locator("time[datetime]")).toHaveCount(1);
      }
      await expect(card).toContainText("המחיר הקובע הוא בקופה");
      if (calls.length) {
        const lookup = calls.find((c) => c.path === `/items/barcode/${FOUND}`);
        expect(lookup).toBeDefined();
      }

      for (const button of await card.getByRole("button").all()) {
        expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(43.5);
      }

      // Quantity 2, add: the list gets the canonical product with the category's level.
      await card.getByRole("button", { name: /הוסיפי כמות של/ }).click();
      await card.getByRole("button", { name: "הוסיפי לרשימה" }).click();
      await expect(page.getByTestId("scan-added")).toBeVisible();
      const stored = await page.evaluate(() =>
        JSON.parse(localStorage.getItem("sc-list-v1") ?? "{}"),
      );
      expect(stored.items).toHaveLength(1);
      expect(stored.items[0]).toMatchObject({ quantity: 2, flexLevel: "any_brand" });
      expect(stored.items[0].canonical.canonical_id).toBe(1004);

      await page.goto("/");
      await expect(page.getByTestId("list-row")).toHaveCount(1);
      await expect(page.getByTestId("list-row")).toContainText("רסק עגבניות");
    });

    test("no horizontal scroll and the manual field is there", async ({ page }) => {
      await mockApi(page);
      await page.goto("/scan");
      await expect(page.getByRole("textbox", { name: /ברקוד \(13 ספרות/ })).toBeVisible();
      const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
    });
  });
}

test.describe("scan: fallbacks", () => {
  test("denied camera permission explains it and manual entry still works", async ({ page }) => {
    await mockApi(page);
    await page.addInitScript(() => {
      navigator.mediaDevices.getUserMedia = async () => {
        throw new DOMException("denied", "NotAllowedError");
      };
    });
    await page.goto("/scan");
    await page.getByRole("button", { name: "הפעלת המצלמה" }).click();
    await expect(page.getByTestId("scan-camera-error")).toContainText("הגישה למצלמה נחסמה");
    await page.getByRole("textbox", { name: /ברקוד \(13 ספרות/ }).fill(FOUND);
    await page.getByRole("button", { name: "חיפוש" }).click();
    await expect(page.getByTestId("scan-result")).toBeVisible();
    await expect(page.getByTestId("scan-substitute")).toContainText(/₪\s8\.90/);
  });

  test("an unknown barcode shows not-found with report-a-gap and never a guess", async ({
    page,
  }) => {
    await mockApi(page);
    await page.goto("/scan");
    await expect(page.getByTestId("scan-store")).not.toHaveValue("");
    await page.getByRole("textbox", { name: /ברקוד \(13 ספרות/ }).fill(NOT_FOUND);
    await page.getByRole("button", { name: "חיפוש" }).click();
    const state = page.getByTestId("scan-notfound");
    await expect(state).toContainText("לא מצאנו את הברקוד הזה");
    await expect(state).toContainText("לא ננחש מוצר");
    await expect(page.getByTestId("scan-result")).toHaveCount(0);
    await state.getByRole("button", { name: /דווחי על פער/ }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("a mistyped barcode is caught before any request", async ({ page }) => {
    const calls = await mockApi(page);
    await page.goto("/scan");
    await page.getByRole("textbox", { name: /ברקוד \(13 ספרות/ }).fill("5901234123450");
    await page.getByRole("button", { name: "חיפוש" }).click();
    await expect(page.getByText(/לא מרכיבות ברקוד תקין/)).toBeVisible();
    expect(calls.some((c) => c.path.startsWith("/items/barcode"))).toBe(false);
  });
});
