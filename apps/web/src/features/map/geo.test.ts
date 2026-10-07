import { describe, expect, it } from "vitest";
import { compareFixture } from "@/mocks/fixtures";
import { circleRing, destinationPoint, distanceM, storePosition } from "./geo";

const modiin = { lat: 31.897, lon: 35.01 };

describe("geo helpers", () => {
  it("destinationPoint and distanceM agree", () => {
    for (const bearing of [0, 45, 90, 180, 270, 333]) {
      const p = destinationPoint(modiin, bearing, 4200);
      expect(distanceM(modiin, p)).toBeCloseTo(4200, 0);
    }
    // North raises the latitude, east raises the longitude.
    expect(destinationPoint(modiin, 0, 1000).lat).toBeGreaterThan(modiin.lat);
    expect(destinationPoint(modiin, 90, 1000).lon).toBeGreaterThan(modiin.lon);
  });

  it("circleRing is closed and every point sits at the radius", () => {
    const ring = circleRing(modiin, 5000, 36);
    expect(ring[0]).toEqual(ring.at(-1));
    for (const [lon, lat] of ring) {
      expect(distanceM(modiin, { lat, lon })).toBeCloseTo(5000, 0);
    }
  });

  it("places a store at its real distance, flagged approximate, deterministically", () => {
    for (const store of compareFixture().stores) {
      const pos = storePosition(store, modiin);
      expect(pos.approximate).toBe(true);
      expect(distanceM(modiin, pos)).toBeCloseTo(store.distance_m, 0);
      expect(storePosition(store, modiin)).toEqual(pos);
    }
    // Different stores do not stack on the same bearing.
    const [a, b] = compareFixture().stores.map((s) => storePosition(s, modiin));
    expect(a).not.toEqual(b);
  });

  it("uses real coordinates when the API provides them", () => {
    const store = { ...compareFixture().stores[0]!, lat: 31.9, lon: 35.02 };
    expect(storePosition(store, modiin)).toEqual({ lat: 31.9, lon: 35.02, approximate: false });
  });
});
