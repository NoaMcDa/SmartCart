import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { resetMeMock } from "../../src/mocks/handlers";
import { resetPhase2Mock } from "../../src/mocks/handlers.phase2";
import { mockApi, pasteList, seedProfile } from "./core-helpers";

/**
 * Arabic UI, second batch (#73): scan, share, map, history, voice, recipe, substitution, product,
 * feedback and the static SEO pages. With the `sc-locale=ar` cookie every route shows Arabic for
 * the migrated strings, `<html lang="ar">`, passes axe and does not scroll sideways at 390 px and
 * at 195 px (200% zoom). The SEO pages' server HTML must stay Hebrew: that is what search engines
 * index (docs/seo.md); only the client switches.
 */
const MILK = "חלב טרי 3%, 1 ליטר";

type Case = {
  path: string;
  /** Text (migrated strings) that must show in Arabic. */
  expects: Array<{ role: "heading" | "link" | "button"; name: string | RegExp }>;
  seo?: boolean;
};

const CASES: Case[] = [
  {
    path: "/scan",
    expects: [
      { role: "heading", name: "مسح الباركود" },
      { role: "heading", name: "المسح بالكاميرا" },
      { role: "button", name: "تشغيل الكاميرا" },
    ],
  },
  {
    path: "/lists/accept/inv-1-abc",
    expects: [
      { role: "heading", name: "الانضمام إلى قائمة مشتركة" },
      { role: "heading", name: "تمت دعوتك إلى قائمة تسوّق مشتركة" },
    ],
  },
  {
    path: "/lists/1/share",
    expects: [{ role: "heading", name: "مشاركة القائمة" }],
  },
  { path: "/map", expects: [{ role: "heading", name: "خريطة الفروع" }] },
  {
    path: `/product/1001?name=${encodeURIComponent(MILK)}`,
    expects: [
      { role: "heading", name: "الأنواع حسب السعر للوحدة" },
      { role: "heading", name: "السعر في كل فرع" },
      { role: "heading", name: "سجل الأسعار" },
    ],
  },
  {
    path: "/compare/substitution/42",
    expects: [{ role: "heading", name: "لم نجد هذا الاستبدال" }],
  },
  { path: "/alerts", expects: [{ role: "heading", name: "التنبيهات" }] },
  {
    path: "/methodology",
    seo: true,
    expects: [
      { role: "heading", name: "كيف نقارن الأسعار" },
      { role: "heading", name: "من أين تأتي الأسعار" },
      { role: "heading", name: "مؤشر جودة المطابقة" },
    ],
  },
  {
    path: "/c/dairy-milk",
    seo: true,
    expects: [{ role: "link", name: "ابنِ قائمة تسوّق" }],
  },
  {
    path: "/p/milk-fresh-3",
    seo: true,
    expects: [
      { role: "heading", name: "الأسعار حسب السلسلة" },
      { role: "heading", name: "ما الذي يُعتبر المنتج نفسه" },
    ],
  },
  {
    path: "/basket-index",
    seo: true,
    expects: [
      { role: "heading", name: "مؤشر السلة الشهري" },
      { role: "heading", name: "السلة الثابتة" },
    ],
  },
];

async function prepare(page: Page) {
  resetMeMock();
  resetPhase2Mock();
  await mockApi(page);
  await seedProfile(page);
}

async function setArabic(page: Page, baseURL: string | undefined) {
  await page.context().addCookies([{ name: "sc-locale", value: "ar", url: baseURL ?? "" }]);
}

async function arabic(page: Page, baseURL: string | undefined) {
  await prepare(page);
  await setArabic(page, baseURL);
}

async function noSidewaysScroll(page: Page) {
  const w = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(w.scroll, "document scrollWidth").toBeLessThanOrEqual(w.client);
  expect(w.body, "body scrollWidth").toBeLessThanOrEqual(w.client);
}

for (const width of [390, 195]) {
  test.describe(`Arabic at ${width} px`, () => {
    test.use({ viewport: { width, height: 844 } });

    for (const c of CASES) {
      test(`${c.path}`, async ({ page, baseURL }) => {
        await arabic(page, baseURL);
        await page.goto(c.path);
        await expect(page.locator("html")).toHaveAttribute("lang", "ar");
        await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
        for (const e of c.expects) {
          await expect(page.getByRole(e.role, { name: e.name }).first()).toBeVisible();
        }
        await page.waitForLoadState("networkidle");
        await noSidewaysScroll(page);
        if (width === 390) {
          const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
          const blocking = results.violations.filter(
            (v) => v.impact === "serious" || v.impact === "critical",
          );
          expect(
            blocking.map((v) => ({
              id: v.id,
              targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")),
            })),
          ).toEqual([]);
        }
      });
    }
  });
}

test.describe("Arabic states behind a tap", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("scan result and not-found", async ({ page, baseURL }) => {
    await arabic(page, baseURL);
    await page.goto("/scan");
    const input = page.getByRole("textbox", { name: /الباركود \(13 رقمًا/ });
    await input.fill("5901234123457");
    await page.getByRole("button", { name: "بحث" }).click();
    await expect(page.getByTestId("scan-result")).toBeVisible();
    await expect(page.getByText("هنا", { exact: true }).first()).toBeVisible();
    await expect(page.getByTestId("scan-cheapest")).toContainText("الأرخص في المنطقة");
    await expect(page.getByLabel(/السعر الذي رأيته على الرف/)).toBeVisible();
    await noSidewaysScroll(page);
    await input.fill("5901234000000");
    await page.getByRole("button", { name: "بحث" }).click();
    await expect(page.getByTestId("scan-notfound")).toContainText("لم نجد هذا الباركود");
    // A wrong check digit shows the Arabic error, not Hebrew.
    await input.fill("5901234123458");
    await page.getByRole("button", { name: "بحث" }).click();
    await expect(page.getByText("هذه الأرقام لا تشكّل باركودًا صحيحًا")).toBeVisible();
  });

  test("the gap report sheet and the price history on a product", async ({ page, baseURL }) => {
    await arabic(page, baseURL);
    await page.goto(`/product/1001?name=${encodeURIComponent(MILK)}`);
    await expect(page.getByTestId("price-history")).toBeVisible();
    await expect(page.getByTestId("history-chart")).toBeVisible();
    await expect(page.getByTestId("price-history").getByText("30 يومًا")).toBeVisible();
    await page.getByRole("button", { name: /إبلاغ/ }).first().click();
    await expect(page.getByRole("dialog")).toContainText("الإبلاغ عن فرق");
    await expect(page.getByRole("dialog")).toContainText("ما الذي لا يتطابق؟");
  });

  test("the shared list and its share sheet", async ({ page, baseURL }) => {
    await prepare(page);
    // The list is made in Hebrew (the list builder is not part of this batch), then shared in Arabic.
    await page.goto("/");
    await pasteList(page, "חלב, 2 רסק עגבניות");
    await setArabic(page, baseURL);
    await page.goto("/lists/mine/share");
    await expect(page.getByRole("heading", { name: "مشاركة قائمتك" })).toBeVisible();
    await page.getByRole("button", { name: "إنشاء قائمة مشتركة" }).click();
    await expect(page).toHaveURL(/\/lists\/1\/share$/);
    await expect(page.getByRole("heading", { name: /الأصناف في القائمة/ })).toBeVisible();
    await expect(page.getByTestId("sync-state")).toContainText(/يتحدّث/);
    await noSidewaysScroll(page);
    await page.getByRole("button", { name: "دعوة أفراد العائلة" }).click();
    await expect(page.getByRole("dialog")).toContainText("مشاركة القائمة");
    await expect(page.getByRole("button", { name: /إنشاء رابط دعوة|تسجيل الدخول/ })).toBeVisible();
  });
});

test.describe("SEO pages stay Hebrew in the server HTML", () => {
  const SERVER: Array<{ path: string; hebrew: string; arabic: string }> = [
    { path: "/methodology", hebrew: "איך אנחנו משווים מחירים", arabic: "كيف نقارن الأسعار" },
    { path: "/c/dairy-milk", hebrew: "חלב ומשקאות חלב", arabic: "بناء قائمة" },
    { path: "/p/milk-fresh-3", hebrew: "מחירים לפי רשת", arabic: "الأسعار حسب السلسلة" },
    { path: "/basket-index", hebrew: "מדד הסל החודשי", arabic: "مؤشر السلة الشهري" },
  ];
  for (const s of SERVER) {
    test(`${s.path}: Hebrew markup for crawlers, even with the Arabic cookie`, async ({
      request,
      baseURL,
    }) => {
      const res = await request.get(s.path, {
        headers: { cookie: "sc-locale=ar", "user-agent": "Googlebot" },
      });
      expect(res.status()).toBe(200);
      const html = await res.text();
      expect(html).toContain('lang="he"');
      expect(html).toContain(s.hebrew);
      expect(html).not.toContain(s.arabic);
      expect(baseURL).toBeTruthy();
    });
  }
});
