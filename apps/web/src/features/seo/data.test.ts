import { describe, expect, it } from "vitest";
import { sitemapEntries } from "./sitemap-entries";
import {
  categoryPages,
  childCategories,
  getBasketIndex,
  getCategories,
  getProduct,
  getProducts,
  getQuality,
  productPages,
  productsIn,
  publishedMonths,
} from "./data";

describe("generated SEO data (public/seo)", () => {
  it("has 50 to 200 static pages generated from the catalog", () => {
    const pages = categoryPages().length + productPages().length;
    expect(pages).toBeGreaterThanOrEqual(50);
    expect(pages).toBeLessThanOrEqual(200);
    expect(getCategories().page_count).toBe(categoryPages().length);
    expect(getProducts().page_count).toBe(productPages().length);
  });

  it("lists every MVP canonical in products.json, with a name, unit and the no-prices flag", () => {
    const { products, count } = getProducts();
    expect(products).toHaveLength(count);
    expect(count).toBeGreaterThanOrEqual(150);
    for (const p of products) {
      expect(p.name_he).toMatch(/[֐-׿]/);
      expect(["100g", "100ml", "unit", "kg"]).toContain(p.base_unit);
      expect(p.no_prices_yet).toBe(p.prices === null);
      expect(p.price_valid_from === null).toBe(p.no_prices_yet);
    }
  });

  it("uses clean ASCII slugs that are unique within each route", () => {
    for (const list of [categoryPages().map((c) => c.slug), productPages().map((p) => p.slug)]) {
      expect(new Set(list).size).toBe(list.length);
      for (const slug of list) expect(slug).toMatch(/^[a-z0-9]+(?:[-_][a-z0-9]+)*$/);
    }
  });

  it("finds products and categories by slug and groups products under categories", () => {
    expect(getProduct("milk-fresh-3")?.name_he).toBe("חלב טרי 3%");
    expect(getProduct("no-such-product")).toBeUndefined();
    const dairy = categoryPages().find((c) => c.slug === "dairy")!;
    const milk = categoryPages().find((c) => c.slug === "dairy-milk")!;
    expect(childCategories("dairy").map((c) => c.slug)).toContain("dairy-milk");
    expect(productsIn(milk).every((p) => p.path[1]?.slug === "dairy-milk")).toBe(true);
    expect(productsIn(dairy).length).toBe(dairy.canonical_count);
  });

  it("every product page belongs to a category page (internal linking)", () => {
    const slugs = new Set(categoryPages().map((c) => c.slug));
    for (const p of productPages()) {
      const parents = p.path.filter((n) => n.slug).map((n) => n.slug!);
      expect(parents.length).toBeGreaterThan(0);
      for (const s of parents) expect(slugs.has(s)).toBe(true);
    }
  });

  it("the basket index is the published 25-item definition and shows no draft month", () => {
    const index = getBasketIndex();
    expect(index.basket.item_count).toBe(25);
    expect(index.basket.items).toHaveLength(25);
    expect(publishedMonths({ ...index, months: [{ ...fakeMonth, status: "draft" }] })).toEqual([]);
    expect(publishedMonths({ ...index, months: [fakeMonth] })).toHaveLength(1);
  });

  it("quality.json says whether a measurement exists", () => {
    const q = getQuality();
    expect(typeof q.available).toBe("boolean");
    if (q.available) {
      expect(q.measured_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
      expect(Object.keys(q.precision).length).toBeGreaterThan(0);
      expect(typeof q.synthetic).toBe("boolean");
    }
  });
});

describe("sitemap", () => {
  it("lists the static pages and every generated page once, with absolute URLs", () => {
    const entries = sitemapEntries();
    const urls = entries.map((e) => e.url);
    expect(new Set(urls).size).toBe(urls.length);
    for (const u of urls) expect(u).toMatch(/^https?:\/\/[^/]+(\/|$)/);
    for (const path of ["/methodology", "/basket-index", "/accessibility"]) {
      expect(urls.some((u) => u.endsWith(path))).toBe(true);
    }
    const generated = categoryPages().length + productPages().length;
    expect(urls.filter((u) => /\/(c|p)\//.test(u))).toHaveLength(generated);
    expect(urls.length).toBeGreaterThanOrEqual(50);
  });
});

const fakeMonth = {
  month: "2026-10",
  basket_version: 1,
  computed_at: "2026-10-07T06:00:00Z",
  price_date: "2026-10-07T05:00:00Z",
  cheapest_chain_id: "a",
  spread_pct: 4.4,
  chains: [],
  status: "published" as const,
  reviewed_by: "reviewer",
};
