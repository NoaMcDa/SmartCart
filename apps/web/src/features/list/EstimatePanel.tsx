"use client";

import type { BasketItemInput, CompareResponse } from "@/api/client";
import { Button, IconChevronNext, Price, PriceRange, Skeleton, UpdatedAt } from "@/components/ui";
import { flexLevelLabel } from "@/components/ui/Chip";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { listMessages } from "@/i18n/messages/list";
import { sharedMessages } from "@/i18n/messages/shared";
import { chainLabel } from "@/lib/storeName";
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
  const t = useT(listMessages);
  const shared = useT(sharedMessages);
  const { locale } = useLocale();
  const estimate = data ? estimateRange(data, basket) : null;
  const toConfirm = items.filter((i) => i.needsConfirmation).length;
  const counts = { exact: 0, any_brand: 0, close: 0 };
  for (const it of items) if (!it.notFound) counts[it.flexLevel] += 1;
  const canCompare = basket.length > 0;

  return (
    <aside className={styles.panel} aria-label={t("estimatePanel")}>
      <div className={[styles.panelCard, styles.bar].join(" ")}>
        <div className={styles.estimate} aria-live="polite" data-trust-scope="estimate">
          <div className={styles.estimateLabel}>
            {estimate
              ? t("estimateRange", { stores: estimate.storeCount, km: radiusKm })
              : t("estimatePanel")}
          </div>
          <div className={styles.estimateValue} data-testid="basket-estimate">
            {loading && !estimate ? (
              <Skeleton width={140} height={26} />
            ) : estimate ? (
              <PriceRange from={estimate.min} to={estimate.max} fractionDigits={0} />
            ) : (
              <span className={styles.estimateEmpty}>
                {canCompare ? t("noEstimate") : t("addItems")}
              </span>
            )}
          </div>
          {newestPrice ? (
            <UpdatedAt iso={newestPrice} prefix={shared("pricesUpdated")} className={styles.desk} />
          ) : null}
        </div>

        {estimate ? (
          <dl className={[styles.facts, styles.desk].join(" ")}>
            {estimate.home ? (
              <div>
                <dt>
                  {t("atHome", { chain: chainLabel(estimate.home.store.chain_name, locale) })}
                </dt>
                <dd>
                  <Price amount={estimate.home.total} fractionDigits={0} />
                </dd>
              </div>
            ) : null}
            <div>
              <dt>{t("cheapestNow")}</dt>
              <dd>
                {chainLabel(estimate.cheapest.chain_name, locale)} ·{" "}
                <Price amount={estimate.min} fractionDigits={0} />
              </dd>
            </div>
            <div>
              <dt>{t("toCheck")}</dt>
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
            {t("compare")}
          </Button>
        ) : (
          <Button disabled className={styles.compare} iconEnd={<IconChevronNext size={18} />}>
            {t("compare")}
          </Button>
        )}
      </div>

      <div className={[styles.panelCard, styles.desk].join(" ")}>
        <h2 className={styles.panelTitle}>{t("flexTitle")}</h2>
        <ul className={styles.flexCounts}>
          {(["exact", "any_brand", "close"] as const).map((level) => (
            <li key={level}>
              <span className={styles.flexDot} data-level={level} aria-hidden="true" />
              <span className={styles.flexCountLabel}>{flexLevelLabel(level, locale)}</span>
              <span dir="ltr">{counts[level]}</span>
            </li>
          ))}
        </ul>
        <p className={styles.panelNote}>{t("flexNote")}</p>
      </div>
    </aside>
  );
}
