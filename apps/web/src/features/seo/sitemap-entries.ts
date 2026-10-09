import type { MetadataRoute } from "next";
import {
  absoluteUrl,
  ACCESSIBILITY_PATH,
  BASKET_INDEX_PATH,
  isIndexable,
  METHODOLOGY_PATH,
  METHODOLOGY_UPDATED,
} from "./config";
import { categoryPages, getBasketIndex, getCategories, getProducts, productPages } from "./data";

/** Every indexable static page with its last modification date. */
export function sitemapEntries(): MetadataRoute.Sitemap {
  const categoriesAt = new Date(getCategories().generated_at);
  const productsAt = new Date(getProducts().generated_at);
  const index = getBasketIndex();
  const entries: MetadataRoute.Sitemap = [
    { url: absoluteUrl("/"), changeFrequency: "weekly", priority: 1 },
    {
      url: absoluteUrl(METHODOLOGY_PATH),
      lastModified: new Date(METHODOLOGY_UPDATED),
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: absoluteUrl(BASKET_INDEX_PATH),
      lastModified: new Date(index.generated_at),
      changeFrequency: "monthly",
      priority: 0.7,
    },
    { url: absoluteUrl(ACCESSIBILITY_PATH), changeFrequency: "yearly", priority: 0.2 },
  ];
  for (const c of categoryPages()) {
    entries.push({
      url: absoluteUrl(`/c/${c.slug}`),
      lastModified: categoriesAt,
      changeFrequency: "daily",
      priority: c.level === 1 ? 0.8 : 0.6,
    });
  }
  for (const p of productPages()) {
    if (!isIndexable(p)) continue;
    entries.push({
      url: absoluteUrl(`/p/${p.slug}`),
      lastModified: p.price_valid_from ? new Date(p.price_valid_from) : productsAt,
      changeFrequency: "daily",
      priority: 0.5,
    });
  }
  return entries;
}
