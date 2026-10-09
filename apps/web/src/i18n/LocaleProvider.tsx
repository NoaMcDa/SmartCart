"use client";

import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { DEFAULT_LOCALE, INTL_LOCALE, LOCALE_KEY, isLocale, type Locale } from "./locales";
import { translate, type MessageSet } from "./messages";

type LocaleContextValue = {
  locale: Locale;
  /** `Intl` locale string for dates and numbers (Latin digits in both locales). */
  intl: string;
  setLocale: (next: Locale) => void;
};

const LocaleContext = createContext<LocaleContextValue>({
  locale: DEFAULT_LOCALE,
  intl: INTL_LOCALE[DEFAULT_LOCALE],
  setLocale: () => {},
});

function readStored(): Locale {
  try {
    const m = document.cookie.match(new RegExp(`(?:^|; )${LOCALE_KEY}=(he|ar)`));
    const value = m?.[1] ?? window.localStorage.getItem(LOCALE_KEY);
    return isLocale(value) ? value : DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE;
  }
}

function store(locale: Locale): void {
  try {
    window.localStorage.setItem(LOCALE_KEY, locale);
  } catch {
    // Private mode: the cookie below still carries it.
  }
  document.cookie = `${LOCALE_KEY}=${locale}; path=/; max-age=31536000; samesite=lax`;
  document.documentElement.lang = locale;
  document.documentElement.dataset.locale = locale;
}

const CHANGE_EVENT = "sc-locale-change";

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

const serverSnapshot = (): Locale => DEFAULT_LOCALE;

/**
 * Holds the UI locale. Hydration uses the Hebrew server snapshot (it matches the server markup);
 * React then re-renders with the stored choice. Both locales are RTL, so nothing shifts.
 */
export function LocaleProvider({ children }: { children: ReactNode }) {
  const locale = useSyncExternalStore(subscribe, readStored, serverSnapshot);

  const setLocale = useCallback((next: Locale) => {
    store(next);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  const value = useMemo(
    () => ({ locale, intl: INTL_LOCALE[locale], setLocale }),
    [locale, setLocale],
  );
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  return useContext(LocaleContext);
}

/** `const t = useT(navMessages); t("lists")` */
export function useT<K extends string>(messages: MessageSet<K>) {
  const { locale } = useLocale();
  return useCallback(
    (key: K, vars?: Record<string, string | number>) => translate(messages, locale, key, vars),
    [messages, locale],
  );
}
