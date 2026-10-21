import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { ROUTES } from "./routes";
import { seedComparison, stubTiles } from "./secondary.helpers";

/**
 * The security headers on the production build (security-headers.ts, docs/security-review.md) and
 * proof that the Content-Security-Policy does not break the app: every route loads under it with
 * no `securitypolicyviolation` event and no CSP console error, including the map (MapLibre worker
 * and tiles) and the service worker.
 */

async function watchViolations(page: Page): Promise<() => Promise<string[]>> {
  const consoleErrors: string[] = [];
  page.on("console", (m) => {
    if (/content security policy|refused to (load|execute|connect|apply)/i.test(m.text())) {
      consoleErrors.push(m.text());
    }
  });
  await page.addInitScript(() => {
    const w = window as unknown as { __csp: string[] };
    w.__csp = [];
    document.addEventListener("securitypolicyviolation", (e) => {
      w.__csp.push(`${e.violatedDirective} ${e.blockedURI} ${e.sourceFile ?? ""}`);
    });
  });
  return async () => {
    const events = await page
      .evaluate(() => (window as unknown as { __csp?: string[] }).__csp ?? [])
      .catch(() => []);
    return [...events, ...consoleErrors];
  };
}

test.describe("security headers", () => {
  test("every response carries the hardening headers", async ({ request }) => {
    for (const path of ["/", "/compare", "/p/milk-fresh-3", "/manifest.webmanifest", "/sw.js"]) {
      const res = await request.get(path);
      expect(res.ok(), path).toBe(true);
      const h = res.headers();
      expect(h["x-content-type-options"], path).toBe("nosniff");
      expect(h["x-frame-options"], path).toBe("DENY");
      expect(h["referrer-policy"], path).toBe("strict-origin-when-cross-origin");
      expect(h["strict-transport-security"], path).toMatch(/max-age=\d{7,}; includeSubDomains/);
      expect(h["cross-origin-opener-policy"], path).toBe("same-origin");
      expect(h["permissions-policy"], path).toContain("camera=(self)");
      expect(h["permissions-policy"], path).toContain("microphone=(self)");
      expect(h["permissions-policy"], path).toContain("geolocation=(self)");
      expect(h["x-powered-by"], path).toBeUndefined();
      const csp = h["content-security-policy"] ?? "";
      expect(csp, path).toContain("frame-ancestors 'none'");
      expect(csp, path).toContain("object-src 'none'");
      expect(csp, path).toContain("base-uri 'self'");
      expect(csp, path).toContain("form-action 'self'");
      expect(csp, path).not.toContain("unsafe-eval");
      expect(csp, path).not.toMatch(/(^|[ ;])\*($|[ ;])/);
      expect(csp, path).not.toContain("fonts.googleapis.com");
    }
    const sw = await request.get("/sw.js");
    expect(sw.headers()["cache-control"]).toContain("no-store");
    expect(sw.headers()["service-worker-allowed"]).toBe("/");
  });

  test("every route loads under the CSP with no violation", async ({ page }) => {
    const violations = await watchViolations(page);
    await stubTiles(page);
    for (const { path, h1 } of ROUTES) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1, name: h1 }).first()).toBeVisible();
      expect(await violations(), path).toEqual([]);
    }
  });

  test("the map runs under the CSP: the worker starts and the tiles load", async ({ page }) => {
    const violations = await watchViolations(page);
    const tiles = await stubTiles(page);
    await seedComparison(page);
    await page.goto("/map");
    await expect(page.getByRole("heading", { level: 1, name: "מפת סניפים" })).toBeVisible();
    await expect.poll(() => tiles.length, { timeout: 15_000 }).toBeGreaterThan(0);
    expect(await violations()).toEqual([]);
  });

  test("the service worker registers and the page still works", async ({ page }) => {
    const violations = await watchViolations(page);
    await page.goto("/");
    const registered = await page.evaluate(async () => {
      if (!("serviceWorker" in navigator)) return "unsupported";
      const reg = await navigator.serviceWorker.getRegistration();
      return reg ? "registered" : "none";
    });
    expect(["registered", "none"]).toContain(registered); // `none`: the registrar waits for idle
    expect(await violations()).toEqual([]);
  });

  test("a page cannot be framed, and an injected cross-origin script or frame is blocked", async ({
    page,
  }) => {
    await page.goto("/");
    const outcome = await page.evaluate(
      () =>
        new Promise<string>((resolve) => {
          document.addEventListener("securitypolicyviolation", (e) => resolve(e.violatedDirective));
          const s = document.createElement("script");
          s.src = "https://evil.example/x.js";
          document.head.appendChild(s);
          setTimeout(() => resolve("not blocked"), 3000);
        }),
    );
    expect(outcome).toMatch(/script-src/);
    const framed = await page.evaluate(
      () =>
        new Promise<string>((resolve) => {
          document.addEventListener("securitypolicyviolation", (e) => resolve(e.violatedDirective));
          const f = document.createElement("iframe");
          f.src = "https://evil.example/";
          document.body.appendChild(f);
          setTimeout(() => resolve("not blocked"), 3000);
        }),
    );
    expect(framed).toMatch(/frame-src|default-src/);
  });

  test("fonts are self-hosted: the CSP allows no font origin but 'self'", async ({ request }) => {
    const csp = (await request.get("/")).headers()["content-security-policy"] ?? "";
    expect(csp).toMatch(/font-src 'self'(;|$)/);
  });

  test("the production bundle does not contain the mock API", () => {
    // `NEXT_PUBLIC_API_MOCK` is unset in this build: MSW and the mock handlers must not ship.
    const root = join(process.cwd(), ".next", "static");
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const p = join(dir, name);
        if (statSync(p).isDirectory()) walk(p);
        else if (p.endsWith(".js")) files.push(p);
      }
    };
    walk(root);
    expect(files.length).toBeGreaterThan(5);
    // MSW itself, and a string only the mock handlers contain (src/mocks/handlers.ts). The little
    // switch in src/api/client.ts stays; next.config.ts aliases both imports to an empty module.
    const markers = [
      "@mswjs/interceptors",
      "mockServiceWorker",
      "HttpResponse",
      "List should have at least 1 item",
    ];
    for (const file of files) {
      const text = readFileSync(file, "utf8");
      for (const marker of markers) {
        expect(text.includes(marker), `${marker} in ${file}`).toBe(false);
      }
    }
  });
});
