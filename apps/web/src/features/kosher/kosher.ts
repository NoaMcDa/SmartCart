/**
 * The kosher preference (docs/matching.md, "Kosher"): the levels a person can choose, how the
 * profile's three fields become the API's `kosher` filter, and the Hebrew or Arabic text of what
 * an item's label says.
 *
 * The transparency files have no kosher field: the API reads certification only from item names
 * and says "unknown" for the rest. Nothing here decides whether an item is kosher; it only names
 * the person's choice and shows what the API answered.
 */
import type { Schemas } from "@/api/client";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { kosherMessages } from "@/i18n/messages/kosher";

export type KosherLevel = NonNullable<Schemas["KosherFilter"]["level"]>;
export type KosherFilter = Schemas["KosherFilter"];
export type KosherLabel = Schemas["KosherLabel"];
type MessageKey = keyof (typeof kosherMessages)["he"];

/** The three general levels, in the order of the segmented control. */
export const GENERAL_LEVELS = [
  "regular",
  "mehadrin",
  "badatz",
] as const satisfies ReadonlyArray<KosherLevel>;
/** A named hechsher a person can ask for; the API rules out an item that states a different one. */
export const SPECIFIC_LEVELS = [
  "badatz_eida",
  "badatz_beit_yosef",
  "badatz_chatam_sofer",
  "badatz_agudat",
  "landau",
  "rabbanut_mehadrin",
] as const satisfies ReadonlyArray<KosherLevel>;
export const KOSHER_LEVELS: ReadonlyArray<KosherLevel> = [...GENERAL_LEVELS, ...SPECIFIC_LEVELS];

export function isKosherLevel(value: unknown): value is KosherLevel {
  return typeof value === "string" && (KOSHER_LEVELS as ReadonlyArray<string>).includes(value);
}

/** The general level a specific one stands in for on the segmented control. */
export function generalLevelOf(level: KosherLevel): (typeof GENERAL_LEVELS)[number] {
  if (level === "landau") return "regular";
  if (level === "rabbanut_mehadrin") return "mehadrin";
  return (GENERAL_LEVELS as ReadonlyArray<string>).includes(level)
    ? (level as (typeof GENERAL_LEVELS)[number])
    : "badatz";
}

export function isSpecificLevel(level: KosherLevel | null): boolean {
  return level !== null && (SPECIFIC_LEVELS as ReadonlyArray<string>).includes(level);
}

/** The preference as the profile stores it: a level, "only stated" and kosher for Passover. */
export type KosherPrefs = {
  level: KosherLevel | null;
  onlyStated: boolean;
  passover: boolean;
};

/** The profile's diet flags that carry the two switches (the API has no column for them). */
export const FLAG_ONLY_STATED = "kosher:only_stated";
export const FLAG_PASSOVER = "kosher:passover";

/** The API's `kosher` request field, or null when the person set nothing (the request is then
 * exactly what it was before the filter existed). */
export function kosherFilter(prefs: KosherPrefs | null | undefined): KosherFilter | null {
  if (!prefs || (prefs.level === null && !prefs.passover)) return null;
  return {
    level: prefs.level,
    only_stated: prefs.onlyStated,
    passover: prefs.passover,
  };
}

export function levelLabel(level: KosherLevel | null, locale: Locale = DEFAULT_LOCALE): string {
  return translate(kosherMessages, locale, `level_${level ?? "none"}` as MessageKey);
}

/** Marks that say something about supervision, in the order the API lists them. */
const CERT_MARKS = [
  "badatz_eida",
  "badatz_beit_yosef",
  "badatz_chatam_sofer",
  "badatz_agudat",
  "badatz",
  "landau",
  "rabbanut_mehadrin",
  "mehadrin",
  "rabbanut",
  "kosher",
] as const;

/** The certifications a label's `stated` codes name, without the generic ones a named one implies
 * (the same rule as `smartcart_catalog.kosher.render`). */
export function statedCertifications(stated: ReadonlyArray<string>): string[] {
  const has = new Set(stated);
  const namedBadatz = SPECIFIC_LEVELS.slice(0, 4).some((l) => has.has(l));
  const kept = CERT_MARKS.filter((m) => has.has(m)).filter((m) => {
    if (m === "badatz") return !namedBadatz;
    if (m === "mehadrin" || m === "rabbanut") return !has.has("rabbanut_mehadrin");
    return true;
  });
  return kept.length > 1 ? kept.filter((m) => m !== "kosher") : kept;
}

/** "מהדרין", 'בד"ץ העדה החרדית': what the item's name states, or null when it states none. */
export function statedText(
  stated: ReadonlyArray<string>,
  locale: Locale = DEFAULT_LOCALE,
): string | null {
  const marks = statedCertifications(stated);
  if (marks.length === 0) return null;
  const sep = translate(kosherMessages, locale, "markSeparator");
  return marks.map((m) => translate(kosherMessages, locale, `mark_${m}` as MessageKey)).join(sep);
}

export type KosherNoteItem = { variant: "matched" | "unverified"; text: string; kind: string };

/**
 * What to show for one item's label: nothing without one, a "meets" note naming what the name
 * states, or the unknown warning. The level and kosher for Passover each get their own note.
 */
export function kosherNotes(
  label: KosherLabel | null | undefined,
  locale: Locale = DEFAULT_LOCALE,
): KosherNoteItem[] {
  if (!label) return [];
  const out: KosherNoteItem[] = [];
  if (label.level === "meets") {
    const mark = statedText(label.stated ?? [], locale);
    out.push({
      variant: "matched",
      kind: "level-meets",
      text: mark
        ? translate(kosherMessages, locale, "meets", { mark })
        : translate(kosherMessages, locale, "meets", { mark: levelLabel("regular", locale) }),
    });
  } else if (label.level === "unknown") {
    out.push({
      variant: "unverified",
      kind: "level-unknown",
      text: translate(kosherMessages, locale, "unknown"),
    });
  }
  if (label.passover === "meets") {
    out.push({
      variant: "matched",
      kind: "passover-meets",
      text: translate(kosherMessages, locale, "passoverMeets"),
    });
  } else if (label.passover === "unknown") {
    out.push({
      variant: "unverified",
      kind: "passover-unknown",
      text: translate(kosherMessages, locale, "passoverUnknown"),
    });
  }
  return out;
}

/** The sentence at the top of the results while a filter is on, or null without one. */
export function activeNoteText(
  prefs: KosherPrefs | null | undefined,
  locale: Locale = DEFAULT_LOCALE,
): string | null {
  const filter = kosherFilter(prefs);
  if (!filter || !prefs) return null;
  const parts = [
    prefs.level ? levelLabel(prefs.level, locale) : null,
    prefs.passover ? translate(kosherMessages, locale, "activeNotePassover") : null,
  ].filter((p): p is string => p !== null);
  return translate(
    kosherMessages,
    locale,
    prefs.onlyStated ? "activeNoteOnlyStated" : "activeNote",
    { level: parts.join(translate(kosherMessages, locale, "markSeparator")) },
  );
}
