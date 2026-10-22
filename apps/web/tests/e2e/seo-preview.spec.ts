import { readFileSync } from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Category, Product } from "../../src/features/seo/types";

/**
 * The static SEO pages on real prices, in a browser (docs/seo.md, "SEO on real prices"). Runs only
 * from `scripts/unblock/seo_preview.py web --e2e`, after the export of a real day has been copied
 * over `public/seo` and built; in a normal `npm run e2e` it is skipped, because it reads whatever
 * the export holds instead of the committed snapshot.
 *
 * It picks the pages real data is most likely to break: the product with the most chains, the one
 * with the longest name, a weighed product, one with a withheld price, the category with the
 * most products, and the basket index. At 390 px each must have no horizontal scroll, no console
 * error, no serious or critical WCAG 2.0 AA violation, the checkout line, and a dated price.
 */
test.skip(!process.env.SEO_PREVIEW, "real-prices preview only (scripts/unblock/seo_preview.py)");

const SEO_DIR = path.join(process.cwd(), "public", "seo");
const read = <T>(name: string): T => JSON.parse(readFileSync(path.join(SEO_DIR, name), "utf-8"));

const products = read<{ products: Product[] }>("products.json").products.filter((p) => p.has_page);
const categories = read<{ categories: Category[] }>("categories.json").categories.filter(
  (c) => c.has_page,
);
const priced = products.filter((p) => p.prices && p.prices.length > 0);

function pick(): { label: string; path: string; priced: boolean }[] {
  const out: { label: string; path: string; priced: boolean }[] = [];
  const add = (label: string, p: Product | undefined) => {
    if (p && !out.some((o) => o.path === `/p/${p.slug}`)) {
      out.push({ label, path: `/p/${p.slug}`, priced: Boolean(p.prices?.length) });
    }
  };
  add(
    "most chains",
    [...priced].sort((a, b) => (b.prices?.length ?? 0) - (a.prices?.length ?? 0))[0],
  );
  add("longest name", [...products].sort((a, b) => b.name_he.length - a.name_he.length)[0]);
  add(
    "weighed",
    priced.find((p) => p.base_unit === "kg"),
  );
  add(
    "withheld price",
    products.find((p) => p.withheld && p.withheld.length > 0),
  );
  add(
    "unpriced",
    products.find((p) => !p.prices?.length),
  );
  const biggest = [...categories].sort((a, b) => b.canonical_count - a.canonical_count)[0];
  if (biggest) out.push({ label: "biggest category", path: `/c/${biggest.slug}`, priced: false });
  out.push({ label: "basket index", path: "/basket-index", priced: false });
  return out;
}

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

for (const target of pick()) {
  test(`${target.label}: ${target.path} at 390 px`, async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    page.on("pageerror", (e) => errors.push(e.message));
    const res = await page.goto(target.path);
    expect(res?.status()).toBe(200);
    await page.waitForLoadState("networkidle");

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, "horizontal scroll").toBeLessThanOrEqual(0);
    await expect(page.getByText("המחיר הקובע הוא בקופה").first()).toBeVisible();
    await expect(page.locator("time").first()).toHaveAttribute("datetime", /^\d{4}-\d{2}-\d{2}$/);
    if (target.priced) {
      const dated = await page.locator("table time").count();
      expect(dated, "an update date in every price row").toBeGreaterThan(0);
    }
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(/\bNaN\b|\bundefined\b|\bInfinity\b/);

    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    const blocking = result.violations.filter((v) => ["serious", "critical"].includes(v.impact!));
    expect(blocking.map((v) => `${v.id}: ${v.nodes.length} nodes`)).toEqual([]);
    expect(errors.filter((e) => !/favicon|service-worker|sw\.js/i.test(e))).toEqual([]);
  });
}
