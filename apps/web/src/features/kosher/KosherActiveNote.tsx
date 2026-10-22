"use client";

import Link from "next/link";
import { IconInfo } from "@/components/ui/icons";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { kosherMessages } from "@/i18n/messages/kosher";
import { activeNoteText, type KosherPrefs } from "./kosher";
import styles from "./Kosher.module.css";

/**
 * Says on the results that a kosher filter is on and what it does, so a missing item or a store
 * that is not listed is never a mystery. Renders nothing without a filter.
 */
export function KosherActiveNote({ prefs }: { prefs: KosherPrefs | null | undefined }) {
  const t = useT(kosherMessages);
  const { locale } = useLocale();
  const text = activeNoteText(prefs, locale);
  if (!text) return null;
  return (
    <p className={styles.active} data-testid="kosher-active">
      <IconInfo size={16} />
      <span>
        {text} <Link href="/profile">{t("changeInProfile")}</Link>
      </span>
    </p>
  );
}
