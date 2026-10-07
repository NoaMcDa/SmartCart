"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import {
  THEME_COLOR,
  THEME_STORAGE_KEY,
  isThemePreference,
  type ResolvedTheme,
  type ThemePreference,
} from "./theme-constants";

type ThemeContextValue = {
  /** What the user chose: follow the OS, or a fixed theme. */
  preference: ThemePreference;
  /** What is applied right now. */
  resolved: ResolvedTheme;
  setPreference: (p: ThemePreference) => void;
  /** Two-state flip used by the header switch: sets an explicit light or dark choice. */
  toggle: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

// ---- preference store (localStorage, wrapped in try/catch; private mode can throw) ----

const listeners = new Set<() => void>();
let memoryPreference: ThemePreference | null = null;

function readStorage(): ThemePreference {
  try {
    const v = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(v) ? v : "system";
  } catch {
    return "system";
  }
}

function writeStorage(p: ThemePreference) {
  try {
    if (p === "system") window.localStorage.removeItem(THEME_STORAGE_KEY);
    else window.localStorage.setItem(THEME_STORAGE_KEY, p);
  } catch {
    // Storage unavailable: the choice lasts for this page view only.
  }
}

function getPreference(): ThemePreference {
  if (memoryPreference === null) memoryPreference = readStorage();
  return memoryPreference;
}

function setStoredPreference(p: ThemePreference) {
  memoryPreference = p;
  writeStorage(p);
  listeners.forEach((l) => l());
}

function subscribePreference(listener: () => void) {
  listeners.add(listener);
  // Keep tabs in sync.
  const onStorage = (e: StorageEvent) => {
    if (e.key !== null && e.key !== THEME_STORAGE_KEY) return;
    memoryPreference = readStorage();
    listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/** Test helper: forget the cached preference so the next read hits storage again. */
export function __resetThemeStoreForTests() {
  memoryPreference = null;
}

// ---- OS preference ----

const DARK_QUERY = "(prefers-color-scheme: dark)";

function subscribeOs(listener: () => void) {
  if (typeof window.matchMedia !== "function") return () => {};
  const mql = window.matchMedia(DARK_QUERY);
  mql.addEventListener("change", listener);
  return () => mql.removeEventListener("change", listener);
}

function getOsDark() {
  return typeof window.matchMedia === "function" && window.matchMedia(DARK_QUERY).matches;
}

// ---- DOM application ----

function applyTheme(resolved: ResolvedTheme, preference: ThemePreference) {
  const root = document.documentElement;
  root.setAttribute("data-theme", resolved);
  // The browser UI color follows the theme. With "system" the media-specific metas already do the
  // right thing; with a manual choice both metas get the chosen theme's color.
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach((meta) => {
    if (!meta.hasAttribute("data-sc-original")) {
      meta.setAttribute("data-sc-original", meta.getAttribute("content") ?? "");
    }
    const original = meta.getAttribute("data-sc-original") ?? "";
    meta.setAttribute("content", preference === "system" ? original : THEME_COLOR[resolved]);
  });
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const preference = useSyncExternalStore(
    subscribePreference,
    getPreference,
    () => "system" as const,
  );
  const osDark = useSyncExternalStore(subscribeOs, getOsDark, () => false);
  const resolved: ResolvedTheme =
    preference === "system" ? (osDark ? "dark" : "light") : preference;

  useEffect(() => {
    applyTheme(resolved, preference);
  }, [resolved, preference]);

  const setPreference = useCallback((p: ThemePreference) => setStoredPreference(p), []);
  const toggle = useCallback(
    () => setStoredPreference(resolved === "dark" ? "light" : "dark"),
    [resolved],
  );

  const value = useMemo(
    () => ({ preference, resolved, setPreference, toggle }),
    [preference, resolved, setPreference, toggle],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}
