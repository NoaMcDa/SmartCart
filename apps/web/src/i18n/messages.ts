import type { Locale } from "./locales";

/**
 * A feature's messages: the Hebrew source and its Arabic translation with exactly the same keys
 * (the compiler rejects a missing or extra key). One module per feature under `messages/` keeps
 * workstreams from editing a shared file.
 *
 *   export const navMessages = defineMessages({
 *     he: { lists: "רשימות" },
 *     ar: { lists: "القوائم" },
 *   });
 *
 * `{name}` placeholders are filled by `t(key, { name })`.
 */
export type MessageSet<K extends string> = Record<Locale, Record<K, string>>;

export function defineMessages<const H extends Record<string, string>>(set: {
  he: H;
  ar: Record<keyof H & string, string>;
}): MessageSet<keyof H & string> {
  return set as MessageSet<keyof H & string>;
}

export function format(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in vars ? String(vars[name]) : whole,
  );
}

/** Non-React lookup, for modules that run outside components (tests, mocks, helpers). */
export function translate<K extends string>(
  messages: MessageSet<K>,
  locale: Locale,
  key: K,
  vars?: Record<string, string | number>,
): string {
  return format(messages[locale][key] ?? messages.he[key], vars);
}
