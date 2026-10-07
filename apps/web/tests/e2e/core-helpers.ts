/**
 * Helpers for the core-screen e2e specs (core-*.spec.ts).
 *
 * `mockApi` answers every browser request to the API origin from the MSW handlers in src/mocks,
 * so the specs run against any production build: one built with NEXT_PUBLIC_API_MOCK=1 resolves
 * in process and never reaches the network, one built without it (CI) calls
 * http://localhost:8000 and lands here. The numbers are the documented mock numbers.
 */
import type { Page } from "@playwright/test";
import { getResponse } from "msw";
import { API_BASE_URL } from "../../src/api/config";
import { handlers } from "../../src/mocks/handlers";

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
};

export type ApiCall = { method: string; path: string; body: unknown };

export async function mockApi(page: Page): Promise<ApiCall[]> {
  const calls: ApiCall[] = [];
  const origin = new URL(API_BASE_URL).origin;
  await page.route(
    (url) => url.origin === origin,
    async (route) => {
      const req = route.request();
      if (req.method() === "OPTIONS") {
        await route.fulfill({ status: 204, headers: CORS });
        return;
      }
      const body = req.method() === "GET" ? undefined : (req.postData() ?? undefined);
      calls.push({
        method: req.method(),
        path: new URL(req.url()).pathname,
        body: body ? JSON.parse(body) : undefined,
      });
      const res = await getResponse(
        handlers,
        new Request(req.url(), {
          method: req.method(),
          headers: { "content-type": "application/json" },
          body,
        }),
      );
      if (!res) {
        await route.fulfill({ status: 501, headers: CORS, body: "{}" });
        return;
      }
      await route.fulfill({
        status: res.status,
        headers: { ...CORS, "content-type": "application/json" },
        body: await res.text(),
      });
    },
  );
  return calls;
}

/** The weekly list from the artboards (9 items) as one paste. */
export const WEEKLY_TEXT =
  "2 חלב, קוטג', משקה סויה, 2 רסק עגבניות, שמן זית כתית מעולה, 3 פסטה, עגבניות, 2 סלמון, 2 ביצים";

export const ACCEPTANCE_TEXT = "חלב, 2 רסק עגבניות, סלמון";

export async function pasteList(page: Page, text: string) {
  const input = page.getByLabel("הוסיפי פריטים לרשימה");
  await input.fill(text);
  await input.press("Enter");
  await page.getByTestId("list-row").first().waitFor();
}

/**
 * Stores the shopper profile the onboarding would write: Modi'in, 5 km, the mock's home store
 * (שופרסל דיל, 103), car with ₪25 per extra stop. Runs before every page script.
 */
export async function seedProfile(page: Page, profile: Record<string, unknown> = {}) {
  await page.addInitScript(
    (value) => {
      window.localStorage.setItem("sc-profile-v1", JSON.stringify(value));
    },
    {
      neighborhood_lat: 31.898,
      neighborhood_lon: 35.01,
      city_label: "מודיעין",
      radius_m: 5000,
      home_store_id: 103,
      travel_mode: "car",
      extra_stop_value: 25,
      ...profile,
    },
  );
}

/** Builds the weekly list on `/` and opens the results (with the seeded home store). */
export async function openWeeklyResults(page: Page) {
  await seedProfile(page);
  await page.goto("/");
  await pasteList(page, WEEKLY_TEXT);
  await page.getByRole("link", { name: "השווי" }).click();
  await page.getByTestId("plan-single").waitFor();
}
