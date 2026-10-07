/** Non-breaking space placed between the shekel sign and the digits (CLAUDE.md conventions). */
export const NBSP = "\u00A0";
export const SHEKEL = "₪";

export type FractionDigits = 0 | 2 | "auto";

/**
 * Format a shekel amount as "₪ 389" / "₪ 6.90" (with a non-breaking space).
 * The API sends money as decimal strings ("389.00"); numbers are accepted too.
 * "auto" drops the agorot when the amount is whole, matching the artboards (₪389, ₪6.90).
 * Negative amounts keep the minus sign (U+2212) before the currency symbol.
 */
export function formatPrice(
  amount: number | string,
  fractionDigits: FractionDigits = "auto",
): string {
  const value = typeof amount === "string" ? Number.parseFloat(amount) : amount;
  if (!Number.isFinite(value)) return `${SHEKEL}${NBSP}—`;
  const abs = Math.abs(value);
  const digits =
    fractionDigits === "auto"
      ? Number.isInteger(Math.round(abs * 100) / 100)
        ? 0
        : 2
      : fractionDigits;
  const body = abs.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    useGrouping: true,
  });
  const sign = value < 0 && abs >= 0.005 ? "\u2212" : "";
  return `${sign}${SHEKEL}${NBSP}${body}`;
}

/** Hebrew relative-free timestamp: "היום 06:40" style is screen-specific; this returns HH:MM. */
export function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("he-IL", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Jerusalem",
  });
}

/** Distance in meters as Hebrew km: 4200 -> "4.2 ק"מ", 800 -> "800 מ'". */
export function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} מ'`;
  return `${(meters / 1000).toFixed(1)} ק"מ`;
}
