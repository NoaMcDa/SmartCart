"use client";

import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { useT } from "@/i18n/LocaleProvider";
import { themeMessages } from "@/i18n/messages/theme";
import { IconMonitor, IconMoon, IconSun } from "@/components/ui/icons";
import { useTheme } from "./ThemeProvider";
import type { ThemePreference } from "./theme-constants";
import type { ReactNode } from "react";

const OPTIONS = [
  { value: "system", labelKey: "auto", icon: <IconMonitor size={16} /> },
  { value: "light", labelKey: "light", icon: <IconSun size={16} /> },
  { value: "dark", labelKey: "dark", icon: <IconMoon size={16} /> },
] as const satisfies ReadonlyArray<{
  value: ThemePreference;
  labelKey: keyof (typeof themeMessages)["he"];
  icon: ReactNode;
}>;

/**
 * Three-state theme choice for the Profile screen. Shares state with the header ThemeToggle
 * through ThemeProvider, so the two always agree.
 */
export function ThemePreferenceControl() {
  const { preference, setPreference } = useTheme();
  const t = useT(themeMessages);
  return (
    <SegmentedControl<ThemePreference>
      label={t("colorScheme")}
      options={OPTIONS.map(({ value, labelKey, icon }) => ({ value, label: t(labelKey), icon }))}
      value={preference}
      onChange={setPreference}
    />
  );
}
