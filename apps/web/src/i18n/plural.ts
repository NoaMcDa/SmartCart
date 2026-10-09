import { useCallback } from "react";
import { useLocale } from "./LocaleProvider";
import type { Locale } from "./locales";
import { translate, type MessageSet } from "./messages";

/**
 * Plural forms of a counted noun (issue #73). Hebrew in this app has two ("פריט" for exactly one,
 * "פריטים" for every other number, zero included). Arabic has four that matter for UI copy: one
 * ("عنصر"), two ("عنصران"), 3 to 10 ("عناصر") and 11 and more ("عنصرًا"). A module that counts
 * something defines `<base>_one`, `<base>_two`, `<base>_few` and `<base>_many`; Hebrew repeats the
 * plural in `_two` and `_few`.
 */
export type PluralForm = "one" | "two" | "few" | "many";

export function pluralForm(n: number, locale: Locale): PluralForm {
  if (locale === "ar") {
    if (n === 1) return "one";
    if (n === 2) return "two";
    const rest = n % 100;
    if (Number.isInteger(n) && rest >= 11 && rest <= 99) return "many";
    return "few";
  }
  return n === 1 ? "one" : "many";
}

/** `translatePlural(messages, "ar", "item", 4)` reads `item_few`. Non-React lookup. */
export function translatePlural<K extends string>(
  messages: MessageSet<K>,
  locale: Locale,
  base: string,
  n: number,
  vars?: Record<string, string | number>,
): string {
  return translate(messages, locale, `${base}_${pluralForm(n, locale)}` as K, vars);
}

/** `const plural = usePlural(messages); plural("item", 3)` */
export function usePlural<K extends string>(messages: MessageSet<K>) {
  const { locale } = useLocale();
  return useCallback(
    (base: string, n: number, vars?: Record<string, string | number>) =>
      translatePlural(messages, locale, base, n, vars),
    [messages, locale],
  );
}
