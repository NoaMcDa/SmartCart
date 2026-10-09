import { DEFAULT_LOCALE, INTL_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { appMessages } from "@/i18n/messages/app";
import { formatMessages } from "@/i18n/messages/format";

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

/** HH:MM in Israel time (the "היום 06:40" style is screen-specific). Latin digits in both locales. */
export function formatTime(iso: string, locale: Locale = DEFAULT_LOCALE): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(INTL_LOCALE[locale], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Jerusalem",
  });
}

/**
 * A canonical product's display name: `display_name_ar` in Arabic when the API has one (machine
 * drafted, pending native review), otherwise the Hebrew name. Hebrew is always the fallback.
 */
export function productName(
  canonical: { display_name_he: string; display_name_ar?: string | null } | null | undefined,
  locale: Locale = DEFAULT_LOCALE,
): string {
  if (!canonical) return "";
  if (locale === "ar" && canonical.display_name_ar) return canonical.display_name_ar;
  return canonical.display_name_he;
}

/**
 * A list's name in the UI language. The default list is stored with its Hebrew name
 * ("הקנייה השבועית"); in Arabic it reads as the Arabic weekly shop. A name the person typed is
 * returned as it is.
 */
export function listNameLabel(name: string, locale: Locale = DEFAULT_LOCALE): string {
  if (locale !== DEFAULT_LOCALE && name === translate(appMessages, DEFAULT_LOCALE, "weeklyShop")) {
    return translate(appMessages, locale, "weeklyShop");
  }
  return name;
}

/**
 * The canonical's name for a priced item, a swap suggestion or a price history: the product the
 * shopper asked for, not the shelf label. `display_name_he` on those is the chain's own item name
 * and stays Hebrew; use it where the UI shows what the shelf says, and this where it names the
 * product generically.
 */
export function itemProductName(
  item: { display_name_he?: string | null; canonical_name_ar?: string | null },
  locale: Locale = DEFAULT_LOCALE,
): string {
  if (locale === "ar" && item.canonical_name_ar) return item.canonical_name_ar;
  return item.display_name_he ?? "";
}

/** Distance in meters as km: 4200 -> "4.2 ק"מ", 800 -> "800 מ'" (Arabic: "4.2 كم", "800 م"). */
export function formatDistance(meters: number, locale: Locale = DEFAULT_LOCALE): string {
  if (meters < 1000) {
    return translate(formatMessages, locale, "meters", { n: Math.round(meters) });
  }
  return translate(formatMessages, locale, "kilometers", { n: (meters / 1000).toFixed(1) });
}
