/** Small geodesy helpers for the map screen. Pure functions, unit tested. */
import type { StoreResult } from "@/api/client";

const EARTH_RADIUS_M = 6_371_008.8;
const rad = (deg: number) => (deg * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

export type LatLon = { lat: number; lon: number };

/** The point `distanceM` metres from `origin` along `bearingDeg` (0 = north, 90 = east). */
export function destinationPoint(origin: LatLon, bearingDeg: number, distanceM: number): LatLon {
  const d = distanceM / EARTH_RADIUS_M;
  const brg = rad(bearingDeg);
  const lat1 = rad(origin.lat);
  const lon1 = rad(origin.lon);
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(d) + Math.cos(lat1) * Math.sin(d) * Math.cos(brg),
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(brg) * Math.sin(d) * Math.cos(lat1),
      Math.cos(d) - Math.sin(lat1) * Math.sin(lat2),
    );
  return { lat: deg(lat2), lon: ((deg(lon2) + 540) % 360) - 180 };
}

/** Great-circle distance in metres (haversine). */
export function distanceM(a: LatLon, b: LatLon): number {
  const dLat = rad(b.lat - a.lat);
  const dLon = rad(b.lon - a.lon);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

/** A closed GeoJSON ring approximating the radius circle, [lon, lat] pairs. */
export function circleRing(center: LatLon, radiusM: number, steps = 72): [number, number][] {
  const ring: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const p = destinationPoint(center, (i / steps) * 360, radiusM);
    ring.push([p.lon, p.lat]);
  }
  return ring;
}

/**
 * Radius of the area drawn around a store placed only at its town centre (`geo_precision` is
 * `locality`). It is a visual size for "somewhere around here", not a promise that the branch is
 * inside it: the API says such a point can be a few km from the branch.
 */
export const APPROX_AREA_M = 2000;

export type StorePosition = LatLon & {
  /** True when the position is placed from the distance only, not from real coordinates. */
  approximate: boolean;
};

const GOLDEN_ANGLE = 137.508;

/**
 * Where to draw a store. `StoreResult.lat` and `.lon` (phase 2) are the store's real coordinates
 * and are used whenever both are finite numbers. They are null until the store's address is
 * geocoded; only then is the store placed at its real distance from the user on a bearing spread
 * by store id (so pins do not stack) and flagged `approximate`, so the screen says the direction
 * is not exact.
 */
export function storePosition(
  store: Pick<StoreResult, "store_id" | "distance_m" | "lat" | "lon">,
  user: LatLon,
): StorePosition {
  const { lat, lon } = store;
  if (
    typeof lat === "number" &&
    typeof lon === "number" &&
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    Math.abs(lat) <= 90 &&
    Math.abs(lon) <= 180
  ) {
    return { lat, lon, approximate: false };
  }
  const bearing = (store.store_id * GOLDEN_ANGLE) % 360;
  return { ...destinationPoint(user, bearing, store.distance_m), approximate: true };
}
