import { cleanup, render } from "@testing-library/react";
import { createElement, type ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AccessibilityPage from "@/app/(seo)/accessibility/page";
import BasketIndexPage from "@/app/(seo)/basket-index/page";
import CategoryPage, { generateMetadata as categoryMetadata } from "@/app/(seo)/c/[slug]/page";
import MethodologyPage from "@/app/(seo)/methodology/page";
import ProductPage, { generateMetadata as productMetadata } from "@/app/(seo)/p/[slug]/page";
import { SITE_URL } from "@/features/seo/config";
import { categoryPages, productPages } from "@/features/seo/data";
import { isoDate } from "@/features/seo/format";
import type { BaseUnit, BasketIndexFile, Product } from "@/features/seo/types";

/**
 * Offline structured-data validation (#35). Builds the JSON-LD of every generated SEO page by
 * rendering the real page components (not by calling the builders again), then checks it against
 * hand-written schema.org shape rules for the types the site uses. It replaces the external
 * validator in CI: Google's Rich Results Test is still a one-time manual check after deploy
 * (docs/seo.md). Priced pages and a published basket month do not exist in the committed snapshot
 * yet, so a second pass runs every page with synthetic prices and a published month.
 */

// Rendering ~200 pages per pass takes several seconds on a slow runner.
vi.setConfig({ testTimeout: 60_000 });

const mode = vi.hoisted(() => ({ priced: false, month: false }));

const PRICED_AT = "2026-10-07T05:00:00Z";

function withPrices(p: Product): Product {
  return {
    ...p,
    no_prices_yet: false,
    price_valid_from: PRICED_AT,
    prices: ["a", "b"].map((id, i) => ({
      chain_id: id,
      chain_name: id === "a" ? "רמי לוי" : "שופרסל",
      min_unit_price: 0.4 + i * 0.1,
      median_unit_price: 0.5 + i * 0.1,
      stores: 12,
      is_estimated: p.base_unit === "kg",
      price_valid_from: PRICED_AT,
    })),
  };
}

vi.mock("@/features/seo/data", async (importOriginal) => {
  const orig = await importOriginal<typeof import("@/features/seo/data")>();
  const products = () => {
    const file = orig.getProducts();
    return mode.priced ? { ...file, products: file.products.map(withPrices) } : file;
  };
  const basket = (): BasketIndexFile => {
    const file = orig.getBasketIndex();
    if (!mode.month) return file;
    const row = (id: string, name: string, total: number, delta: number) => ({
      chain_id: id,
      name,
      total,
      delta_vs_cheapest: delta,
      delta_pct: delta === 0 ? 0 : 4.4,
      items_priced: file.basket.item_count,
      estimated_items: 0,
      stores: 10,
      complete: true,
      missing: [],
    });
    return {
      ...file,
      months: [
        {
          month: "2026-10",
          basket_version: file.basket.version,
          computed_at: PRICED_AT,
          price_date: PRICED_AT,
          cheapest_chain_id: "a",
          spread_pct: 4.4,
          chains: [row("a", "רמי לוי", 400, 0), row("b", "שופרסל", 418, 18)],
          status: "published",
          reviewed_by: "reviewer",
        },
      ],
    };
  };
  return {
    ...orig,
    getProducts: products,
    getBasketIndex: basket,
    productPages: () => products().products.filter((p) => p.has_page),
    getProduct: (slug: string) =>
      products()
        .products.filter((p) => p.has_page)
        .find((p) => p.slug === slug),
    productsIn: (category: { level: 1 | 2; slug: string }) =>
      products().products.filter((p) => p.path[category.level - 1]?.slug === category.slug),
    publishedMonths: (index: BasketIndexFile = basket()) =>
      index.months.filter((m) => m.status === "published"),
  };
});

afterEach(() => {
  cleanup();
  mode.priced = false;
  mode.month = false;
});

// ---------------------------------------------------------------- the validator

type Json = Record<string, unknown>;
type Problems = string[];

const ORIGIN = new URL(SITE_URL).origin;
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2}))?$/;
/** UN/CEFACT common codes the site quotes unit prices in: grams, millilitres, units, kilograms. */
const UNIT_CODES = new Set(["GRM", "MLT", "C62", "KGM"]);

const isObject = (v: unknown): v is Json =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isText = (v: unknown): v is string => typeof v === "string" && v.trim() !== "";

function isIsoDate(v: unknown): boolean {
  if (typeof v !== "string") return false;
  const m = ISO_DATE.exec(v);
  if (!m) return false;
  const [, y, mo, d] = m;
  const date = new Date(Date.UTC(Number(y), Number(mo) - 1, Number(d)));
  return (
    date.getUTCFullYear() === Number(y) &&
    date.getUTCMonth() === Number(mo) - 1 &&
    date.getUTCDate() === Number(d) &&
    !Number.isNaN(Date.parse(v))
  );
}

/** Absolute, http(s), and on the site's own origin. */
function isSiteUrl(v: unknown): boolean {
  if (typeof v !== "string") return false;
  try {
    return new URL(v).origin === ORIGIN && /^https?:\/\//.test(v);
  } catch {
    return false;
  }
}

function need(node: Json, key: string, ok: (v: unknown) => boolean, where: string, out: Problems) {
  if (!(key in node)) out.push(`${where}: missing "${key}"`);
  else if (!ok(node[key])) out.push(`${where}: invalid "${key}" (${JSON.stringify(node[key])})`);
}

function typeOf(node: unknown): string {
  return isObject(node) && typeof node["@type"] === "string" ? node["@type"] : "";
}

function priceFields(n: Json, where: string, out: Problems) {
  need(n, "price", (v) => typeof v === "number" && Number.isFinite(v) && v > 0, where, out);
  need(n, "priceCurrency", (v) => v === "ILS", where, out);
}

const validators: Record<string, (n: Json, where: string, out: Problems) => void> = {
  ListItem(n, where, out) {
    need(n, "position", (v) => Number.isInteger(v) && (v as number) >= 1, where, out);
    need(n, "name", isText, where, out);
    if ("item" in n) need(n, "item", isSiteUrl, where, out);
    if ("url" in n) need(n, "url", isSiteUrl, where, out);
  },
  BreadcrumbList(n, where, out) {
    const list = n.itemListElement;
    if (!Array.isArray(list) || list.length === 0) {
      out.push(`${where}: itemListElement must be a non-empty array`);
      return;
    }
    list.forEach((item, i) => {
      if (typeOf(item) !== "ListItem") {
        out.push(`${where}[${i}]: not a ListItem`);
        return;
      }
      const li = item as Json;
      validators.ListItem!(li, `${where}[${i}]`, out);
      if (li.position !== i + 1) out.push(`${where}[${i}]: position must be ${i + 1}`);
      // A breadcrumb step is a link: Google needs "item" on every step but the last; we give all.
      need(li, "item", isSiteUrl, `${where}[${i}]`, out);
    });
  },
  ItemList(n, where, out) {
    const list = n.itemListElement;
    if (!Array.isArray(list)) {
      out.push(`${where}: itemListElement must be an array`);
      return;
    }
    need(n, "numberOfItems", (v) => v === list.length, where, out);
    list.forEach((item, i) => {
      if (typeOf(item) !== "ListItem") {
        out.push(`${where}[${i}]: not a ListItem`);
        return;
      }
      validators.ListItem!(item as Json, `${where}[${i}]`, out);
      if ((item as Json).position !== i + 1) out.push(`${where}[${i}]: position must be ${i + 1}`);
    });
  },
  CollectionPage(n, where, out) {
    need(n, "name", isText, where, out);
    need(n, "url", isSiteUrl, where, out);
    need(n, "inLanguage", (v) => v === "he", where, out);
    need(n, "mainEntity", (v) => typeOf(v) === "ItemList", where, out);
    if (isObject(n.mainEntity)) validate(n.mainEntity, `${where}.mainEntity`, out);
  },
  WebSite(n, where, out) {
    need(n, "name", isText, where, out);
    need(n, "url", isSiteUrl, where, out);
  },
  WebPage(n, where, out) {
    need(n, "name", isText, where, out);
    need(n, "description", isText, where, out);
    need(n, "url", isSiteUrl, where, out);
    need(n, "inLanguage", (v) => v === "he", where, out);
    need(n, "dateModified", isIsoDate, where, out);
    need(n, "isPartOf", (v) => typeOf(v) === "WebSite", where, out);
    if (isObject(n.isPartOf)) validate(n.isPartOf, `${where}.isPartOf`, out);
  },
  Dataset(n, where, out) {
    need(n, "name", isText, where, out);
    need(n, "description", isText, where, out);
    if ("url" in n) need(n, "url", isSiteUrl, where, out);
    if ("dateModified" in n) need(n, "dateModified", isIsoDate, where, out);
  },
  Organization(n, where, out) {
    need(n, "name", isText, where, out);
  },
  QuantitativeValue(n, where, out) {
    need(n, "value", (v) => typeof v === "number" && v > 0, where, out);
    need(n, "unitCode", (v) => typeof v === "string" && UNIT_CODES.has(v), where, out);
  },
  UnitPriceSpecification(n, where, out) {
    priceFields(n, where, out);
    need(n, "referenceQuantity", (v) => typeOf(v) === "QuantitativeValue", where, out);
    if (isObject(n.referenceQuantity)) {
      validate(n.referenceQuantity, `${where}.referenceQuantity`, out);
    }
    for (const key of ["validFrom", "validThrough"]) {
      if (key in n) need(n, key, isIsoDate, where, out);
    }
  },
  Offer(n, where, out) {
    priceFields(n, where, out);
    need(n, "seller", (v) => typeOf(v) === "Organization", where, out);
    if (isObject(n.seller)) validate(n.seller, `${where}.seller`, out);
    if ("priceSpecification" in n) {
      const spec = n.priceSpecification;
      if (!isObject(spec)) out.push(`${where}: priceSpecification must be an object`);
      else {
        validate(spec, `${where}.priceSpecification`, out);
        if (spec.price !== n.price) {
          out.push(`${where}: priceSpecification.price differs from price`);
        }
      }
    }
    for (const key of ["validFrom", "priceValidUntil"]) {
      if (key in n) need(n, key, isIsoDate, where, out);
    }
  },
  AggregateOffer(n, where, out) {
    need(n, "priceCurrency", (v) => v === "ILS", where, out);
    need(n, "lowPrice", (v) => typeof v === "number" && v > 0, where, out);
    need(n, "highPrice", (v) => typeof v === "number" && v > 0, where, out);
    if (
      typeof n.lowPrice === "number" &&
      typeof n.highPrice === "number" &&
      n.lowPrice > n.highPrice
    ) {
      out.push(`${where}: lowPrice is above highPrice`);
    }
    need(n, "offerCount", (v) => Number.isInteger(v) && (v as number) >= 1, where, out);
  },
  Product(n, where, out) {
    need(n, "name", isText, where, out);
    need(n, "description", isText, where, out);
    need(n, "url", isSiteUrl, where, out);
    need(n, "category", isText, where, out);
    need(n, "inLanguage", (v) => v === "he", where, out);
    if ("offers" in n) {
      const offers = Array.isArray(n.offers) ? n.offers : [n.offers];
      if (offers.length === 0) out.push(`${where}: offers is empty (omit it instead)`);
      offers.forEach((o, i) => {
        if (!["Offer", "AggregateOffer"].includes(typeOf(o))) {
          out.push(`${where}.offers[${i}]: not an Offer`);
        } else validate(o as Json, `${where}.offers[${i}]`, out);
      });
    }
  },
};

function validate(node: Json, where: string, out: Problems) {
  const type = typeOf(node);
  const check = validators[type];
  if (!check) out.push(`${where}: no validator for @type "${type}"`);
  else check(node, where, out);
}

/** Every node that carries a price, however deeply nested. */
function priceNodes(value: unknown, found: Json[] = []): Json[] {
  if (Array.isArray(value)) value.forEach((v) => priceNodes(v, found));
  else if (isObject(value)) {
    if ("price" in value || "lowPrice" in value || "highPrice" in value) found.push(value);
    Object.values(value).forEach((v) => priceNodes(v, found));
  }
  return found;
}

function currencies(value: unknown, found: unknown[] = []): unknown[] {
  if (Array.isArray(value)) value.forEach((v) => currencies(v, found));
  else if (isObject(value)) {
    for (const [k, v] of Object.entries(value)) {
      if (k === "priceCurrency") found.push(v);
      else currencies(v, found);
    }
  }
  return found;
}

/**
 * Validates the JSON-LD blocks of one rendered page. `visibleDates` are the `<time datetime>`
 * values the same page shows: a price is only allowed on a page that dates it.
 */
function validatePage(blocks: Json[], visibleDates: string[]): Problems {
  const out: Problems = [];
  blocks.forEach((block, i) => {
    const where = `block ${i} (${typeOf(block) || "no @type"})`;
    if (block["@context"] !== "https://schema.org") {
      out.push(`${where}: @context must be https://schema.org`);
    }
    validate(block, where, out);
  });
  for (const c of currencies(blocks)) {
    if (c !== "ILS") out.push(`currency ${JSON.stringify(c)} is not ILS`);
  }
  if (priceNodes(blocks).length > 0) {
    if (visibleDates.length === 0) out.push("prices without a visible update date on the page");
    for (const d of visibleDates) if (!isIsoDate(d)) out.push(`visible date ${d} is not ISO 8601`);
  }
  return out;
}

// ---------------------------------------------------------------- rendering helpers

function extract(container: Element): { blocks: Json[]; raw: string[] } {
  const raw = [...container.querySelectorAll('script[type="application/ld+json"]')].map(
    (s) => s.textContent ?? "",
  );
  const blocks = raw.flatMap((text) => {
    const parsed = JSON.parse(text) as Json | Json[];
    return Array.isArray(parsed) ? parsed : [parsed];
  });
  return { blocks, raw };
}

function renderAndCheck(element: ReactElement) {
  const { container, unmount } = render(element);
  const { blocks, raw } = extract(container);
  const dates = [...container.querySelectorAll("time[datetime]")].map((t) =>
    t.getAttribute("datetime")!,
  );
  const problems = validatePage(blocks, dates);
  unmount();
  return { blocks, raw, dates, problems };
}

const types = (blocks: Json[]) => blocks.map(typeOf);
const lastCrumb = (blocks: Json[]) =>
  (blocks.find((b) => typeOf(b) === "BreadcrumbList")?.itemListElement as Json[] | undefined)?.at(
    -1,
  )?.item;

// ---------------------------------------------------------------- the validator catches mistakes

describe("the hand-written validator", () => {
  const ok = (extra: Json = {}): Json => ({
    "@context": "https://schema.org",
    "@type": "Product",
    name: "חלב",
    description: "תיאור",
    url: `${ORIGIN}/p/milk`,
    category: "חלב",
    inLanguage: "he",
    ...extra,
  });
  const spec = (extra: Json = {}): Json => ({
    "@type": "UnitPriceSpecification",
    price: 0.5,
    priceCurrency: "ILS",
    referenceQuantity: { "@type": "QuantitativeValue", value: 100, unitCode: "MLT" },
    ...extra,
  });
  const offer = (extra: Json = {}): Json => ({
    "@type": "Offer",
    price: 0.5,
    priceCurrency: "ILS",
    seller: { "@type": "Organization", name: "רמי לוי" },
    priceSpecification: spec(),
    ...extra,
  });

  it("accepts a well-formed product with offers on a dated page", () => {
    expect(validatePage([ok({ offers: [offer()] })], [PRICED_AT])).toEqual([]);
  });

  const badUnit = spec({
    referenceQuantity: { "@type": "QuantitativeValue", value: 1, unitCode: "XYZ" },
  });

  it.each<[string, Json, string[], RegExp]>([
    ["a relative URL", ok({ url: "/p/milk" }), [], /invalid "url"/],
    ["another origin", ok({ url: "https://evil.example/p/milk" }), [], /invalid "url"/],
    ["a missing name", ok({ name: "" }), [], /invalid "name"/],
    ["a wrong currency", ok({ offers: [offer({ priceCurrency: "USD" })] }), [PRICED_AT], /not ILS/],
    ["a zero price", ok({ offers: [offer({ price: 0 })] }), [PRICED_AT], /invalid "price"/],
    ["a price as text", ok({ offers: [offer({ price: "0.5" })] }), [PRICED_AT], /invalid "price"/],
    [
      "an unknown unit code",
      ok({ offers: [offer({ priceSpecification: badUnit })] }),
      [PRICED_AT],
      /unitCode/,
    ],
    [
      "an offer without a seller",
      ok({ offers: [offer({ seller: undefined })] }),
      [PRICED_AT],
      /seller/,
    ],
    ["an empty offers list", ok({ offers: [] }), [], /offers is empty/],
    ["a price without a date", ok({ offers: [offer()] }), [], /without a visible update date/],
    [
      "a non-ISO date",
      ok({ offers: [offer({ validFrom: "07/10/2026" })] }),
      [PRICED_AT],
      /validFrom/,
    ],
    [
      "an impossible date",
      ok({ offers: [offer({ validFrom: "2026-02-31" })] }),
      [PRICED_AT],
      /validFrom/,
    ],
    [
      "an unknown type",
      { "@context": "https://schema.org", "@type": "Recipe", name: "x" },
      [],
      /no validator/,
    ],
    ["a wrong context", { ...ok(), "@context": "http://schema.org" }, [], /@context/],
  ])("rejects %s", (_name, node, dates, message) => {
    expect(validatePage([node], dates).join("\n")).toMatch(message);
  });

  it("checks BreadcrumbList order, ItemList counts, WebPage dates and AggregateOffer ranges", () => {
    const crumbs = (positions: number[]): Json => ({
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: positions.map((position) => ({
        "@type": "ListItem",
        position,
        name: "x",
        item: `${ORIGIN}/c/x`,
      })),
    });
    expect(validatePage([crumbs([1, 2])], [])).toEqual([]);
    expect(validatePage([crumbs([2, 1])], []).join()).toMatch(/position must be/);

    const list = (n: number): Json => ({
      "@context": "https://schema.org",
      "@type": "ItemList",
      numberOfItems: n,
      itemListElement: [{ "@type": "ListItem", position: 1, name: "x" }],
    });
    expect(validatePage([list(1)], [])).toEqual([]);
    expect(validatePage([list(2)], []).join()).toMatch(/numberOfItems/);

    const page = (dateModified: string): Json => ({
      "@context": "https://schema.org",
      "@type": "WebPage",
      name: "x",
      description: "y",
      url: `${ORIGIN}/x`,
      inLanguage: "he",
      dateModified,
      isPartOf: { "@type": "WebSite", name: "SmartCart", url: `${ORIGIN}/` },
    });
    expect(validatePage([page("2026-10-07T00:00:00+03:00")], [])).toEqual([]);
    expect(validatePage([page("2026-10-07")], [])).toEqual([]);
    expect(validatePage([page("yesterday")], []).join()).toMatch(/dateModified/);

    const aggregate = (low: number, high: number): Json =>
      ok({
        offers: {
          "@type": "AggregateOffer",
          priceCurrency: "ILS",
          lowPrice: low,
          highPrice: high,
          offerCount: 2,
        },
      });
    expect(validatePage([aggregate(1, 2)], [PRICED_AT])).toEqual([]);
    expect(validatePage([aggregate(3, 2)], [PRICED_AT]).join()).toMatch(/lowPrice is above/);
    const dataset = { "@context": "https://schema.org", "@type": "Dataset", name: "x" };
    expect(validatePage([dataset], []).join()).toMatch(/missing "description"/);
    expect(validatePage([{ ...dataset, description: "y" }], [])).toEqual([]);
  });
});

// ---------------------------------------------------------------- every generated page

describe.each([
  ["the committed snapshot", false],
  ["synthetic prices and a published basket month", true],
] as const)("JSON-LD of every generated page, %s", (_label, synthetic) => {
  const setup = () => {
    mode.priced = synthetic;
    mode.month = synthetic;
  };

  it("category pages: BreadcrumbList and a CollectionPage with an ItemList, all valid", async () => {
    setup();
    const pages = categoryPages();
    expect(pages.length).toBeGreaterThanOrEqual(50);
    const failures: string[] = [];
    for (const c of pages) {
      const element = (await CategoryPage({
        params: Promise.resolve({ slug: c.slug }),
      })) as ReactElement;
      const { blocks, raw, problems } = renderAndCheck(element);
      const meta = await categoryMetadata({ params: Promise.resolve({ slug: c.slug }) });
      const url = `${SITE_URL}/c/${c.slug}`;
      if (types(blocks).join() !== "BreadcrumbList,CollectionPage") {
        failures.push(`${c.slug}: ${types(blocks)}`);
      }
      if (String(meta.alternates?.canonical) !== url) failures.push(`${c.slug}: canonical`);
      if (blocks.find((b) => typeOf(b) === "CollectionPage")?.url !== url) {
        failures.push(`${c.slug}: CollectionPage.url is not the canonical URL`);
      }
      if (lastCrumb(blocks) !== url) failures.push(`${c.slug}: last breadcrumb is not this page`);
      if (raw.some((r) => r.includes("<"))) failures.push(`${c.slug}: unescaped "<"`);
      failures.push(...problems.map((p) => `${c.slug}: ${p}`));
    }
    expect(failures).toEqual([]);
  });

  it("product pages: BreadcrumbList and a Product, offers only with prices and a date", async () => {
    setup();
    const pages = productPages();
    expect(pages.length).toBeGreaterThanOrEqual(50);
    const failures: string[] = [];
    let withOffers = 0;
    for (const p of pages) {
      const element = (await ProductPage({
        params: Promise.resolve({ slug: p.slug }),
      })) as ReactElement;
      const { blocks, raw, dates, problems } = renderAndCheck(element);
      const meta = await productMetadata({ params: Promise.resolve({ slug: p.slug }) });
      const url = `${SITE_URL}/p/${p.slug}`;
      if (types(blocks).join() !== "BreadcrumbList,Product") {
        failures.push(`${p.slug}: ${types(blocks)}`);
      }
      if (String(meta.alternates?.canonical) !== url) failures.push(`${p.slug}: canonical`);
      const product = blocks.find((b) => typeOf(b) === "Product");
      if (product?.url !== url) failures.push(`${p.slug}: Product.url is not the canonical URL`);
      if (lastCrumb(blocks) !== url) failures.push(`${p.slug}: last breadcrumb is not this page`);
      if (raw.some((r) => r.includes("<"))) failures.push(`${p.slug}: unescaped "<"`);
      const priced = Boolean(p.prices && p.prices.length > 0);
      if (priced !== Boolean(product && "offers" in product)) {
        failures.push(`${p.slug}: offers must exist exactly when prices do`);
      }
      if (priced) {
        withOffers += 1;
        if ((product?.offers as Json[]).length !== p.prices!.length) {
          failures.push(`${p.slug}: one Offer per chain`);
        }
        if (!dates.includes(isoDate(p.price_valid_from!))) {
          failures.push(`${p.slug}: the page does not show the price date`);
        }
      }
      failures.push(...problems.map((m) => `${p.slug}: ${m}`));
    }
    expect(failures).toEqual([]);
    if (synthetic) expect(withOffers).toBe(pages.length);
  });

  it("methodology, basket index and accessibility pages: BreadcrumbList and a WebPage", () => {
    setup();
    const pages: [string, ReactElement][] = [
      ["/methodology", createElement(MethodologyPage)],
      ["/basket-index", createElement(BasketIndexPage)],
      ["/accessibility", createElement(AccessibilityPage)],
    ];
    const failures: string[] = [];
    for (const [path, element] of pages) {
      const { blocks, problems } = renderAndCheck(element);
      if (types(blocks).join() !== "BreadcrumbList,WebPage") {
        failures.push(`${path}: ${types(blocks)}`);
      }
      if (blocks.find((b) => typeOf(b) === "WebPage")?.url !== `${SITE_URL}${path}`) {
        failures.push(`${path}: WebPage.url`);
      }
      failures.push(...problems.map((m) => `${path}: ${m}`));
    }
    expect(failures).toEqual([]);
  });
});

describe("what the unit prices claim", () => {
  it("quotes each base unit with the matching UN/CEFACT code", async () => {
    mode.priced = true;
    const expected: Record<BaseUnit, { value: number; unitCode: string }> = {
      "100g": { value: 100, unitCode: "GRM" },
      "100ml": { value: 100, unitCode: "MLT" },
      unit: { value: 1, unitCode: "C62" },
      kg: { value: 1, unitCode: "KGM" },
    };
    const seen = new Set<BaseUnit>();
    for (const p of productPages()) {
      if (seen.has(p.base_unit)) continue;
      seen.add(p.base_unit);
      const element = (await ProductPage({
        params: Promise.resolve({ slug: p.slug }),
      })) as ReactElement;
      const { blocks } = renderAndCheck(element);
      const product = blocks.find((b) => typeOf(b) === "Product")!;
      for (const offer of product.offers as Json[]) {
        const spec = offer.priceSpecification as Json;
        expect(spec.referenceQuantity).toMatchObject({
          "@type": "QuantitativeValue",
          ...expected[p.base_unit],
        });
      }
    }
    expect(seen.size).toBeGreaterThanOrEqual(2);
  });
});
