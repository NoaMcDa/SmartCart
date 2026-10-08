import type { FlexLevel } from "@/api/client";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { profileMessages, type ProfileMessageKey } from "@/i18n/messages/profile";
import { SMART_DEFAULTS, lookupDefault } from "@/state/flex";
import type { KosherLevel } from "./profileState";

const he = (key: ProfileMessageKey) => translate(profileMessages, DEFAULT_LOCALE, key);

/** `label` is Hebrew; use `kosherLabel(value, locale)` where the locale can be Arabic. */
export const KOSHER_OPTIONS: ReadonlyArray<{ value: KosherLevel | "none"; label: string }> = [
  { value: "none", label: he("kosher_none") },
  { value: "regular", label: he("kosher_regular") },
  { value: "mehadrin", label: he("kosher_mehadrin") },
  { value: "badatz", label: he("kosher_badatz") },
];

export function kosherLabel(value: KosherLevel | "none", locale: Locale = DEFAULT_LOCALE): string {
  return translate(profileMessages, locale, `kosher_${value}` as ProfileMessageKey);
}

/** `label` is Hebrew; use `allergenLabel(key, locale)` where the locale can be Arabic. */
export const ALLERGENS: ReadonlyArray<{ key: string; label: string }> = [
  { key: "peanuts", label: he("allergen_peanuts") },
  { key: "tree_nuts", label: he("allergen_tree_nuts") },
  { key: "sesame", label: he("allergen_sesame") },
  { key: "milk", label: he("allergen_milk") },
  { key: "eggs", label: he("allergen_eggs") },
  { key: "soy", label: he("allergen_soy") },
  { key: "wheat", label: he("allergen_wheat") },
  { key: "fish", label: he("allergen_fish") },
];

export function allergenLabel(key: string, locale: Locale = DEFAULT_LOCALE): string {
  return translate(profileMessages, locale, `allergen_${key}` as ProfileMessageKey);
}

const DEPARTMENT_IDS = [
  "dairy",
  "meat",
  "fish",
  "deli",
  "produce",
  "bakery",
  "pantry",
  "canned",
  "frozen",
  "beverages",
  "snacks",
  "baby",
  "cleaning",
  "paper",
  "toiletries",
  "health",
  "pets",
  "holiday",
  "alcohol",
] as const;

/** The 19 taxonomy departments (data/taxonomy.yaml) with their Hebrew names. */
export const DEPARTMENTS: ReadonlyArray<{ id: string; label: string }> = DEPARTMENT_IDS.map(
  (id) => ({ id, label: he(`dept_${id}`) }),
);

/** Smart default (D4) for a category: the shared table in `@/state/flex`, else "any brand". */
export function smartDefault(taxonomyId: string): FlexLevel {
  return lookupDefault(taxonomyId, SMART_DEFAULTS) ?? "any_brand";
}

/** The department name in `locale`. */
export function departmentLabel(id: string, locale: Locale = DEFAULT_LOCALE): string {
  return translate(profileMessages, locale, `dept_${id}` as ProfileMessageKey);
}

const KNOWN_CATEGORIES: ReadonlySet<string> = new Set([
  "dairy.milk",
  "dairy.cheese",
  "dairy.yogurt",
  "dairy.cream",
  "dairy.eggs",
]);

/** Label for a taxonomy node id (Hebrew by default), falling back to the department or the raw id. */
export function categoryLabel(taxonomyId: string, locale: Locale = DEFAULT_LOCALE): string {
  if ((DEPARTMENT_IDS as ReadonlyArray<string>).includes(taxonomyId)) {
    return departmentLabel(taxonomyId, locale);
  }
  if (KNOWN_CATEGORIES.has(taxonomyId)) {
    return translate(
      profileMessages,
      locale,
      `cat_${taxonomyId.replace(".", "_")}` as ProfileMessageKey,
    );
  }
  return taxonomyId;
}
