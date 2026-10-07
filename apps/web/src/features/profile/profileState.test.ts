import { beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_PROFILE,
  adoptHomeStore,
  getProfile,
  resetProfileCache,
  roundCoord,
  sanitizeProfile,
  setLocation,
  updateProfile,
} from "./profileState";
import { PROFILE_KEY, readShopper } from "@/state/shopper";
import { STORAGE_KEYS, clearLocalData } from "./storage";

beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
});

/** Every decimal number in a JSON string, to prove nothing finer than 3 places is stored. */
function decimals(json: string): string[] {
  return json.match(/-?\d+\.\d+/g) ?? [];
}

describe("location rounding (D11)", () => {
  it("rounds to 3 decimals, about 100 m", () => {
    expect(roundCoord(32.0853123)).toBe(32.085);
    expect(roundCoord(34.7818987)).toBe(34.782);
    expect(roundCoord(-0.0004)).toBe(-0);
  });

  it("setLocation stores the rounded value, never the exact device coordinates", () => {
    setLocation({ lat: 32.08531234567, lon: 34.78189876543, source: "device" });
    const raw = window.localStorage.getItem(STORAGE_KEYS.profile)!;
    expect(raw).not.toContain("32.0853123");
    expect(raw).not.toContain("34.7818987");
    for (const d of decimals(raw)) {
      const places = d.split(".")[1]!.length;
      // costPerKm (1.2) is the only other decimal; coordinates have at most 3 places.
      expect(places).toBeLessThanOrEqual(3);
    }
    const p = getProfile();
    expect(p.location).toMatchObject({ lat: 32.085, lon: 34.782, source: "device" });
    expect(p.consentLocation).toBe(true);
  });

  it("re-rounds anything unrounded that reaches storage by another path", () => {
    window.localStorage.setItem(
      STORAGE_KEYS.profile,
      JSON.stringify({
        consentLocation: true,
        location: {
          lat: 31.89876543,
          lon: 35.00123456,
          city: null,
          neighborhood: null,
          source: "device",
        },
      }),
    );
    expect(getProfile().location).toMatchObject({ lat: 31.899, lon: 35.001 });
    // And a write through updateProfile persists the rounded form.
    updateProfile({ radiusKm: 6 });
    const raw = window.localStorage.getItem(STORAGE_KEYS.profile)!;
    expect(raw).not.toContain("31.89876543");
  });

  it("drops a stored location when consent is missing", () => {
    const p = sanitizeProfile({
      consentLocation: false,
      location: { lat: 32.1, lon: 34.8, city: "x", neighborhood: null, source: "manual" },
    });
    expect(p.location).toBeNull();
  });
});

describe("profile state", () => {
  it("starts with the documented defaults and no baseline store", () => {
    const p = getProfile();
    expect(p).toEqual(DEFAULT_PROFILE);
    expect(p.homeChainId).toBeNull();
    expect(p.radiusKm).toBe(5);
    expect(p.extraStopValue).toBe(25);
    expect(p.travelMode).toBe("car");
  });

  it("clamps the radius to 1-15 km and the extra stop value to 0-50 ILS", () => {
    updateProfile({ radiusKm: 99, extraStopValue: -5 });
    expect(getProfile()).toMatchObject({ radiusKm: 15, extraStopValue: 0 });
    updateProfile({ radiusKm: 0, extraStopValue: 80 });
    expect(getProfile()).toMatchObject({ radiusKm: 1, extraStopValue: 50 });
  });

  it("ignores garbage in storage instead of throwing", () => {
    window.localStorage.setItem(STORAGE_KEYS.profile, "{not json");
    expect(getProfile()).toEqual(DEFAULT_PROFILE);
    window.localStorage.setItem(
      STORAGE_KEYS.profile,
      JSON.stringify({
        travelMode: "teleport",
        clubs: [1, "x"],
      }),
    );
    const p = getProfile();
    expect(p.travelMode).toBe("car");
    expect(p.clubs).toEqual(["x"]);
  });

  it("mirrors every change to the shopper context the comparison reads (sc-profile-v1)", () => {
    expect(window.localStorage.getItem(PROFILE_KEY)).toBeNull();
    setLocation({ lat: 31.8969, lon: 35.0104, city: "מודיעין-מכבים-רעות", source: "manual" });
    updateProfile({
      radiusKm: 8,
      clubs: ["רמי לוי"],
      travelMode: "walk_transit",
      extraStopValue: 10,
      homeStoreId: 103,
    });
    const stored = JSON.parse(window.localStorage.getItem(PROFILE_KEY)!);
    expect(stored).toMatchObject({
      neighborhood_lat: 31.897,
      neighborhood_lon: 35.01,
      city_label: "מודיעין-מכבים-רעות",
      radius_m: 8000,
      home_store_id: 103,
      clubs: ["רמי לוי"],
      travel_mode: "walk_transit",
      extra_stop_value: "10",
    });
    expect(readShopper()).toMatchObject({
      lat: 31.897,
      lon: 35.01,
      radiusM: 8000,
      homeStoreId: 103,
      travelMode: "walk_transit",
      extraStopValue: 10,
    });
  });

  it("no home chain means an explicit null home store: no baseline, no saving (D7)", () => {
    updateProfile({ radiusKm: 6 });
    expect(JSON.parse(window.localStorage.getItem(PROFILE_KEY)!).home_store_id).toBeNull();
    expect(readShopper().homeStoreId).toBeNull();
  });

  it("resolves the home chain to the nearest store of that chain", () => {
    updateProfile({ homeChainId: "rami_levy" });
    const stores = [
      { store_id: 1, chain_id: "rami_levy", chain_name: "רמי לוי", distance_m: 5000 },
      { store_id: 2, chain_id: "rami_levy", chain_name: "רמי לוי", distance_m: 2000 },
      { store_id: 3, chain_id: "shufersal", chain_name: "שופרסל", distance_m: 500 },
    ];
    expect(adoptHomeStore(stores)).toBe(true);
    expect(getProfile().homeStoreId).toBe(2);
    // Already resolved: nothing changes.
    expect(adoptHomeStore(stores)).toBe(false);
  });

  it("clearLocalData removes every key the secondary screens own", () => {
    updateProfile({ radiusKm: 7 });
    window.localStorage.setItem("sc-list-v1", "{}");
    window.localStorage.setItem(STORAGE_KEYS.shopping, "{}");
    window.localStorage.setItem(STORAGE_KEYS.savings, "[]");
    window.localStorage.setItem("sc-theme", "dark");
    clearLocalData();
    for (const key of [...Object.values(STORAGE_KEYS), PROFILE_KEY, "sc-list-v1"]) {
      expect(window.localStorage.getItem(key), key).toBeNull();
    }
    // The theme is a device display setting, not personal data.
    expect(window.localStorage.getItem("sc-theme")).toBe("dark");
  });
});
