"use client";

import { useState } from "react";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { personalMessages } from "@/i18n/messages/personal";
import { rescueFocus } from "@/lib/focus";
import { productName } from "@/lib/format";
import { listActions, type ListItem } from "@/state/list";
import { usualQuantities, type UsualItem } from "./habits";
import { dayIndex, type PersonalDoc } from "./personalDoc";
import { Qty } from "./personalCopy";
import { usePersonal } from "./personalState";
import { useNow } from "./useNow";
import styles from "./Personal.module.css";

const cache = new WeakMap<PersonalDoc, { day: number; map: Map<number, UsualItem> }>();

/** One computation per document and day, shared by every row of the list. */
function usualMap(doc: PersonalDoc, now: Date): Map<number, UsualItem> {
  const day = dayIndex(now.toISOString());
  const hit = cache.get(doc);
  if (hit && hit.day === day) return hit.map;
  const map = usualQuantities(doc, now);
  cache.set(doc, { day, map });
  return map;
}

/**
 * Under a list row's name: "you usually take N of these", from the person's own history (at least
 * three shopping days), with a one-tap button to set that quantity when the row has another. It
 * never changes the quantity by itself.
 */
export function UsualQuantityHint({ item }: { item: ListItem }) {
  const t = useT(personalMessages);
  const { locale } = useLocale();
  const { doc, hydrated } = usePersonal();
  const now = useNow();
  const [done, setDone] = useState<string | null>(null);
  if (!hydrated || !doc.prefs.learn || !item.canonical) return null;
  const usual = usualMap(doc, now).get(item.canonical.canonical_id);
  if (!usual) return null;
  const kg = item.unit === "kg";
  const name = productName(item.canonical, locale);
  const qty = <Qty quantity={usual.quantity} kg={kg} locale={locale} />;
  const differs = Math.abs(item.quantity - usual.quantity) > 0.0001;
  const qtyText = `${usual.quantity}${kg ? ` ${t("kg")}` : ""}`;
  return (
    <div className={styles.usualLine} data-testid="usual-quantity">
      <span>{formatRich(t("rowUsual"), { qty })}</span>
      {differs ? (
        <button
          type="button"
          className={styles.usualSet}
          aria-label={t("rowUsualSetAria", { name, qty: qtyText })}
          onClick={(e) => {
            // The button goes away once the quantity matches: focus moves to the row's first control.
            const row = e.currentTarget.closest<HTMLElement>('[data-testid="list-row"]');
            rescueFocus(e.currentTarget, {
              neighbors: false,
              fallback: () => row?.querySelector<HTMLElement>("button") ?? null,
            });
            listActions.setQuantity(item.id, usual.quantity);
            setDone(t("rowUsualDone", { name, qty: qtyText }));
          }}
        >
          {formatRich(t("rowUsualSet"), { qty })}
        </button>
      ) : null}
      <span role="status" className="sr-only">
        {done}
      </span>
    </div>
  );
}
