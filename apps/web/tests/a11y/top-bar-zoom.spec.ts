import { expect, test, type Page } from "@playwright/test";

/**
 * Issue #91: the top bar overflowed by 7 px at 195 px, which is a 390 px phone at 200% zoom
 * (WCAG 1.4.4 resize text, 1.4.10 reflow). The bar must fit its content inside the viewport: no
 * horizontal scroll, and the brand link, the theme switch and the profile link (desktop only)
 * all inside the visible width, in both themes. Only the bar is asserted: other content on the
 * page (the list builder, Profile) has its own overflow at this width and is not part of #91.
 */
const WIDTHS = [195, 240, 320] as const;
const THEMES = ["light", "dark"] as const;
const PATHS = ["/", "/compare", "/profile", "/offline"] as const;

async function barMetrics(page: Page) {
  return page.evaluate(() => {
    const header = document.querySelector('[data-testid="top-nav"]')?.closest("header");
    if (!header) return null;
    const viewport = document.documentElement.clientWidth;
    const outside = [...header.querySelectorAll<HTMLElement>("a, button, [role=switch]")]
      .filter((el) => el.getClientRects().length > 0)
      .map((el) => {
        const r = el.getBoundingClientRect();
        return {
          name: el.getAttribute("aria-label") ?? el.textContent?.trim() ?? el.tagName,
          start: Math.round(r.left * 10) / 10,
          end: Math.round(r.right * 10) / 10,
        };
      })
      .filter((box) => box.start < -0.5 || box.end > viewport + 0.5);
    return {
      viewport,
      headerScroll: header.scrollWidth,
      headerClient: header.clientWidth,
      outside,
    };
  });
}

for (const width of WIDTHS) {
  for (const theme of THEMES) {
    test.describe(`top bar at ${width} px, ${theme} theme`, () => {
      test.use({ viewport: { width, height: 700 } });

      for (const path of PATHS) {
        test(`${path}: no horizontal overflow, every control inside the viewport`, async ({
          page,
        }) => {
          await page.addInitScript((value) => localStorage.setItem("sc-theme", value), theme);
          await page.emulateMedia({ colorScheme: theme });
          await page.goto(path);
          await expect(page.locator('header:has([data-testid="top-nav"])')).toBeVisible();
          const m = await barMetrics(page);
          expect(m, "the page has a top bar").not.toBeNull();
          expect(m!.outside, "controls outside the viewport").toEqual([]);
          expect(m!.headerScroll, "header content wider than the header").toBeLessThanOrEqual(
            m!.headerClient,
          );
        });
      }
    });
  }
}

test.describe("top bar at 195 px keeps its names and targets", () => {
  test.use({ viewport: { width: 195, height: 700 } });

  test("the brand link and the theme switch are named and at least 44 px tall", async ({
    page,
  }) => {
    await page.goto("/");
    const brand = page.getByRole("link", { name: "SmartCart, לדף הבית" });
    const toggle = page.getByRole("switch", { name: "מצב כהה" });
    for (const control of [brand, toggle]) {
      await expect(control).toBeVisible();
      const box = await control.boundingBox();
      expect(box!.height).toBeGreaterThanOrEqual(44);
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(195);
    }
  });
});
