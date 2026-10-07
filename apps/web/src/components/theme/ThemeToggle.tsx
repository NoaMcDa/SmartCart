"use client";

import { IconMoon, IconSun } from "@/components/ui/icons";
import { useTheme } from "./ThemeProvider";
import styles from "./ThemeToggle.module.css";

/**
 * Header dark-mode switch, as in every artboard: moon in light mode, sun in dark mode.
 * Two-state; the three-state choice (system/light/dark) lives in Profile (ThemePreferenceControl).
 * Both icons are rendered and CSS shows the right one from [data-theme], so the icon is correct
 * before hydration too.
 */
export function ThemeToggle({ shape = "square" }: { shape?: "square" | "round" }) {
  const { resolved, toggle } = useTheme();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={resolved === "dark"}
      aria-label="מצב כהה"
      onClick={toggle}
      className={[styles.toggle, shape === "round" ? styles.round : null].filter(Boolean).join(" ")}
      data-testid="theme-toggle"
    >
      <IconMoon className={styles.moon} />
      <IconSun className={styles.sun} />
    </button>
  );
}
