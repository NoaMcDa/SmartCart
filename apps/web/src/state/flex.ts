/**
 * Flexibility levels (D4): smart defaults per category, the user's remembered category defaults,
 * and the per-category copy and soft attributes the flexibility sheet shows.
 */
import type { CanonicalRef, FlexLevel } from "@/api/client";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { stateMessages } from "@/i18n/messages/state";

type StateKey = keyof (typeof stateMessages)["he"];

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
export function department(
  canonical: CanonicalRef | null | undefined,
  locale: Locale = DEFAULT_LOCALE,
): string {
  return canonical?.category_path_he?.[0] ?? translate(stateMessages, locale, "otherDepartment");
}

/** "זכרי בחירה זו לכל סוגי החלב". One-word categories take the definite article. */
export function rememberLabel(
  canonical: CanonicalRef | null | undefined,
  locale: Locale = DEFAULT_LOCALE,
): string {
  const leaf = categoryLeaf(canonical);
  if (!leaf) return translate(stateMessages, locale, "rememberGeneric");
  return translate(
    stateMessages,
    locale,
    /\s/.test(leaf) ? "rememberLeaf" : "rememberLeafDefinite",
    {
      leaf,
    },
  );
}

export type LevelCopy = { explanation: string; example: string };

type LevelCopyKeys = { explanation: StateKey; example: StateKey };

const GENERIC_COPY: Record<FlexLevel, LevelCopyKeys> = {
  exact: { explanation: "exactExplanation", example: "exactExample" },
  any_brand: { explanation: "anyBrandExplanation", example: "anyBrandExample" },
  close: { explanation: "closeExplanation", example: "closeExample" },
};

/** Category-specific copy from the Flexibility artboard. Keys are taxonomy nodes. */
const CATEGORY_COPY: Record<string, Partial<Record<FlexLevel, LevelCopyKeys>>> = {
  "dairy.milk": {
    exact: { explanation: "milkExactExplanation", example: "milkExactExample" },
    any_brand: { explanation: "milkAnyBrandExplanation", example: "milkAnyBrandExample" },
    close: { explanation: "milkCloseExplanation", example: "milkCloseExample" },
  },
};

function resolveCopy(keys: LevelCopyKeys, locale: Locale): LevelCopy {
  return {
    explanation: translate(stateMessages, locale, keys.explanation),
    example: translate(stateMessages, locale, keys.example),
  };
}

export function levelCopy(
  taxonomyId: string | null | undefined,
  level: FlexLevel,
  locale: Locale = DEFAULT_LOCALE,
): LevelCopy {
  if (taxonomyId) {
    for (const id of taxonomyAncestors(taxonomyId)) {
      const copy = CATEGORY_COPY[id]?.[level];
      if (copy) return resolveCopy(copy, locale);
    }
  }
  return resolveCopy(GENERIC_COPY[level], locale);
}

type SoftAttribute = { key: string; label: string };
type SoftAttributeKeys = ReadonlyArray<{ key: string; labelKey: StateKey }>;

/**
 * Soft attributes the user may allow to differ, by category. The API does not expose category
 * attribute schemas yet, so the lists live here; keys are stored with the list item.
 */
const SOFT_ATTRIBUTES: Record<string, SoftAttributeKeys> = {
  "dairy.milk": [
    { key: "pack_size", labelKey: "softPackSize" },
    { key: "packaging", labelKey: "softPackaging" },
    { key: "fat_pct", labelKey: "softFatPct" },
  ],
  dairy: [
    { key: "pack_size", labelKey: "softPackSize" },
    { key: "fat_pct", labelKey: "softFatPct" },
  ],
  produce: [{ key: "variety", labelKey: "softVariety" }],
};

const GENERIC_SOFT: SoftAttributeKeys = [
  { key: "pack_size", labelKey: "softPackSize" },
  { key: "packaging", labelKey: "softPackagingType" },
  { key: "flavor", labelKey: "softFlavor" },
];

export function softAttributes(
  taxonomyId: string | null | undefined,
  locale: Locale = DEFAULT_LOCALE,
): ReadonlyArray<SoftAttribute> {
  let keys = GENERIC_SOFT;
  if (taxonomyId) {
    for (const id of taxonomyAncestors(taxonomyId)) {
      const list = SOFT_ATTRIBUTES[id];
      if (list) {
        keys = list;
        break;
      }
    }
  }
  return keys.map(({ key, labelKey }) => ({
    key,
    label: translate(stateMessages, locale, labelKey),
  }));
}
