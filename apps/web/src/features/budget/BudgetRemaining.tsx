"use client";

import Link from "next/link";
import { Card, IconInfo, Price, UpdatedAt } from "@/components/ui";
import { formatRich } from "@/i18n/format";
import { useT } from "@/i18n/LocaleProvider";
import { budgetMessages } from "@/i18n/messages/budget";
import { sharedMessages } from "@/i18n/messages/shared";
import { useBudget } from "./budgetState";
import { currentMonth } from "./month";
import { budgetStatus, useSpend } from "./spendState";
import styles from "./Budget.module.css";

export type BudgetRemainingProps = {
  /** The plan on screen, ILS; adds "אחרי הקנייה הזו". */
  planTotal?: number | string | null;
  /** When the plan's prices were updated (the trust signal for `planTotal`). */
  updatedAt?: string | null;
};

/**
 * "נותר החודש": what is left of the monthly budget (issue #70), on the results and the split
 * screens. Renders nothing without a budget: no prompt, no nagging. Spent comes from the shops the
 * person recorded with "סיימתי לקנות" (prices as shown, not receipts); "אחרי הקנייה הזו" subtracts
 * the plan on screen, whose prices carry their update time like everywhere else.
 */
export function BudgetRemaining({ planTotal, updatedAt }: BudgetRemainingProps) {
  const t = useT(budgetMessages);
  const shared = useT(sharedMessages);
  const budget = useBudget();
  const { entries } = useSpend();
  const plan = planTotal === null || planTotal === undefined ? null : Number(planTotal);
  const status = budgetStatus(budget, entries, currentMonth(), plan);
  if (!status) return null;
  const over = status.remaining < 0;
  const overAfter = status.afterPlan !== null && status.afterPlan < 0;

  return (
    <Card
      as="section"
      aria-label={t("sectionTitle")}
      className={styles.remaining}
      data-testid="budget-remaining"
      data-trust-scope="budget"
    >
      <p className={styles.remainingMain}>
        <span>{over ? t("overBudget") : t("leftThisMonth")}</span>
        <Price
          amount={Math.abs(status.remaining)}
          size="lg"
          data-testid="budget-left"
          tone="default"
        />
        <span className={styles.muted}>
          {formatRich(t("ofBudget"), { price: <Price amount={status.budget} /> })}
        </span>
      </p>
      {status.afterPlan !== null ? (
        <p className={overAfter ? styles.warn : styles.line} data-testid="budget-after">
          {overAfter ? <IconInfo size={16} /> : null}
          <span>
            {formatRich(t(overAfter ? "afterOver" : "afterLeft"), {
              price: <Price amount={Math.abs(status.afterPlan)} />,
            })}
          </span>
          {updatedAt ? (
            <span className={styles.muted}>
              <UpdatedAt iso={updatedAt} prefix={shared("pricesUpdated")} />
            </span>
          ) : null}
        </p>
      ) : null}
      <p className={styles.note}>
        {t("footnote")} <Link href="/profile#budget">{t("toBudget")}</Link>
      </p>
    </Card>
  );
}
