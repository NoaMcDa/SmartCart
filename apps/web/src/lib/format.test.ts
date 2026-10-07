import { describe, expect, it } from "vitest";
import { formatDistance, formatPrice } from "./format";

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
