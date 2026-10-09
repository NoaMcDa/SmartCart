"use client";

import { countMessages } from "@/i18n/messages/counts";
import { usePlural } from "@/i18n/plural";

export type CountNoun = "item" | "items" | "replaced" | "missing" | "promo" | "unit";

/**
 * A number in an LTR island followed by its noun in the right plural form of the UI language
 * ("3 פריטים", "3 أصناف"). `items` keeps the plural for every number, as the Hebrew screens do.
 */
export function Count({ n, noun }: { n: number; noun: CountNoun }) {
  const plural = usePlural(countMessages);
  return (
    <>
      <span dir="ltr">{n}</span> {plural(noun, n)}
    </>
  );
}
