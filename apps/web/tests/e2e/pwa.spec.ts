import { createServer, request as httpRequest, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { expect, test } from "@playwright/test";

test.describe("PWA", () => {
  test("manifest is Hebrew, RTL, standalone, with real icons", async ({ page, request }) => {
    const res = await request.get("/manifest.webmanifest");
    expect(res.ok()).toBe(true);
    const m = await res.json();
    expect(m).toMatchObject({
      name: "SmartCart",
      short_name: "סמארטקארט",
      lang: "he",
      dir: "rtl",
      display: "standalone",
      start_url: "/",
    });
    const sizes = m.icons.map((i: { sizes: string }) => i.sizes);
    expect(sizes).toEqual(expect.arrayContaining(["192x192", "512x512"]));
    expect(m.icons.some((i: { purpose?: string }) => i.purpose === "maskable")).toBe(true);
    for (const icon of m.icons) {
      const r = await request.get(icon.src);
      expect(r.ok(), icon.src).toBe(true);
    }

    await page.goto("/");
    await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
      "href",
      "/manifest.webmanifest",
    );
    await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute(
      "href",
      /apple-touch-icon\.png/,
    );
    await expect(page.locator('meta[name="apple-mobile-web-app-capable"]')).toHaveAttribute(
      "content",
      "yes",
    );
    await expect(page.locator('meta[name="apple-mobile-web-app-title"]')).toHaveAttribute(
      "content",
      "סמארטקארט",
    );
    await expect(page.locator('meta[name="theme-color"]')).toHaveCount(2);
  });

  test("Heebo is served locally: no Google Fonts requests, all four weights load with the network blocked", async ({
    page,
  }) => {
    const external: string[] = [];
    await page.route("**/*", (route) => {
      const url = new URL(route.request().url());
      if (url.hostname !== "localhost" && url.hostname !== "127.0.0.1") {
        external.push(url.href);
        return route.abort("internetdisconnected");
      }
      return route.continue();
    });
    const fontResponses: string[] = [];
    page.on("response", (r) => {
      if (r.url().endsWith(".woff2") && r.ok()) fontResponses.push(r.url());
    });
    await page.goto("/");
    const result = await page.evaluate(async () => {
      const family = getComputedStyle(document.body).fontFamily.split(",")[0]!.trim();
      const weights = [400, 500, 600, 700];
      const loaded = await Promise.all(
        weights.map((w) => document.fonts.load(`${w} 16px ${family}`, "שלום")),
      );
      await document.fonts.ready;
      return {
        family,
        loadedPerWeight: loaded.map((faces) => faces.length),
        h1Font: getComputedStyle(document.querySelector("h1")!).fontFamily,
        check: weights.map((w) => document.fonts.check(`${w} 16px ${family}`, "שלום")),
      };
    });
    expect(result.family.toLowerCase()).toContain("heebo");
    expect(result.loadedPerWeight.every((n) => n > 0)).toBe(true);
    expect(result.check).toEqual([true, true, true, true]);
    expect(fontResponses.length).toBeGreaterThanOrEqual(1);
    expect(fontResponses.every((u) => u.startsWith("http://localhost"))).toBe(true);
    expect(external.filter((u) => /fonts\.(googleapis|gstatic)\.com/.test(u))).toEqual([]);
  });

  test("service worker precaches the shell and serves it offline", async ({ browser, baseURL }) => {
    // Playwright's setOffline() does not cover requests made by a service worker. Instead the page
    // talks to the app through a local proxy on its own origin, and "offline" makes the proxy drop
    // every connection, so the worker's network fetches really fail.
    const upstream = new URL(baseURL!);
    let offline = false;
    const proxy: Server = createServer((req, res) => {
      if (offline) {
        req.socket.destroy();
        return;
      }
      const up = httpRequest(
        {
          host: upstream.hostname,
          port: upstream.port,
          path: req.url,
          method: req.method,
          headers: { ...req.headers, host: upstream.host },
        },
        (upRes) => {
          res.writeHead(upRes.statusCode ?? 502, upRes.headers);
          upRes.pipe(res);
        },
      );
      up.on("error", () => res.destroy());
      req.pipe(up);
    });
    await new Promise<void>((resolve) => proxy.listen(0, "127.0.0.1", resolve));
    const base = `http://localhost:${(proxy.address() as AddressInfo).port}`;

    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    try {
      const page = await context.newPage();
      await page.goto(`${base}/`);
      await page.evaluate(async () => {
        await navigator.serviceWorker.ready;
      });
      // Reload so the page is controlled by the now-active worker.
      await page.reload();
      await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);

      const cached = await page.evaluate(async () => {
        const urls: string[] = [];
        for (const n of await caches.keys()) {
          for (const r of await (await caches.open(n)).keys()) urls.push(new URL(r.url).pathname);
        }
        return urls;
      });
      expect(cached).toEqual(expect.arrayContaining(["/", "/offline", "/manifest.webmanifest"]));
      expect(cached.some((u) => u.endsWith(".woff2"))).toBe(true);
      expect(cached.some((u) => u.startsWith("/_next/static/") && u.endsWith(".js"))).toBe(true);

      offline = true;
      expect(
        await fetch(`${base}/`).then(
          () => "online",
          () => "offline",
        ),
      ).toBe("offline");

      await page.reload();
      await expect(page.getByRole("heading", { level: 1, name: "הקנייה השבועית" })).toBeVisible();
      await expect(page.getByTestId("bottom-nav")).toBeVisible();
      // The shell is interactive offline: the theme switch still works.
      await page.getByRole("switch", { name: "מצב כהה" }).click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

      // A route never visited falls back to the offline page, inside the app shell.
      const res = await page.goto(`${base}/split`);
      expect(res?.fromServiceWorker()).toBe(true);
      await expect(
        page.getByRole("heading", { level: 1, name: "אין חיבור לאינטרנט" }),
      ).toBeVisible();
      await expect(page.getByTestId("bottom-nav")).toBeVisible();
    } finally {
      await context.close();
      proxy.closeAllConnections();
      await new Promise((resolve) => proxy.close(resolve));
    }
  });
});
