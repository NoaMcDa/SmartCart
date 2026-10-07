import { expect, test } from "@playwright/test";
import { ROUTES } from "./routes";

test.describe("routes and document direction", () => {
  for (const { path, h1 } of ROUTES) {
    test(`${path} renders "${h1}" in an RTL Hebrew document`, async ({ page }) => {
      const res = await page.goto(path);
      expect(res?.status()).toBe(200);
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
      await expect(page.locator("html")).toHaveAttribute("lang", "he");
      await expect(page.getByRole("heading", { level: 1, name: h1 })).toBeVisible();
    });
  }

  test("unknown routes get the Hebrew 404", async ({ page }) => {
    const res = await page.goto("/no-such-page");
    expect(res?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1, name: "הדף לא נמצא" })).toBeVisible();
  });
});

test.describe("phone, 390 px", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  for (const path of ["/", "/compare", "/profile", "/design-system", "/methodology"]) {
    test(`${path} has no horizontal scroll`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
    });
  }

  test("bottom nav: five tabs right to left, raised scan button, 44 px targets", async ({
    page,
  }) => {
    await page.goto("/");
    const nav = page.getByTestId("bottom-nav");
    await expect(nav).toBeVisible();
    await expect(page.getByTestId("top-nav")).toBeHidden();
    const labels = ["רשימות", "השוואה", "סריקה", "התראות", "פרופיל"];
    const xs: number[] = [];
    for (const label of labels) {
      const box = await nav.getByText(label, { exact: true }).boundingBox();
      expect(box).not.toBeNull();
      xs.push(box!.x);
    }
    // RTL: each next tab sits further left.
    for (let i = 1; i < xs.length; i++) expect(xs[i]!).toBeLessThan(xs[i - 1]!);
    const scan = nav.getByRole("link", { name: "סריקת ברקוד" });
    const scanBox = await scan.boundingBox();
    expect(scanBox!.height).toBeGreaterThanOrEqual(56);
    for (const link of await nav.getByRole("link").all()) {
      const b = await link.boundingBox();
      expect(b!.height).toBeGreaterThanOrEqual(44);
    }
    await expect(nav.getByRole("link", { name: "רשימות" })).toHaveAttribute("aria-current", "page");
  });

  test("bottom nav navigates", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("bottom-nav").getByRole("link", { name: "השוואה" }).click();
    await expect(page).toHaveURL(/\/compare$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "איפה הכי זול השבוע?" }),
    ).toBeVisible();
  });
});

test.describe("desktop, 1280 px", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("content is capped at 1200 px and centered; top bar carries the sections", async ({
    page,
  }) => {
    await page.goto("/design-system");
    const box = await page.getByTestId("content").boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeLessThanOrEqual(1200);
    expect(Math.abs(box!.x - (1280 - box!.width) / 2)).toBeLessThanOrEqual(1);
    await expect(page.getByTestId("bottom-nav")).toBeHidden();
    const top = page.getByTestId("top-nav");
    await expect(top).toBeVisible();
    for (const label of ["רשימות", "השוואה", "סריקה", "התראות"]) {
      await expect(top.getByRole("link", { name: label })).toBeVisible();
    }
    await expect(page.getByRole("link", { name: "פרופיל" })).toBeVisible();
  });

  test("no horizontal scroll at 1280 either", async ({ page }) => {
    await page.goto("/design-system");
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
