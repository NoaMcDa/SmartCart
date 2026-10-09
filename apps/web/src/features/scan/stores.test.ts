import { describe, expect, it } from "vitest";
import type { StoreRef } from "@/api/client";
import { scanOptionText, type ScanStoreOption } from "./stores";

const ref = (over: Partial<StoreRef> = {}): StoreRef => ({
  store_id: 104,
  chain_id: "7290803800003",
  chain_name: "יוחננוף",
  store_name: "מודיעין",
  channel: "physical",
  distance_m: 3600,
  geo_precision: "locality",
  distance_approximate: true,
  ...over,
});

const option = (r: StoreRef | null): ScanStoreOption => ({
  storeId: r?.store_id ?? 1,
  label: r ? `${r.chain_name} · ${r.store_name}` : "הסופר שלי",
  ref: r,
});

describe("scanOptionText", () => {
  it("shows chain, store and an approximate distance in Hebrew", () => {
    expect(scanOptionText(option(ref()), "he")).toBe('יוחננוף · מודיעין · כ־3.6 ק"מ · מיקום משוער');
  });

  it("shows an exact distance with no note", () => {
    expect(
      scanOptionText(option(ref({ distance_approximate: false, geo_precision: "address" })), "he"),
    ).toBe('יוחננוף · מודיעין · 3.6 ק"מ');
  });

  it("writes the chain in Latin letters and the city in Arabic in Arabic", () => {
    const text = scanOptionText(option(ref()), "ar");
    expect(text).toMatch(/^Yochananof · /);
    expect(text).not.toMatch(/[֐-׿]/);
    expect(text).toContain("نحو 3.6 كم · الموقع تقريبي");
  });

  it("leaves an option with no store behind it as its label", () => {
    expect(scanOptionText(option(null), "he")).toBe("הסופר שלי");
  });
});
