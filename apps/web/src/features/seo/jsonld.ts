import { absoluteUrl, SITE_NAME } from "./config";
import { PER_UNIT } from "./format";
import type { BaseUnit, Category, Product } from "./types";

/** schema.org structured data builders. Every URL is absolute (NEXT_PUBLIC_SITE_URL). */
export type JsonLd = Record<string, unknown>;

export type Crumb = { name: string; path: string };

export function breadcrumbList(crumbs: Crumb[]): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: c.name,
      item: absoluteUrl(c.path),
    })),
  };
}

/** UN/CEFACT codes for the unit a price is quoted per, and how many of them. */
const REFERENCE_QUANTITY: Record<BaseUnit, { value: number; unitCode: string }> = {
  "100g": { value: 100, unitCode: "GRM" },
  "100ml": { value: 100, unitCode: "MLT" },
  unit: { value: 1, unitCode: "C62" },
  kg: { value: 1, unitCode: "KGM" },
};

/**
 * schema.org Product. `offers` exists only when prices exist: one Offer per chain at the median
 * unit price, with a UnitPriceSpecification that says what the price is per. Without prices the
 * page claims nothing a validator could read as an offer.
 */
export function productJsonLd(product: Product, url: string): JsonLd {
  const data: JsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name_he,
    url,
    description: `${product.name_he}: מוצר מייצג בקטלוג של ${SITE_NAME}, מושווה בין סופרים לפי מחיר ${PER_UNIT[product.base_unit]}.`,
    category: product.path.map((p) => p.name_he).join(" > "),
    inLanguage: "he",
  };
  if (product.prices && product.prices.length > 0) {
    const reference = {
      "@type": "QuantitativeValue",
      ...REFERENCE_QUANTITY[product.base_unit],
    };
    data.offers = product.prices.map((p) => ({
      "@type": "Offer",
      price: p.median_unit_price,
      priceCurrency: "ILS",
      description: `מחיר ${PER_UNIT[product.base_unit]}, חציון בין סניפי הרשת`,
      priceSpecification: {
        "@type": "UnitPriceSpecification",
        price: p.median_unit_price,
        priceCurrency: "ILS",
        referenceQuantity: reference,
      },
      seller: { "@type": "Organization", name: p.chain_name },
    }));
  }
  return data;
}

export function categoryJsonLd(category: Category, products: Product[], url: string): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: category.name_he,
    url,
    inLanguage: "he",
    mainEntity: {
      "@type": "ItemList",
      numberOfItems: products.length,
      itemListElement: products.map((p, i) => ({
        "@type": "ListItem",
        position: i + 1,
        name: p.name_he,
        ...(p.has_page ? { url: absoluteUrl(`/p/${p.slug}`) } : {}),
      })),
    },
  };
}

export function webPageJsonLd(opts: {
  name: string;
  description: string;
  path: string;
  dateModified: string;
}): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: opts.name,
    description: opts.description,
    url: absoluteUrl(opts.path),
    inLanguage: "he",
    dateModified: opts.dateModified,
    isPartOf: { "@type": "WebSite", name: SITE_NAME, url: absoluteUrl("/") },
  };
}

/** JSON for a <script type="application/ld+json">: `<` is escaped so no text can close the tag. */
export function serializeJsonLd(data: JsonLd | JsonLd[]): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
