import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemePreferenceControl } from "./ThemePreferenceControl";
import { __resetThemeStoreForTests, ThemeProvider } from "./ThemeProvider";
import { ThemeToggle } from "./ThemeToggle";
import { THEME_COLOR, THEME_INIT_SCRIPT, THEME_STORAGE_KEY } from "./theme-constants";

type Listener = () => void;

/** Controllable prefers-color-scheme. */
function mockOs(initialDark: boolean) {
  let dark = initialDark;
  const listeners = new Set<Listener>();
  vi.stubGlobal("matchMedia", (query: string) => ({
    get matches() {
      return query.includes("dark") ? dark : !dark;
    },
    media: query,
    addEventListener: (_: string, l: Listener) => listeners.add(l),
    removeEventListener: (_: string, l: Listener) => listeners.delete(l),
  }));
  window.matchMedia = globalThis.matchMedia;
  return {
    set(next: boolean) {
      dark = next;
      listeners.forEach((l) => l());
    },
  };
}

function setup() {
  return render(
    <ThemeProvider>
      <ThemeToggle />
      <ThemePreferenceControl />
    </ThemeProvider>,
  );
}

const root = () => document.documentElement;

beforeEach(() => {
  localStorage.clear();
  __resetThemeStoreForTests();
  root().removeAttribute("data-theme");
  document.head.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.remove());
  for (const [media, color] of [
    ["(prefers-color-scheme: light)", THEME_COLOR.light],
    ["(prefers-color-scheme: dark)", THEME_COLOR.dark],
  ]) {
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    meta.media = media!;
    meta.content = color!;
    document.head.appendChild(meta);
  }
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ThemeProvider", () => {
  it("follows the OS with no saved choice, and updates live when the OS changes", () => {
    const os = mockOs(true);
    setup();
    expect(root().getAttribute("data-theme")).toBe("dark");
    expect(screen.getByRole("switch", { name: "מצב כהה" })).toHaveAttribute("aria-checked", "true");
    act(() => os.set(false));
    expect(root().getAttribute("data-theme")).toBe("light");
    expect(screen.getByRole("radio", { name: /אוטומטי/ })).toHaveAttribute("aria-checked", "true");
  });

  it("header switch flips the theme, persists it, and keeps the Profile control in sync", async () => {
    mockOs(false);
    setup();
    const user = userEvent.setup();
    await user.click(screen.getByRole("switch", { name: "מצב כהה" }));
    expect(root().getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(screen.getByRole("radio", { name: /כהה/ })).toHaveAttribute("aria-checked", "true");
    // Manual choice: both theme-color metas carry the chosen theme's color.
    document.querySelectorAll('meta[name="theme-color"]').forEach((m) => {
      expect(m.getAttribute("content")).toBe(THEME_COLOR.dark);
    });

    await user.click(screen.getByRole("radio", { name: /אוטומטי/ }));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    expect(root().getAttribute("data-theme")).toBe("light");
    const metas = [...document.querySelectorAll('meta[name="theme-color"]')].map((m) =>
      m.getAttribute("content"),
    );
    expect(metas).toEqual([THEME_COLOR.light, THEME_COLOR.dark]);
  });

  it("a saved light choice wins over a dark OS", () => {
    mockOs(true);
    localStorage.setItem(THEME_STORAGE_KEY, "light");
    setup();
    expect(root().getAttribute("data-theme")).toBe("light");
    expect(screen.getByRole("switch", { name: "מצב כהה" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("survives a throwing localStorage (private mode)", async () => {
    mockOs(false);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    setup();
    await userEvent.setup().click(screen.getByRole("switch", { name: "מצב כהה" }));
    expect(root().getAttribute("data-theme")).toBe("dark");
  });
});

describe("THEME_INIT_SCRIPT (runs before first paint)", () => {
  const run = () => new Function(THEME_INIT_SCRIPT)();

  it("applies the saved choice", () => {
    mockOs(false);
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    run();
    expect(root().getAttribute("data-theme")).toBe("dark");
  });

  it("falls back to the OS preference", () => {
    mockOs(true);
    run();
    expect(root().getAttribute("data-theme")).toBe("dark");
  });

  it("never throws when storage is blocked", () => {
    mockOs(false);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    expect(run).not.toThrow();
    expect(root().getAttribute("data-theme")).toBe("light");
  });
});
