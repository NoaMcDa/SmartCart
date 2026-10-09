/**
 * UI locales (issue #73). Hebrew is the source and the default; Arabic is the second locale. Both
 * are right-to-left, so switching never flips the layout: only `lang`, the copy, the font and the
 * `Intl` locale change. Numbers stay in Latin digits in both (prices render LTR, CLAUDE.md).
 */
export const LOCALES = ["he", "ar"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "he";

/** Cookie and localStorage key holding the chosen locale. */
export const LOCALE_KEY = "sc-locale";

/** `Intl` locale per UI locale. `-u-nu-latn` keeps Latin digits in Arabic. */
export const INTL_LOCALE: Record<Locale, string> = {
  he: "he-IL",
  ar: "ar-IL-u-nu-latn",
};

export const LOCALE_NAME: Record<Locale, string> = { he: "עברית", ar: "العربية" };

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

/**
 * Runs before first paint (like THEME_INIT_SCRIPT): sets `<html lang>` from the stored choice so
 * screen readers and the font stack pick the right language at once. The copy itself switches when
 * `LocaleProvider` mounts. The server markup is always Hebrew, so static pages stay static.
 */
export const LOCALE_INIT_SCRIPT = `(function(){try{var m=document.cookie.match(/(?:^|; )${LOCALE_KEY}=(he|ar)/);var l=(m&&m[1])||localStorage.getItem("${LOCALE_KEY}");if(l==="ar"||l==="he"){document.documentElement.lang=l;document.documentElement.dataset.locale=l;}}catch(e){}})();`;
