import { describe, expect, it } from "vitest";
import { formatDistance, formatPrice, formatStoreDistance } from "./format";

const NBSP = "\u00A0";

describe("formatPrice", () => {
  it.each([
    [389, `₪${NBSP}389`],
    ["389.00", `₪${NBSP}389`],
    ["6.9", `₪${NBSP}6.90`],
    [1.726, `₪${NBSP}1.73`],
    [1234.5, `₪${NBSP}1,234.50`],
    [-5, `\u2212₪${NBSP}5`],
    [0, `₪${NBSP}0`],
  ])("formats %s", (input, expected) => {
    expect(formatPrice(input)).toBe(expected);
  });

  it("forces two decimals when asked", () => {
    expect(formatPrice(4.5, 2)).toBe(`₪${NBSP}4.50`);
    expect(formatPrice(389, 2)).toBe(`₪${NBSP}389.00`);
  });

  it("does not throw on garbage", () => {
    expect(formatPrice("abc")).toBe(`₪${NBSP}—`);
  });
});

describe("formatDistance", () => {
  it("uses meters below 1 km and one decimal above", () => {
    expect(formatDistance(800)).toBe("800 מ'");
    expect(formatDistance(4200)).toBe('4.2 ק"מ');
  });
});

describe("formatStoreDistance (approximate distances)", () => {
  it("leaves an exact distance exactly as it was", () => {
    expect(formatStoreDistance({ distance_m: 4200, distance_approximate: false })).toBe('4.2 ק"מ');
    expect(formatStoreDistance({ distance_m: 4200 })).toBe('4.2 ק"מ');
    expect(formatStoreDistance({ distance_m: 4200, distance_approximate: null }, "ar")).toBe(
      "4.2 كم",
    );
  });

  it("marks an approximate one with the prefix and the words, in both languages", () => {
    const store = { distance_m: 3600, distance_approximate: true };
    expect(formatStoreDistance(store)).toBe('כ־3.6 ק"מ · מיקום משוער');
    expect(formatStoreDistance(store, "ar")).toBe("نحو 3.6 كم · الموقع تقريبي");
    expect(formatStoreDistance({ ...store, distance_m: 800 })).toBe("כ־800 מ' · מיקום משוער");
  });

  it("can keep only the prefix when the note is shown once elsewhere", () => {
    expect(
      formatStoreDistance({ distance_m: 3600, distance_approximate: true }, "he", { note: false }),
    ).toBe('כ־3.6 ק"מ');
  });

  it("never shows 0 as a measured distance for a store without a point", () => {
    expect(formatStoreDistance({ distance_m: 0, distance_approximate: true })).toBe("מיקום משוער");
    expect(formatStoreDistance({ distance_m: 0, distance_approximate: true }, "ar")).toBe(
      "الموقع تقريبي",
    );
  });
});
