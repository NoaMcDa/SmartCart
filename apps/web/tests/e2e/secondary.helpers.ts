import { createServer, request as httpRequest, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import type { Browser, BrowserContext, Page } from "@playwright/test";
import { shopperSeed, weeklyListState } from "../../src/mocks/lastResult";
import { mockApi, type ApiCall } from "./core-helpers";

/** localStorage keys of the secondary screens (src/features/profile/storage.ts). */
export const KEYS = {
  profile: "sc-profile",
  /** The core screens' list and shopper context (src/state), which the comparison is built from. */
  list: "sc-list-v1",
  shopper: "sc-profile-v1",
  shopping: "sc-shopping",
  savings: "sc-savings-history",
} as const;

/** A 1x1 transparent PNG, so map tiles never touch the network in tests. */
const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

export async function stubTiles(page: Page): Promise<string[]> {
  const requested: string[] = [];
  await page.route("https://tile.openstreetmap.org/**", (route) => {
    requested.push(route.request().url());
    return route.fulfill({ status: 200, contentType: "image/png", body: PNG_1X1 });
  });
  return requested;
}

/**
 * Writes localStorage entries before the app loads, once per tab: a marker in sessionStorage keeps
 * a reload from re-creating something the test deleted on purpose.
 */
export async function seed(page: Page, entries: Record<string, unknown>): Promise<void> {
  await page.addInitScript((e: Record<string, unknown>) => {
    for (const [key, value] of Object.entries(e)) {
      const marker = `seeded:${key}`;
      if (sessionStorage.getItem(marker)) continue;
      sessionStorage.setItem(marker, "1");
      localStorage.setItem(key, JSON.stringify(value));
    }
  }, entries);
}

export const profileSeed = (over: Record<string, unknown> = {}) => ({
  version: 1,
  onboardingDone: true,
  consentLocation: true,
  location: {
    lat: 31.897,
    lon: 35.01,
    city: "מודיעין-מכבים-רעות",
    neighborhood: null,
    source: "manual",
  },
  radiusKm: 5,
  homeChainId: "shufersal",
  homeStoreId: 103,
  clubs: [],
  travelMode: "car",
  extraStopValue: 25,
  costPerKm: 1.2,
  diet: { vegan: false, glutenFree: false, kosherLevel: null, allergens: [] },
  flexDefaults: {},
  updatedAt: null,
  ...over,
});

/**
 * Starts from "the weekly list is built and the shopper is in Modi'in with Shufersal as the home
 * store": the API mock answers /optimize and /compare for it, so /split, /map and /store-mode have
 * a comparison to show. Returns the log of API calls.
 */
export async function seedComparison(page: Page): Promise<ApiCall[]> {
  const calls = await mockApi(page);
  await seed(page, { [KEYS.list]: weeklyListState(), [KEYS.shopper]: shopperSeed() });
  return calls;
}

export { mockApi };

export async function noHorizontalScroll(page: Page): Promise<void> {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  if (scrollWidth > clientWidth) {
    throw new Error(`horizontal scroll: scrollWidth ${scrollWidth} > clientWidth ${clientWidth}`);
  }
}

/**
 * A proxy in front of the app. `setOffline(true)` makes it drop every connection, so requests
 * made by the service worker fail too (Playwright's own offline switch does not cover them);
 * the same technique as pwa.spec.ts.
 */
export async function offlineProxy(baseURL: string) {
  const upstream = new URL(baseURL);
  let offline = false;
  const server: Server = createServer((req, res) => {
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
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://localhost:${(server.address() as AddressInfo).port}`;
  return {
    base,
    setOffline: (value: boolean) => {
      offline = value;
    },
    async newContext(browser: Browser): Promise<BrowserContext> {
      return browser.newContext({ viewport: { width: 390, height: 844 }, locale: "he-IL" });
    },
    async close() {
      server.closeAllConnections();
      await new Promise((resolve) => server.close(resolve));
    },
  };
}
