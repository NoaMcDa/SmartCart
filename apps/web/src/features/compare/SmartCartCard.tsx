"use client";

import { useMemo, useState } from "react";
import type { AttributeTag, Plan, SwapSuggestion } from "@/api/client";
import { Button, Card, Price, Tag, UpdatedAt } from "@/components/ui";
import { IconCheck, IconRefresh } from "@/components/ui/icons";
import { applySwap, dismissSwap, undoSwap } from "@/features/swaps/actions";
import { aggregate, savingOf, useSwapsState, visibleSwaps } from "@/features/swaps/swapState";
import { useSwaps } from "@/features/swaps/useSwaps";
import { buildCompareInput, planUpdatedAt } from "@/state/comparison";
import { basketItems, useList } from "@/state/list";
import { useShopper } from "@/state/shopper";
import styles from "./SmartCartCard.module.css";

const TAG_KEYS: Record<string, string> = {
  product_type: "סוג מוצר",
  pack_size: "גודל אריזה",
  brand: "מותג",
  fat_pct: "אחוז שומן",
  base: "בסיס",
  kosher: "כשרות",
};

export function swapTagText(tag: AttributeTag): string {
  const key = TAG_KEYS[tag.key] ?? tag.key;
  if (tag.status === "unverified") return `${key}${tag.value ? ` ${tag.value}` : ""} · לא מאומת`;
  if (tag.status === "differs") return tag.value ? `${key}: ${tag.value}` : key;
  return tag.value ? `${key}, ${tag.value}` : key;
}

const REASONS: Record<SwapSuggestion["flex_level"], string> = {
  any_brand: "אותו סוג מוצר ואותה כמות, במותג אחר. מתאים לרמת ״כל מותג״.",
  close:
    "תחליף קרוב: מוצר דומה מאוד עם הבדל קטן באחד המאפיינים (ראי את התגיות). מתאים לרמת ״תחליף קרוב״.",
  exact: "אותו מוצר בדיוק, במחיר נמוך יותר בסניף הזה.",
};

export function swapsHeadline(count: number): string {
  if (count === 1) return "החלפה אחת תחסוך לך";
  return `${count} החלפות יחסכו לך`;
}

/**
 * The smart cart (issue #45): "3 swaps save you ₪41" for the recommended store, one suggestion at
 * a time (the biggest), with what changes, why, the saving and the confidence. Applying switches
 * the list's flexibility for that product after a tap and can be undone; dismissing sends the
 * swap back as a labeling signal and keeps it away until its saving changes materially. Nothing is
 * ever applied automatically. Renders nothing while loading, on an error, or when there is nothing
 * to suggest, so it never blocks the results.
 */
export function SmartCartCard({ plan }: { plan: Plan }) {
  const { state } = useList();
  const shopper = useShopper();
  const swapsState = useSwapsState();
  const [undone, setUndone] = useState<string | null>(null);

  const store = plan.stores[0]?.store ?? null;
  const request = useMemo(() => {
    if (!shopper || !store) return null;
    const body = buildCompareInput(basketItems(state), shopper);
    return body ? { storeId: store.store_id, body } : null;
  }, [state, shopper, store]);
  const result = useSwaps(request);
  const data = result.status === "success" ? result.data : null;

  const visible = useMemo(
    () => (data ? visibleSwaps(data.swaps, swapsState) : []),
    [data, swapsState],
  );
  const { count, total } = aggregate(visible);
  const top = visible[0] ?? null;
  const lastApplied = swapsState.applied[swapsState.applied.length - 1] ?? null;

  if (!store || (!top && !lastApplied && !undone)) return null;

  return (
    <Card
      as="section"
      aria-labelledby="smart-cart-title"
      className={styles.smart}
      data-testid="smart-cart"
      data-trust-scope="smart-cart"
    >
      <p className={styles.smartEyebrow}>
        <IconRefresh size={14} /> עגלה חכמה · {store.chain_name}
      </p>

      {top ? (
        <>
          <h2 id="smart-cart-title" className={styles.smartTitle} data-testid="smart-cart-title">
            {swapsHeadline(count)} <Price amount={total} tone="good" size="lg" />
          </h2>
          <p className={styles.muted}>
            לעומת הרשימה שלך כמו שהיא עכשיו, בסניף {store.store_name}. ההחלפות לא חופפות, אז הסכום
            לא סופר חיסכון פעמיים.
          </p>

          <div className={styles.smartTop} data-testid="smart-cart-top">
            <p className={styles.smartLabel}>ההחלפה המשתלמת ביותר</p>
            <h3 className={styles.smartName}>{top.to_display_name_he}</h3>
            <p className={styles.smartMeta}>
              חיסכון <Price amount={savingOf(top)} tone="good" fractionDigits={2} />
              {top.confidence != null ? (
                <>
                  {" · "}ביטחון בהתאמה <span dir="ltr">{Math.round(top.confidence * 100)}%</span>
                </>
              ) : null}
            </p>
            <p className={styles.smartWhy} data-testid="smart-cart-why">
              למה: {REASONS[top.flex_level]}
            </p>
            {top.tags && top.tags.length > 0 ? (
              <ul className={styles.smartTags} aria-label="השוואת תכונות">
                {top.tags.map((t) => (
                  <li key={`${t.key}-${t.value ?? ""}`}>
                    <Tag variant={t.status}>{swapTagText(t)}</Tag>
                  </li>
                ))}
              </ul>
            ) : null}
            <div className={styles.smartActions}>
              <Button
                onClick={() => {
                  setUndone(null);
                  applySwap(top);
                }}
                aria-label={`החליפי ל${top.to_display_name_he}`}
              >
                החלפה
              </Button>
              <Button variant="outline" onClick={() => dismissSwap(top)}>
                לא עכשיו
              </Button>
            </div>
          </div>
        </>
      ) : (
        <h2 id="smart-cart-title" className={styles.smartTitle}>
          אין החלפות נוספות להציע
        </h2>
      )}

      <div role="status" aria-live="polite">
        {lastApplied ? (
          <p className={styles.smartApplied} data-testid="smart-cart-applied">
            <IconCheck size={14} /> הוחלף: {lastApplied.name} (חיסכון{" "}
            <Price amount={lastApplied.saving} tone="good" fractionDigits={2} />
            ).{" "}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (undoSwap(lastApplied.key)) setUndone(lastApplied.name);
              }}
            >
              ביטול ההחלפה
            </Button>
          </p>
        ) : null}
        {undone && !lastApplied ? (
          <p className={styles.muted} data-testid="smart-cart-undone">
            ההחלפה בוטלה והרשימה חזרה למה שהייתה.
          </p>
        ) : null}
      </div>

      <p className={styles.muted}>
        <UpdatedAt iso={planUpdatedAt(plan)} prefix="מחירים עודכנו" withIcon /> · המחיר הקובע הוא
        בקופה.
      </p>
    </Card>
  );
}
