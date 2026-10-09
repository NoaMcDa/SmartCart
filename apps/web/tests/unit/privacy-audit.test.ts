// @vitest-environment node
/**
 * Issue #30: "A dependency and network audit shows no third-party ad or tracking SDKs in the web
 * app." This is the automated half: the dependency list, the source code and the hosts the code
 * can talk to are checked against what the privacy policy promises. If a test here fails, either
 * remove the SDK or update the policy, docs/web.md and this allow-list on purpose.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const ROOT = fileURLToPath(new URL("../..", import.meta.url));

const BANNED_PACKAGES =
  /(google-?analytics|gtag|gtm|segment|mixpanel|amplitude|sentry|hotjar|fullstory|logrocket|datadog|newrelic|posthog|clarity|facebook|fbq|pixel|adsense|adsbygoogle|doubleclick|onesignal|intercom|crisp|hubspot|appsflyer|adjust|firebase|bugsnag|rollbar|smartlook|plausible|matomo|vercel\/analytics|speed-insights|react-ga|ga4|tiktok|twitter-pixel|linkedin-insight)/i;

const BANNED_CODE =
  /(\bgtag\s*\(|\bfbq\s*\(|\bdataLayer\b|googletagmanager|google-analytics|\b_paq\b|\bmixpanel\b|\bamplitude\b|\bposthog\b|\bhotjar\b|connect\.facebook\.net|doubleclick|adsbygoogle|clarity\.ms|segment\.com|sentry\.io|datadoghq)/i;

/** Hosts the web app's own code may reference. Anything else is a new third party. */
const ALLOWED_HOSTS = new Set([
  "localhost", // the default API origin in development
  "tile.openstreetmap.org", // map tiles (privacy policy discloses it)
  "www.openstreetmap.org", // attribution link
  "schema.org", // JSON-LD @context identifier on the SEO pages, a name and never fetched
  "smartcart.example", // placeholder public origin for canonical URLs and the sitemap (no request)
  // Mock-only placeholder for the chains' online-store addresses in src/mocks (#72). A reserved
  // .example host: never requested. No real chain host is in the web code: the real addresses live
  // in the database (chains.online_url) and reach the browser as links from GET /chains/online.
  "chain-shop.example",
]);

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

const sourceFiles = walk(join(ROOT, "src")).filter(
  (f) =>
    /\.(ts|tsx|css|js|mjs)$/.test(f) && !/\.test\.(ts|tsx)$/.test(f) && !f.endsWith("api/types.ts"),
);

describe("privacy audit: no third-party ad or tracking SDKs", () => {
  it("package.json has no analytics, advertising or tracking dependency", () => {
    const pkg = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8")) as {
      dependencies?: Record<string, string>;
      devDependencies?: Record<string, string>;
    };
    const names = [
      ...Object.keys(pkg.dependencies ?? {}),
      ...Object.keys(pkg.devDependencies ?? {}),
    ];
    expect(names.length).toBeGreaterThan(5);
    expect(names.filter((n) => BANNED_PACKAGES.test(n))).toEqual([]);
  });

  it("no source file loads or calls a tracking script", () => {
    const hits: string[] = [];
    for (const file of sourceFiles) {
      const text = readFileSync(file, "utf8");
      if (BANNED_CODE.test(text)) hits.push(relative(ROOT, file));
      if (/<script[^>]+\bsrc=/.test(text) || /from\s+["']next\/script["']/.test(text)) {
        hits.push(`${relative(ROOT, file)} (external script)`);
      }
    }
    expect(hits).toEqual([]);
  });

  it("the code references no host other than the allow-list", () => {
    const unexpected = new Set<string>();
    for (const file of sourceFiles) {
      const text = readFileSync(file, "utf8");
      for (const m of text.matchAll(/https?:\/\/([a-z0-9.-]+)/gi)) {
        const host = m[1]!.toLowerCase();
        if (!ALLOWED_HOSTS.has(host)) unexpected.add(`${host} in ${relative(ROOT, file)}`);
      }
    }
    expect([...unexpected]).toEqual([]);
  });

  it("the privacy policy page exists and states the no-sale commitment", () => {
    // The words live in the catalog (the route file is a server component that renders them).
    const page = readFileSync(join(ROOT, "src/i18n/messages/privacy.ts"), "utf8").replace(
      /\s+/g,
      " ",
    );
    expect(page).toContain("לא מוכרים");
    expect(page).toContain("OpenStreetMap");
    expect(page).toContain("מחקי את הנתונים שלי");
  });
});
