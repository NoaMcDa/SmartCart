"use client";

import { useEffect, useId, useMemo, useState, type FormEvent } from "react";
import { Button, Card, IconInfo, Price } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import controls from "@/features/profile/controls/controls.module.css";
import { totalSaved, useSavings } from "@/features/profile/savingsHistory";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { budgetMessages } from "@/i18n/messages/budget";
import { clearBudget, MAX_BUDGET, saveBudget, useBudget } from "./budgetState";
import { currentMonth, israelDate, monthName, monthOf, monthsEndingAt } from "./month";
import { SpendChart } from "./SpendChart";
import { SpendEntries } from "./SpendEntries";
import { budgetStatus, monthlyTotals, useSpend } from "./spendState";
import { syncSpend } from "./sync";
import styles from "./Budget.module.css";

/**
 * Monthly budget and spend (issue #70) for Profile: set, change or clear the budget; spent and
 * remaining this month; a six-month bar chart; this month's shops. All amounts are the prices the
 * app showed when the shop was recorded ("לפי המחירים שהוצגו"), not receipts, and say so. Signed
 * in, shops recorded while signed in are also saved to the account and shops from other devices
 * appear here; signed out, everything stays on this device.
 */
export function MonthlyBudgetSection({ className }: { className?: string }) {
  const t = useT(budgetMessages);
  const { locale, intl } = useLocale();
  const headingId = useId();
  const fieldId = useId();
  const auth = useAuth();
  const budget = useBudget();
  const { entries, pending } = useSpend();
  const savings = useSavings();
  // null = show the saved budget; a string = what the person is typing.
  const [draft, setDraft] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const month = currentMonth();
  const months = useMemo(() => monthsEndingAt(month, 6), [month]);
  const signedIn = auth.status === "signed-in";
  useEffect(() => {
    if (signedIn) void syncSpend(months);
  }, [signedIn, months]);

  const totals = monthlyTotals(entries, months);
  const status = budgetStatus(budget, entries, month);
  const thisMonth = entries
    .filter((e) => monthOf(e.date) === month)
    .sort((a, b) => (a.date === b.date ? b.id.localeCompare(a.id) : b.date.localeCompare(a.date)));
  const spent = totals.at(-1)?.total ?? 0;
  // Net saving versus the person's own store, recorded by "סיימתי" (same method as "החיסכון שלי").
  const monthSavings = savings.filter((e) => monthOf(israelDate(new Date(e.at))) === month);
  const saved = totalSaved(monthSavings);
  const shown = draft ?? (budget !== null ? String(budget) : "");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (saveBudget(shown)) {
      setDraft(null);
      setMessage({ kind: "ok", text: t("budgetSaved") });
    } else {
      setMessage({
        kind: "error",
        text: t("budgetInvalid", { max: MAX_BUDGET.toLocaleString(intl) }),
      });
    }
  }

  function onClear() {
    clearBudget();
    setDraft(null);
    setMessage({ kind: "ok", text: t("budgetCleared") });
  }

  return (
    <Card
      as="section"
      id="budget"
      aria-labelledby={headingId}
      className={className}
      data-testid="budget-section"
    >
      <h2 id={headingId} className={styles.sectionTitle}>
        {t("sectionTitle")}
      </h2>

      <form className={styles.form} onSubmit={onSubmit} noValidate>
        <div className={controls.field}>
          <label htmlFor={fieldId} className={controls.label}>
            {t("question")}
          </label>
          <input
            id={fieldId}
            className={controls.input}
            type="number"
            inputMode="numeric"
            min={1}
            max={MAX_BUDGET}
            step={1}
            dir="ltr"
            placeholder="2500"
            value={shown}
            aria-describedby={message ? `${fieldId}-msg` : undefined}
            onChange={(e) => {
              setDraft(e.target.value);
              setMessage(null);
            }}
          />
        </div>
        <div className={styles.actions}>
          <Button type="submit" size="sm" disabled={shown.trim() === ""}>
            {t("saveBudget")}
          </Button>
          {budget !== null ? (
            <Button type="button" size="sm" variant="outline" onClick={onClear}>
              {t("clearBudget")}
            </Button>
          ) : null}
        </div>
        {message ? (
          <p
            id={`${fieldId}-msg`}
            className={message.kind === "error" ? styles.warn : styles.muted}
            role={message.kind === "error" ? "alert" : "status"}
          >
            {message.kind === "error" ? <IconInfo size={16} /> : null}
            {message.text}
          </p>
        ) : null}
      </form>

      <dl className={styles.facts} data-testid="budget-facts">
        <div>
          <dt>{t("spentIn", { month: monthName(month, "long", locale) })}</dt>
          <dd>
            <Price amount={spent} size="lg" data-testid="budget-spent" />
          </dd>
        </div>
        <div>
          <dt>{status && status.remaining < 0 ? t("overBudget") : t("leftThisMonth")}</dt>
          <dd>
            {status ? (
              <Price
                amount={Math.abs(status.remaining)}
                size="lg"
                data-testid="budget-remaining-value"
              />
            ) : (
              <span className={styles.muted}>{t("noBudget")}</span>
            )}
          </dd>
        </div>
        {monthSavings.length > 0 ? (
          <div>
            <dt>{t("netSavingVsHome")}</dt>
            <dd>
              <Price
                amount={saved}
                size="lg"
                tone={saved > 0 ? "good" : "default"}
                data-testid="budget-saved"
              />
            </dd>
          </div>
        ) : null}
      </dl>

      {entries.length === 0 ? (
        <p className={styles.muted} data-testid="spend-empty">
          {t("spendEmpty")}
        </p>
      ) : (
        <>
          <h3 className={styles.subTitle}>{t("lastSixMonths")}</h3>
          <SpendChart data={totals} budget={budget} highlight={month} />
        </>
      )}

      {/* Always mounted: its undo window must outlive the last shop leaving the list. */}
      <SpendEntries
        entries={thisMonth}
        signedIn={signedIn}
        heading={t("shopsIn", { month: monthName(month, "long", locale) })}
      />

      <p className={styles.note} data-testid="budget-method">
        {t("method")}
      </p>
      <p className={styles.note}>
        {signedIn
          ? pending.length > 0
            ? t("pendingSave", { n: pending.length })
            : t("syncedNote")
          : t("localOnly")}
      </p>
    </Card>
  );
}
