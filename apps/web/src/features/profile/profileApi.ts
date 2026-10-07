/**
 * Mapping between the local profile and the API's /me/profile, plus the calls. All of it needs a
 * signed-in user (the Supabase JWT is attached by features/auth/apiAuth). The local profile stays
 * the source of truth for the screens; these functions only mirror it.
 *
 * Encoding choices (the API has no columns for them yet):
 * - `diet_flags`: "vegan", "gluten_free" and "allergen:<key>" entries.
 * - `kosher_level`: "regular" | "mehadrin" | "badatz" or null.
 * - City and neighborhood text stay on the device; only the rounded coordinates go up, and only
 *   with `consent_location = true` (the API answers 422 otherwise).
 */
import { api, ApiError, type Schemas } from "@/api/client";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import type { LocalProfile } from "./profileState";

export type ServerProfile = Schemas["Profile"];
export type ProfileUpdate = Schemas["ProfileUpdate"];
type ThemePref = ProfileUpdate["theme"];

export function toProfileUpdate(
  local: LocalProfile,
  theme: ThemePref = "system",
  flexDefaults: Record<string, "exact" | "any_brand" | "close"> = {},
): ProfileUpdate {
  const share = local.consentLocation && local.location !== null;
  const dietFlags = [
    ...(local.diet.vegan ? ["vegan"] : []),
    ...(local.diet.glutenFree ? ["gluten_free"] : []),
    ...local.diet.allergens.map((a) => `allergen:${a}`),
  ];
  return {
    home_store_id: local.homeStoreId,
    radius_m: Math.round(local.radiusKm * 1000),
    clubs: local.clubs,
    travel_mode: local.travelMode,
    cost_per_km: local.costPerKm,
    extra_stop_value: local.extraStopValue,
    max_stores: 2,
    kosher_level: local.diet.kosherLevel,
    diet_flags: dietFlags,
    flex_defaults: flexDefaults,
    consent_location: share,
    neighborhood_lat: share ? local.location!.lat : null,
    neighborhood_lon: share ? local.location!.lon : null,
    theme,
  };
}

/** A local profile patch built from a stored server profile (only when `exists`). */
export function fromServerProfile(
  server: ServerProfile,
  local: LocalProfile,
): Partial<LocalProfile> {
  const flags = server.diet_flags ?? [];
  const lat = server.neighborhood_lat;
  const lon = server.neighborhood_lon;
  const kosher = server.kosher_level;
  const sameSpot = local.location && local.location.lat === lat && local.location.lon === lon;
  return {
    onboardingDone: true,
    consentLocation: server.consent_location,
    location:
      server.consent_location && typeof lat === "number" && typeof lon === "number"
        ? {
            lat,
            lon,
            city: sameSpot ? local.location!.city : null,
            neighborhood: sameSpot ? local.location!.neighborhood : null,
            source: sameSpot ? local.location!.source : "manual",
          }
        : null,
    radiusKm: Math.round(server.radius_m / 1000) || 1,
    homeStoreId: server.home_store_id ?? null,
    clubs: server.clubs ?? [],
    travelMode: server.travel_mode,
    extraStopValue: Number(server.extra_stop_value),
    costPerKm: Number(server.cost_per_km),
    diet: {
      vegan: flags.includes("vegan"),
      glutenFree: flags.includes("gluten_free"),
      kosherLevel:
        kosher === "regular" || kosher === "mehadrin" || kosher === "badatz" ? kosher : null,
      allergens: flags
        .filter((f) => f.startsWith("allergen:"))
        .map((f) => f.slice("allergen:".length)),
    },
  };
}

function check<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined || !result.response.ok) {
    throw new ApiError(result.response.status, result.error);
  }
  return result.data;
}

export async function fetchServerProfile(): Promise<ServerProfile> {
  ensureApiAuth();
  return check(await api.GET("/me/profile"));
}

export async function pushServerProfile(update: ProfileUpdate): Promise<ServerProfile> {
  ensureApiAuth();
  return check(await api.PUT("/me/profile", { body: update }));
}
