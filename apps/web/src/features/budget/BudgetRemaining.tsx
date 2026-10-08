"use client";

import Link from "next/link";
import { Card, IconInfo, Price, UpdatedAt } from "@/components/ui";
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
      aria-label="תקציב חודשי"
      className={styles.remaining}
      data-testid="budget-remaining"
      data-trust-scope="budget"
    >
      <p className={styles.remainingMain}>
        <span>{over ? "חריגה מהתקציב" : "נותר החודש"}</span>
        <Price
          amount={Math.abs(status.remaining)}
          size="lg"
          data-testid="budget-left"
          tone="default"
        />
        <span className={styles.muted}>
          מתוך <Price amount={status.budget} />
        </span>
      </p>
      {status.afterPlan !== null ? (
        <p className={overAfter ? styles.warn : styles.line} data-testid="budget-after">
          {overAfter ? <IconInfo size={16} /> : null}
          <span>
            {overAfter ? "הקנייה הזו חורגת מהתקציב ב" : "אחרי הקנייה הזו יישארו "}
            <Price amount={Math.abs(status.afterPlan)} />
          </span>
          {updatedAt ? (
            <span className={styles.muted}>
              <UpdatedAt iso={updatedAt} prefix="מחירים עודכנו" />
            </span>
          ) : null}
        </p>
      ) : null}
      <p className={styles.note}>
        לפי המחירים שהוצגו, לא לפי קבלות. המחיר הקובע הוא בקופה.{" "}
        <Link href="/profile#budget">לתקציב</Link>
      </p>
    </Card>
  );
}
