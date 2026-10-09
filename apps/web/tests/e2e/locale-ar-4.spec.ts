import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { resetMeMock } from "../../src/mocks/handlers";
import { resetPhase2Mock } from "../../src/mocks/handlers.phase2";
import { resetBetaMock } from "../../src/mocks/handlers.beta";
import { noHorizontalScroll, seedComparison } from "./secondary.helpers";

/**
 * Arabic UI, fourth batch (#73): the list, comparison, split, store mode, alerts, the budget in
 * Profile, the privacy page, the accessibility statement and the beta pages. With the
 * `sc-locale=ar` cookie every route shows Arabic for the migrated strings, has `<html lang="ar">`,
 * shows no Hebrew letter outside the runs marked `lang="he"` (data that exists only in Hebrew:
 * the chain's own item names), passes axe in the light and the dark theme, and does not scroll
 * sideways at 390 px or at 195 px (200% zoom). The legal texts carry the "translation, the Hebrew
 * governs" line.
 */
const NOTE = "هذه ترجمة، والنص العبري هو الملزم";

type Case = {
  path: string;
  expects: Array<{ role: "heading" | "link" | "button"; name: string; level?: number }>;
  legal?: boolean;
};

const CASES: Case[] = [
  {
    path: "/",
    expects: [
      { role: "heading", name: "التسوّق الأسبوعي" },
      { role: "button", name: "من وصفة" },
      { role: "link", name: "مشاركة" },
    ],
  },
  {
    path: "/compare",
    expects: [
      { role: "heading", name: "أين الأرخص هذا الأسبوع؟" },
      { role: "button", name: "الإبلاغ عن فرق في السعر" },
    ],
  },
  {
    path: "/split",
    expects: [
      { role: "heading", level: 1, name: "تقسيم السلة" },
      { role: "heading", name: "من أين يأتي التوفير" },
    ],
  },
  {
    path: "/store-mode?store=101",
    expects: [
      { role: "heading", name: "وضع المتجر" },
      { role: "button", name: "انتهيت من التسوق" },
    ],
  },
  {
    path: "/alerts",
    expects: [
      { role: "heading", name: "التنبيهات" },
      { role: "heading", name: "التنبيهات في المتصفح" },
    ],
  },
  {
    path: "/profile",
    expects: [{ role: "heading", name: "الميزانية الشهرية" }],
  },
  {
    path: "/privacy",
    legal: true,
    expects: [
      { role: "heading", name: "سياسة الخصوصية" },
      { role: "heading", name: "ما الذي يُحفظ ولماذا" },
      { role: "heading", name: "صور الإيصالات والقوائم" },
    ],
  },
  {
    path: "/accessibility",
    legal: true,
    expects: [
      { role: "heading", name: "بيان إمكانية الوصول" },
      { role: "heading", name: "ما الذي فُحص" },
    ],
  },
  {
    path: "/beta",
    legal: true,
    expects: [{ role: "heading", name: "النسخة التجريبية من SmartCart" }],
  },
  {
    path: "/beta/join/BETA-KOSHER",
    legal: true,
    expects: [
      { role: "heading", name: "النسخة التجريبية من SmartCart" },
      { role: "heading", name: "ما الذي نقيسه" },
    ],
  },
];

/** Every route gets the weekly list and the shopper (harmless where it is not used). */
async function prepare(page: Page, baseURL: string | undefined, theme: string) {
  resetMeMock();
  resetPhase2Mock();
  resetBetaMock();
  await seedComparison(page);
  await page.context().addCookies([{ name: "sc-locale", value: "ar", url: baseURL ?? "" }]);
  await page.addInitScript((t) => {
    try {
      localStorage.setItem("sc-theme", t);
    } catch {
      // blocked storage: the data-theme assertion below fails loudly
    }
  }, theme);
  await page.emulateMedia({ colorScheme: theme as "light" | "dark" });
}

/** Hebrew letters in the page's main region, outside the runs marked `lang="he"`. */
async function hebrewOutsideData(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const main = document.querySelector("main") ?? document.body;
    const copy = main.cloneNode(true) as HTMLElement;
    for (const el of copy.querySelectorAll('[lang="he"], script, style')) el.remove();
    return (copy.textContent ?? "").match(/\S*[֐-׿]+\S*/g) ?? [];
  });
}

async function axeBlocking(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) }));
}

async function openAndCheck(page: Page, c: Case) {
  await page.goto(c.path);
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  for (const e of c.expects) {
    await expect(page.getByRole(e.role, { name: e.name, level: e.level }).first()).toBeVisible();
  }
  if (c.legal) await expect(page.getByTestId("legal-translation-note").first()).toHaveText(NOTE);
  await page.waitForLoadState("networkidle");
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`Arabic, ${theme} theme, 390 px`, () => {
    test.use({ viewport: { width: 390, height: 844 } });

    for (const c of CASES) {
      test(`${c.path}`, async ({ page, baseURL }) => {
        await prepare(page, baseURL, theme);
        await openAndCheck(page, c);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        expect(await hebrewOutsideData(page)).toEqual([]);
        await noHorizontalScroll(page);
        expect(await axeBlocking(page)).toEqual([]);
      });
    }
  });
}

test.describe("Arabic at 195 px (200% zoom)", () => {
  test.use({ viewport: { width: 195, height: 844 } });

  for (const c of CASES) {
    test(`${c.path}`, async ({ page, baseURL }) => {
      await prepare(page, baseURL, "light");
      await openAndCheck(page, c);
      await noHorizontalScroll(page);
    });
  }
});

test.describe("Arabic states behind a tap", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the comparison shows Latin chain names, Arabic product names and the Hebrew shelf name marked", async ({
    page,
    baseURL,
  }) => {
    await prepare(page, baseURL, "light");
    await page.goto("/compare");
    const plan = page.getByTestId("plan-single");
    await expect(plan).toContainText("موصى به");
    await expect(plan).toContainText("Shufersal Deal");
    const details = page.getByTestId("basket-details").first();
    await details.locator("summary").click();
    await expect(details).toContainText("حليب طازج 3%");
    // The chain's own item name stays Hebrew and says so.
    await expect(details.locator('[lang="he"]').first()).toBeVisible();
  });

  test("the flexibility sheet and the gap report in Arabic", async ({ page, baseURL }) => {
    await prepare(page, baseURL, "light");
    await page.goto("/");
    await page.getByTestId("list-row").first().getByRole("button").first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("مستوى المرونة للصنف");
    await expect(dialog).toContainText("يمكن التنازل عن");
    expect(await dialog.evaluate((el) => /[֐-׿]/.test(el.textContent ?? ""))).toBe(false);
  });

  test("the budget section in Profile in Arabic", async ({ page, baseURL }) => {
    await prepare(page, baseURL, "light");
    await page.goto("/profile");
    const section = page.getByTestId("budget-section");
    await expect(section).toContainText("الميزانية الشهرية");
    await expect(section).toContainText("لم تُحدَّد ميزانية");
    await page.getByLabel(/كم تريد أن تنفق على البقالة/).fill("2500");
    await page.getByRole("button", { name: "حفظ الميزانية" }).click();
    await expect(section).toContainText("تم حفظ الميزانية.");
    await noHorizontalScroll(page);
  });
});
