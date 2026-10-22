import { readFileSync } from "node:fs";
import path from "node:path";
import { PREVIEW_DRAFTS } from "./config";
import type {
  BasketIndexFile,
  BasketMonth,
  CategoriesFile,
  Category,
  Product,
  ProductsFile,
  Quality,
} from "./types";

/**
 * Build-time readers for the generated data in `public/seo`. Pages are static: these run while
 * `next build` prerenders `generateStaticParams`, so the site builds without a database. The
 * files are regenerated with `smartcart-catalog export-seo` (docs/seo.md).
 */
const SEO_DIR = path.join(process.cwd(), "public", "seo");

const cache = new Map<string, unknown>();

function readJson<T>(name: string): T {
  if (!cache.has(name)) {
    cache.set(name, JSON.parse(readFileSync(path.join(SEO_DIR, name), "utf-8")));
  }
  return cache.get(name) as T;
}

export const getCategories = (): CategoriesFile => readJson<CategoriesFile>("categories.json");
export const getProducts = (): ProductsFile => readJson<ProductsFile>("products.json");
export const getQuality = (): Quality => readJson<Quality>("quality.json");
export const getBasketIndex = (): BasketIndexFile => readJson<BasketIndexFile>("basket-index.json");

/** Categories that have a page of their own (at least one canonical underneath). */
export function categoryPages(): Category[] {
  return getCategories().categories.filter((c) => c.has_page);
}

/** Products that have a page of their own (the best-ranked ones within the page budget). */
export function productPages(): Product[] {
  return getProducts().products.filter((p) => p.has_page);
}

export function getCategory(slug: string): Category | undefined {
  return categoryPages().find((c) => c.slug === slug);
}

export function getProduct(slug: string): Product | undefined {
  return productPages().find((p) => p.slug === slug);
}

/** Level 2 categories of a department that have pages. */
export function childCategories(slug: string): Category[] {
  return categoryPages().filter((c) => c.parent_slug === slug);
}

/** Every MVP canonical under a category (level 1 or 2), best-ranked first. */
export function productsIn(category: Category): Product[] {
  const level = category.level;
  return getProducts().products.filter((p) => p.path[level - 1]?.slug === category.slug);
}

/** Months the reviewer published, newest first. Drafts are never shown. */
export function publishedMonths(index: BasketIndexFile = getBasketIndex()): BasketMonth[] {
  return index.months.filter((m) => m.status === "published");
}

/**
 * The months the basket-index page shows: the published ones, and only in a preview build
 * (`SEO_PREVIEW_DRAFTS=1`, never a deploy build: config.ts) the drafts too, which the page then
 * labels as drafts. Newest first.
 */
export function shownMonths(
  index: BasketIndexFile = getBasketIndex(),
  previewDrafts: boolean = PREVIEW_DRAFTS,
): BasketMonth[] {
  return previewDrafts ? index.months : publishedMonths(index);
}

/** True when the basket-index page would show a draft month: it is then `noindex` and not in the sitemap. */
export function basketShowsDraft(
  index: BasketIndexFile = getBasketIndex(),
  previewDrafts: boolean = PREVIEW_DRAFTS,
): boolean {
  return shownMonths(index, previewDrafts).some((m) => m.status !== "published");
}
