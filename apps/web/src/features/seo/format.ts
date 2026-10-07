import type { BaseUnit } from "./types";

const DATE_FORMAT = new Intl.DateTimeFormat("he-IL", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Asia/Jerusalem",
});

/** "7 באוקטובר 2026" for an ISO timestamp, in Israel time. */
export function formatDateHe(iso: string): string {
  return DATE_FORMAT.format(new Date(iso));
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

/** "2026-10" -> "אוקטובר 2026". */
export function monthLabelHe(month: string): string {
  const [year, mm] = month.split("-");
  return `${MONTHS_HE[Number(mm) - 1] ?? mm} ${year}`;
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

export function attrLabel(key: string): string {
  return ATTR_LABELS[key] ?? key;
}

/** Display form of an attribute value; fat is a percentage, the rest map to Hebrew words. */
export function attrValue(key: string, value: string | number): string {
  if (key === "fat_pct") return `${value}%`;
  if (key === "state") return STATE_VALUES[String(value)] ?? String(value);
  if (key === "flavor") return FLAVOR_VALUES[String(value)] ?? String(value);
  return String(value);
}

/** Share as a percentage, rounded DOWN to one decimal so a number is never overstated. */
export function percentDown(share: number): string {
  return `${(Math.floor(share * 1000 + 1e-9) / 10).toFixed(1)}%`;
}
