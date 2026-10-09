import { INTL_LOCALE, type Locale } from "@/i18n/locales";
import type { BaseUnit } from "./types";

const DATE_FORMAT = new Intl.DateTimeFormat(INTL_LOCALE.he, {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Asia/Jerusalem",
});
const PARTS_FORMAT = new Intl.DateTimeFormat(INTL_LOCALE.ar, {
  day: "numeric",
  month: "numeric",
  year: "numeric",
  timeZone: "Asia/Jerusalem",
});

/**
 * Arabic month names as Arab citizens of Israel write them (the Levantine names; Intl would give
 * the Gulf names "أكتوبر", "نوفمبر").
 */
const MONTHS_AR = [
  "كانون الثاني",
  "شباط",
  "آذار",
  "نيسان",
  "أيار",
  "حزيران",
  "تموز",
  "آب",
  "أيلول",
  "تشرين الأول",
  "تشرين الثاني",
  "كانون الأول",
] as const;

/** "7 באוקטובר 2026" / "7 تشرين الأول 2026" for an ISO timestamp, in Israel time. */
export function formatDate(iso: string, locale: Locale = "he"): string {
  if (locale === "he") return DATE_FORMAT.format(new Date(iso));
  const parts = PARTS_FORMAT.formatToParts(new Date(iso));
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${part("day")} ${MONTHS_AR[Number(part("month")) - 1] ?? part("month")} ${part("year")}`;
}

/** "7 באוקטובר 2026" for an ISO timestamp, in Israel time. */
export function formatDateHe(iso: string): string {
  return formatDate(iso, "he");
}

/** `2026-10-07` for the datetime attribute of <time>. */
export function isoDate(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Jerusalem" }).format(new Date(iso));
}

const MONTHS_HE = [
  "ינואר",
  "פברואר",
  "מרץ",
  "אפריל",
  "מאי",
  "יוני",
  "יולי",
  "אוגוסט",
  "ספטמבר",
  "אוקטובר",
  "נובמבר",
  "דצמבר",
] as const;

/** "2026-10" -> "אוקטובר 2026" / "تشرين الأول 2026". */
export function monthLabel(month: string, locale: Locale = "he"): string {
  const [year, mm] = month.split("-");
  const names = locale === "ar" ? MONTHS_AR : MONTHS_HE;
  return `${names[Number(mm) - 1] ?? mm} ${year}`;
}

/** "2026-10" -> "אוקטובר 2026". */
export function monthLabelHe(month: string): string {
  return monthLabel(month, "he");
}

/** The unit a price is quoted per, as a noun phrase ("100 גרם"). */
export const UNIT_LABEL: Record<BaseUnit, string> = {
  "100g": "100 גרם",
  "100ml": "100 מ״ל",
  unit: "יחידה",
  kg: "ק״ג",
};

/** "per 100 g" as a phrase: "מחיר ל-100 גרם", "מחיר ליחידה". */
export const PER_UNIT: Record<BaseUnit, string> = {
  "100g": "ל-100 גרם",
  "100ml": "ל-100 מ״ל",
  unit: "ליחידה",
  kg: "לק״ג",
};

const UNIT_LABEL_AR: Record<BaseUnit, string> = {
  "100g": "100 غرام",
  "100ml": "100 مل",
  unit: "وحدة",
  kg: "كغ",
};

const PER_UNIT_AR: Record<BaseUnit, string> = {
  "100g": "لكل 100 غرام",
  "100ml": "لكل 100 مل",
  unit: "للوحدة",
  kg: "لكل كغ",
};

export function unitLabel(unit: BaseUnit, locale: Locale = "he"): string {
  return locale === "ar" ? UNIT_LABEL_AR[unit] : UNIT_LABEL[unit];
}

export function perUnit(unit: BaseUnit, locale: Locale = "he"): string {
  return locale === "ar" ? PER_UNIT_AR[unit] : PER_UNIT[unit];
}

/** Hebrew names for the critical attribute keys and values the catalog uses. */
const ATTR_LABELS: Record<string, string> = {
  fat_pct: "אחוז שומן",
  state: "מצב המוצר",
  flavor: "טעם",
};

const STATE_VALUES: Record<string, string> = {
  fresh: "טרי",
  frozen: "קפוא",
  chilled: "מקורר",
  canned: "משומר",
  dry: "יבש",
};

const FLAVOR_VALUES: Record<string, string> = {
  plain: "טבעי",
  chocolate: "שוקולד",
  chicken: "עוף",
  grill: "גריל",
  salted: "מלוח",
  milk: "חלב",
  strawberry: "תות",
  cheese: "גבינה",
  dark: "מריר",
  peach: "אפרסק",
  potato: "תפוח אדמה",
  vanilla: "וניל",
  onion: "בצל",
  lemon: "לימון",
};

const ATTR_LABELS_AR: Record<string, string> = {
  fat_pct: "نسبة الدسم",
  state: "حالة المنتج",
  flavor: "النكهة",
};

const STATE_VALUES_AR: Record<string, string> = {
  fresh: "طازج",
  frozen: "مجمّد",
  chilled: "مبرّد",
  canned: "معلّب",
  dry: "جاف",
};

const FLAVOR_VALUES_AR: Record<string, string> = {
  plain: "طبيعي",
  chocolate: "شوكولاتة",
  chicken: "دجاج",
  grill: "مشاوي",
  salted: "مالح",
  milk: "حليب",
  strawberry: "فراولة",
  cheese: "جبنة",
  dark: "داكنة",
  peach: "خوخ",
  potato: "بطاطا",
  vanilla: "فانيليا",
  onion: "بصل",
  lemon: "ليمون",
};

export function attrLabel(key: string, locale: Locale = "he"): string {
  return (locale === "ar" ? ATTR_LABELS_AR : ATTR_LABELS)[key] ?? key;
}

/** Display form of an attribute value; fat is a percentage, the rest map to words. */
export function attrValue(key: string, value: string | number, locale: Locale = "he"): string {
  const ar = locale === "ar";
  if (key === "fat_pct") return `${value}%`;
  if (key === "state") return (ar ? STATE_VALUES_AR : STATE_VALUES)[String(value)] ?? String(value);
  if (key === "flavor") {
    return (ar ? FLAVOR_VALUES_AR : FLAVOR_VALUES)[String(value)] ?? String(value);
  }
  return String(value);
}

/** Share as a percentage, rounded DOWN to one decimal so a number is never overstated. */
export function percentDown(share: number): string {
  return `${(Math.floor(share * 1000 + 1e-9) / 10).toFixed(1)}%`;
}
