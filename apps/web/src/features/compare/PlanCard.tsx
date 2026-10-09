"use client";

import Link from "next/link";
import { useId, useState } from "react";
import type { Plan, StoreResult } from "@/api/client";
import {
  Card,
  IconCheck,
  IconClock,
  IconClose,
  IconPin,
  IconRefresh,
  Price,
  UpdatedAt,
} from "@/components/ui";
import type { Locale } from "@/i18n/locales";
import { PlanHandoff } from "@/features/handoff/PlanHandoff";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { compareMessages } from "@/i18n/messages/compare";
import { sharedMessages } from "@/i18n/messages/shared";
import { formatDistance } from "@/lib/format";
import { chainLabel, storeLabel } from "@/lib/storeName";
import { planPromos, planSubstitutions, planUpdatedAt } from "@/state/comparison";
import { Count } from "./Count";
import styles from "./Results.module.css";

export type PlanCardProps = {
  plan: Plan;
  /** The user's own store (minimum-effort plan), the only baseline for savings (D7). */
  home: StoreResult | null;
  /** canonical id -> display name, for the missing-items list. */
  names: Map<number, string>;
};

function chainList(plan: Plan, locale: Locale) {
  return plan.stores.map((s) => chainLabel(s.store.chain_name, locale));
}

/**
 * One plan on the results screen: recommended single store, two-store split, or minimum effort
 * (the home store). The saving block is always versus the home store, named explicitly.
 */
export function PlanCard({ plan, home, names }: PlanCardProps) {
  const t = useT(compareMessages);
  const shared = useT(sharedMessages);
  const { locale } = useLocale();
  const [showMissing, setShowMissing] = useState(false);
  const missingId = useId();
  const subs = planSubstitutions(plan);
  const promos = planPromos(plan);
  const updated = planUpdatedAt(plan);
  const missing = plan.missing ?? [];
  const first = plan.stores[0]?.store;
  const isHome = plan.kind === "minimum_effort";
  const breakdown = plan.breakdown ?? null;
  const net = breakdown ? Number.parseFloat(breakdown.net_saving) : null;
  const travel = breakdown ? Number.parseFloat(breakdown.travel_cost) : 0;
  const extraStop = breakdown ? Number.parseFloat(breakdown.extra_stop_cost) : 0;
  const homeName = home ? storeLabel(home.store_name, locale) : null;
  const testId = `plan-${plan.kind}`;

  return (
    <Card
      as="article"
      variant={plan.recommended ? "recommended" : "default"}
      className={styles.plan}
      data-testid={testId}
      data-recommended={plan.recommended ? "true" : "false"}
      aria-labelledby={`${missingId}-title`}
      data-trust-scope="plan"
    >
      <div className={styles.planTop}>
        <div className={styles.badges}>
          {plan.recommended ? (
            <span className={styles.badgeRecommended}>
              <IconCheck size={13} />
              {t("recommended")}
            </span>
          ) : null}
          {plan.kind === "split" ? (
            <span className={styles.badgeSplit}>
              {formatRich(t("splitBadge"), { n: <span dir="ltr">{plan.stores.length}</span> })}
            </span>
          ) : null}
          {isHome ? <span className={styles.badgeHome}>{t("homeBadge")}</span> : null}
        </div>
        {plan.kind === "split" ? (
          <span className={styles.meta}>
            <IconClock size={14} />
            <span dir="ltr">+{plan.extra_minutes}</span> {t("minutes")}
          </span>
        ) : first ? (
          <span className={styles.meta}>
            <IconPin size={14} />
            {formatDistance(first.distance_m, locale)}
          </span>
        ) : null}
      </div>

      <div className={styles.planHead}>
        <h2 id={`${missingId}-title`} className={styles.storeName}>
          {plan.kind === "split"
            ? chainList(plan, locale).map((c, i) => (
                <span key={c + i}>
                  {i > 0 ? <span className={styles.plus}> + </span> : null}
                  {c}
                </span>
              ))
            : first
              ? storeLabel(first.store_name, locale)
              : ""}
        </h2>
        <div className={styles.planSub}>
          {plan.kind === "split"
            ? plan.stores.map((s, i) => (
                <span key={s.store.store_id}>
                  {i > 0 ? " · " : ""}
                  <Count n={s.item_ids.length} noun="item" />{" "}
                  {t("inChain", { chain: chainLabel(s.store.chain_name, locale) })}
                </span>
              ))
            : isHome
              ? t("homeBase")
              : missing.length
                ? t("oneStore")
                : t("oneStoreAll")}
        </div>
      </div>

      <div className={styles.totals}>
        <div className={styles.total}>
          <div className={styles.totalLabel}>{t("basketTotal")}</div>
          <Price amount={plan.total} size="hero" data-testid={`${testId}-total`} />
        </div>

        {isHome ? (
          <div className={styles.baseline}>
            <div className={styles.baselineTitle}>{t("baselineTitle")}</div>
            <div className={styles.baselineSub}>
              <Count n={plan.substituted_count} noun="replaced" />
            </div>
          </div>
        ) : breakdown && net !== null && net > 0 ? (
          <div className={styles.saving} data-testid={`${testId}-saving`}>
            <div className={styles.savingValue}>
              <IconCheck size={16} />
              <span>
                {formatRich(t(plan.kind === "split" ? "savesNet" : "saves"), {
                  price: <Price amount={breakdown.net_saving} tone="good" />,
                })}
              </span>
            </div>
            <div className={styles.savingVs}>
              {homeName ? t("vsHome", { name: homeName }) : t("vsHomeGeneric")}
            </div>
          </div>
        ) : breakdown ? (
          <div className={styles.baseline} data-testid={`${testId}-saving`}>
            <div className={styles.baselineTitle}>{t("notCheaper")}</div>
            <div className={styles.baselineSub}>
              {homeName ? t("afterTravelVs", { name: homeName }) : t("afterTravel")}
            </div>
          </div>
        ) : null}
      </div>

      {breakdown && !isHome && (travel > 0 || extraStop > 0) ? (
        <p className={styles.afterTravel}>
          {formatRich(t("breakdown"), {
            basket: <Price amount={breakdown.basket_saving} />,
            travel: <Price amount={travel} />,
          })}
          {extraStop > 0
            ? formatRich(t("breakdownStop"), { stop: <Price amount={extraStop} /> })
            : null}
          .
        </p>
      ) : null}

      <div className={styles.planFoot}>
        {subs.length && !isHome ? (
          <Link
            href={`/compare/substitution/${subs[0]!.item.item_id}?plan=${plan.kind}`}
            className={styles.subsLink}
          >
            <IconRefresh size={14} />
            <Count n={subs.length} noun="replaced" />
          </Link>
        ) : !isHome ? (
          <span className={styles.muted}>
            <Count n={0} noun="replaced" />
          </span>
        ) : null}

        {plan.kind === "split" ? (
          <Link href="/split" className={styles.subsLink} data-testid="split-link">
            <IconRefresh size={14} />
            {t("splitLink")}
          </Link>
        ) : null}

        {missing.length ? (
          <button
            type="button"
            className={styles.missing}
            aria-expanded={showMissing}
            aria-controls={missingId}
            onClick={() => setShowMissing((v) => !v)}
          >
            <IconClose size={14} />
            <Count n={missing.length} noun="missing" />
          </button>
        ) : (
          <span className={styles.muted}>
            <Count n={0} noun="missing" />
          </span>
        )}

        {promos.total ? (
          <span className={styles.muted}>
            <Count n={promos.total} noun="promo" />
            {promos.club
              ? formatRich(t("promoClub"), { n: <span dir="ltr">{promos.club}</span> })
              : null}
          </span>
        ) : null}

        <PlanHandoff plan={plan} />
      </div>

      {missing.length && showMissing ? (
        <ul id={missingId} className={styles.missingList} aria-label={t("missingListLabel")}>
          {missing.map((id) => (
            <li key={id}>
              <IconClose size={13} />
              {names.get(id) ?? t("missingFallback", { id })}
              <span className={styles.missingNote}> · {t("missingNote")}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <UpdatedAt iso={updated} prefix={shared("pricesUpdated")} withIcon />
    </Card>
  );
}
