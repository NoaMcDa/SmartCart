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
import { formatDistance } from "@/lib/format";
import { planPromos, planSubstitutions, planUpdatedAt } from "@/state/comparison";
import styles from "./Results.module.css";

export function Count({ n, one, many }: { n: number; one: string; many: string }) {
  return (
    <>
      <span dir="ltr">{n}</span> {n === 1 ? one : many}
    </>
  );
}

export type PlanCardProps = {
  plan: Plan;
  /** The user's own store (minimum-effort plan), the only baseline for savings (D7). */
  home: StoreResult | null;
  /** canonical id -> display name, for the missing-items list. */
  names: Map<number, string>;
};

function chainList(plan: Plan) {
  return plan.stores.map((s) => s.store.chain_name);
}

/**
 * One plan on the results screen: recommended single store, two-store split, or minimum effort
 * (the home store). The saving block is always versus the home store, named explicitly.
 */
export function PlanCard({ plan, home, names }: PlanCardProps) {
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
  const homeName = home?.store_name ?? null;
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
              מומלץ
            </span>
          ) : null}
          {plan.kind === "split" ? (
            <span className={styles.badgeSplit}>
              פיצול ל-<span dir="ltr">{plan.stores.length}</span> סופרים
            </span>
          ) : null}
          {isHome ? <span className={styles.badgeHome}>מינימום מאמץ · הסופר שלך</span> : null}
        </div>
        {plan.kind === "split" ? (
          <span className={styles.meta}>
            <IconClock size={14} />
            <span dir="ltr">+{plan.extra_minutes}</span> דק&apos;
          </span>
        ) : first ? (
          <span className={styles.meta}>
            <IconPin size={14} />
            {formatDistance(first.distance_m)}
          </span>
        ) : null}
      </div>

      <div className={styles.planHead}>
        <h2 id={`${missingId}-title`} className={styles.storeName}>
          {plan.kind === "split"
            ? chainList(plan).map((c, i) => (
                <span key={c + i}>
                  {i > 0 ? <span className={styles.plus}> + </span> : null}
                  {c}
                </span>
              ))
            : (first?.store_name ?? "")}
        </h2>
        <div className={styles.planSub}>
          {plan.kind === "split"
            ? plan.stores.map((s, i) => (
                <span key={s.store.store_id}>
                  {i > 0 ? " · " : ""}
                  <Count n={s.item_ids.length} one="פריט" many="פריטים" /> ב{s.store.chain_name}
                </span>
              ))
            : isHome
              ? "הבסיס שאליו משווים"
              : missing.length
                ? "סופר אחד"
                : "סופר אחד, כל הרשימה"}
        </div>
      </div>

      <div className={styles.totals}>
        <div className={styles.total}>
          <div className={styles.totalLabel}>סך הסל</div>
          <Price amount={plan.total} size="hero" data-testid={`${testId}-total`} />
        </div>

        {isHome ? (
          <div className={styles.baseline}>
            <div className={styles.baselineTitle}>הבסיס להשוואה</div>
            <div className={styles.baselineSub}>
              <Count n={plan.substituted_count} one="פריט הוחלף" many="פריטים הוחלפו" />
            </div>
          </div>
        ) : breakdown && net !== null && net > 0 ? (
          <div className={styles.saving} data-testid={`${testId}-saving`}>
            <div className={styles.savingValue}>
              <IconCheck size={16} />
              <span>
                חוסך <Price amount={breakdown.net_saving} tone="good" />
                {plan.kind === "split" ? " נטו" : ""}
              </span>
            </div>
            <div className={styles.savingVs}>
              {homeName ? `לעומת ${homeName}, הסופר שלך` : "לעומת הסופר שלך"}
            </div>
          </div>
        ) : breakdown ? (
          <div className={styles.baseline} data-testid={`${testId}-saving`}>
            <div className={styles.baselineTitle}>לא זול יותר מהסופר שלך</div>
            <div className={styles.baselineSub}>
              {homeName ? `לעומת ${homeName}, ` : ""}אחרי נסיעה ועצירות
            </div>
          </div>
        ) : null}
      </div>

      {breakdown && !isHome && (travel > 0 || extraStop > 0) ? (
        <p className={styles.afterTravel}>
          חיסכון בסל <Price amount={breakdown.basket_saving} />, פחות <Price amount={travel} />{" "}
          נסיעה
          {extraStop > 0 ? (
            <>
              {" "}
              ו-
              <Price amount={extraStop} /> שווי העצירה הנוספת
            </>
          ) : null}
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
            <Count n={subs.length} one="פריט הוחלף" many="פריטים הוחלפו" />
          </Link>
        ) : !isHome ? (
          <span className={styles.muted}>
            <Count n={0} one="פריט הוחלף" many="פריטים הוחלפו" />
          </span>
        ) : null}

        {plan.kind === "split" ? (
          <Link href="/split" className={styles.subsLink} data-testid="split-link">
            <IconRefresh size={14} />
            פירוט הפיצול בין הסופרים
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
            <Count n={missing.length} one="פריט חסר" many="פריטים חסרים" />
          </button>
        ) : (
          <span className={styles.muted}>
            <Count n={0} one="פריט חסר" many="פריטים חסרים" />
          </span>
        )}

        {promos.total ? (
          <span className={styles.muted}>
            <Count n={promos.total} one="מבצע כלול" many="מבצעים כלולים" />
            {promos.club ? (
              <>
                , <span dir="ltr">{promos.club}</span> למועדון
              </>
            ) : null}
          </span>
        ) : null}
      </div>

      {missing.length && showMissing ? (
        <ul id={missingId} className={styles.missingList} aria-label="פריטים חסרים">
          {missing.map((id) => (
            <li key={id}>
              <IconClose size={13} />
              {names.get(id) ?? `פריט ${id}`}
              <span className={styles.missingNote}> · לא נמכר בסניף, לא נספר בסך</span>
            </li>
          ))}
        </ul>
      ) : null}

      <UpdatedAt iso={updated} prefix="מחירים עודכנו" withIcon />
    </Card>
  );
}
