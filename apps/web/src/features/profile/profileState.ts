/**
 * The user's local profile: what onboarding collects and Profile edits. It is the single source
 * the optimizer inputs are built from (`toRequestInputs`), whether or not the user is signed in.
 * Signed in, `ProfileSync` mirrors it to PUT /me/profile.
 *
 * Privacy (D11): `setLocation` rounds to 3 decimals (about 100 m, neighborhood level) before the
 * value is stored, and `sanitizeProfile` rounds again on every read and write, so exact device
 * coordinates are never persisted.
 */
import { useSyncExternalStore } from "react";
import { saveShopperProfile } from "@/state/shopper";
import { resolveHomeStoreId } from "./chains";
import { STORAGE_KEYS, notifyStorageChange, subscribeStorage } from "./storage";

export type TravelMode = "car" | "walk_transit" | "delivery";
export type KosherLevel = "regular" | "mehadrin" | "badatz";

export type LocalLocation = {
  lat: number;
  lon: number;
  city: string | null;
  neighborhood: string | null;
  source: "device" | "manual";
};

export type LocalProfile = {
  version: 1;
  /** True once the onboarding flow was finished or skipped to the end. */
  onboardingDone: boolean;
  /** Explicit consent to use and store a neighborhood-level location (D11). */
  consentLocation: boolean;
  location: LocalLocation | null;
  /** 1 to 15 km. */
  radiusKm: number;
  /** "הסופר שלי": the chain the net saving is measured against (D7). */
  homeChainId: string | null;
  /** Resolved store id when known (see resolveHomeStoreId in chains.ts). */
  homeStoreId: number | null;
  /** Club names (chain names). */
  clubs: string[];
  travelMode: TravelMode;
  /** 0 to 50 ILS. */
  extraStopValue: number;
  costPerKm: number;
  diet: {
    vegan: boolean;
    glutenFree: boolean;
    kosherLevel: KosherLevel | null;
    /** Allergen keys, see ALLERGENS in dietOptions.ts. */
    allergens: string[];
  };
  updatedAt: string | null;
};

export const RADIUS_MIN_KM = 1;
export const RADIUS_MAX_KM = 15;
export const EXTRA_STOP_MIN = 0;
export const EXTRA_STOP_MAX = 50;

export const DEFAULT_PROFILE: LocalProfile = {
  version: 1,
  onboardingDone: false,
  consentLocation: false,
  location: null,
  radiusKm: 5,
  homeChainId: null,
  homeStoreId: null,
  clubs: [],
  travelMode: "car",
  extraStopValue: 25,
  costPerKm: 1.2,
  diet: { vegan: false, glutenFree: false, kosherLevel: null, allergens: [] },
  updatedAt: null,
};

/** Rounds a coordinate to 3 decimals (about 100 m), D11. */
export function roundCoord(value: number): number {
  return Math.round(value * 1000) / 1000;
}

const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));
const strings = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
const num = (v: unknown, fallback: number) =>
  typeof v === "number" && Number.isFinite(v) ? v : fallback;

/** Validates and clamps anything read from storage; rounds the location. Never throws. */
export function sanitizeProfile(raw: unknown): LocalProfile {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const loc = r.location as Record<string, unknown> | null | undefined;
  const consent = r.consentLocation === true;
  const location: LocalLocation | null =
    consent &&
    loc &&
    typeof loc === "object" &&
    typeof loc.lat === "number" &&
    typeof loc.lon === "number" &&
    Number.isFinite(loc.lat) &&
    Number.isFinite(loc.lon)
      ? {
          lat: roundCoord(clamp(loc.lat, -90, 90)),
          lon: roundCoord(clamp(loc.lon, -180, 180)),
          city: typeof loc.city === "string" ? loc.city : null,
          neighborhood: typeof loc.neighborhood === "string" ? loc.neighborhood : null,
          source: loc.source === "device" ? "device" : "manual",
        }
      : null;
  const diet = (r.diet && typeof r.diet === "object" ? r.diet : {}) as Record<string, unknown>;
  const mode = r.travelMode;
  const kosher = diet.kosherLevel;
  return {
    version: 1,
    onboardingDone: r.onboardingDone === true,
    consentLocation: consent,
    location,
    radiusKm: clamp(
      Math.round(num(r.radiusKm, DEFAULT_PROFILE.radiusKm)),
      RADIUS_MIN_KM,
      RADIUS_MAX_KM,
    ),
    homeChainId: typeof r.homeChainId === "string" ? r.homeChainId : null,
    homeStoreId:
      typeof r.homeStoreId === "number" && Number.isInteger(r.homeStoreId) ? r.homeStoreId : null,
    clubs: strings(r.clubs),
    travelMode: mode === "walk_transit" || mode === "delivery" ? mode : "car",
    extraStopValue: clamp(
      Math.round(num(r.extraStopValue, DEFAULT_PROFILE.extraStopValue)),
      EXTRA_STOP_MIN,
      EXTRA_STOP_MAX,
    ),
    costPerKm: clamp(num(r.costPerKm, DEFAULT_PROFILE.costPerKm), 0, 10),
    diet: {
      vegan: diet.vegan === true,
      glutenFree: diet.glutenFree === true,
      kosherLevel:
        kosher === "regular" || kosher === "mehadrin" || kosher === "badatz" ? kosher : null,
      allergens: strings(diet.allergens),
    },
    updatedAt: typeof r.updatedAt === "string" ? r.updatedAt : null,
  };
}

// ---------------------------------------------------------------------------------------------
// Store (localStorage + same-tab notification), read through useSyncExternalStore.

let cachedRaw: string | null | undefined;
let cachedProfile: LocalProfile = DEFAULT_PROFILE;

export function getProfile(): LocalProfile {
  if (typeof window === "undefined") return DEFAULT_PROFILE;
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEYS.profile);
  } catch {
    raw = null;
  }
  if (raw === cachedRaw) return cachedProfile;
  cachedRaw = raw;
  if (raw === null) {
    cachedProfile = DEFAULT_PROFILE;
  } else {
    try {
      cachedProfile = sanitizeProfile(JSON.parse(raw));
    } catch {
      cachedProfile = DEFAULT_PROFILE;
    }
  }
  return cachedProfile;
}

/** Applies a patch, sanitizes (so the location is always rounded) and persists. */
export function updateProfile(
  patch: Partial<LocalProfile> | ((current: LocalProfile) => Partial<LocalProfile>),
): LocalProfile {
  const current = getProfile();
  const delta = typeof patch === "function" ? patch(current) : patch;
  const next = sanitizeProfile({ ...current, ...delta, updatedAt: new Date().toISOString() });
  try {
    window.localStorage.setItem(STORAGE_KEYS.profile, JSON.stringify(next));
  } catch {
    // Storage unavailable: keep the value in memory for this page view.
    cachedRaw = undefined;
    cachedProfile = next;
  }
  mirrorToShopper(next);
  notifyStorageChange();
  return next;
}

/**
 * The comparison screens (W4b) read where and how the user shops from `src/state/shopper.ts`
 * (`sc-profile-v1`, API Profile field names). Every change to the local profile is written there
 * too, so "changes affect the next comparison". Without a location the coordinates are null and
 * the comparison falls back to its default city; without a home chain the home store is an
 * explicit null (no baseline, no saving, D7).
 */
export function mirrorToShopper(p: LocalProfile): void {
  saveShopperProfile({
    neighborhood_lat: p.location?.lat ?? null,
    neighborhood_lon: p.location?.lon ?? null,
    city_label: p.location?.city ?? null,
    radius_m: p.radiusKm * 1000,
    home_store_id: p.homeStoreId,
    clubs: p.clubs,
    travel_mode: p.travelMode,
    cost_per_km: String(p.costPerKm),
    extra_stop_value: String(p.extraStopValue),
  });
}

/**
 * The only write path for a location: rounds to 3 decimals before anything is stored (D11) and
 * records the consent that makes storing it legitimate.
 */
export function setLocation(input: {
  lat: number;
  lon: number;
  city?: string | null;
  neighborhood?: string | null;
  source: "device" | "manual";
}): LocalProfile {
  return updateProfile({
    consentLocation: true,
    location: {
      lat: roundCoord(input.lat),
      lon: roundCoord(input.lon),
      city: input.city ?? null,
      neighborhood: input.neighborhood ?? null,
      source: input.source,
    },
  });
}

export function clearLocation(): LocalProfile {
  return updateProfile({ location: null, consentLocation: false });
}

export function toggleClub(profile: LocalProfile, club: string): string[] {
  return profile.clubs.includes(club)
    ? profile.clubs.filter((c) => c !== club)
    : [...profile.clubs, club];
}

export function useProfile(): LocalProfile {
  return useSyncExternalStore(subscribeStorage, getProfile, () => DEFAULT_PROFILE);
}

/** Forgets the in-memory cache (tests, and after clearLocalData). */
export function resetProfileCache(): void {
  cachedRaw = undefined;
  cachedProfile = DEFAULT_PROFILE;
}

// ---------------------------------------------------------------------------------------------
// Home store resolution

/**
 * Call with the stores of any compare result: when the user picked a home chain but no store id is
 * known yet, stores the nearest store of that chain, so the next request carries `home_store_id`
 * and the API can compute the net saving (D7). Returns true when it changed the profile.
 */
export function adoptHomeStore(
  stores: ReadonlyArray<{
    store_id: number;
    chain_id: string;
    chain_name: string;
    distance_m: number;
  }>,
): boolean {
  const current = getProfile();
  if (!current.homeChainId || current.homeStoreId !== null) return false;
  const id = resolveHomeStoreId(current.homeChainId, stores);
  if (id === null) return false;
  updateProfile({ homeStoreId: id });
  return true;
}
