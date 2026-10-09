/**
 * Site-level constants for the static SEO pages (D8). Read at build time (NEXT_PUBLIC_* values are
 * inlined by Next.js), documented in docs/seo.md.
 *
 * NEXT_PUBLIC_SITE_URL         the public origin, used for canonical URLs, the sitemap and JSON-LD.
 *                              Infrastructure is not provisioned yet, so the default is the
 *                              reserved `.example` domain. An empty value counts as unset (the
 *                              Dockerfile passes an empty build arg when no variable is set).
 * NEXT_PUBLIC_INDEX_UNPRICED   "1" (default) or "0": may product pages with no prices yet be
 *                              indexed? See `INDEX_UNPRICED` below.
 * SEO_STRICT_SITE_URL          "1" makes a production build fail when the site URL is unset, the
 *                              placeholder or not absolute https. Opt-in, so CI and local builds
 *                              keep working without a domain; set it in the deploy build.
 * SEO_ALLOW_PLACEHOLDER        "1" turns the strict check off again (CI, local builds).
 */
export const PLACEHOLDER_SITE_URL = "https://smartcart.example";

type Env = Record<string, string | undefined>;

/** `"0"` (also `false`/`off`/`no`) is false, `"1"` (also `true`/`on`/`yes`) and unset are true. */
export function parseIndexUnpriced(value: string | undefined): boolean {
  const v = (value ?? "").trim().toLowerCase();
  return !["0", "false", "off", "no"].includes(v);
}

export function normalizeSiteUrl(value: string | undefined): string {
  const v = (value ?? "").trim();
  return (v === "" ? PLACEHOLDER_SITE_URL : v).replace(/\/+$/, "");
}

/**
 * Throws a message that says what to set when the strict check is on (production build,
 * `SEO_STRICT_SITE_URL=1`, no `SEO_ALLOW_PLACEHOLDER=1`) and the site URL is not a real absolute
 * https origin. Pure: takes the environment, so tests can try every case.
 */
export function assertSiteUrl(env: Env): void {
  if (env.NODE_ENV !== "production") return;
  if (env.SEO_STRICT_SITE_URL !== "1" || env.SEO_ALLOW_PLACEHOLDER === "1") return;
  const raw = (env.NEXT_PUBLIC_SITE_URL ?? "").trim();
  const fail = (why: string): never => {
    throw new Error(
      `NEXT_PUBLIC_SITE_URL ${why}. Canonical URLs, the sitemap and JSON-LD would point at the wrong origin. ` +
        `Set it to the public https origin for this build, ` +
        `or set SEO_ALLOW_PLACEHOLDER=1 for a CI or local build (docs/seo.md).`,
    );
  };
  if (raw === "") return fail("is not set");
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return fail(`is not an absolute URL (got "${raw}")`);
  }
  if (url.protocol !== "https:") return fail(`must be an https URL (got "${raw}")`);
  if (url.hostname === new URL(PLACEHOLDER_SITE_URL).hostname) {
    return fail(`is still the placeholder ${PLACEHOLDER_SITE_URL}`);
  }
}

assertSiteUrl({
  NODE_ENV: process.env.NODE_ENV,
  NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL,
  SEO_STRICT_SITE_URL: process.env.SEO_STRICT_SITE_URL,
  SEO_ALLOW_PLACEHOLDER: process.env.SEO_ALLOW_PLACEHOLDER,
});

export const SITE_URL = normalizeSiteUrl(process.env.NEXT_PUBLIC_SITE_URL);

export const SITE_NAME = "SmartCart";

/**
 * Whether pages for products with no prices yet may be indexed. They are real pages (what the
 * product is, what must match) but thin until prices load. Set NEXT_PUBLIC_INDEX_UNPRICED=0 at
 * build time to send `noindex` for them and drop them from the sitemap until the catalog has
 * prices (docs/seo.md). Default: true, as before.
 */
export const INDEX_UNPRICED = parseIndexUnpriced(process.env.NEXT_PUBLIC_INDEX_UNPRICED);

/** Whether a product page is indexable: priced pages always, unpriced ones only if allowed. */
export function isIndexable(product: { no_prices_yet: boolean }): boolean {
  return !product.no_prices_yet || INDEX_UNPRICED;
}

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
