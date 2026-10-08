"use client";

import { SegmentedControl, type SegmentOption } from "@/components/ui/SegmentedControl";
import { trackEvent } from "@/features/seo/track";
import { useLocale, useT } from "./LocaleProvider";
import { LOCALES, LOCALE_NAME, type Locale } from "./locales";
import { localeMessages } from "./messages/locale";

/** Each option is named in its own language and tagged with `lang`, so a reader of either locale finds theirs. */
const OPTIONS: ReadonlyArray<SegmentOption<Locale>> = LOCALES.map((value) => ({
  value,
  label: <span lang={value}>{LOCALE_NAME[value]}</span>,
}));

/**
 * Hebrew / Arabic switch: a radio group (roving tabindex, arrow keys) built on SegmentedControl.
 * The choice is stored by `LocaleProvider` (cookie + localStorage) and sets `<html lang>`; both
 * locales are RTL, so nothing flips. The group's accessible name follows the active locale.
 *
 * TODO(#73): sync to the profile when signed in. The profile schema has no locale column yet, so
 * today the choice is per browser only.
 *
 * Mount it in Profile (next to ThemePreferenceControl).
 */
export function LocaleSwitch({ className }: { className?: string }) {
  const { locale, setLocale } = useLocale();
  const t = useT(localeMessages);

  function onChange(next: Locale) {
    if (next === locale) return;
    setLocale(next);
    trackEvent("locale_changed", { locale: next });
  }

  return (
    <SegmentedControl<Locale>
      label={t("group")}
      options={OPTIONS}
      value={locale}
      onChange={onChange}
      className={className}
    />
  );
}
