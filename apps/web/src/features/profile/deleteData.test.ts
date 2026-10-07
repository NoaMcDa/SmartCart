import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { api } from "@/api/client";
import { API_BASE_URL } from "@/api/config";
import { getApiToken, setApiToken } from "@/features/auth/apiAuth";
import { resetMeMock } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { deleteMyData } from "./deleteData";
import { fetchServerProfile, pushServerProfile, toProfileUpdate } from "./profileApi";
import { getProfile, resetProfileCache, setLocation, updateProfile } from "./profileState";
import { LOCAL_DATA_KEYS, STORAGE_KEYS } from "./storage";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
  resetMeMock();
  setApiToken("test-token");
});

async function seedAccount() {
  setLocation({ lat: 31.8969, lon: 35.0104, city: "מודיעין-מכבים-רעות", source: "manual" });
  updateProfile({
    homeStoreId: 103,
    clubs: ["רמי לוי"],
    diet: { vegan: true, glutenFree: false, kosherLevel: "mehadrin", allergens: ["sesame"] },
  });
  await pushServerProfile(toProfileUpdate(getProfile(), "system", { "dairy.milk": "exact" }));
  for (const name of ["הקנייה השבועית", "סופ״ש"]) {
    const res = await api.POST("/me/lists", {
      body: {
        name,
        is_recurring: false,
        items: [{ canonical_id: 1001, quantity: 2, confirmed: true, flex_level: "any_brand" }],
      },
    });
    expect(res.response.status).toBe(201);
  }
  window.localStorage.setItem("sc-list-v1", "{}");
  window.localStorage.setItem(STORAGE_KEYS.savings, "[]");
}

describe("profile sync payload", () => {
  it("sends the rounded neighborhood location only with consent, and encodes diet flags", async () => {
    await seedAccount();
    const stored = await fetchServerProfile();
    expect(stored).toMatchObject({
      exists: true,
      consent_location: true,
      neighborhood_lat: 31.897,
      neighborhood_lon: 35.01,
      home_store_id: 103,
      kosher_level: "mehadrin",
      clubs: ["רמי לוי"],
      flex_defaults: { "dairy.milk": "exact" },
    });
    expect(stored.diet_flags).toEqual(["vegan", "allergen:sesame"]);

    // Without a location the update carries no coordinates, and consent is off.
    updateProfile({ location: null, consentLocation: false });
    const body = toProfileUpdate(getProfile());
    expect(body).toMatchObject({
      consent_location: false,
      neighborhood_lat: null,
      neighborhood_lon: null,
    });
  });
});

describe("delete my data (issue #30)", () => {
  it("signed in: deletes every list, resets the stored profile, clears the device and signs out", async () => {
    await seedAccount();
    expect((await api.GET("/me/lists")).data).toHaveLength(2);

    // DELETE /me runs after the device is cleared and while the token is still set.
    const order: string[] = [];
    let auth: string | null = null;
    server.use(
      http.delete(`${API_BASE_URL}/me`, ({ request }) => {
        order.push(
          window.localStorage.getItem(STORAGE_KEYS.profile) === null
            ? "delete-me:device-clear"
            : "delete-me:device-NOT-clear",
        );
        auth = request.headers.get("authorization");
        return HttpResponse.json({ ok: true, id: null });
      }),
    );
    let signedOut = false;
    const result = await deleteMyData({
      signedIn: true,
      signOut: async () => {
        order.push("sign-out");
        signedOut = true;
      },
    });
    expect(result).toEqual({ ok: true, signedIn: true, listsDeleted: 2, accountRowRemains: false });
    expect(signedOut).toBe(true);
    expect(order).toEqual(["delete-me:device-clear", "sign-out"]);
    expect(auth).toBe("Bearer test-token");

    // Server side: no lists, and the profile is back to the defaults with no location or consent.
    expect((await api.GET("/me/lists")).data).toEqual([]);
    const profile = await fetchServerProfile();
    expect(profile).toMatchObject({
      consent_location: false,
      neighborhood_lat: null,
      neighborhood_lon: null,
      home_store_id: null,
      clubs: [],
      diet_flags: [],
      kosher_level: null,
      flex_defaults: {},
    });

    // Device side.
    for (const key of LOCAL_DATA_KEYS) expect(window.localStorage.getItem(key), key).toBeNull();
    expect(getProfile().location).toBeNull();
    expect(getProfile().homeStoreId).toBeNull();
  });

  it("DELETE /me failing keeps the device clear, signs out and reports that the account remains", async () => {
    await seedAccount();
    server.use(http.delete(`${API_BASE_URL}/me`, () => HttpResponse.json({}, { status: 500 })));
    let signedOut = false;
    const result = await deleteMyData({
      signedIn: true,
      signOut: async () => {
        signedOut = true;
      },
    });
    expect(result).toEqual({ ok: true, signedIn: true, listsDeleted: 2, accountRowRemains: true });
    expect(signedOut).toBe(true);
    for (const key of LOCAL_DATA_KEYS) expect(window.localStorage.getItem(key), key).toBeNull();
    expect((await api.GET("/me/lists")).data).toEqual([]);
  });

  it("does not call DELETE /me when the list or profile cleanup failed", async () => {
    await seedAccount();
    let called = false;
    server.use(
      http.get(`${API_BASE_URL}/me/lists`, () => HttpResponse.json({}, { status: 500 })),
      http.delete(`${API_BASE_URL}/me`, () => {
        called = true;
        return HttpResponse.json({ ok: true, id: null });
      }),
    );
    const result = await deleteMyData({ signedIn: true, signOut: async () => undefined });
    expect(result.ok).toBe(false);
    expect(called).toBe(false);
  });

  it("signed out: clears the device without touching the API", async () => {
    server.use(
      http.all(`${API_BASE_URL}/me/*`, () => {
        throw new Error("signed-out deletion must not call /me");
      }),
    );
    updateProfile({ homeChainId: "shufersal" });
    const result = await deleteMyData({ signedIn: false, signOut: async () => undefined });
    expect(result).toMatchObject({
      ok: true,
      signedIn: false,
      listsDeleted: 0,
      accountRowRemains: false,
    });
    expect(window.localStorage.getItem(STORAGE_KEYS.profile)).toBeNull();
  });

  it("keeps the local data when the server fails, so the user can retry", async () => {
    await seedAccount();
    server.use(http.get(`${API_BASE_URL}/me/lists`, () => HttpResponse.json({}, { status: 500 })));
    const result = await deleteMyData({ signedIn: true, signOut: async () => undefined });
    expect(result.ok).toBe(false);
    expect(window.localStorage.getItem(STORAGE_KEYS.profile)).not.toBeNull();
  });
});

describe("API token", () => {
  it("is attached to calls through the openapi-fetch middleware", async () => {
    let header: string | null = null;
    server.use(
      http.get(`${API_BASE_URL}/me/profile`, ({ request }) => {
        header = request.headers.get("authorization");
        return HttpResponse.json({}, { status: 500 });
      }),
    );
    expect(getApiToken()).toBe("test-token");
    await fetchServerProfile().catch(() => undefined);
    expect(header).toBe("Bearer test-token");
    setApiToken(null);
    header = "unset";
    await fetchServerProfile().catch(() => undefined);
    expect(header).toBeNull();
  });
});
