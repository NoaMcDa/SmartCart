/**
 * Site-level constants for the static SEO pages (D8).
 *
 * NEXT_PUBLIC_SITE_URL  the public origin, used for canonical URLs, the sitemap and JSON-LD.
 *                       Infrastructure is not provisioned yet, so the default is the reserved
 *                       `.example` domain: set the real one before the build that goes live.
 */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://smartcart.example").replace(
  /\/+$/,
  "",
);

export const SITE_NAME = "SmartCart";

/**
 * Whether pages for products with no prices yet may be indexed. They are real pages (what the
 * product is, what must match) but thin until prices load. Flip to false to send `noindex` for
 * them and drop them from the sitemap until the catalog has prices (docs/seo.md).
 */
export const INDEX_UNPRICED = true;

export const METHODOLOGY_PATH = "/methodology";
/** Bump when the methodology text changes (docs/methodology.md). The metric carries its own date. */
export const METHODOLOGY_UPDATED = "2026-10-07T00:00:00+03:00";
export const BASKET_INDEX_PATH = "/basket-index";
export const ACCESSIBILITY_PATH = "/accessibility";
/** The list builder: the call to action on every SEO page. */
export const LIST_BUILDER_PATH = "/";

/** The one line every price context carries (D10). */
export const CHECKOUT_GOVERNS = "המחיר הקובע הוא בקופה.";

export function absoluteUrl(path: string): string {
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
