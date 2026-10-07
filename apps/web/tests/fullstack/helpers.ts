/**
 * Shared pieces of the full-stack specs. Unlike tests/e2e, nothing here answers API calls: every
 * request goes to the FastAPI started by scripts/demo/up.sh, which reads the demo database.
 *
 * The demo world (docs/fullstack.md): the shopper's rounded neighborhood point is in Ramat Gan
 * (32.085, 34.820); within 5 km are Tiv Taam Ramat Gan (0.7 km), Machsanei Hashuk Bnei Brak
 * (1.3 km) and the home store, Shufersal Tel Aviv (3.6 km). Prices are synthetic.
 */
import { createHmac } from "node:crypto";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API_BASE_URL = (process.env.DEMO_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/+$/,
  "",
);

/** The device position the browser reports; onboarding rounds it to 32.085, 34.820. */
export const DEVICE_POSITION = { latitude: 32.0851234, longitude: 34.8201234 };
export const NEIGHBORHOOD = { lat: 32.085, lon: 34.82 };

/** The demo list (scripts/demo/smoke.py uses the same one). */
export const DEMO_LIST =
  '3 חלב טרי 3%, 2 קוטג\' 5%, לחם אחיד, 2 ק"ג עגבניות שרי, 6 במבה, 2 שמן קנולה, 2 ק"ג בננות, 4 שוקולד מריר';

/** A barcode every fixture chain sells (build_synthetic.ITEMS[0]). */
export const MILK_BARCODE = "7290004131074";

export const DISCLAIMER = "המחיר הקובע הוא בקופה.";

// Must match scripts/demo/demo_user.py.
export const DEMO_USER_ID = "00000000-0000-4000-8000-00000000d3e0";
export const DEMO_USER_EMAIL = "demo@smartcart.invalid";
const DEMO_JWT_SECRET = "smartcart-demo-secret-not-for-production-0123456789";
const SUPABASE_ORIGIN = "http://127.0.0.1:54321";
/** supabase-js keeps the session under sb-<first label of the project host>-auth-token. */
const SUPABASE_STORAGE_KEY = "sb-127-auth-token";

const b64url = (data: string | Buffer) => Buffer.from(data).toString("base64url");

/** An HS256 access token shaped like Supabase's, signed with the secret the demo API verifies. */
export function mintToken(ttlSeconds = 3600): string {
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = b64url(
    JSON.stringify({
      sub: DEMO_USER_ID,
      aud: "authenticated",
      role: "authenticated",
      email: DEMO_USER_EMAIL,
      iat: now,
      exp: now + ttlSeconds,
    }),
  );
  const secret = process.env.SUPABASE_JWT_SECRET || DEMO_JWT_SECRET;
  const signature = createHmac("sha256", secret).update(`${header}.${payload}`).digest();
  return `${header}.${payload}.${b64url(signature)}`;
}

/**
 * The demo runs no Supabase Auth server. Signed-out tests still get an answer for any call the
 * client makes there, so nothing waits on a dead port.
 */
export async function stubSupabase(page: Page): Promise<void> {
  await page.route(`${SUPABASE_ORIGIN}/**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "*" },
      body: JSON.stringify({
        id: DEMO_USER_ID,
        aud: "authenticated",
        role: "authenticated",
        email: DEMO_USER_EMAIL,
      }),
    }),
  );
}

/**
 * Signs the page in as the demo user the way a finished email sign-in leaves it: a session in
 * supabase-js storage whose access token the real API verifies (scripts/demo/up.sh gives the API
 * the same secret). Only the Auth server is stood in for; every /me/* call reaches the API.
 */
export async function signIn(page: Page): Promise<string> {
  const token = mintToken();
  const expiresAt = Math.floor(Date.now() / 1000) + 3600;
  const session = {
    access_token: token,
    token_type: "bearer",
    expires_in: 3600,
    expires_at: expiresAt,
    refresh_token: "demo-refresh-token",
    user: {
      id: DEMO_USER_ID,
      aud: "authenticated",
      role: "authenticated",
      email: DEMO_USER_EMAIL,
      app_metadata: { provider: "email" },
      user_metadata: {},
      created_at: new Date().toISOString(),
    },
  };
  await stubSupabase(page);
  await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), [
    SUPABASE_STORAGE_KEY,
    JSON.stringify(session),
  ] as const);
  return token;
}

/** The demo user's server profile, with the consent alerts need (the API answers 422 without). */
export async function putServerProfile(
  request: APIRequestContext,
  token: string,
  homeStoreId: number,
): Promise<void> {
  const res = await request.put(`${API_BASE_URL}/me/profile`, {
    headers: { authorization: `Bearer ${token}` },
    data: {
      home_store_id: homeStoreId,
      radius_m: 5000,
      neighborhood_lat: NEIGHBORHOOD.lat,
      neighborhood_lon: NEIGHBORHOOD.lon,
      consent_location: true,
    },
  });
  expect(res.ok(), await res.text()).toBe(true);
}

export type StoreRef = { store_id: number; chain_name: string; store_name: string };

/** The nearest store of a chain, straight from the API (for ids the UI shows only as names). */
export async function nearestStore(request: APIRequestContext, chainId: string): Promise<StoreRef> {
  const res = await request.get(
    `${API_BASE_URL}/stores/nearest?chain_id=${chainId}&lon=${NEIGHBORHOOD.lon}&lat=${NEIGHBORHOOD.lat}`,
  );
  expect(res.ok()).toBe(true);
  return (await res.json()) as StoreRef;
}

export const SHUFERSAL = "7290027600007";

/**
 * Onboarding through its real screens: device location (granted by the test context), the
 * radius left at 5 km, Shufersal as "my store", car travel and the default extra stop.
 */
export async function onboard(page: Page): Promise<void> {
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { level: 1, name: "ברוכים הבאים" })).toBeVisible();
  await expect(page.getByTestId("step-count")).toContainText("שלב 1 מתוך 3");
  await page.getByRole("button", { name: "אישור שימוש במיקום המכשיר" }).click();
  await expect(page.getByTestId("location-summary")).toContainText("מעוגל לשכונה");
  await page.getByTestId("onboarding-next").click();

  await expect(page.getByTestId("step-count")).toContainText("שלב 2 מתוך 3");
  await page.getByRole("button", { name: "הסופר שלי: שופרסל" }).click();
  await expect(page.getByRole("button", { name: "הסופר שלי: שופרסל" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByTestId("onboarding-next").click();

  await expect(page.getByTestId("step-count")).toContainText("שלב 3 מתוך 3");
  await page.getByTestId("onboarding-next").click();
  await expect(page).toHaveURL(/\/$/);
}

/**
 * What onboarding leaves on the device once the home store is known (the two profile keys of
 * docs/web.md, "State and storage"), for specs that start after onboarding. Written once per tab.
 */
export async function seedShopper(page: Page, homeStoreId: number): Promise<void> {
  const profile = {
    version: 1,
    onboardingDone: true,
    consentLocation: true,
    location: { ...NEIGHBORHOOD, city: "רמת גן", neighborhood: null, source: "device" },
    radiusKm: 5,
    homeChainId: "shufersal",
    homeStoreId,
    clubs: [],
    travelMode: "car",
    extraStopValue: 25,
    costPerKm: 1.2,
    diet: { vegan: false, glutenFree: false, kosherLevel: null, allergens: [] },
    flexDefaults: {},
    updatedAt: null,
  };
  const shopper = {
    neighborhood_lat: NEIGHBORHOOD.lat,
    neighborhood_lon: NEIGHBORHOOD.lon,
    city_label: "רמת גן",
    radius_m: 5000,
    home_store_id: homeStoreId,
    clubs: [],
    travel_mode: "car",
    cost_per_km: 1.2,
    extra_stop_value: 25,
    max_stores: 2,
  };
  await page.addInitScript(
    (entries: Record<string, unknown>) => {
      if (sessionStorage.getItem("seeded:fullstack")) return;
      sessionStorage.setItem("seeded:fullstack", "1");
      for (const [key, value] of Object.entries(entries)) {
        localStorage.setItem(key, JSON.stringify(value));
      }
    },
    { "sc-profile": profile, "sc-profile-v1": shopper },
  );
}

export async function pasteList(page: Page, text: string): Promise<void> {
  const input = page.getByLabel("הוסיפי פריטים לרשימה");
  await input.fill(text);
  await input.press("Enter");
  await page.getByTestId("list-row").first().waitFor();
}

/** "₪ 1,234.50" -> 1234.5 */
export const money = (text: string | null): number =>
  Number((text ?? "").replace(/[^\d.−-]/g, "").replace("−", "-"));
