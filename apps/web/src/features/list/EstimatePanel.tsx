"use client";

import type { BasketItemInput, CompareResponse } from "@/api/client";
import {
  Button,
  FLEX_LEVELS,
  IconChevronNext,
  Price,
  PriceRange,
  Skeleton,
  UpdatedAt,
} from "@/components/ui";
import { estimateRange } from "@/state/comparison";
import type { ListItem } from "@/state/list";
import styles from "./ListBuilder.module.css";

export type EstimatePanelProps = {
  items: ListItem[];
  basket: BasketItemInput[];
  data: CompareResponse | undefined;
  loading: boolean;
  radiusKm: number;
  newestPrice: string | null;
};

/**
 * Basket estimate and the Compare action. A sticky bottom bar on phones, a side card on desktop
 * (DesktopList artboard). The range covers the stores within the radius that carry every
 * product; quantities apply locally so the range follows the steppers without a refetch.
 */
export function EstimatePanel({
  items,
  basket,
  data,
  loading,
  radiusKm,
  newestPrice,
}: EstimatePanelProps) {
  const estimate = data ? estimateRange(data, basket) : null;
  const toConfirm = items.filter((i) => i.needsConfirmation).length;
  const counts = { exact: 0, any_brand: 0, close: 0 };
  for (const it of items) if (!it.notFound) counts[it.flexLevel] += 1;
  const canCompare = basket.length > 0;

  return (
    <aside className={styles.panel} aria-label="הערכת סל">
      <div className={[styles.panelCard, styles.bar].join(" ")}>
        <div className={styles.estimate} aria-live="polite" data-trust-scope="estimate">
          <div className={styles.estimateLabel}>
            {estimate ? `הערכת סל ב-${estimate.storeCount} סניפים עד ${radiusKm} ק"מ` : "הערכת סל"}
          </div>
          <div className={styles.estimateValue} data-testid="basket-estimate">
            {loading && !estimate ? (
              <Skeleton width={140} height={26} />
            ) : estimate ? (
              <PriceRange from={estimate.min} to={estimate.max} fractionDigits={0} />
            ) : (
              <span className={styles.estimateEmpty}>
                {canCompare ? "אין עדיין הערכה" : "הוסיפי פריטים"}
              </span>
            )}
          </div>
          {newestPrice ? (
            <UpdatedAt iso={newestPrice} prefix="מחירים עודכנו" className={styles.desk} />
          ) : null}
        </div>

        {estimate ? (
          <dl className={[styles.facts, styles.desk].join(" ")}>
            {estimate.home ? (
              <div>
                <dt>בסופר שלך, {estimate.home.store.chain_name}</dt>
                <dd>
                  <Price amount={estimate.home.total} fractionDigits={0} />
                </dd>
              </div>
            ) : null}
            <div>
              <dt>הזול ביותר כרגע</dt>
              <dd>
                {estimate.cheapest.chain_name} · <Price amount={estimate.min} fractionDigits={0} />
              </dd>
            </div>
            <div>
              <dt>פריטים לבדיקה</dt>
              <dd>
                <span dir="ltr">{toConfirm}</span>
              </dd>
            </div>
          </dl>
        ) : null}

        {canCompare ? (
          <Button
            href="/compare"
            className={styles.compare}
            iconEnd={<IconChevronNext size={18} />}
          >
            השווי
          </Button>
        ) : (
          <Button disabled className={styles.compare} iconEnd={<IconChevronNext size={18} />}>
            השווי
          </Button>
        )}
      </div>

      <div className={[styles.panelCard, styles.desk].join(" ")}>
        <h2 className={styles.panelTitle}>גמישות ברשימה</h2>
        <ul className={styles.flexCounts}>
          {(["exact", "any_brand", "close"] as const).map((level) => (
            <li key={level}>
              <span className={styles.flexDot} data-level={level} aria-hidden="true" />
              <span className={styles.flexCountLabel}>{FLEX_LEVELS[level].label}</span>
              <span dir="ltr">{counts[level]}</span>
            </li>
          ))}
        </ul>
        <p className={styles.panelNote}>
          ככל שיותר פריטים ב&quot;כל מותג&quot;, החיסכון גדל. אפשר לשנות לכל פריט בנפרד.
        </p>
      </div>
    </aside>
  );
}
