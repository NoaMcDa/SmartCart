import { afterEach, describe, expect, it, vi } from "vitest";
import type { Product } from "@/features/seo/types";

/**
 * Build-time SEO configuration (#35): NEXT_PUBLIC_INDEX_UNPRICED decides whether product pages
 * with no prices are indexed (page meta robots, sitemap), and the opt-in SEO_STRICT_SITE_URL
 * check refuses a production build that would publish canonical URLs on the placeholder domain.
 * The constants are read when `config.ts` loads, so each case resets the module registry.
 */

vi.setConfig({ testTimeout: 30_000 });

const PRICED_AT = "2026-10-07T05:00:00Z";

/** Every other product page priced, so both sides of the flag are present. */
function mixedPrices(p: Product, index: number): Product {
  if (index % 2 === 1) return p;
  return {
    ...p,
    no_prices_yet: false,
    price_valid_from: PRICED_AT,
    prices: [
      {
        chain_id: "a",
        chain_name: "רמי לוי",
        min_unit_price: 0.4,
        median_unit_price: 0.5,
        stores: 5,
        is_estimated: false,
        price_valid_from: PRICED_AT,
      },
    ],
  };
}

const ENV_KEYS = [
  "NODE_ENV",
  "NEXT_PUBLIC_INDEX_UNPRICED",
  "NEXT_PUBLIC_SITE_URL",
  "SEO_STRICT_SITE_URL",
  "SEO_ALLOW_PLACEHOLDER",
] as const;

type Env = Partial<Record<(typeof ENV_KEYS)[number], string>>;

async function load(env: Env = {}) {
  vi.resetModules();
  vi.unstubAllEnvs();
  for (const key of ENV_KEYS) {
    if (key === "NODE_ENV") vi.stubEnv(key, env[key] ?? "test");
    else vi.stubEnv(key, env[key]);
  }
  vi.doMock("@/features/seo/data", async (importOriginal) => {
    const orig = await importOriginal<typeof import("@/features/seo/data")>();
    const products = () => {
      const file = orig.getProducts();
      let n = 0;
      return {
        ...file,
        products: file.products.map((p) => (p.has_page ? mixedPrices(p, n++) : p)),
      };
    };
    return {
      ...orig,
      getProducts: products,
      productPages: () => products().products.filter((p) => p.has_page),
      getProduct: (slug: string) =>
        products()
          .products.filter((p) => p.has_page)
          .find((p) => p.slug === slug),
    };
  });
  const config = await import("@/features/seo/config");
  const sitemap = await import("@/features/seo/sitemap-entries");
  const data = await import("@/features/seo/data");
  const product = await import("@/app/(seo)/p/[slug]/page");
  const robots = await import("@/app/(seo)/robots.txt/route");
  const sitemapRoute = await import("@/app/(seo)/sitemap");
  return { config, sitemap, data, product, robots, sitemapRoute };
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.doUnmock("@/features/seo/data");
  vi.resetModules();
});

describe("parseIndexUnpriced", () => {
  it("defaults to true and only an explicit off value turns it off", async () => {
    const { parseIndexUnpriced: parse } = (await load()).config;
    expect(parse(undefined)).toBe(true);
    expect(parse("")).toBe(true);
    expect(parse("1")).toBe(true);
    expect(parse("true")).toBe(true);
    expect(parse("0")).toBe(false);
    expect(parse(" 0 ")).toBe(false);
    expect(parse("false")).toBe(false);
    expect(parse("OFF")).toBe(false);
  });
});

describe.each([
  ["unset (default)", undefined, true],
  ["1", "1", true],
  ["0", "0", false],
] as const)("NEXT_PUBLIC_INDEX_UNPRICED=%s", (_label, value, indexUnpriced) => {
  const env: Env = value === undefined ? {} : { NEXT_PUBLIC_INDEX_UNPRICED: value };

  it("sets the flag", async () => {
    expect((await load(env)).config.INDEX_UNPRICED).toBe(indexUnpriced);
  });

  it("decides which product pages the sitemap lists", async () => {
    const { sitemap, data } = await load(env);
    const pages = data.productPages();
    const priced = pages.filter((p) => !p.no_prices_yet);
    const unpriced = pages.filter((p) => p.no_prices_yet);
    expect(priced.length).toBeGreaterThan(0);
    expect(unpriced.length).toBeGreaterThan(0);
    const urls = sitemap.sitemapEntries().map((e) => e.url);
    for (const p of priced) expect(urls.some((u) => u.endsWith(`/p/${p.slug}`))).toBe(true);
    for (const p of unpriced) {
      expect(urls.some((u) => u.endsWith(`/p/${p.slug}`))).toBe(indexUnpriced);
    }
    // Category and static pages are not affected.
    expect(urls.filter((u) => /\/c\//.test(u)).length).toBe(data.categoryPages().length);
    for (const path of ["/methodology", "/basket-index", "/accessibility"]) {
      expect(urls.some((u) => u.endsWith(path))).toBe(true);
    }
  });

  it("serves the same list from /sitemap.xml", async () => {
    const { sitemap, sitemapRoute } = await load(env);
    expect(sitemapRoute.default()).toEqual(sitemap.sitemapEntries());
  });

  it("sends noindex, follow exactly for the pages the sitemap leaves out", async () => {
    const { sitemap, data, product } = await load(env);
    const urls = sitemap.sitemapEntries().map((e) => e.url);
    for (const p of data.productPages()) {
      const meta = await product.generateMetadata({ params: Promise.resolve({ slug: p.slug }) });
      const listed = urls.some((u) => u.endsWith(`/p/${p.slug}`));
      expect(listed, p.slug).toBe(meta.robots === undefined);
      if (p.no_prices_yet && !indexUnpriced) {
        expect(meta.robots).toEqual({ index: false, follow: true });
      } else {
        expect(meta.robots).toBeUndefined();
      }
    }
  });

  it("keeps robots.txt crawlable for product pages so a crawler can read the noindex", async () => {
    const { robots } = await load(env);
    const text = await robots.GET().text();
    expect(text).toContain("Allow: /");
    expect(text).not.toMatch(/Disallow: \/(p|c)(\/|$)/);
    expect(text).toMatch(/Sitemap: https?:\/\/\S+\/sitemap\.xml/);
  });
});

describe("site URL", () => {
  it("falls back to the placeholder when unset or empty, and drops trailing slashes", async () => {
    expect((await load()).config.SITE_URL).toBe("https://smartcart.example");
    expect((await load({ NEXT_PUBLIC_SITE_URL: "" })).config.SITE_URL).toBe(
      "https://smartcart.example",
    );
    expect((await load({ NEXT_PUBLIC_SITE_URL: "https://www.shop.co.il//" })).config.SITE_URL).toBe(
      "https://www.shop.co.il",
    );
  });

  it("canonical URLs, robots.txt and the sitemap use the configured origin", async () => {
    const { config, sitemap, robots } = await load({
      NEXT_PUBLIC_SITE_URL: "https://www.shop.co.il",
    });
    expect(config.absoluteUrl("/p/milk")).toBe("https://www.shop.co.il/p/milk");
    expect(await robots.GET().text()).toContain("Sitemap: https://www.shop.co.il/sitemap.xml");
    for (const e of sitemap.sitemapEntries()) expect(e.url).toMatch(/^https:\/\/www\.shop\.co\.il/);
  });
});

describe("assertSiteUrl (SEO_STRICT_SITE_URL)", () => {
  const strict = { NODE_ENV: "production", SEO_STRICT_SITE_URL: "1" };

  it("does nothing unless it is a production build with the strict flag", async () => {
    const { assertSiteUrl } = (await load()).config;
    expect(() => assertSiteUrl({ NODE_ENV: "production" })).not.toThrow();
    expect(() =>
      assertSiteUrl({ NODE_ENV: "development", SEO_STRICT_SITE_URL: "1" }),
    ).not.toThrow();
    expect(() => assertSiteUrl({ NODE_ENV: "test", SEO_STRICT_SITE_URL: "1" })).not.toThrow();
    expect(() => assertSiteUrl({ ...strict, SEO_STRICT_SITE_URL: "0" })).not.toThrow();
  });

  it("fails with a message that says what to set when the URL is unset or empty", async () => {
    const { assertSiteUrl } = (await load()).config;
    expect(() => assertSiteUrl(strict)).toThrow(/NEXT_PUBLIC_SITE_URL is not set/);
    expect(() => assertSiteUrl({ ...strict, NEXT_PUBLIC_SITE_URL: "  " })).toThrow(/is not set/);
    expect(() => assertSiteUrl(strict)).toThrow(/SEO_ALLOW_PLACEHOLDER=1/);
  });

  it("fails on the placeholder, on http and on a value that is not a URL", async () => {
    const { assertSiteUrl } = (await load()).config;
    const placeholder = "https://smartcart.example";
    expect(() => assertSiteUrl({ ...strict, NEXT_PUBLIC_SITE_URL: placeholder })).toThrow(
      /still the placeholder/,
    );
    expect(() => assertSiteUrl({ ...strict, NEXT_PUBLIC_SITE_URL: `${placeholder}/` })).toThrow(
      /still the placeholder/,
    );
    expect(() =>
      assertSiteUrl({ ...strict, NEXT_PUBLIC_SITE_URL: "http://www.shop.co.il" }),
    ).toThrow(/must be an https URL/);
    expect(() => assertSiteUrl({ ...strict, NEXT_PUBLIC_SITE_URL: "www.shop.co.il" })).toThrow(
      /not an absolute URL/,
    );
  });

  it("accepts a real https origin, and SEO_ALLOW_PLACEHOLDER=1 switches the check off", async () => {
    const { assertSiteUrl } = (await load()).config;
    expect(() =>
      assertSiteUrl({ ...strict, NEXT_PUBLIC_SITE_URL: "https://www.shop.co.il" }),
    ).not.toThrow();
    expect(() =>
      assertSiteUrl({ ...strict, NEXT_PUBLIC_SITE_URL: "https://www.shop.co.il/he/" }),
    ).not.toThrow();
    expect(() => assertSiteUrl({ ...strict, SEO_ALLOW_PLACEHOLDER: "1" })).not.toThrow();
    expect(() =>
      assertSiteUrl({
        ...strict,
        SEO_ALLOW_PLACEHOLDER: "1",
        NEXT_PUBLIC_SITE_URL: "https://smartcart.example",
      }),
    ).not.toThrow();
  });

  it("makes loading the config fail in a strict production build, and pass with a real URL", async () => {
    await expect(load({ NODE_ENV: "production", SEO_STRICT_SITE_URL: "1" })).rejects.toThrow(
      /NEXT_PUBLIC_SITE_URL is not set/,
    );
    await expect(
      load({
        NODE_ENV: "production",
        SEO_STRICT_SITE_URL: "1",
        NEXT_PUBLIC_SITE_URL: "https://smartcart.example",
      }),
    ).rejects.toThrow(/placeholder/);
    const ok = await load({
      NODE_ENV: "production",
      SEO_STRICT_SITE_URL: "1",
      NEXT_PUBLIC_SITE_URL: "https://www.shop.co.il",
    });
    expect(ok.config.SITE_URL).toBe("https://www.shop.co.il");
    const allowed = await load({
      NODE_ENV: "production",
      SEO_STRICT_SITE_URL: "1",
      SEO_ALLOW_PLACEHOLDER: "1",
    });
    expect(allowed.config.SITE_URL).toBe("https://smartcart.example");
  });
});
