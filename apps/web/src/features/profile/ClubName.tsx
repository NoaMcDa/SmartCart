"use client";

import { DataText } from "@/i18n/DataText";
import { useLocale } from "@/i18n/LocaleProvider";
import { clubRuleParts } from "./clubs";

/**
 * A promo's club in a sentence: the club's own (Hebrew) name as a data run, so an Arabic screen
 * marks it `lang="he"` like every other name that exists only in Hebrew, and the rule words ("or",
 * "and") in the language of the screen. Renders nothing when there is no name to show.
 */
export function ClubName({ rule }: { rule: string | null | undefined }) {
  const { locale } = useLocale();
  const parts = clubRuleParts(rule, locale);
  if (parts === null) return null;
  return (
    <>
      {parts.map((part, i) =>
        part.name ? <DataText key={i}>{part.text}</DataText> : <span key={i}>{part.text}</span>,
      )}
    </>
  );
}
