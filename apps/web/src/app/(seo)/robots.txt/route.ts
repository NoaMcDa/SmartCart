import { absoluteUrl } from "@/features/seo/config";

export const dynamic = "force-static";

/** Pages that are per-person or not content (results, profile, onboarding, tooling). */
const PRIVATE_PATHS = [
  "/compare",
  "/profile",
  "/onboarding",
  "/store-mode",
  "/offline",
  "/design-system",
];

/**
 * NEXT_PUBLIC_INDEX_UNPRICED=0 (config.ts) does not add a Disallow for unpriced product pages: a
 * crawler that may not fetch a page never sees its `noindex`, and the URL can still be indexed
 * from links. Those pages stay crawlable, carry `<meta name="robots" content="noindex, follow">`
 * (p/[slug]/page.tsx) and are left out of the sitemap (sitemap-entries.ts). Same flag, same rule
 * (`isIndexable`), in all three places.
 */

/** Plain text, so the file works from inside the route group (robots.ts only works at the app root). */
function robotsTxt(): string {
  return [
    "User-agent: *",
    "Allow: /",
    ...PRIVATE_PATHS.map((p) => `Disallow: ${p}`),
    "",
    `Sitemap: ${absoluteUrl("/sitemap.xml")}`,
    "",
  ].join("\n");
}

export function GET(): Response {
  return new Response(robotsTxt(), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
