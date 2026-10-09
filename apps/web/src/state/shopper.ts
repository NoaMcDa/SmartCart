/**
 * Where and how the user shops: location, radius, home store, clubs, travel. The comparison
 * screens read it; onboarding and Profile (W5) write it with `saveShopperProfile`.
 *
 * Stored in localStorage under PROFILE_KEY with the field names of the API `Profile` schema
 * (neighborhood_lat/lon, radius_m, home_store_id, clubs, travel_mode, cost_per_km,
 * extra_stop_value, max_stores) plus `city_label` for display, so a fetched /me/profile can be
 * stored as is. Missing fields fall back to defaults: Modi'in, 5 km, car, ₪25 per extra stop.
 * The home store falls back to the mock's (שופרסל דיל, id 103) only when the API mock is on; a
 * real build without a home store shows "set your store" instead of inventing a baseline (D7).
 */
import { useSyncExternalStore } from "react";
import { API_MOCK } from "@/api/config";
import type { OptimizeInput, Schemas } from "@/api/client";
import { cityLabelFor } from "@/features/profile/cities";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { stateMessages } from "@/i18n/messages/state";
import { readJson, writeJson } from "./storage";

export const PROFILE_KEY = "sc-profile-v1";

/** Modi'in city center, rounded to neighborhood precision (D11). The artboards' city. */
export const DEFAULT_LOCATION = { lat: 31.898, lon: 35.01 };
export const DEFAULT_CITY = translate(stateMessages, DEFAULT_LOCALE, "defaultCity");
export const MOCK_HOME_STORE_ID = 103;

export type StoredProfile = Partial<
  Pick<
    Schemas["Profile"],
    | "neighborhood_lat"
    | "neighborhood_lon"
    | "radius_m"
    | "home_store_id"
    | "clubs"
    | "travel_mode"
    | "cost_per_km"
    | "extra_stop_value"
    | "max_stores"
  >
> & { city_label?: string | null };

export type ShopperContext = {
  lat: number;
  lon: number;
  radiusM: number;
  cityLabel: string | null;
  homeStoreId: number | null;
  clubs: string[];
  travelMode: "car" | "walk_transit" | "delivery";
  costPerKm: number;
  extraStopValue: number;
  maxStores: number;
  /** True when nothing was stored and the defaults are in use. */
  usingDefaults: boolean;
};

const num = (v: unknown, fallback: number) => {
  const n = typeof v === "number" ? v : typeof v === "string" ? Number.parseFloat(v) : NaN;
  return Number.isFinite(n) ? n : fallback;
};

/** `locale` only changes `cityLabel` (a known city or the default city in Arabic); Hebrew by default. */
export function shopperFromStored(
  stored: StoredProfile | null,
  mock = API_MOCK,
  locale: Locale = DEFAULT_LOCALE,
): ShopperContext {
  const s = stored ?? {};
  const hasLocation =
    typeof s.neighborhood_lat === "number" && typeof s.neighborhood_lon === "number";
  // An explicit null means "no home store yet"; only a missing field takes the mock default.
  const homeStoreId =
    typeof s.home_store_id === "number"
      ? s.home_store_id
      : s.home_store_id === undefined && mock
        ? MOCK_HOME_STORE_ID
        : null;
  const mode = s.travel_mode;
  return {
    lat: hasLocation ? s.neighborhood_lat! : DEFAULT_LOCATION.lat,
    lon: hasLocation ? s.neighborhood_lon! : DEFAULT_LOCATION.lon,
    radiusM: Math.min(15000, Math.max(1000, num(s.radius_m, 5000))),
    cityLabel:
      s.city_label !== undefined && s.city_label !== null
        ? cityLabelFor(s.city_label, locale)
        : hasLocation
          ? null
          : translate(stateMessages, locale, "defaultCity"),
    homeStoreId,
    clubs: Array.isArray(s.clubs) ? s.clubs.filter((c) => typeof c === "string") : [],
    travelMode: mode === "walk_transit" || mode === "delivery" ? mode : "car",
    costPerKm: num(s.cost_per_km, 1.2),
    extraStopValue: num(s.extra_stop_value, 25),
    maxStores: Math.min(2, Math.max(1, Math.round(num(s.max_stores, 2)))),
    usingDefaults: stored === null,
  };
}

export function readShopper(): ShopperContext {
  return shopperFromStored(readJson<StoredProfile | null>(PROFILE_KEY, null));
}

let cached: { raw: string | null; ctx: ShopperContext } | null = null;
const listeners = new Set<() => void>();

function rawProfile(): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(PROFILE_KEY);
  } catch {
    return null;
  }
}

function snapshot(): ShopperContext {
  const raw = rawProfile();
  if (!cached || cached.raw !== raw) cached = { raw, ctx: readShopper() };
  return cached.ctx;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => {
    if (e.key === PROFILE_KEY) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/** Null during server rendering and hydration; the context once the client has read storage. */
export function useShopper(): ShopperContext | null {
  return useSyncExternalStore(subscribe, snapshot, () => null);
}

/** Merge and store profile fields (onboarding, Profile). */
export function saveShopperProfile(patch: StoredProfile): void {
  const prev = readJson<StoredProfile | null>(PROFILE_KEY, null) ?? {};
  writeJson(PROFILE_KEY, { ...prev, ...patch });
  for (const l of listeners) l();
}

/** The request fields /compare and /optimize take from the shopper context. */
export function shopperRequestFields(
  ctx: ShopperContext,
): Pick<OptimizeInput, "location" | "home_store_id" | "clubs" | "travel" | "max_stores"> {
  return {
    location: { lat: ctx.lat, lon: ctx.lon, radius_m: ctx.radiusM },
    home_store_id: ctx.homeStoreId,
    clubs: ctx.clubs,
    travel: {
      mode: ctx.travelMode,
      cost_per_km: ctx.costPerKm,
      extra_stop_value: ctx.extraStopValue,
    },
    max_stores: ctx.maxStores,
  };
}
