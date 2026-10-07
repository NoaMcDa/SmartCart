import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { ROUTES } from "../e2e/routes";

/** The SEO group is W6's: keyboard order, focus visibility, target size. */
const SEO_PATHS = [
  "/methodology",
  "/c/dairy",
  "/c/dairy-milk",
  "/p/milk-fresh-3",
  "/basket-index",
  "/accessibility",
];

test("the harness fails on a real violation (low contrast text)", async ({ page }) => {
  await page.setContent(
    `<!doctype html><html lang="he" dir="rtl"><head><title>t</title></head>
     <body><main><h1>כותרת</h1><p style="color:#cccccc;background:#ffffff">טקסט בניגודיות נמוכה</p></main></body></html>`,
  );
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const blocking = results.violations.filter((v) =>
    ["serious", "critical"].includes(v.impact ?? ""),
  );
  expect(blocking.map((v) => v.id)).toContain("color-contrast");
});

test.describe("keyboard", () => {
  for (const path of SEO_PATHS) {
    test(`${path}: the skip link is the first stop and moves focus to the content`, async ({
      page,
    }) => {
      await page.goto(path);
      await page.keyboard.press("Tab");
      const skip = page.getByRole("link", { name: "דילוג לתוכן" });
      await expect(skip).toBeFocused();
      await expect(skip).toBeInViewport();
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(/#main$/);
    });

    test(`${path}: every stop has a visible focus indicator`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const stops = Math.min(60, await page.locator("a[href], button, summary").count());
      for (let i = 0; i < stops; i++) {
        await page.keyboard.press("Tab");
        const visible = await page.evaluate(() => {
          const el = document.activeElement as HTMLElement | null;
          if (!el || el === document.body) return true;
          const style = getComputedStyle(el);
          const outline = style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0;
          return outline || style.boxShadow !== "none";
        });
        expect(visible, `stop ${i + 1} on ${path}`).toBe(true);
      }
    });
  }

  test("the basket definition and history disclosures open with Enter and Space", async ({
    page,
  }) => {
    await page.goto("/basket-index");
    const summary = page.locator("summary").first();
    await summary.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("details").first()).toHaveAttribute("open", "");
    await page.keyboard.press("Space");
    await expect(page.locator("details").first()).not.toHaveAttribute("open", "");
  });
});

test.describe("touch targets at 390 px", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  for (const path of SEO_PATHS) {
    test(`${path}: list rows, breadcrumbs, buttons and footer links are at least 44 px tall`, async ({
      page,
    }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      // In-text links inside a sentence are exempt (WCAG 2.5.5 is AAA); everything laid out as a control is not.
      const small = await page.evaluate(() => {
        const controls = document.querySelectorAll(
          "main nav a, main summary, main ul > li > a, main a[class*='linkRow'], main [class*='cta'] a, footer a, header a, nav a",
        );
        return [...controls]
          .filter((el) => {
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
          })
          .filter((el) => el.getBoundingClientRect().height < 43.5)
          .map((el) => `${el.tagName} ${(el.textContent ?? "").trim().slice(0, 30)}`);
      });
      expect(small).toEqual([]);
    });
  }
});

test.describe("reflow", () => {
  // WCAG 1.4.10 (reflow) is a 2.1 criterion, stricter than the 2.0 level the standard requires:
  // content must fit 320 CSS px wide, which is 400% zoom on a desktop browser.
  test.describe("320 px wide, every route", () => {
    test.use({ viewport: { width: 320, height: 700 } });

    for (const { path } of ROUTES) {
      test(`${path}: no horizontal scroll`, async ({ page }) => {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow).toBeLessThanOrEqual(0);
      });
    }
  });

  // 200% zoom on a 390 px phone leaves 195 CSS px (issue #26: usable at 200% text size). The
  // shell's top bar still overflows by 7 px there (docs/a11y-report.md, open finding, not ours
  // to fix), so this checks the page content and the footer, which are ours.
  test.describe("195 px wide (200% zoom on a phone), SEO pages", () => {
    test.use({ viewport: { width: 195, height: 844 } });

    for (const path of SEO_PATHS) {
      test(`${path}: content and footer stay inside the viewport`, async ({ page }) => {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        const outside = await page.evaluate(() => {
          const width = document.documentElement.clientWidth;
          return [...document.querySelectorAll("main *, footer *")]
            .filter((el) => {
              const r = el.getBoundingClientRect();
              if (r.width === 0 || el.closest(".sr-only")) return false;
              // Data tables scroll inside their own wrapper (the WCAG 1.4.10 exception for
              // tables); the wrapper itself must still fit.
              const wrapper = el.closest("[class*='tableWrap']");
              if (wrapper && wrapper !== el) return false;
              return r.right > width + 0.5 || r.left < -0.5;
            })
            .map((el) => `${el.tagName}.${String(el.className).slice(0, 30)}`);
        });
        expect(outside).toEqual([]);
      });
    }
  });
});
