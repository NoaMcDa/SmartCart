"use client";

import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { IconMonitor, IconMoon, IconSun } from "@/components/ui/icons";
import { useTheme } from "./ThemeProvider";
import type { ThemePreference } from "./theme-constants";
import type { ReactNode } from "react";

const OPTIONS = [
  { value: "system", label: "אוטומטי", icon: <IconMonitor size={16} /> },
  { value: "light", label: "בהיר", icon: <IconSun size={16} /> },
  { value: "dark", label: "כהה", icon: <IconMoon size={16} /> },
] as const satisfies ReadonlyArray<{ value: ThemePreference; label: string; icon: ReactNode }>;

/**
 * Three-state theme choice for the Profile screen. Shares state with the header ThemeToggle
 * through ThemeProvider, so the two always agree.
 */
export function ThemePreferenceControl() {
  const { preference, setPreference } = useTheme();
  return (
    <SegmentedControl<ThemePreference>
      label="ערכת צבעים"
      options={OPTIONS}
      value={preference}
      onChange={setPreference}
    />
  );
}
