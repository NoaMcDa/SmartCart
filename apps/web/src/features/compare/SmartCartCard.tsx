"use client";

import { useMemo } from "react";
import type { AttributeTag, Plan, SwapSuggestion } from "@/api/client";
import { Button, Card, Price, Tag, UpdatedAt } from "@/components/ui";
import { IconCheck, IconRefresh } from "@/components/ui/icons";
import { applySwap, dismissSwap, undoSwap } from "@/features/swaps/actions";
import {
  aggregate,
  savingOf,
  setUndoneName,
  undoableSwaps,
  useSwapsState,
  useUndoneName,
  visibleSwaps,
} from "@/features/swaps/swapState";
import { useSwaps } from "@/features/swaps/useSwaps";
import { DataText } from "@/i18n/DataText";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { compareMessages } from "@/i18n/messages/compare";
import { sharedMessages } from "@/i18n/messages/shared";
import { translatePlural } from "@/i18n/plural";
import { attributeTagText, foldTags } from "@/lib/attributes";
import { chainLabel, storeLabel } from "@/lib/storeName";
import { buildCompareInput, planUpdatedAt } from "@/state/comparison";
import { basketItems, useList } from "@/state/list";
import { useShopper } from "@/state/shopper";
import styles from "./SmartCartCard.module.css";

export function swapTagText(tag: AttributeTag, locale: Locale = DEFAULT_LOCALE): string {
  return attributeTagText(tag, { locale });
}

const REASONS = {
  any_brand: "reasonAnyBrand",
  close: "reasonClose",
  exact: "reasonExact",
} as const satisfies Record<SwapSuggestion["flex_level"], string>;

export function swapsHeadline(count: number, locale: Locale = DEFAULT_LOCALE): string {
  return translatePlural(compareMessages, locale, "headline", count, { count });
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
  const t = useT(compareMessages);
  const shared = useT(sharedMessages);
  const { locale } = useLocale();
  const { state } = useList();
  const shopper = useShopper();
  const swapsState = useSwapsState();
  const undone = useUndoneName();

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
  const undoable = useMemo(
    () => undoableSwaps(swapsState, new Set(state.items.map((i) => i.id))),
    [swapsState, state.items],
  );
  const lastApplied = undoable[undoable.length - 1] ?? null;

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
        <IconRefresh size={14} />{" "}
        {t("smartEyebrow", { chain: chainLabel(store.chain_name, locale) })}
      </p>

      {top ? (
        <>
          <h2 id="smart-cart-title" className={styles.smartTitle} data-testid="smart-cart-title">
            {swapsHeadline(count, locale)} <Price amount={total} tone="good" size="lg" />
          </h2>
          <p className={styles.muted}>
            {t("smartSub", { store: storeLabel(store.store_name, locale) })}
          </p>

          <div className={styles.smartTop} data-testid="smart-cart-top">
            <p className={styles.smartLabel}>{t("bestSwap")}</p>
            <h3 className={styles.smartName}>
              <DataText>{top.to_display_name_he}</DataText>
            </h3>
            <p className={styles.smartMeta}>
              {formatRich(t("swapSaving"), {
                price: <Price amount={savingOf(top)} tone="good" fractionDigits={2} />,
              })}
              {top.confidence != null ? (
                <>
                  {" · "}
                  {formatRich(t("swapConfidence"), {
                    pct: <span dir="ltr">{Math.round(top.confidence * 100)}%</span>,
                  })}
                </>
              ) : null}
            </p>
            <p className={styles.smartWhy} data-testid="smart-cart-why">
              {t("swapWhy", { reason: t(REASONS[top.flex_level]) })}
            </p>
            {top.tags && top.tags.length > 0 ? (
              <ul className={styles.smartTags} aria-label={t("tagsLabel")}>
                {foldTags(top.tags).map((tag) => (
                  <li key={`${tag.key}-${tag.value ?? ""}`}>
                    <Tag variant={tag.status}>{swapTagText(tag, locale)}</Tag>
                  </li>
                ))}
              </ul>
            ) : null}
            <div className={styles.smartActions}>
              <Button
                onClick={() => {
                  setUndoneName(null);
                  applySwap(top);
                }}
                aria-label={t("applyLabel", { name: top.to_display_name_he })}
              >
                {t("apply")}
              </Button>
              <Button variant="outline" onClick={() => dismissSwap(top)}>
                {t("notNow")}
              </Button>
            </div>
          </div>
        </>
      ) : (
        <h2 id="smart-cart-title" className={styles.smartTitle}>
          {t("noSwaps")}
        </h2>
      )}

      <div role="status" aria-live="polite">
        {lastApplied ? (
          <p className={styles.smartApplied} data-testid="smart-cart-applied">
            <IconCheck size={14} />{" "}
            {formatRich(t("swapApplied"), {
              name: lastApplied.name,
              price: <Price amount={lastApplied.saving} tone="good" fractionDigits={2} />,
            })}{" "}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (undoSwap(lastApplied.key)) setUndoneName(lastApplied.name);
              }}
            >
              {t("undoApplied")}
            </Button>
          </p>
        ) : null}
        {undone && !lastApplied ? (
          <p className={styles.muted} data-testid="smart-cart-undone">
            {t("swapUndone")}
          </p>
        ) : null}
      </div>

      <p className={styles.muted}>
        <UpdatedAt iso={planUpdatedAt(plan)} prefix={shared("pricesUpdated")} withIcon /> ·{" "}
        {shared("checkoutGoverns")}
      </p>
    </Card>
  );
}
