import { expect, test } from "@playwright/test";

/**
 * Language switch (#73). The test-only page /locale-test mounts LocaleSwitch inside the real shell
 * (the switch itself is mounted in Profile by the app). Both locales are RTL, so only `lang`, the
 * copy and the font change.
 */
test.describe("locale switch", () => {
  // Phone width: the bottom tab bar (the migrated nav) is visible there.
  test.use({ viewport: { width: 390, height: 844 } });

  test("switches to Arabic: html lang, nav copy, persistence across reload", async ({ page }) => {
    await page.goto("/locale-test");
    const html = page.locator("html");
    await expect(html).toHaveAttribute("lang", "he");
    await expect(html).toHaveAttribute("dir", "rtl");
    const nav = page.getByTestId("bottom-nav");
    await expect(nav.getByRole("link", { name: "רשימות" })).toBeAttached();

    await page.getByRole("radio", { name: "العربية" }).click();

    await expect(html).toHaveAttribute("lang", "ar");
    await expect(html).toHaveAttribute("dir", "rtl");
    await expect(nav.getByRole("link", { name: "القوائم" })).toBeAttached();
    await expect(page.getByRole("radiogroup", { name: "اللغة" })).toBeVisible();
    const cookies = await page.context().cookies();
    expect(cookies.find((c) => c.name === "sc-locale")?.value).toBe("ar");

    await page.reload();
    await expect(html).toHaveAttribute("lang", "ar");
    await expect(nav.getByRole("link", { name: "القوائم" })).toBeAttached();
    await expect(page.getByRole("radio", { name: "العربية" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  test("the choice carries to another page and back to Hebrew", async ({ page }) => {
    await page.goto("/locale-test");
    await page.getByRole("radio", { name: "العربية" }).click();
    await page.goto("/offline");
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(
      page.getByTestId("bottom-nav").getByRole("link", { name: "القوائم" }),
    ).toBeAttached();

    await page.goto("/locale-test");
    await page.getByRole("radio", { name: "עברית" }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "he");
    await expect(
      page.getByTestId("bottom-nav").getByRole("link", { name: "רשימות" }),
    ).toBeAttached();
  });

  test("Arabic glyphs render in Noto Sans Arabic, Hebrew stays in Heebo, no horizontal scroll", async ({
    page,
  }) => {
    await page.goto("/locale-test");
    await page.getByRole("radio", { name: "العربية" }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    // The font stack lists Heebo first and Noto Sans Arabic second (--sc-font).
    const stack = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
    expect(stack).toMatch(/heebo/i);
    expect(stack).toMatch(/noto/i);
    // The Arabic file really loads once an Arabic glyph needs it.
    const loaded = await page.evaluate(async () => {
      await document.fonts.ready;
      return [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family);
    });
    expect(loaded.some((f) => /noto|__.*arabic/i.test(f))).toBe(true);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test("/locale-test is noindex", async ({ page }) => {
    await page.goto("/locale-test");
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  });
});
