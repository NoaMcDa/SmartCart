import { describe, expect, it } from "vitest";
import { checkBarcode, checkDigit, isValidEan } from "./barcode";
import { classifyCameraError } from "./camera";
import { pickStore, type ScanStoreOption } from "./stores";

describe("EAN check digits", () => {
  it("accepts real EAN-13 and EAN-8 codes", () => {
    expect(isValidEan("5901234123457")).toBe(true);
    expect(isValidEan("4006381333931")).toBe(true);
    expect(isValidEan("96385074")).toBe(true);
    expect(isValidEan("73513537")).toBe(true);
  });

  it("rejects a wrong check digit, wrong lengths and non-digits", () => {
    expect(isValidEan("5901234123458")).toBe(false);
    expect(isValidEan("590123412345")).toBe(false); // 12 digits (UPC-A) is out of scope
    expect(isValidEan("59012341234570")).toBe(false);
    expect(isValidEan("59012341234a7")).toBe(false);
    expect(isValidEan("")).toBe(false);
  });

  it("computes the check digit from the body", () => {
    expect(checkDigit("590123412345")).toBe(7);
    expect(checkDigit("9638507")).toBe(4);
  });
});

describe("manual entry cleanup", () => {
  it("strips spaces, dashes and bidi marks, and reads Arabic-Indic digits", () => {
    expect(checkBarcode(" 5901234 123457 ")).toEqual({ ok: true, code: "5901234123457" });
    expect(checkBarcode("590-1234-123457")).toEqual({ ok: true, code: "5901234123457" });
    expect(checkBarcode("‎5901234123457‏")).toEqual({ ok: true, code: "5901234123457" });
    expect(checkBarcode("٩٦٣٨٥٠٧٤")).toEqual({ ok: true, code: "96385074" });
  });

  it("says what is wrong", () => {
    expect(checkBarcode("")).toEqual({ ok: false, reason: "empty" });
    expect(checkBarcode("12ab")).toEqual({ ok: false, reason: "digits" });
    expect(checkBarcode("123456")).toEqual({ ok: false, reason: "length" });
    expect(checkBarcode("5901234123450")).toEqual({ ok: false, reason: "checksum" });
  });
});

describe("camera errors", () => {
  it("maps browser errors to what the screen says", () => {
    expect(classifyCameraError({ name: "NotAllowedError" })).toBe("denied");
    expect(classifyCameraError({ name: "SecurityError" })).toBe("denied");
    expect(classifyCameraError({ name: "NotFoundError" })).toBe("no-camera");
    expect(classifyCameraError({ name: "NotReadableError" })).toBe("busy");
    expect(classifyCameraError(new Error("boom"))).toBe("unsupported");
    expect(classifyCameraError(null)).toBe("unsupported");
  });
});

describe("store choice", () => {
  const option = (storeId: number, distance: number): ScanStoreOption => ({
    storeId,
    label: `סניף ${storeId}`,
    ref: {
      store_id: storeId,
      chain_id: "c",
      chain_name: "ר",
      store_name: "ס",
      channel: "physical",
      distance_m: distance,
      distance_approximate: false,
    },
  });
  const options = [option(101, 4200), option(102, 5100), option(103, 1100)];

  it("prefers the remembered store, then the home store, then the nearest", () => {
    expect(pickStore(options, 102, 103)).toBe(102);
    expect(pickStore(options, 999, 101)).toBe(101);
    expect(pickStore(options, null, null)).toBe(103);
    expect(pickStore([], null, 103)).toBeNull();
  });
});
