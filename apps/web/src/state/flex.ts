/**
 * Flexibility levels (D4): smart defaults per category, the user's remembered category defaults,
 * and the per-category copy and soft attributes the flexibility sheet shows.
 */
import type { CanonicalRef, FlexLevel } from "@/api/client";

export type FlexDefaults = Record<string, FlexLevel>;

/**
 * Smart defaults by taxonomy node (data/taxonomy.yaml ids). Cosmetics, toiletries, health and baby
 * products default to the exact product (people are loyal to the specific item there); staples
 * fall through to the server's level, which is "any brand" unless the user saved something else.
 */
export const SMART_DEFAULTS: FlexDefaults = {
  toiletries: "exact",
  health: "exact",
  baby: "exact",
};

const LEVELS: ReadonlySet<string> = new Set(["exact", "any_brand", "close"]);

export function isFlexLevel(value: unknown): value is FlexLevel {
  return typeof value === "string" && LEVELS.has(value);
}

/** "dairy.milk.fresh" -> ["dairy.milk.fresh", "dairy.milk", "dairy"]. */
export function taxonomyAncestors(taxonomyId: string): string[] {
  const parts = taxonomyId.split(".");
  return parts.map((_, i) => parts.slice(0, parts.length - i).join("."));
}

/** First match of the node or its ancestors in `defaults`. */
export function lookupDefault(taxonomyId: string, defaults: FlexDefaults): FlexLevel | undefined {
  for (const id of taxonomyAncestors(taxonomyId)) {
    const level = defaults[id];
    if (isFlexLevel(level)) return level;
  }
  return undefined;
}

/**
 * The level a new row starts with: the user's remembered category default first, then the smart
 * default for the category, then what /parse-list returned (the server applies the same
 * flex_defaults we send, and falls back to any_brand).
 */
export function resolveFlexLevel(
  taxonomyId: string | null | undefined,
  userDefaults: FlexDefaults,
  serverLevel: FlexLevel | undefined,
): FlexLevel {
  if (taxonomyId) {
    const user = lookupDefault(taxonomyId, userDefaults);
    if (user) return user;
    const smart = lookupDefault(taxonomyId, SMART_DEFAULTS);
    if (smart) return smart;
  }
  return serverLevel ?? "any_brand";
}

/** The leaf category name ("חלב"), used in "remember this for all milk". */
export function categoryLeaf(canonical: CanonicalRef | null | undefined): string | null {
  const path = canonical?.category_path_he ?? [];
  return path.length ? (path[path.length - 1] ?? null) : null;
}

/** The department (first level of the path), used to group list rows. */
export function department(canonical: CanonicalRef | null | undefined): string {
  return canonical?.category_path_he?.[0] ?? "שונות";
}

/** "זכרי בחירה זו לכל סוגי החלב". One-word categories take the definite article. */
export function rememberLabel(canonical: CanonicalRef | null | undefined): string {
  const leaf = categoryLeaf(canonical);
  if (!leaf) return "זכרי בחירה זו לכל המוצרים מהסוג הזה";
  return /\s/.test(leaf) ? `זכרי בחירה זו לכל סוגי ${leaf}` : `זכרי בחירה זו לכל סוגי ה${leaf}`;
}

export type LevelCopy = { explanation: string; example: string };

const GENERIC_COPY: Record<FlexLevel, LevelCopy> = {
  exact: {
    explanation: "רק הברקוד שבחרת, בלי החלפות.",
    example: "לדוגמה: אותו יצרן, אותה אריזה ואותו גודל.",
  },
  any_brand: {
    explanation: "אותו מוצר מכל יצרן, כולל מותג פרטי. התכונות החשובות נשמרות.",
    example: "לדוגמה: מותג פרטי במקום מותג מוכר, באותו גודל ובאותו סוג.",
  },
  close: {
    explanation: "גם גודל, אריזה או הרכב קצת שונים. תמיד מסומן כתחליף.",
    example: "לדוגמה: אריזה גדולה יותר או טעם דומה, עם הסבר מה שונה.",
  },
};

/** Category-specific copy from the Flexibility artboard. Keys are taxonomy nodes. */
const CATEGORY_COPY: Record<string, Partial<Record<FlexLevel, LevelCopy>>> = {
  "dairy.milk": {
    exact: {
      explanation: "רק הברקוד שבחרת.",
      example: "לדוגמה: תנובה, 3%, קרטון 1 ליטר.",
    },
    any_brand: {
      explanation: "אותו מוצר מכל יצרן.",
      example: "תנובה, טרה, יטבתה, מותג פרטי. נשמר: 3% שומן, טרי, 1 ליטר.",
    },
    close: {
      explanation: "גם אחוז שומן, אריזה או גודל אחרים. תמיד מסומן כתחליף.",
      example: "לדוגמה: 1% או 2%, שקית במקום קרטון.",
    },
  },
};

export function levelCopy(taxonomyId: string | null | undefined, level: FlexLevel): LevelCopy {
  if (taxonomyId) {
    for (const id of taxonomyAncestors(taxonomyId)) {
      const copy = CATEGORY_COPY[id]?.[level];
      if (copy) return copy;
    }
  }
  return GENERIC_COPY[level];
}

/**
 * Soft attributes the user may allow to differ, by category. The API does not expose category
 * attribute schemas yet, so the lists live here; keys are stored with the list item.
 */
const SOFT_ATTRIBUTES: Record<string, ReadonlyArray<{ key: string; label: string }>> = {
  "dairy.milk": [
    { key: "pack_size", label: "גודל אריזה אחר" },
    { key: "packaging", label: "קרטון או שקית" },
    { key: "fat_pct", label: "אחוז שומן אחר" },
  ],
  dairy: [
    { key: "pack_size", label: "גודל אריזה אחר" },
    { key: "fat_pct", label: "אחוז שומן אחר" },
  ],
  produce: [{ key: "variety", label: "זן אחר" }],
};

const GENERIC_SOFT: ReadonlyArray<{ key: string; label: string }> = [
  { key: "pack_size", label: "גודל אריזה אחר" },
  { key: "packaging", label: "סוג אריזה אחר" },
  { key: "flavor", label: "טעם או גרסה דומים" },
];

export function softAttributes(taxonomyId: string | null | undefined) {
  if (taxonomyId) {
    for (const id of taxonomyAncestors(taxonomyId)) {
      const list = SOFT_ATTRIBUTES[id];
      if (list) return list;
    }
  }
  return GENERIC_SOFT;
}
