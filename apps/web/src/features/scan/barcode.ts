/**
 * EAN-13 and EAN-8 helpers (issue #39). A scan is accepted only when its check digit is right, so a
 * misread never turns into a wrong product (D5: precision over recall).
 */
import type { ScanMessageKey } from "@/i18n/messages/scan";

export type BarcodeCheck =
  { ok: true; code: string } | { ok: false; reason: "empty" | "digits" | "length" | "checksum" };

/** The check digit for the digits before it (7 for EAN-8, 12 for EAN-13). */
export function checkDigit(body: string): number {
  let sum = 0;
  // Weights alternate 3, 1 starting from the digit next to the check digit.
  for (let i = 0; i < body.length; i += 1) {
    const digit = Number(body[body.length - 1 - i]);
    sum += digit * (i % 2 === 0 ? 3 : 1);
  }
  return (10 - (sum % 10)) % 10;
}

export function isValidEan(code: string): boolean {
  if (!/^\d+$/.test(code) || (code.length !== 13 && code.length !== 8)) return false;
  return checkDigit(code.slice(0, -1)) === Number(code.slice(-1));
}

/** Cleans what a person typed or a scanner read (spaces, dashes, Arabic-Indic digits) and checks it. */
export function checkBarcode(raw: string): BarcodeCheck {
  const code = raw
    .replace(/[\s\-‎‏]/g, "")
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
  if (code === "") return { ok: false, reason: "empty" };
  if (!/^\d+$/.test(code)) return { ok: false, reason: "digits" };
  if (code.length !== 13 && code.length !== 8) return { ok: false, reason: "length" };
  if (!isValidEan(code)) return { ok: false, reason: "checksum" };
  return { ok: true, code };
}

/** Message key (`scanMessages`) per failed barcode check; the screen translates it. */
export const BARCODE_ERRORS = {
  empty: "errEmpty",
  digits: "errDigits",
  length: "errLength",
  checksum: "errChecksum",
} as const satisfies Record<Exclude<BarcodeCheck, { ok: true }>["reason"], ScanMessageKey>;
