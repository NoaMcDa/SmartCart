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
