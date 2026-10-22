"use client";

import { Tag } from "@/components/ui";
import { useLocale } from "@/i18n/LocaleProvider";
import { kosherNotes, type KosherLabel } from "./kosher";

/**
 * What the kosher filter knows about one offered item: the certification its name states, or the
 * amber "כשרות לא ידועה — בדקו על האריזה". A trust signal with the same weight as the substitute
 * tags: shown on every line, swap and substitute, and nothing at all without a filter (no label).
 * Colour never carries it alone: every tag has an icon and its text.
 */
export function KosherNote({ label }: { label: KosherLabel | null | undefined }) {
  const { locale } = useLocale();
  return (
    <>
      {kosherNotes(label, locale).map((n) => (
        <span key={n.kind} data-testid="kosher-note" data-kosher={n.kind}>
          <Tag variant={n.variant}>{n.text}</Tag>
        </span>
      ))}
    </>
  );
}

/** The same notes as list items, for the tag lists of a substitute and a swap. */
export function KosherNoteItems({ label }: { label: KosherLabel | null | undefined }) {
  const { locale } = useLocale();
  return (
    <>
      {kosherNotes(label, locale).map((n) => (
        <li key={n.kind} data-testid="kosher-note" data-kosher={n.kind}>
          <Tag variant={n.variant}>{n.text}</Tag>
        </li>
      ))}
    </>
  );
}
