import { expect, test, type Page } from "@playwright/test";

const LIGHT_BG = "rgb(246, 245, 242)"; // --sc-bg light #F6F5F2
const DARK_BG = "rgb(20, 20, 19)"; // --sc-bg dark #141413

const theme = (page: Page) => page.locator("html").getAttribute("data-theme");
const bodyBg = (page: Page) => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
const activeThemeColor = (page: Page) =>
  page.evaluate(() => {
    const metas = [...document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')];
    const match = metas.find((m) => !m.media || window.matchMedia(m.media).matches);
    return match?.content.toUpperCase();
  });

test.describe("theme", () => {
  test("follows the OS by default and reacts live to OS changes", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await bodyBg(page)).toBe(DARK_BG);
    expect(await activeThemeColor(page)).toBe("#1F1F1D");

    await page.emulateMedia({ colorScheme: "light" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    expect(await bodyBg(page)).toBe(LIGHT_BG);
    expect(await activeThemeColor(page)).toBe("#FFFFFF");
  });

  test("header switch toggles data-theme, shows moon/sun, persists across reloads", async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");
    const toggle = page.getByRole("switch", { name: "מצב כהה" });
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    await expect(toggle.locator('[data-icon="moon"]')).toBeVisible();
    await expect(toggle.locator('[data-icon="sun"]')).toBeHidden();

    await toggle.click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await expect(toggle.locator('[data-icon="sun"]')).toBeVisible();
    await expect(toggle.locator('[data-icon="moon"]')).toBeHidden();
    expect(await bodyBg(page)).toBe(DARK_BG);
    // Manual choice overrides the OS for the browser UI color too.
    expect(await activeThemeColor(page)).toBe("#1F1F1D");

    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.getByRole("switch", { name: "מצב כהה" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("no flash: the saved theme is applied before any app JavaScript runs", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");
    await page.evaluate(() => localStorage.setItem("sc-theme", "dark"));
    // Hold every JS chunk so React cannot hydrate; only the inline head script can act.
    await page.route("**/_next/static/**/*.js", async (route) => {
      await new Promise((r) => setTimeout(r, 3000));
      await route.continue();
    });
    await page.goto("/compare", { waitUntil: "domcontentloaded" });
    expect(await theme(page)).toBe("dark");
    expect(await bodyBg(page)).toBe(DARK_BG);
  });

  test("Profile has the same setting, in sync with the header", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/profile");
    const group = page.getByRole("radiogroup", { name: "ערכת צבעים" });
    await expect(group.getByRole("radio", { name: "אוטומטי" })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    await page.getByRole("switch", { name: "מצב כהה" }).click();
    await expect(group.getByRole("radio", { name: "כהה" })).toHaveAttribute("aria-checked", "true");

    await group.getByRole("radio", { name: "בהיר" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect(page.getByRole("switch", { name: "מצב כהה" })).toHaveAttribute(
      "aria-checked",
      "false",
    );

    // Back to "system" on a dark OS.
    await page.emulateMedia({ colorScheme: "dark" });
    await group.getByRole("radio", { name: "אוטומטי" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await page.evaluate(() => localStorage.getItem("sc-theme"))).toBeNull();
  });
});
