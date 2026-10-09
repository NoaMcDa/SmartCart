import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { KEYS, mockApi, profileSeed, seed } from "./secondary.helpers";

/**
 * Issue #73, workstream AR-1: with the `sc-locale=ar` cookie the shell, the ui components, the
 * profile, onboarding, sign-in, offline, not-found and design-system pages, and the page chrome of
 * the core routes read Arabic. Features that other workstreams migrate (the list builder, the
 * results, the budget and consent controls) are left out of the "no Hebrew" regions on purpose.
 */

const HEBREW = /[֐-׿]/;
const EASTERN_DIGITS = /[٠-٩۰-۹]/;

type Route = {
  path: string;
  /** Selectors whose whole content must be Arabic (no Hebrew letters, in text or attributes). */
  regions: string[];
  /** The back link under the core pages, in Arabic. */
  backLink?: string;
  /** The page h1, in Arabic. */
  h1: string;
  /** Hebrew text of other workstreams to ignore inside the regions: any label containing it goes. */
  skipLabelsContaining?: string[];
  /** The profile is seeded so the location summary and the savings list render. */
  seedProfile?: boolean;
};

const CHROME = ["header", '[data-testid="bottom-nav"]'];

const ROUTES: ReadonlyArray<Route> = [
  { path: "/", regions: [...CHROME, "main h1"], h1: "التسوّق الأسبوعي" },
  {
    path: "/compare",
    regions: [...CHROME, "main h1"],
    h1: "أين الأرخص هذا الأسبوع؟",
    backLink: "العودة إلى القائمة",
  },
  {
    path: "/compare/substitution/42",
    regions: [...CHROME, "main h1"],
    h1: "تفاصيل البديل",
    backLink: "العودة إلى النتائج",
  },
  { path: "/onboarding", regions: [...CHROME, "main"], h1: "أهلًا بك" },
  {
    path: "/profile",
    regions: [...CHROME, "main"],
    h1: "الملف الشخصي",
    seedProfile: true,
    // The budget section (#70) and the usage-events switch (consent) belong to other workstreams.
    skipLabelsContaining: ["אירועי שימוש"],
  },
  { path: "/offline", regions: [...CHROME, "main"], h1: "لا يوجد اتصال بالإنترنت" },
  { path: "/design-system", regions: [...CHROME, "main"], h1: "مجموعة التصميم" },
  { path: "/no-such-page", regions: [...CHROME, "main"], h1: "الصفحة غير موجودة" },
];

async function open(page: Page, route: Route) {
  await mockApi(page);
  if (route.seedProfile) {
    await seed(page, {
      [KEYS.profile]: profileSeed(),
      [KEYS.savings]: [
        {
          id: "s1",
          at: "2026-10-01T10:00:00Z",
          storeName: "Rami Levy",
          listName: null,
          net: 31.4,
        },
      ],
    });
  }
  await page.goto(route.path);
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.locator("main h1").first()).toHaveText(route.h1);
  // `.first()` is the page's own back link (first in the DOM). The substitution card's not-found
  // state adds a second link to the same place with the same words (AR-2 migrated its copy), so
  // a strict locator would match two links.
  if (route.backLink)
    await expect(page.getByRole("link", { name: route.backLink }).first()).toBeVisible();
}

/** Hebrew letters in the text, the labels and the titles of the regions, minus skipped pieces. */
async function hebrewIn(page: Page, route: Route): Promise<string[]> {
  return page.evaluate(
    ({ regions, skip, skipSections }) => {
      const found: string[] = [];
      const hebrew = /[֐-׿]+/g;
      for (const selector of regions) {
        for (const root of document.querySelectorAll(selector)) {
          // Text marked `lang="he"` is Hebrew on purpose (the language switch labels each option
          // in its own language), so it is exempt, root and descendants alike. Nothing else is.
          if (root.closest('[lang="he"]')) continue;
          const clone = root.cloneNode(true) as Element;
          clone.querySelectorAll('[lang="he"]').forEach((n) => n.remove());
          for (const section of skipSections)
            clone.querySelectorAll(section).forEach((n) => n.remove());
          for (const label of clone.querySelectorAll("label")) {
            if (skip.some((s) => label.textContent?.includes(s))) label.closest("div")?.remove();
          }
          for (const el of [clone, ...clone.querySelectorAll("*")]) {
            for (const attr of ["aria-label", "title", "placeholder", "alt", "value"]) {
              const value = el.getAttribute(attr);
              if (value && hebrew.test(value)) found.push(`${selector} ${attr}="${value}"`);
              hebrew.lastIndex = 0;
            }
          }
          const text = clone.textContent ?? "";
          for (const match of text.match(hebrew) ?? []) found.push(`${selector} text "${match}"`);
        }
      }
      return found;
    },
    {
      regions: route.regions,
      skip: route.skipLabelsContaining ?? [],
      // The budget section (#70) is not migrated by AR-1.
      skipSections: ['[data-testid="budget-section"]'],
    },
  );
}

test.beforeEach(async ({ context, baseURL }) => {
  await context.addCookies([{ name: "sc-locale", value: "ar", url: baseURL! }]);
});

test.describe("Arabic, every route in the AR-1 scope", () => {
  for (const route of ROUTES) {
    test(`${route.path}: Arabic copy, lang, no Hebrew, axe clean`, async ({ page }) => {
      await open(page, route);
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
      expect(await hebrewIn(page, route)).toEqual([]);
      // The page title follows the locale too (not-found has none of its own).
      if (route.path !== "/no-such-page") {
        await expect.poll(() => page.title()).not.toMatch(HEBREW);
        await expect.poll(() => page.title()).toContain("SmartCart");
      }
      expect(await page.locator("body").innerText()).not.toMatch(EASTERN_DIGITS);

      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      const blocking = results.violations.filter((v) =>
        ["serious", "critical"].includes(v.impact ?? ""),
      );
      expect(
        blocking.map((v) => ({
          id: v.id,
          targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
        })),
      ).toEqual([]);
    });

    for (const width of [390, 195]) {
      test(`${route.path}: no horizontal scroll at ${width} px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 844 });
        await open(page, route);
        const { scroll, client } = await page.evaluate(() => ({
          scroll: document.documentElement.scrollWidth,
          client: document.documentElement.clientWidth,
        }));
        expect(client).toBe(width);
        expect(scroll).toBeLessThanOrEqual(client);
      });
    }
  }
});

test.describe("Arabic copy, sampled", () => {
  test("shell: top bar, bottom bar, skip link and the theme switch", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await open(page, ROUTES[0]!);
    const nav = page.getByTestId("bottom-nav");
    await expect(nav.getByRole("link", { name: "القوائم" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "مسح الباركود" })).toBeVisible();
    await expect(page.getByRole("switch", { name: "الوضع الداكن" })).toBeVisible();
    await expect(page.getByRole("link", { name: "تخطي إلى المحتوى" })).toHaveCount(1);
  });

  test("onboarding: steps, why-we-ask, chains in Latin letters, buttons", async ({ page }) => {
    await open(page, ROUTES[3]!);
    await expect(page.getByTestId("step-count")).toContainText("الخطوة 1 من 3");
    await expect(page.getByLabel("لماذا نسأل")).toBeVisible();
    await expect(page.getByRole("button", { name: "السماح باستخدام موقع الجهاز" })).toBeVisible();
    await expect(page.getByRole("slider", { name: "نطاق البحث" })).toBeVisible();
    await page.getByTestId("onboarding-next").click();
    await expect(page.getByTestId("step-count")).toContainText("الخطوة 2 من 3");
    await page.getByRole("button", { name: "سوبرماركتي: Shufersal" }).click();
    await expect(page.getByRole("button", { name: "سوبرماركتي: Shufersal" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.getByRole("button", { name: "نادي Rami Levy" })).toBeVisible();
    await page.getByTestId("onboarding-next").click();
    await expect(page.getByRole("radiogroup", { name: "وسيلة التنقل" })).toBeVisible();
    await expect(page.getByTestId("onboarding-next")).toHaveText("إنهاء");
  });

  test("profile: sections, localized city, Latin digits, theme control, delete sheet", async ({
    page,
  }) => {
    await open(page, ROUTES[4]!);
    await expect(page.getByRole("heading", { name: "نمط الألوان" })).toBeVisible();
    await expect(page.getByRole("radiogroup", { name: "نمط الألوان" })).toBeVisible();
    await expect(page.getByTestId("location-summary")).toContainText("موديعين-مكابيم-رعوت");
    await expect(page.getByTestId("savings-total")).toContainText("31.40");
    await expect(page.getByText("1/10")).toBeVisible();
    await expect(page.getByTestId("flex-defaults")).toContainText("الألبان والبيض");
    await page.getByRole("button", { name: "حذف بياناتي" }).click();
    const dialog = page.getByRole("dialog", { name: "حذف جميع بياناتي؟" });
    await expect(dialog).toBeVisible();
    expect(await dialog.innerText()).not.toMatch(HEBREW);
    await expect(dialog.getByRole("button", { name: "إغلاق" })).toBeVisible();
  });

  test("sign-in sheet", async ({ page }) => {
    await open(page, ROUTES[4]!);
    await page.getByRole("button", { name: "تسجيل الدخول بالبريد الإلكتروني" }).click();
    const dialog = page.getByRole("dialog", { name: "تسجيل الدخول" });
    await expect(dialog).toBeVisible();
    expect(await dialog.innerText()).not.toMatch(HEBREW);
  });

  test("manifest follows the locale cookie", async ({ page }) => {
    const res = await page.request.get("/manifest.webmanifest");
    expect(res.ok()).toBe(true);
    expect(await res.json()).toMatchObject({
      name: "SmartCart",
      short_name: "SmartCart",
      lang: "ar",
      dir: "rtl",
    });
  });

  test("Hebrew is still the default without the cookie", async ({ page, context }) => {
    await context.clearCookies();
    await mockApi(page);
    await page.goto("/offline");
    await expect(page.locator("html")).toHaveAttribute("lang", "he");
    await expect(page.getByRole("heading", { level: 1, name: "אין חיבור לאינטרנט" })).toBeVisible();
    const res = await page.request.get("/manifest.webmanifest");
    expect(await res.json()).toMatchObject({ short_name: "סמארטקארט", lang: "he" });
  });
});
